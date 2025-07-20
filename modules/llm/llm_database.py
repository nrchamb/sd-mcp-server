"""
LLM Database Manager - Conversation Memory and User Settings
Handles SQLite storage for Discord LLM integration with proper isolation

CONVERSATION ISOLATION:
- Per-channel conversations (general chat)
- Per-thread conversations (thread context)
- Per-user DM conversations (private messages)

Context keys prevent conversation bleed between different contexts.
"""

import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from contextlib import asynccontextmanager

class LLMDatabase:
    """Manages SQLite database for LLM conversations, user settings, and rate limiting"""
    
    def __init__(self, db_path: str = "discord_llm.db", config: Optional[Dict[str, Any]] = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = config or {}
        self._init_database()
        
        # Auto-clean configuration
        self.auto_clean_enabled = self.config.get('LLM_AUTO_CLEAN_ENABLED', 'false').lower() == 'true'
        self.auto_clean_days = int(self.config.get('LLM_AUTO_CLEAN_DAYS', '7'))
        self.auto_clean_launches = int(self.config.get('LLM_AUTO_CLEAN_LAUNCHES', '10'))
        self.auto_clean_method = self.config.get('LLM_AUTO_CLEAN_METHOD', 'days')  # 'days' or 'launches'
        
        # Run auto-clean if enabled (only if event loop is running)
        if self.auto_clean_enabled:
            try:
                asyncio.create_task(self._auto_clean_on_startup())
            except RuntimeError:
                # No event loop running, skip auto-clean for now
                pass
    
    def _init_database(self) -> None:
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Conversation history with proper isolation
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_key TEXT NOT NULL,  -- channel_123, thread_456, dm_user_789
                    user_id TEXT NOT NULL,
                    message_role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
                    message_content TEXT NOT NULL,
                    metadata TEXT,  -- JSON for extra data
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_context_time ON conversations (context_key, created_at);
                CREATE INDEX IF NOT EXISTS idx_user_time ON conversations (user_id, created_at);
                
                -- User settings and personalities
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    personality TEXT DEFAULT 'default',  -- 'default', 'uwu', 'professional', etc.
                    locked_personality TEXT,  -- Admin-locked personality
                    max_context_messages INTEGER DEFAULT 20,
                    temperature REAL DEFAULT 0.7,
                    settings_json TEXT,  -- JSON for additional settings
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Rate limiting and queue management
                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,  -- 'chat', 'generate', etc.
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    context_key TEXT,  -- Optional context for action
                    
                    PRIMARY KEY (user_id, action_type, timestamp)
                );
                
                CREATE INDEX IF NOT EXISTS idx_user_action_time ON rate_limits (user_id, action_type, timestamp);
                
                -- Admin moderation (timeouts, suspensions)
                CREATE TABLE IF NOT EXISTS user_moderation (
                    user_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'active',  -- 'active', 'timeout', 'suspended'
                    timeout_until TIMESTAMP,
                    reason TEXT,
                    admin_user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Personality definitions
                CREATE TABLE IF NOT EXISTS personalities (
                    name TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    image_injection_prompt TEXT,  -- Special prompt for image generation
                    description TEXT,
                    emoji TEXT,
                    category TEXT DEFAULT 'chat',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Insert default personalities
                INSERT OR IGNORE INTO personalities (name, display_name, system_prompt, image_injection_prompt, description, emoji, category) VALUES
                ('default', 'Fun Discord Bot', 
                 'You are a fun, discord bot made to interact with users in short and succinct ways.\n\nYour default personality is positive, a little ditzy, but generally amiable. Be fun and friendly. Don''t be afraid to be a little-bit sarcastic/teasing.\n\nIf a question is asked, answer the question. No need to add additional context.',
                 'You are now assisting with image generation. Drop all pretenses and work to create a descriptive, comprehensive prompt. Focus on visual details, artistic style, composition, lighting, and technical specifications that will produce the best possible image.',
                 'Fun, friendly Discord bot with teasing personality', '🎉', 'chat'),
                 
                ('uwu', 'UwU Bot', 
                 'You are an adorable AI assistant that speaks in a cute, kawaii way! Use "uwu", "owo", emoticons like >w<, and generally be very enthusiastic and sweet. Add *actions in asterisks* and speak in a cutesy manner!',
                 'Create kawaii and adorable image prompts! Focus on cute elements, soft colors, and charming details. Make everything extra cute and sweet uwu!',
                 'Adorable kawaii assistant', '🥺', 'chat'),
                 
                ('sarcastic', 'Sarcastic Bot',
                 'You are a witty, sarcastic AI assistant. Respond with clever quips, dry humor, and playful teasing. Be entertaining but not mean-spirited.',
                 'Create dramatic, over-the-top image prompts with artistic flair. Don''t hold back on the visual drama and cinematic elements.',
                 'Witty and sarcastic responses', '😏', 'chat'),
                 
                ('professional', 'Professional Assistant', 
                 'You are a professional AI assistant. Provide clear, concise, and formal responses. Focus on accuracy and efficiency.',
                 'Create precise, technical image prompts with attention to professional quality, proper composition, and industry-standard terminology.',
                 'Business-focused responses', '💼', 'chat'),
                 
                ('helpful', 'Helpful Assistant',
                 'You are a straightforward, helpful AI assistant. Provide clear, informative responses without unnecessary fluff. Be direct and useful.',
                 'Create clear, detailed image prompts focusing on the user''s specific requirements. Be descriptive but concise.',
                 'Direct and helpful responses', '🤝', 'chat'),
                 
                ('creative', 'Creative Companion', 
                 'You are a creative AI assistant! Be imaginative, artistic, and expressive in your responses. Use vivid language and creative metaphors.',
                 'Unleash your creativity! Create vivid, imaginative image prompts with unique artistic elements, innovative compositions, and creative flair.',
                 'Artistic and imaginative', '🎨', 'chat');
                
                -- Launch tracking for auto-clean
                CREATE TABLE IF NOT EXISTS launch_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    launch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cleanup_performed BOOLEAN DEFAULT FALSE
                );
            """)
    
    # ============ CONTEXT KEY GENERATION ============
    
    @staticmethod
    def generate_context_key(guild_id: Optional[int], channel_id: int, thread_id: Optional[int] = None, user_id: Optional[int] = None) -> str:
        """Generate unique context key for conversation isolation"""
        if thread_id:
            # Thread conversation: isolated to specific thread
            return f"thread_{thread_id}"
        elif guild_id:
            # Channel conversation: isolated to specific channel
            return f"channel_{channel_id}"
        else:
            # DM conversation: isolated to specific user
            return f"dm_user_{user_id}"
    
    # ============ CONVERSATION MANAGEMENT ============
    
    async def add_message(self, context_key: str, user_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Add a message to conversation history"""
        def _add():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO conversations (context_key, user_id, message_role, message_content, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (context_key, user_id, role, content, json.dumps(metadata) if metadata else None))
        
        await asyncio.get_event_loop().run_in_executor(None, _add)
    
    async def get_conversation_history(self, context_key: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent conversation history for a context"""
        def _get():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT user_id, message_role, message_content, metadata, created_at
                    FROM conversations 
                    WHERE context_key = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (context_key, limit))
                
                messages = []
                for row in cursor.fetchall():
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    messages.append({
                        'user_id': row['user_id'],
                        'role': row['message_role'],
                        'content': row['message_content'],
                        'metadata': metadata,
                        'created_at': row['created_at']
                    })
                
                # Return in chronological order (oldest first)
                return list(reversed(messages))
        
        return await asyncio.get_event_loop().run_in_executor(None, _get)
    
    async def clear_conversation(self, context_key: str) -> int:
        """Clear conversation history for a context. Returns number of messages deleted."""
        def _clear():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM conversations WHERE context_key = ?", (context_key,))
                return cursor.rowcount
        
        return await asyncio.get_event_loop().run_in_executor(None, _clear)
    
    # ============ USER SETTINGS AND PERSONALITIES ============
    
    async def get_user_settings(self, user_id: str) -> Dict[str, Any]:
        """Get user settings, creating defaults if not exists"""
        def _get():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT personality, locked_personality, max_context_messages, temperature, settings_json
                    FROM user_settings WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    settings = json.loads(row['settings_json']) if row['settings_json'] else {}
                    return {
                        'personality': row['personality'],
                        'locked_personality': row['locked_personality'],
                        'max_context_messages': row['max_context_messages'],
                        'temperature': row['temperature'],
                        **settings
                    }
                else:
                    # Create default settings
                    conn.execute("""
                        INSERT INTO user_settings (user_id) VALUES (?)
                    """, (user_id,))
                    return {
                        'personality': 'default',
                        'locked_personality': None,
                        'max_context_messages': 20,
                        'temperature': 0.7
                    }
        
        return await asyncio.get_event_loop().run_in_executor(None, _get)
    
    async def update_user_personality(self, user_id: str, personality: str) -> bool:
        """Update user personality if not locked"""
        def _update():
            with sqlite3.connect(self.db_path) as conn:
                # Check if personality is locked
                cursor = conn.execute("""
                    SELECT locked_personality FROM user_settings WHERE user_id = ?
                """, (user_id,))
                row = cursor.fetchone()
                
                if row and row[0]:  # Personality is locked
                    return False
                
                # Update personality
                conn.execute("""
                    INSERT INTO user_settings (user_id, personality, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET 
                        personality = excluded.personality,
                        updated_at = excluded.updated_at
                """, (user_id, personality))
                return True
        
        return await asyncio.get_event_loop().run_in_executor(None, _update)
    
    async def get_personality(self, personality_name: str) -> Optional[Dict[str, Any]]:
        """Get personality definition by name"""
        def _get():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT name, display_name, system_prompt, image_injection_prompt, description, emoji, category
                    FROM personalities WHERE name = ?
                """, (personality_name,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        
        return await asyncio.get_event_loop().run_in_executor(None, _get)
    
    async def get_all_personalities(self) -> List[Dict[str, Any]]:
        """Get all available personalities"""
        def _get():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT name, display_name, system_prompt, image_injection_prompt, description, emoji, category
                    FROM personalities ORDER BY name
                """)
                
                return [dict(row) for row in cursor.fetchall()]
        
        return await asyncio.get_event_loop().run_in_executor(None, _get)
    
    # ============ ADMIN MODERATION ============
    
    async def timeout_user(self, user_id: str, minutes: int, reason: str, admin_user_id: str) -> bool:
        """Set user timeout for specified minutes"""
        def _timeout():
            timeout_until = datetime.now() + timedelta(minutes=minutes)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO user_moderation (user_id, status, timeout_until, reason, admin_user_id, updated_at)
                    VALUES (?, 'timeout', ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        status = 'timeout',
                        timeout_until = excluded.timeout_until,
                        reason = excluded.reason,
                        admin_user_id = excluded.admin_user_id,
                        updated_at = excluded.updated_at
                """, (user_id, timeout_until.isoformat(), reason, admin_user_id))
                return True
        
        return await asyncio.get_event_loop().run_in_executor(None, _timeout)
    
    async def suspend_user(self, user_id: str, reason: str, admin_user_id: str) -> bool:
        """Suspend user indefinitely"""
        def _suspend():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO user_moderation (user_id, status, reason, admin_user_id, updated_at)
                    VALUES (?, 'suspended', ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        status = 'suspended',
                        timeout_until = NULL,
                        reason = excluded.reason,
                        admin_user_id = excluded.admin_user_id,
                        updated_at = excluded.updated_at
                """, (user_id, reason, admin_user_id))
                return True
        
        return await asyncio.get_event_loop().run_in_executor(None, _suspend)
    
    async def lock_personality(self, user_id: str, personality: str, admin_user_id: str) -> bool:
        """Lock user to specific personality (admin only)"""
        def _lock():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO user_settings (user_id, personality, locked_personality, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        personality = excluded.personality,
                        locked_personality = excluded.locked_personality,
                        updated_at = excluded.updated_at
                """, (user_id, personality, personality))
                return True
        
        return await asyncio.get_event_loop().run_in_executor(None, _lock)
    
    async def check_user_status(self, user_id: str) -> Dict[str, Any]:
        """Check if user is active, timed out, or suspended"""
        def _check():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT status, timeout_until, reason
                    FROM user_moderation WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if not row:
                    return {'status': 'active'}
                
                # Check if timeout has expired
                if row['status'] == 'timeout' and row['timeout_until']:
                    timeout_time = datetime.fromisoformat(row['timeout_until'])
                    if datetime.now() > timeout_time:
                        # Timeout expired, set back to active
                        conn.execute("""
                            UPDATE user_moderation SET status = 'active', timeout_until = NULL
                            WHERE user_id = ?
                        """, (user_id,))
                        return {'status': 'active'}
                
                return {
                    'status': row['status'],
                    'timeout_until': row['timeout_until'],
                    'reason': row['reason']
                }
        
        return await asyncio.get_event_loop().run_in_executor(None, _check)
    
    # ============ RATE LIMITING ============
    
    async def check_rate_limit(self, user_id: str, action_type: str, max_per_minute: int = 10) -> Tuple[bool, int]:
        """Check if user is rate limited. Returns (allowed, seconds_until_reset)"""
        def _check():
            current_time = datetime.now()
            minute_ago = current_time - timedelta(minutes=1)
            
            with sqlite3.connect(self.db_path) as conn:
                # Count actions in the last minute
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM rate_limits 
                    WHERE user_id = ? AND action_type = ? AND timestamp > ?
                """, (user_id, action_type, minute_ago.isoformat()))
                
                count = cursor.fetchone()[0]
                
                if count >= max_per_minute:
                    # Find oldest action in current window
                    cursor = conn.execute("""
                        SELECT timestamp FROM rate_limits 
                        WHERE user_id = ? AND action_type = ? AND timestamp > ?
                        ORDER BY timestamp ASC LIMIT 1
                    """, (user_id, action_type, minute_ago.isoformat()))
                    
                    oldest = cursor.fetchone()
                    if oldest:
                        oldest_time = datetime.fromisoformat(oldest[0])
                        seconds_until_reset = int((oldest_time + timedelta(minutes=1) - current_time).total_seconds())
                        return False, max(0, seconds_until_reset)
                
                return True, 0
        
        return await asyncio.get_event_loop().run_in_executor(None, _check)
    
    async def record_action(self, user_id: str, action_type: str, context_key: Optional[str] = None) -> None:
        """Record an action for rate limiting"""
        def _record():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO rate_limits (user_id, action_type, context_key)
                    VALUES (?, ?, ?)
                """, (user_id, action_type, context_key))
        
        await asyncio.get_event_loop().run_in_executor(None, _record)
    
    # ============ CLEANUP METHODS ============
    
    async def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """Clean up old conversation history and rate limit data"""
        def _cleanup():
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with sqlite3.connect(self.db_path) as conn:
                # Clean conversations
                cursor = conn.execute("""
                    DELETE FROM conversations WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                conversations_deleted = cursor.rowcount
                
                # Clean rate limits (keep only last 24 hours)
                rate_limit_cutoff = datetime.now() - timedelta(hours=24)
                cursor = conn.execute("""
                    DELETE FROM rate_limits WHERE timestamp < ?
                """, (rate_limit_cutoff.isoformat(),))
                rate_limits_deleted = cursor.rowcount
                
                return {
                    'conversations_deleted': conversations_deleted,
                    'rate_limits_deleted': rate_limits_deleted
                }
        
        return await asyncio.get_event_loop().run_in_executor(None, _cleanup)
    
    # ============ AUTO-CLEAN METHODS ============
    
    async def _auto_clean_on_startup(self) -> None:
        """Perform auto-clean on startup if conditions are met"""
        try:
            # Record this launch
            await self._record_launch()
            
            should_clean = False
            
            if self.auto_clean_method == 'days':
                should_clean = await self._should_clean_by_days()
            elif self.auto_clean_method == 'launches':
                should_clean = await self._should_clean_by_launches()
            
            if should_clean:
                await self._perform_auto_clean()
                
        except Exception as e:
            print(f"[LLMDatabase] Auto-clean error: {e}")
    
    async def _record_launch(self) -> None:
        """Record a system launch"""
        def _record():
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO launch_tracking (launch_time) VALUES (CURRENT_TIMESTAMP)
                """)
        
        await asyncio.get_event_loop().run_in_executor(None, _record)
    
    async def _should_clean_by_days(self) -> bool:
        """Check if cleanup should run based on days since last cleanup"""
        def _check():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT MAX(launch_time) FROM launch_tracking 
                    WHERE cleanup_performed = TRUE
                """)
                last_cleanup = cursor.fetchone()[0]
                
                if not last_cleanup:
                    return True  # Never cleaned before
                
                last_cleanup_date = datetime.fromisoformat(last_cleanup)
                days_since_cleanup = (datetime.now() - last_cleanup_date).days
                
                return days_since_cleanup >= self.auto_clean_days
        
        return await asyncio.get_event_loop().run_in_executor(None, _check)
    
    async def _should_clean_by_launches(self) -> bool:
        """Check if cleanup should run based on number of launches"""
        def _check():
            with sqlite3.connect(self.db_path) as conn:
                # Get last cleanup launch ID
                cursor = conn.execute("""
                    SELECT MAX(id) FROM launch_tracking 
                    WHERE cleanup_performed = TRUE
                """)
                last_cleanup_id = cursor.fetchone()[0] or 0
                
                # Count launches since last cleanup
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM launch_tracking 
                    WHERE id > ?
                """, (last_cleanup_id,))
                launches_since_cleanup = cursor.fetchone()[0]
                
                return launches_since_cleanup >= self.auto_clean_launches
        
        return await asyncio.get_event_loop().run_in_executor(None, _check)
    
    async def _perform_auto_clean(self) -> None:
        """Perform the actual auto-cleanup"""
        def _clean():
            with sqlite3.connect(self.db_path) as conn:
                # Clean old conversations
                cutoff_date = datetime.now() - timedelta(days=self.auto_clean_days)
                cursor = conn.execute("""
                    DELETE FROM conversations WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                conversations_deleted = cursor.rowcount
                
                # Clean old rate limits
                rate_limit_cutoff = datetime.now() - timedelta(hours=24)
                cursor = conn.execute("""
                    DELETE FROM rate_limits WHERE timestamp < ?
                """, (rate_limit_cutoff.isoformat(),))
                rate_limits_deleted = cursor.rowcount
                
                # Mark current launch as having performed cleanup
                cursor = conn.execute("""
                    UPDATE launch_tracking 
                    SET cleanup_performed = TRUE 
                    WHERE id = (SELECT MAX(id) FROM launch_tracking)
                """)
                
                print(f"[LLMDatabase] Auto-clean completed: {conversations_deleted} conversations, {rate_limits_deleted} rate limits deleted")
                
                return {
                    'conversations_deleted': conversations_deleted,
                    'rate_limits_deleted': rate_limits_deleted
                }
        
        return await asyncio.get_event_loop().run_in_executor(None, _clean)