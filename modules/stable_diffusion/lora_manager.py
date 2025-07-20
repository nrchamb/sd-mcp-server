import json
import sqlite3
import os
from typing import List, Dict, Any, Optional
from .models import LoRAModel, LoRAInfo, LoRASuggestion, LoRAValidation
from .sd_client import SDClient

class LoRAManager:
    def __init__(self, db_path: str = "lora_database.db", sd_client: Optional[SDClient] = None, auto_sync: bool = True):
        self.db_path = db_path
        self.sd_client = sd_client or SDClient()
        self.auto_sync = auto_sync
        self._init_database()
        
        # Auto-sync on initialization if enabled
        if self.auto_sync:
            import asyncio
            try:
                # Try to sync in the background
                asyncio.create_task(self._auto_sync_on_init())
            except:
                # If we can't create a task, defer sync to first search
                pass
    
    def _init_database(self):
        """Initialize SQLite database for LoRA metadata with smart caching"""
        with sqlite3.connect(self.db_path) as conn:
            # Main LoRA table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS loras (
                    name TEXT PRIMARY KEY,
                    alias TEXT,
                    path TEXT,
                    filename TEXT,
                    weight REAL DEFAULT 1.0,
                    category TEXT DEFAULT 'general',
                    description TEXT,
                    trigger_words TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Sync metadata table for smart caching
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY,
                    last_sync_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    lora_count INTEGER DEFAULT 0,
                    lora_list_hash TEXT,
                    cache_version INTEGER DEFAULT 1,
                    sync_duration_ms INTEGER DEFAULT 0
                )
            """)
            
            # Search cache table for frequent queries
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    query_hash TEXT PRIMARY KEY,
                    original_query TEXT,
                    results_json TEXT,
                    hit_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Enhanced indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON loras(category)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trigger_words ON loras(trigger_words)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_name_search ON loras(name)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_description_search ON loras(description)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_last_used ON search_cache(last_used DESC)
            """)
            
            conn.commit()
    
    async def _auto_sync_on_init(self):
        """Auto-sync LoRA database on initialization if needed"""
        try:
            print("🔍 Checking if LoRA database needs syncing...")
            await self.sync_with_sd_api()
        except Exception as e:
            print(f"⚠️ Auto-sync failed: {e}")
    
    def _calculate_lora_list_hash(self, loras: List) -> str:
        """Calculate hash of LoRA list for change detection"""
        import hashlib
        # Create a hash from LoRA names and paths
        lora_data = [f"{lora.name}:{lora.path}" for lora in loras]
        lora_string = "|".join(sorted(lora_data))
        return hashlib.md5(lora_string.encode()).hexdigest()
    
    def _get_sync_metadata(self) -> Dict[str, Any]:
        """Get current sync metadata"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT last_sync_check, lora_count, lora_list_hash, cache_version, sync_duration_ms
                FROM sync_metadata ORDER BY id DESC LIMIT 1
            """).fetchone()
            
            if row:
                return {
                    "last_sync_check": row[0],
                    "lora_count": row[1], 
                    "lora_list_hash": row[2],
                    "cache_version": row[3],
                    "sync_duration_ms": row[4]
                }
            return {}
    
    def _update_sync_metadata(self, lora_count: int, lora_hash: str, sync_duration_ms: int):
        """Update sync metadata after successful sync"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sync_metadata (last_sync_check, lora_count, lora_list_hash, sync_duration_ms)
                VALUES (CURRENT_TIMESTAMP, ?, ?, ?)
            """, (lora_count, lora_hash, sync_duration_ms))
            conn.commit()
    
    async def _should_sync(self) -> bool:
        """Determine if LoRA database needs syncing"""
        try:
            # Get current LoRA list from SD API
            loras = await self.sd_client.get_loras()
            current_hash = self._calculate_lora_list_hash(loras)
            current_count = len(loras)
            
            # Get last sync metadata
            sync_meta = self._get_sync_metadata()
            
            # Force sync if no previous sync or significant changes
            if not sync_meta:
                return True, current_count, current_hash, "No previous sync data"
            
            if sync_meta.get("lora_count", 0) != current_count:
                return True, current_count, current_hash, f"Count changed: {sync_meta.get('lora_count', 0)} → {current_count}"
            
            if sync_meta.get("lora_list_hash") != current_hash:
                return True, current_count, current_hash, "LoRA collection changed"
            
            return False, current_count, current_hash, "No changes detected"
            
        except Exception as e:
            # If we can't check, err on the side of syncing
            return True, 0, "", f"Error checking: {str(e)}"
    
    async def sync_with_sd_api(self) -> int:
        """Smart sync LoRA database with SD WebUI API - only if changes detected"""
        import time
        start_time = time.time()
        
        # Check if sync is needed
        should_sync, lora_count, lora_hash, reason = await self._should_sync()
        
        if not should_sync:
            print(f"⏭️ Skipping LoRA sync: {reason}")
            return 0
        
        print(f"🔄 Syncing LoRA database: {reason}")
        
        # Get LoRAs from SD API
        loras = await self.sd_client.get_loras()
        updated_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            for lora in loras:
                # Parse tag frequency and analyze metadata
                tag_freq = self._parse_tag_frequency(lora.metadata)
                
                # Fallback to name-based analysis if no metadata
                if not tag_freq:
                    auto_category, extracted_triggers, content_type, description = self._analyze_from_name_and_path(lora.name, lora.path)
                else:
                    # Auto-categorize based on tags
                    auto_category = self._auto_categorize_from_tags(tag_freq)
                    
                    # Extract trigger words from training data
                    extracted_triggers = self._extract_trigger_words_from_tags(tag_freq)
                    
                    # Detect content type
                    content_type = self._detect_content_type(tag_freq)
                    
                    # Create description from top tags
                    top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:5]
                    description = f"Trained on: {', '.join([tag for tag, freq in top_tags])}" if top_tags else ""
                
                existing = conn.execute(
                    "SELECT name FROM loras WHERE name = ?", (lora.name,)
                ).fetchone()
                
                if existing:
                    conn.execute("""
                        UPDATE loras SET 
                            alias = ?, path = ?, category = ?, trigger_words = ?, 
                            description = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE name = ?
                    """, (
                        lora.alias, lora.path, auto_category, 
                        json.dumps(extracted_triggers), description,
                        json.dumps({
                            **lora.metadata,
                            "content_type": content_type,
                            "tag_frequency_parsed": len(tag_freq) > 0
                        }), 
                        lora.name
                    ))
                else:
                    filename = os.path.basename(lora.path) if lora.path else ""
                    conn.execute("""
                        INSERT INTO loras (name, alias, path, filename, category, trigger_words, description, metadata) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lora.name, lora.alias, lora.path, filename, auto_category,
                        json.dumps(extracted_triggers), description,
                        json.dumps({
                            **lora.metadata,
                            "content_type": content_type,
                            "tag_frequency_parsed": len(tag_freq) > 0
                        })
                    ))
                
                updated_count += 1
        
        # Update sync metadata
        sync_duration_ms = int((time.time() - start_time) * 1000)
        self._update_sync_metadata(len(loras), lora_hash, sync_duration_ms)
        
        print(f"✅ LoRA sync complete: {updated_count} updated, {len(loras)} total ({sync_duration_ms}ms)")
        return updated_count
    
    def get_lora_info(self, name: str) -> Optional[LoRAInfo]:
        """Get detailed LoRA information"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT name, filename, weight, trigger_words, category, description, metadata
                FROM loras WHERE name = ?
            """, (name,)).fetchone()
            
            if not row:
                return None
            
            trigger_words = json.loads(row[3]) if row[3] else []
            metadata = json.loads(row[6]) if row[6] else {}
            
            return LoRAInfo(
                name=row[0],
                filename=row[1],
                weight=row[2],
                trigger_words=trigger_words,
                category=row[4],
                description=row[5] or "",
                metadata=metadata
            )
    
    def search_loras(self, query: str, category: Optional[str] = None) -> List[LoRAInfo]:
        """Search LoRAs by name, trigger words, or description"""
        with sqlite3.connect(self.db_path) as conn:
            sql = """
                SELECT name, filename, weight, trigger_words, category, description, metadata
                FROM loras 
                WHERE (name LIKE ? OR description LIKE ? OR trigger_words LIKE ?)
            """
            params = [f"%{query}%", f"%{query}%", f"%{query}%"]
            
            if category:
                sql += " AND category = ?"
                params.append(category)
            
            rows = conn.execute(sql, params).fetchall()
            
            results = []
            for row in rows:
                trigger_words = json.loads(row[3]) if row[3] else []
                metadata = json.loads(row[6]) if row[6] else {}
                
                results.append(LoRAInfo(
                    name=row[0],
                    filename=row[1],
                    weight=row[2],
                    trigger_words=trigger_words,
                    category=row[4],
                    description=row[5] or "",
                    metadata=metadata
                ))
            
            return results
    
    def _get_query_hash(self, query: str, category: Optional[str] = None) -> str:
        """Generate hash for query caching"""
        import hashlib
        cache_key = f"{query.lower().strip()}:{category or ''}"
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    def _get_cached_search(self, query_hash: str) -> Optional[List[LoRAInfo]]:
        """Get cached search results"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT results_json, hit_count FROM search_cache 
                WHERE query_hash = ? AND datetime(last_used) > datetime('now', '-1 hour')
            """, (query_hash,)).fetchone()
            
            if row:
                # Update hit count and last used
                conn.execute("""
                    UPDATE search_cache 
                    SET hit_count = hit_count + 1, last_used = CURRENT_TIMESTAMP
                    WHERE query_hash = ?
                """, (query_hash,))
                conn.commit()
                
                # Parse cached results
                try:
                    cached_data = json.loads(row[0])
                    results = []
                    for item in cached_data:
                        results.append(LoRAInfo(**item))
                    return results
                except:
                    return None
            
            return None
    
    def _cache_search_results(self, query_hash: str, query: str, results: List[LoRAInfo]):
        """Cache search results"""
        # Convert LoRAInfo objects to serializable format
        results_data = []
        for lora in results:
            results_data.append({
                "name": lora.name,
                "filename": lora.filename,
                "weight": lora.weight,
                "trigger_words": lora.trigger_words,
                "category": lora.category,
                "description": lora.description,
                "metadata": lora.metadata
            })
        
        results_json = json.dumps(results_data)
        
        with sqlite3.connect(self.db_path) as conn:
            # Use INSERT OR REPLACE to handle duplicates
            conn.execute("""
                INSERT OR REPLACE INTO search_cache 
                (query_hash, original_query, results_json, hit_count, created_at, last_used)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (query_hash, query, results_json))
            conn.commit()
    
    def _cleanup_old_cache(self):
        """Clean up old cache entries (keep last 100, remove older than 24h)"""
        with sqlite3.connect(self.db_path) as conn:
            # Remove entries older than 24 hours
            conn.execute("""
                DELETE FROM search_cache 
                WHERE datetime(last_used) < datetime('now', '-24 hours')
            """)
            
            # Keep only top 100 most recently used
            conn.execute("""
                DELETE FROM search_cache 
                WHERE query_hash NOT IN (
                    SELECT query_hash FROM search_cache 
                    ORDER BY last_used DESC LIMIT 100
                )
            """)
            conn.commit()
    
    async def search_loras_cached(self, query: str, category: Optional[str] = None, limit: int = 10) -> List[LoRAInfo]:
        """Search LoRAs with caching for performance"""
        query_hash = self._get_query_hash(query, category)
        
        # Try cache first
        cached_results = self._get_cached_search(query_hash)
        if cached_results is not None:
            return cached_results[:limit]
        
        # Cache miss - perform actual search
        results = self.search_loras(query, category)
        
        # Cache the results for future use
        if results:
            self._cache_search_results(query_hash, query, results)
        
        # Occasionally clean up old cache entries
        if hash(query) % 50 == 0:  # Clean up 2% of the time
            self._cleanup_old_cache()
        
        return results[:limit]
    
    def analyze_prompt_for_loras(self, prompt: str) -> List[LoRASuggestion]:
        """Analyze prompt to suggest relevant LoRAs"""
        suggestions = []
        
        # Category-based keyword matching
        category_keywords = {
            "anime": ["anime", "manga", "2d", "chibi", "kawaii"],
            "realistic": ["photorealistic", "realistic", "photo", "portrait"],
            "art": ["painting", "artwork", "drawing", "sketch"],
            "character": ["character", "person", "girl", "boy", "woman", "man"],
            "style": ["style", "aesthetic", "look", "theme"]
        }
        
        prompt_lower = prompt.lower()
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    matching_loras = self.search_loras(keyword, category)
                    for lora in matching_loras[:3]:  # Top 3 matches per category
                        confidence = 0.7 if keyword in lora.trigger_words else 0.5
                        suggestions.append(LoRASuggestion(
                            lora=lora.name,
                            confidence=confidence,
                            reason=f"'{keyword}' matches {category} category"
                        ))
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_suggestions = []
        for suggestion in sorted(suggestions, key=lambda x: x.confidence, reverse=True):
            if suggestion.lora not in seen:
                seen.add(suggestion.lora)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions[:5]  # Return top 5 suggestions
    
    def validate_lora_combination(self, loras: List[Dict[str, Any]]) -> LoRAValidation:
        """Validate LoRA combination for conflicts"""
        validation = LoRAValidation(valid=True)
        
        # Check total weight
        total_weight = sum(lora.get("weight", 1.0) for lora in loras)
        if total_weight > 3.0:
            validation.warnings.append(f"Total LoRA weight ({total_weight:.1f}) exceeds 3.0, may cause artifacts")
        
        # Check for style conflicts
        style_loras = []
        for lora in loras:
            lora_info = self.get_lora_info(lora.get("name", ""))
            if lora_info and lora_info.category == "style":
                style_loras.append(lora_info.name)
        
        if len(style_loras) > 2:
            validation.warnings.append(f"Multiple style LoRAs detected: {', '.join(style_loras)}. May cause conflicts.")
        
        # Check for character conflicts
        character_loras = []
        for lora in loras:
            lora_info = self.get_lora_info(lora.get("name", ""))
            if lora_info and lora_info.category == "character":
                character_loras.append(lora_info.name)
        
        if len(character_loras) > 1:
            validation.warnings.append(f"Multiple character LoRAs detected: {', '.join(character_loras)}. Consider using only one.")
        
        # Add recommendations
        if total_weight < 1.5:
            validation.recommendations.append("Consider increasing LoRA weights for stronger effect")
        
        if not any(
            (lora_info := self.get_lora_info(lora.get("name", ""))) and lora_info.category == "style" 
            for lora in loras
        ):
            validation.recommendations.append("Consider adding a style LoRA for better aesthetic control")
        
        return validation
    
    def optimize_lora_weights(self, loras: List[Dict[str, Any]], target_style: str = "balanced") -> List[Dict[str, Any]]:
        """Optimize LoRA weights based on target style"""
        optimized = []
        
        for lora in loras:
            optimized_lora = lora.copy()
            current_weight = lora.get("weight", 1.0)
            
            if target_style == "strong":
                optimized_lora["weight"] = min(current_weight * 1.3, 1.5)
            elif target_style == "subtle":
                optimized_lora["weight"] = current_weight * 0.7
            elif target_style == "extreme":
                optimized_lora["weight"] = min(current_weight * 1.5, 2.0)
            # "balanced" = no change
            
            optimized.append(optimized_lora)
        
        return optimized
    
    def update_lora_metadata(self, name: str, trigger_words: List[str] = None, 
                           category: str = None, description: str = None) -> bool:
        """Update LoRA metadata"""
        with sqlite3.connect(self.db_path) as conn:
            updates = []
            params = []
            
            if trigger_words is not None:
                updates.append("trigger_words = ?")
                params.append(json.dumps(trigger_words))
            
            if category:
                updates.append("category = ?")
                params.append(category)
            
            if description:
                updates.append("description = ?")
                params.append(description)
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(name)
                
                sql = f"UPDATE loras SET {', '.join(updates)} WHERE name = ?"
                conn.execute(sql, params)
                return conn.rowcount > 0
        
        return False
    
    def get_lora_summary(self) -> Dict[str, Any]:
        """Get a concise summary of available LoRAs by category"""
        with sqlite3.connect(self.db_path) as conn:
            # Get category counts
            category_counts = {}
            rows = conn.execute("""
                SELECT category, COUNT(*) as count 
                FROM loras 
                GROUP BY category
                ORDER BY count DESC
            """).fetchall()
            
            total_loras = 0
            for category, count in rows:
                category_counts[category] = count
                total_loras += count
            
            # Get top trigger words
            trigger_word_counts = {}
            all_triggers = conn.execute("""
                SELECT trigger_words FROM loras WHERE trigger_words IS NOT NULL AND trigger_words != ''
            """).fetchall()
            
            for row in all_triggers:
                if row[0]:
                    try:
                        triggers = json.loads(row[0])
                        for trigger in triggers:
                            trigger_word_counts[trigger] = trigger_word_counts.get(trigger, 0) + 1
                    except:
                        continue
            
            # Top 10 trigger words
            top_triggers = sorted(trigger_word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "total_loras": total_loras,
                "categories": category_counts,
                "top_trigger_words": [{"word": word, "count": count} for word, count in top_triggers],
                "summary_text": f"{total_loras} LoRAs available across {len(category_counts)} categories"
            }
    
    def get_loras_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get LoRAs from a specific category with essential info only"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT name, trigger_words, description 
                FROM loras 
                WHERE category = ? 
                ORDER BY name 
                LIMIT ?
            """, (category, limit)).fetchall()
            
            results = []
            for row in rows:
                trigger_words = json.loads(row[1]) if row[1] else []
                results.append({
                    "name": row[0],
                    "trigger_words": trigger_words[:3],  # Only first 3 trigger words
                    "description": (row[2] or "")[:100] + "..." if row[2] and len(row[2]) > 100 else (row[2] or "")
                })
            
            return results
    
    def search_loras_smart(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Smart search with relevance scoring and concise results"""
        with sqlite3.connect(self.db_path) as conn:
            # Search in name, description, and trigger words
            sql = """
                SELECT name, trigger_words, description, category,
                       CASE 
                           WHEN name LIKE ? THEN 3
                           WHEN trigger_words LIKE ? THEN 2
                           WHEN description LIKE ? THEN 1
                           ELSE 0
                       END as relevance_score
                FROM loras 
                WHERE relevance_score > 0
                ORDER BY relevance_score DESC, name
                LIMIT ?
            """
            
            search_term = f"%{query.lower()}%"
            rows = conn.execute(sql, (search_term, search_term, search_term, max_results)).fetchall()
            
            results = []
            for row in rows:
                trigger_words = json.loads(row[1]) if row[1] else []
                # Find matching trigger words
                matching_triggers = [tw for tw in trigger_words if query.lower() in tw.lower()]
                
                results.append({
                    "name": row[0],
                    "category": row[3],
                    "relevance": "high" if row[4] == 3 else "medium" if row[4] == 2 else "low",
                    "matching_triggers": matching_triggers[:2],  # Max 2 matching triggers
                    "description": (row[2] or "")[:80] + "..." if row[2] and len(row[2]) > 80 else (row[2] or "")
                })
            
            return results
    
    def suggest_loras_for_prompt_smart(self, prompt: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Enhanced prompt analysis using tag frequency data"""
        with sqlite3.connect(self.db_path) as conn:
            # Get all LoRAs with their metadata
            rows = conn.execute("""
                SELECT name, category, trigger_words, description, metadata
                FROM loras 
                ORDER BY name
            """).fetchall()
            
            lora_scores = []
            
            for row in rows:
                name, category, trigger_words_json, description, metadata_json = row
                
                try:
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    tag_freq = self._parse_tag_frequency(metadata)
                    trigger_words = json.loads(trigger_words_json) if trigger_words_json else []
                    
                    if tag_freq:
                        # Use tag frequency for intelligent scoring
                        score = self._calculate_prompt_tag_score(prompt, tag_freq)
                        
                        if score > 0.05:  # Only include if there's meaningful overlap
                            # Find matching triggers
                            prompt_words = set(prompt.lower().split())
                            matching_triggers = []
                            for trigger in trigger_words:
                                if any(word in trigger.lower() for word in prompt_words):
                                    matching_triggers.append(trigger)
                            
                            # Determine confidence level
                            if score > 0.3:
                                confidence = "high"
                                weight = 1.0
                            elif score > 0.15:
                                confidence = "medium" 
                                weight = 0.8
                            else:
                                confidence = "low"
                                weight = 0.6
                            
                            # Create reason based on tag analysis
                            top_matching_tags = []
                            prompt_words_set = set(prompt.lower().replace(",", " ").split())
                            for tag, freq in sorted(tag_freq.items(), key=lambda x: x[1], reverse=True):
                                tag_words = set(tag.lower().replace("_", " ").split())
                                if tag_words.intersection(prompt_words_set):
                                    top_matching_tags.append(tag)
                                    if len(top_matching_tags) >= 2:
                                        break
                            
                            reason = f"Strong match on tags: {', '.join(top_matching_tags)}" if top_matching_tags else "Tag frequency analysis"
                            
                            lora_scores.append({
                                "name": name,
                                "score": score,
                                "confidence": confidence,
                                "reason": reason,
                                "category": category,
                                "key_triggers": matching_triggers[:3] or trigger_words[:3],
                                "recommended_weight": weight,
                                "matching_tags": top_matching_tags
                            })
                    else:
                        # Fallback to basic name/trigger matching when no tag frequency available
                        prompt_words = set(prompt.lower().split())
                        
                        # Score based on name and trigger word matching
                        name_score = 0.0
                        name_words = set(name.lower().replace("_", " ").split())
                        name_matches = len(name_words.intersection(prompt_words))
                        if name_matches > 0:
                            name_score = min(name_matches * 0.2, 0.8)
                        
                        trigger_score = 0.0
                        matching_triggers = []
                        for trigger in trigger_words:
                            trigger_words_set = set(trigger.lower().split())
                            if trigger_words_set.intersection(prompt_words):
                                matching_triggers.append(trigger)
                                trigger_score += 0.3
                        
                        total_score = min(name_score + trigger_score, 1.0)
                        
                        if total_score > 0.1:  # Include if there's some relevance
                            if total_score > 0.5:
                                confidence = "medium"
                                weight = 0.8
                            else:
                                confidence = "low"
                                weight = 0.6
                            
                            reason = f"Name/trigger match: {name_matches} name words, {len(matching_triggers)} triggers"
                            
                            lora_scores.append({
                                "name": name,
                                "score": total_score,
                                "confidence": confidence,
                                "reason": reason,
                                "category": category,
                                "key_triggers": matching_triggers[:3] or trigger_words[:3],
                                "recommended_weight": weight,
                                "matching_tags": []
                            })
                    
                except (json.JSONDecodeError, TypeError):
                    continue
            
            # Sort by score and return top results
            lora_scores.sort(key=lambda x: x["score"], reverse=True)
            return lora_scores[:limit]
    
    def _parse_tag_frequency(self, metadata: Dict[str, Any]) -> Dict[str, int]:
        """Parse ss_tag_frequency from LoRA metadata"""
        tag_freq = {}
        
        # Look for ss_tag_frequency in metadata
        ss_tag_freq = metadata.get("ss_tag_frequency")
        if not ss_tag_freq:
            return tag_freq
        
        try:
            # ss_tag_frequency can be a JSON string or already parsed
            if isinstance(ss_tag_freq, str):
                tag_data = json.loads(ss_tag_freq)
            else:
                tag_data = ss_tag_freq
            
            # Combine all tag frequencies from different categories
            for category_name, tags in tag_data.items():
                if isinstance(tags, dict):
                    for tag, freq in tags.items():
                        if isinstance(freq, (int, float)):
                            tag_freq[tag] = tag_freq.get(tag, 0) + int(freq)
            
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        
        return tag_freq
    
    def _auto_categorize_from_tags(self, tag_freq: Dict[str, int]) -> str:
        """Auto-categorize LoRA based on tag frequency patterns"""
        if not tag_freq:
            return "general"
        
        # Get top tags by frequency
        top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:20]
        top_tag_names = [tag for tag, freq in top_tags]
        
        # Define category patterns
        anime_indicators = ["anime", "manga", "2d", "chibi", "kawaii", "anime style", "cel shading"]
        realistic_indicators = ["photorealistic", "realistic", "photo", "photography", "real", "portrait"]
        character_indicators = ["1girl", "1boy", "character", "person", "face", "portrait"]
        style_indicators = ["art style", "painting", "drawing", "sketch", "watercolor", "oil painting"]
        concept_indicators = ["pose", "clothing", "outfit", "background", "lighting", "effect"]
        
        # Score categories based on tag matches
        category_scores = {
            "anime": sum(1 for tag in top_tag_names if any(ind in tag.lower() for ind in anime_indicators)),
            "realistic": sum(1 for tag in top_tag_names if any(ind in tag.lower() for ind in realistic_indicators)),
            "character": sum(1 for tag in top_tag_names if any(ind in tag.lower() for ind in character_indicators)),
            "style": sum(1 for tag in top_tag_names if any(ind in tag.lower() for ind in style_indicators)),
            "concept": sum(1 for tag in top_tag_names if any(ind in tag.lower() for ind in concept_indicators))
        }
        
        # Additional heuristics
        if "1girl" in tag_freq and tag_freq["1girl"] > 100:
            category_scores["character"] += 2
        if "anime" in tag_freq or "manga" in tag_freq:
            category_scores["anime"] += 3
        if "photorealistic" in tag_freq or "realistic" in tag_freq:
            category_scores["realistic"] += 3
        
        # Return highest scoring category
        best_category = max(category_scores.items(), key=lambda x: x[1])
        return best_category[0] if best_category[1] > 0 else "general"
    
    def _extract_trigger_words_from_tags(self, tag_freq: Dict[str, int], limit: int = 10) -> List[str]:
        """Extract meaningful trigger words from tag frequency data"""
        if not tag_freq:
            return []
        
        # Filter out overly generic tags
        generic_tags = {
            "1girl", "1boy", "solo", "breasts", "looking at viewer", "simple background", 
            "white background", "upper body", "portrait", "close-up", "medium shot",
            "long hair", "short hair", "brown hair", "black hair", "blonde hair",
            "blue eyes", "brown eyes", "green eyes", "smile", "open mouth"
        }
        
        # Get high-frequency, non-generic tags
        filtered_tags = []
        for tag, freq in tag_freq.items():
            if (tag.lower() not in generic_tags and 
                freq > 5 and  # Must appear in multiple training images
                len(tag) > 2 and  # Not too short
                not tag.isdigit()):  # Not just numbers
                filtered_tags.append((tag, freq))
        
        # Sort by frequency and take top triggers
        filtered_tags.sort(key=lambda x: x[1], reverse=True)
        return [tag for tag, freq in filtered_tags[:limit]]
    
    def _calculate_prompt_tag_score(self, prompt: str, tag_freq: Dict[str, int]) -> float:
        """Calculate how well a prompt matches a LoRA's tag frequency"""
        if not tag_freq:
            return 0.0
        
        prompt_words = set(prompt.lower().replace(",", " ").split())
        total_score = 0.0
        total_possible = sum(tag_freq.values())
        
        if total_possible == 0:
            return 0.0
        
        for tag, freq in tag_freq.items():
            tag_words = set(tag.lower().replace("_", " ").split())
            
            # Check for word overlap between prompt and tag
            if tag_words.intersection(prompt_words):
                # Score based on frequency (more frequent = more important to this LoRA)
                tag_weight = freq / total_possible
                total_score += tag_weight
        
        return min(total_score, 1.0)  # Cap at 1.0
    
    def _detect_content_type(self, tag_freq: Dict[str, int]) -> str:
        """Detect content type/rating based on tags"""
        if not tag_freq:
            return "unknown"
        
        # NSFW indicators (adjust threshold as needed)
        nsfw_tags = {
            "nude", "naked", "nipples", "penis", "vagina", "sex", "nsfw", 
            "explicit", "pornography", "adult", "mature", "r18"
        }
        
        # Check for explicit content
        nsfw_score = sum(freq for tag, freq in tag_freq.items() 
                        if any(nsfw_tag in tag.lower() for nsfw_tag in nsfw_tags))
        
        total_freq = sum(tag_freq.values())
        nsfw_ratio = nsfw_score / total_freq if total_freq > 0 else 0
        
        if nsfw_ratio > 0.1:  # If >10% of training data contains NSFW tags
            return "nsfw"
        elif nsfw_ratio > 0.05:  # If >5% contains suggestive content
            return "suggestive"
        else:
            return "safe"
    
    def _analyze_from_name_and_path(self, name: str, path: str) -> tuple[str, List[str], str, str]:
        """Fallback analysis based on LoRA name and path when metadata is unavailable"""
        name_lower = name.lower()
        path_lower = path.lower() if path else ""
        
        # Extract category from name/path patterns
        category = "general"
        triggers = []
        content_type = "safe"
        description = ""
        
        # Category detection from name patterns
        if any(keyword in name_lower for keyword in ["anime", "manga", "2d", "cartoon", "cel"]):
            category = "anime"
            triggers.extend(["anime style", "manga", "2d"])
        elif any(keyword in name_lower for keyword in ["real", "photo", "realistic", "portrait"]):
            category = "realistic" 
            triggers.extend(["photorealistic", "realistic", "photo"])
        elif any(keyword in name_lower for keyword in ["character", "person", "girl", "boy", "woman", "man"]):
            category = "character"
        elif any(keyword in name_lower for keyword in ["style", "art", "painting", "draw"]):
            category = "style"
        elif any(keyword in name_lower for keyword in ["pose", "outfit", "clothing", "background"]):
            category = "concept"
        
        # Extract potential trigger words from name
        # Remove version numbers and common suffixes
        clean_name = name.replace("_", " ").replace("-", " ")
        import re
        clean_name = re.sub(r'[vV]\d+', '', clean_name)  # Remove version numbers
        clean_name = re.sub(r'\d+', '', clean_name)      # Remove other numbers
        
        # Split and filter meaningful words
        name_words = [word.strip() for word in clean_name.split() if len(word.strip()) > 2]
        triggers.extend(name_words[:3])  # Take first 3 meaningful words
        
        # Content type detection (basic)
        nsfw_indicators = ["nsfw", "nude", "adult", "xxx", "porn", "sex", "breast", "hentai"]
        if any(indicator in name_lower for indicator in nsfw_indicators):
            content_type = "nsfw"
        
        # Create description
        description = f"LoRA: {name} (inferred from filename)"
        
        return category, triggers[:5], content_type, description