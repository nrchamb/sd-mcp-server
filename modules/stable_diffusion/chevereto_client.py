#!/usr/bin/env python3
"""
Chevereto Image Hosting Client
Integrates with Chevereto API for public image hosting with user authentication and folder management
"""

import httpx
import os
import json
import hashlib
import asyncio
import sqlite3
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@dataclass
class CheveretoUser:
    """User configuration for Chevereto integration"""
    user_id: str  # Discord user ID or username
    api_key: str  # Chevereto API key
    default_album_id: Optional[str] = None  # Default album for this user
    username: str = ""  # Chevereto username
    created_at: datetime = None
    last_used: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_used is None:
            self.last_used = datetime.now()

@dataclass
class CheveretoConfig:
    """Chevereto server configuration"""
    base_url: str = None
    user_api_key: Optional[str] = None  # Default user API key (fallback)
    guest_api_key: Optional[str] = None  # Guest API key for anonymous uploads (30min expiry)
    admin_api_key: Optional[str] = None  # Admin API key for user management (if needed)
    timeout: int = 30
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    fallback_to_local: bool = True
    
    @classmethod
    def from_env_dict(cls, env_dict: dict) -> 'CheveretoConfig':
        """Create config from MCP environment dictionary"""
        return cls(
            base_url=env_dict.get("CHEVERETO_BASE_URL"),
            user_api_key=env_dict.get("CHEVERETO_USER_API_KEY"),
            guest_api_key=env_dict.get("CHEVERETO_GUEST_API_KEY"),
            admin_api_key=env_dict.get("CHEVERETO_ADMIN_API_KEY"),
            timeout=int(env_dict.get("CHEVERETO_TIMEOUT", "30")),
            max_file_size=int(env_dict.get("CHEVERETO_MAX_FILE_SIZE", str(50 * 1024 * 1024))),
            fallback_to_local=env_dict.get("CHEVERETO_FALLBACK_TO_LOCAL", "true").lower() == "true"
        )
    
class CheveretoClient:
    """
    Chevereto API client with user management and Discord integration
    """
    
    def __init__(self, config: CheveretoConfig, db_path: str = "chevereto_users.db"):
        self.config = config
        self.db_path = db_path
        self._init_database()
        
    def _init_database(self):
        """Initialize user database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                api_key TEXT,
                chevereto_username TEXT,
                default_album_id TEXT,
                username TEXT,
                created_at TIMESTAMP,
                last_used TIMESTAMP,
                upload_mode TEXT DEFAULT 'guest'
            )
        ''')
        
        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN chevereto_username TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN upload_mode TEXT DEFAULT "guest"')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS albums (
                album_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS uploads (
                upload_id TEXT PRIMARY KEY,
                user_id TEXT,
                filename TEXT NOT NULL,
                chevereto_url TEXT NOT NULL,
                local_path TEXT,
                album_id TEXT,
                upload_timestamp TIMESTAMP,
                file_size INTEGER,
                nsfw_detected BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: str, api_key: str = None, username: str = "", 
                 chevereto_username: str = "", default_album_id: str = None, 
                 upload_mode: str = "guest") -> bool:
        """Add or update user configuration"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, api_key, chevereto_username, username, default_album_id, 
                 created_at, last_used, upload_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, api_key, chevereto_username, username, default_album_id, now, now, upload_mode))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to add user {user_id}: {e}")
            return False
    
    def set_personal_api_key(self, user_id: str, api_key: str, chevereto_username: str = "") -> bool:
        """Set personal Chevereto API key for a Discord user"""
        try:
            # Get existing user or create new one
            user = self.get_user(user_id)
            if user:
                # Update existing user
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET api_key = ?, chevereto_username = ?, upload_mode = 'personal', last_used = ?
                    WHERE user_id = ?
                ''', (api_key, chevereto_username, datetime.now(), user_id))
                conn.commit()
                conn.close()
            else:
                # Create new user with personal key
                self.add_user(
                    user_id=user_id,
                    api_key=api_key,
                    chevereto_username=chevereto_username,
                    upload_mode="personal"
                )
            
            logger.info(f"Set personal API key for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set personal API key for {user_id}: {e}")
            return False
    
    def remove_personal_api_key(self, user_id: str) -> bool:
        """Remove personal API key for a Discord user (fall back to guest mode)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if user exists first
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                # User doesn't exist, nothing to remove
                conn.close()
                logger.info(f"User {user_id} doesn't exist, nothing to remove")
                return True
            
            # Update user to remove API key (set to empty string instead of NULL)
            cursor.execute('''
                UPDATE users 
                SET api_key = '', chevereto_username = '', upload_mode = 'guest', last_used = ?
                WHERE user_id = ?
            ''', (datetime.now(), user_id))
            conn.commit()
            conn.close()
            
            logger.info(f"Removed personal API key for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove personal API key for {user_id}: {e}")
            return False
    
    def get_user(self, user_id: str) -> Optional[CheveretoUser]:
        """Get user configuration"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_id, api_key, default_album_id, username, created_at, last_used
                FROM users WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return CheveretoUser(
                    user_id=row[0],
                    api_key=row[1],
                    default_album_id=row[2],
                    username=row[3],
                    created_at=datetime.fromisoformat(row[4]) if row[4] else None,
                    last_used=datetime.fromisoformat(row[5]) if row[5] else None
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    def get_user_upload_mode(self, user_id: str) -> str:
        """Get user's upload mode (guest or personal)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT upload_mode, api_key, chevereto_username
                FROM users WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                upload_mode, api_key, chevereto_username = row
                if upload_mode == "personal" and api_key:
                    return f"personal ({chevereto_username or 'unnamed'})"
                else:
                    return "guest"
            else:
                return "guest"
                
        except Exception as e:
            logger.error(f"Failed to get upload mode for {user_id}: {e}")
            return "guest"
    
    def _update_user_last_used(self, user_id: str):
        """Update user's last used timestamp"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_used = ? WHERE user_id = ?
            ''', (datetime.now(), user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update last used for {user_id}: {e}")
    
    async def create_album(self, user_id: str, album_name: str, description: str = "") -> Optional[str]:
        """Create album for user (requires Chevereto API support)"""
        user = self.get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return None
        
        try:
            # Note: Chevereto API v1.1 doesn't support album creation via API
            # This is a placeholder for future API versions or manual setup
            album_id = f"album_{hashlib.md5(f'{user_id}_{album_name}'.encode()).hexdigest()[:8]}"
            
            # Store in local database for tracking
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO albums 
                (album_id, user_id, name, description, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (album_id, user_id, album_name, description, datetime.now()))
            conn.commit()
            conn.close()
            
            logger.info(f"Created album {album_id} for user {user_id}")
            return album_id
            
        except Exception as e:
            logger.error(f"Failed to create album for {user_id}: {e}")
            return None
    
    async def upload_image(self, image_path: str, user_id: str = None, 
                          album_id: str = None, title: str = None, 
                          description: str = None, tags: List[str] = None,
                          nsfw_detected: bool = False) -> Dict[str, Any]:
        """
        Upload image to Chevereto with user authentication or guest mode
        Falls back to local storage if Chevereto is unavailable
        
        Upload modes:
        1. Personal API Key: User has registered their own Chevereto API key (persistent)
        2. Guest Mode: Uses guest API key for anonymous uploads (30min expiry)
        3. Fallback: Local storage if no API keys available
        """
        if not os.path.exists(image_path):
            return {"success": False, "error": "Image file not found"}
        
        # Determine upload mode and API key
        api_key = None
        upload_mode = "guest"
        user = None
        
        if user_id:
            user = self.get_user(user_id)
            if user and user.api_key and user.api_key.strip():
                # User has personal API key
                api_key = user.api_key
                upload_mode = "personal"
                album_id = album_id or user.default_album_id
                self._update_user_last_used(user_id)
                logger.info(f"Using personal API key for user {user_id}")
            else:
                # Try guest API key first, fallback to user API key (if available)
                if self.config.guest_api_key and self.config.guest_api_key.strip():
                    api_key = self.config.guest_api_key
                    upload_mode = "guest"
                    logger.info(f"Using guest mode for user {user_id}")
                elif self.config.user_api_key and self.config.user_api_key.strip():
                    api_key = self.config.user_api_key
                    upload_mode = "shared"
                    logger.info(f"Using shared mode for user {user_id}")
                else:
                    api_key = None
                    upload_mode = "none"
        else:
            # No user specified, use guest mode or fallback to user API key (if available)
            if self.config.guest_api_key and self.config.guest_api_key.strip():
                api_key = self.config.guest_api_key
                upload_mode = "guest"
                logger.info("Using guest mode (no user specified)")
            elif self.config.user_api_key and self.config.user_api_key.strip():
                api_key = self.config.user_api_key
                upload_mode = "shared"
                logger.info("Using shared mode (no user specified)")
            else:
                api_key = None
                upload_mode = "none"
        
        if not api_key:
            logger.warning("No API key available (guest, personal, or shared), falling back to local storage")
            if self.config.fallback_to_local:
                return await self._fallback_local_upload(image_path, user_id, nsfw_detected)
            return {"success": False, "error": "No API key configured"}
        
        try:
            # Prepare upload
            filename = os.path.basename(image_path)
            upload_id = hashlib.md5(f"{user_id}_{filename}_{datetime.now()}".encode()).hexdigest()
            
            # Upload to Chevereto
            result = await self._upload_to_chevereto(
                image_path, api_key, album_id, title, description, tags
            )
            
            if result["success"]:
                # Store upload record
                self._store_upload_record(
                    upload_id, user_id, filename, result["url"], 
                    image_path, album_id, nsfw_detected, os.path.getsize(image_path)
                )
                
                expiry_map = {
                    "guest": "30 minutes (guest)",
                    "shared": "permanent (shared account)", 
                    "personal": "permanent (your account)"
                }
                
                return {
                    "success": True,
                    "url": result["url"],
                    "upload_id": upload_id,
                    "filename": filename,
                    "hosting_service": "chevereto",
                    "upload_mode": upload_mode,
                    "expiry_note": expiry_map.get(upload_mode, "unknown"),
                    "user_id": user_id,
                    "album_id": album_id,
                    "nsfw_detected": nsfw_detected
                }
            else:
                # Fallback to local if enabled
                if self.config.fallback_to_local:
                    logger.warning(f"Chevereto upload failed, falling back to local: {result.get('error')}")
                    fallback_result = await self._fallback_local_upload(image_path, user_id, nsfw_detected)
                    # Preserve the intended upload mode in fallback result
                    if fallback_result["success"]:
                        expiry_map = {
                            "guest": "30 minutes (guest, local fallback)",
                            "shared": "permanent (shared account, local fallback)", 
                            "personal": "permanent (your account, local fallback)"
                        }
                        fallback_result["upload_mode"] = upload_mode
                        fallback_result["expiry_note"] = expiry_map.get(upload_mode, "unknown")
                        fallback_result["intended_service"] = "chevereto"
                        fallback_result["fallback_reason"] = result.get("error", "Upload failed")
                    return fallback_result
                return result
                
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            if self.config.fallback_to_local:
                return await self._fallback_local_upload(image_path, user_id, nsfw_detected)
            return {"success": False, "error": str(e)}
    
    async def _upload_to_chevereto(self, image_path: str, api_key: str, 
                                  album_id: str = None, title: str = None,
                                  description: str = None, tags: List[str] = None) -> Dict[str, Any]:
        """Upload image to Chevereto API"""
        url = f"{self.config.base_url.rstrip('/')}/api/1/upload"
        
        logger.info(f"🔑 Using API key: {api_key[:8]}...{api_key[-8:] if len(api_key) > 16 else '***'}")
        
        # Use X-API-Key header authentication for all API keys (standard Chevereto V1.1)
        headers = {"X-API-Key": api_key}
        data = {}
        
        # Log which type of API key is being used for debugging
        if api_key == self.config.guest_api_key:
            logger.info("📤 Using X-API-Key header authentication (guest API)")
        elif api_key == self.config.user_api_key:
            logger.info("📤 Using X-API-Key header authentication (user API)")
        else:
            logger.info("📤 Using X-API-Key header authentication (personal API)")
        
        # Add other parameters
        if album_id:
            data["album_id"] = album_id
        if title:
            data["title"] = title
        if description:
            data["description"] = description
        if tags:
            data["tags"] = ",".join(tags)
        
        # Always request JSON format for consistent parsing
        data["format"] = "json"
        
        logger.info(f"📤 Uploading to: {url}")
        logger.info(f"📋 Data: {dict((k, v if k != 'key' else f'{v[:8]}...{v[-8:]}') for k, v in data.items())}")
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                with open(image_path, 'rb') as f:
                    files = {
                        "source": (os.path.basename(image_path), f, "image/png")
                    }
                    
                    response = await client.post(url, headers=headers, data=data, files=files)
                    
                    logger.info(f"📡 Response status: {response.status_code}")
                    logger.info(f"📄 Response body: {response.text[:500]}...")
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("status_code") == 200:
                            return {
                                "success": True,
                                "url": result["image"]["url"],
                                "delete_url": result["image"].get("delete_url"),
                                "expiration_date": result["image"].get("expiration_date_gmt"),
                                "response": result
                            }
                        else:
                            return {
                                "success": False,
                                "error": result.get("error", {}).get("message", "Unknown API error"),
                                "full_response": result
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {response.text}",
                            "status_code": response.status_code
                        }
                        
        except Exception as e:
            logger.error(f"Upload exception: {e}")
            return {"success": False, "error": str(e)}
    
    async def _fallback_local_upload(self, image_path: str, user_id: str = None, 
                                   nsfw_detected: bool = False) -> Dict[str, Any]:
        """Fallback to local file storage (compatible with existing simple file server)"""
        try:
            # Use the standard upload directory (no user subdirs for compatibility)
            upload_dir = Path("/tmp/uploaded_images")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with user prefix if provided
            filename = os.path.basename(image_path)
            file_hash = hashlib.md5(open(image_path, 'rb').read()).hexdigest()[:8]
            
            if user_id:
                final_filename = f"{user_id}_{file_hash}_{filename}"
            else:
                final_filename = f"sd_{file_hash}_{filename}"
            
            # Copy file to main directory (no subdirs)
            dest_path = upload_dir / final_filename
            import shutil
            shutil.copy2(image_path, dest_path)
            
            # Generate URL using MCP HTTP server configuration
            http_host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
            http_port = os.getenv("MCP_HTTP_PORT", "8000")
            url = f"http://{http_host}:{http_port}/images/{final_filename}"
            
            return {
                "success": True,
                "url": url,
                "filename": final_filename,
                "hosting_service": "local",
                "user_id": user_id,
                "local_path": str(dest_path),
                "nsfw_detected": nsfw_detected
            }
            
        except Exception as e:
            return {"success": False, "error": f"Local fallback failed: {e}"}
    
    def _store_upload_record(self, upload_id: str, user_id: str, filename: str,
                           url: str, local_path: str, album_id: str,
                           nsfw_detected: bool, file_size: int):
        """Store upload record in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO uploads 
                (upload_id, user_id, filename, chevereto_url, local_path, album_id, 
                 upload_timestamp, file_size, nsfw_detected)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (upload_id, user_id, filename, url, local_path, album_id,
                  datetime.now(), file_size, nsfw_detected))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to store upload record: {e}")
    
    def get_user_uploads(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's upload history"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT upload_id, filename, chevereto_url, album_id, upload_timestamp, 
                       file_size, nsfw_detected
                FROM uploads WHERE user_id = ? 
                ORDER BY upload_timestamp DESC LIMIT ?
            ''', (user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "upload_id": row[0],
                    "filename": row[1],
                    "url": row[2],
                    "album_id": row[3],
                    "upload_timestamp": row[4],
                    "file_size": row[5],
                    "nsfw_detected": bool(row[6])
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get uploads for {user_id}: {e}")
            return []
    
    def get_user_albums(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's albums"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT album_id, name, description, created_at
                FROM albums WHERE user_id = ? 
                ORDER BY created_at DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "album_id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get albums for {user_id}: {e}")
            return []
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to Chevereto API"""
        try:
            if not self.config.base_url or self.config.base_url == "https://your-chevereto-domain.com":
                return {"success": False, "error": "Chevereto base URL not configured"}
            
            # Test connection by checking if we can reach the base URL
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.config.base_url.rstrip('/'))
                
                if response.status_code in [200, 302]:  # 200 = OK, 302 = redirect (normal)
                    return {"success": True, "message": "Chevereto server is accessible"}
                else:
                    return {"success": False, "error": f"Server returned: {response.status_code}"}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}

# Example usage and configuration
def create_chevereto_client() -> CheveretoClient:
    """Create configured Chevereto client"""
    config = CheveretoConfig(
        base_url=os.getenv("CHEVERETO_BASE_URL"),
        user_api_key=os.getenv("CHEVERETO_USER_API_KEY"),
        admin_api_key=os.getenv("CHEVERETO_ADMIN_API_KEY"),
        fallback_to_local=True
    )
    
    return CheveretoClient(config)