#!/usr/bin/env python3
"""
Discord Integration for Chevereto Image Hosting
Handles Discord user authentication and user-specific folder management
"""

import os
import hashlib
import json
import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .chevereto_client import CheveretoClient, CheveretoConfig

logger = logging.getLogger(__name__)

class DiscordUserManager:
    """
    Manages Discord user authentication and Chevereto integration
    """
    
    def __init__(self, db_path: str = "discord_users.db", chevereto_client: CheveretoClient = None):
        self.db_path = db_path
        self.chevereto_client = chevereto_client
        self._init_database()
    
    def _init_database(self):
        """Initialize Discord user database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discord_users (
                discord_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                discriminator TEXT,
                avatar_url TEXT,
                chevereto_api_key TEXT,
                chevereto_username TEXT,
                default_album_id TEXT,
                preferences TEXT,  -- JSON string
                created_at TIMESTAMP,
                last_active TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                discord_id TEXT NOT NULL,
                created_at TIMESTAMP,
                expires_at TIMESTAMP,
                last_used TIMESTAMP,
                FOREIGN KEY (discord_id) REFERENCES discord_users (discord_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_folders (
                folder_id TEXT PRIMARY KEY,
                discord_id TEXT NOT NULL,
                folder_name TEXT NOT NULL,
                chevereto_album_id TEXT,
                description TEXT,
                is_default BOOLEAN DEFAULT 0,
                created_at TIMESTAMP,
                FOREIGN KEY (discord_id) REFERENCES discord_users (discord_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def register_discord_user(self, discord_id: str, username: str, 
                            discriminator: str = None, avatar_url: str = None,
                            chevereto_api_key: str = None) -> Dict[str, Any]:
        """Register new Discord user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now()
            preferences = json.dumps({
                "nsfw_filter": True,
                "auto_album": True,
                "notification_dm": True,
                "default_privacy": "public"
            })
            
            cursor.execute('''
                INSERT OR REPLACE INTO discord_users 
                (discord_id, username, discriminator, avatar_url, chevereto_api_key, 
                 preferences, created_at, last_active, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (discord_id, username, discriminator, avatar_url, chevereto_api_key,
                  preferences, now, now, True))
            
            conn.commit()
            conn.close()
            
            # Register with Chevereto client if API key provided
            if chevereto_api_key and self.chevereto_client:
                self.chevereto_client.add_user(discord_id, chevereto_api_key, username)
            
            # Create default folder
            self.create_user_folder(discord_id, "My Images", "Default folder for images", is_default=True)
            
            logger.info(f"Registered Discord user {username} ({discord_id})")
            return {"success": True, "message": f"User {username} registered successfully"}
            
        except Exception as e:
            logger.error(f"Failed to register Discord user {discord_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_discord_user(self, discord_id: str) -> Optional[Dict[str, Any]]:
        """Get Discord user information"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT discord_id, username, discriminator, avatar_url, chevereto_api_key,
                       chevereto_username, default_album_id, preferences, created_at, 
                       last_active, is_active
                FROM discord_users WHERE discord_id = ?
            ''', (discord_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "discord_id": row[0],
                    "username": row[1],
                    "discriminator": row[2],
                    "avatar_url": row[3],
                    "chevereto_api_key": row[4],
                    "chevereto_username": row[5],
                    "default_album_id": row[6],
                    "preferences": json.loads(row[7]) if row[7] else {},
                    "created_at": row[8],
                    "last_active": row[9],
                    "is_active": bool(row[10])
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Discord user {discord_id}: {e}")
            return None
    
    def update_chevereto_api_key(self, discord_id: str, api_key: str) -> bool:
        """Update user's Chevereto API key"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE discord_users 
                SET chevereto_api_key = ?, last_active = ?
                WHERE discord_id = ?
            ''', (api_key, datetime.now(), discord_id))
            
            conn.commit()
            conn.close()
            
            # Update in Chevereto client
            if self.chevereto_client:
                user = self.get_discord_user(discord_id)
                if user:
                    self.chevereto_client.add_user(discord_id, api_key, user["username"])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update API key for {discord_id}: {e}")
            return False
    
    def create_user_folder(self, discord_id: str, folder_name: str, 
                          description: str = "", is_default: bool = False) -> Optional[str]:
        """Create user folder/album"""
        try:
            # Generate folder ID
            folder_id = hashlib.md5(f"{discord_id}_{folder_name}_{datetime.now()}".encode()).hexdigest()[:12]
            
            # Create album in Chevereto if user has API key
            chevereto_album_id = None
            if self.chevereto_client:
                user = self.get_discord_user(discord_id)
                if user and user.get("chevereto_api_key"):
                    import asyncio
                    chevereto_album_id = asyncio.run(
                        self.chevereto_client.create_album(discord_id, folder_name, description)
                    )
            
            # Store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # If this is default, unset other defaults
            if is_default:
                cursor.execute('''
                    UPDATE user_folders SET is_default = 0 WHERE discord_id = ?
                ''', (discord_id,))
            
            cursor.execute('''
                INSERT INTO user_folders 
                (folder_id, discord_id, folder_name, chevereto_album_id, description, 
                 is_default, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (folder_id, discord_id, folder_name, chevereto_album_id, description,
                  is_default, datetime.now()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created folder {folder_name} for user {discord_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"Failed to create folder for {discord_id}: {e}")
            return None
    
    def get_user_folders(self, discord_id: str) -> List[Dict[str, Any]]:
        """Get user's folders"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT folder_id, folder_name, chevereto_album_id, description, 
                       is_default, created_at
                FROM user_folders WHERE discord_id = ?
                ORDER BY is_default DESC, created_at DESC
            ''', (discord_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "folder_id": row[0],
                    "folder_name": row[1],
                    "chevereto_album_id": row[2],
                    "description": row[3],
                    "is_default": bool(row[4]),
                    "created_at": row[5]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to get folders for {discord_id}: {e}")
            return []
    
    def get_default_folder(self, discord_id: str) -> Optional[Dict[str, Any]]:
        """Get user's default folder"""
        folders = self.get_user_folders(discord_id)
        for folder in folders:
            if folder["is_default"]:
                return folder
        return folders[0] if folders else None
    
    def create_session(self, discord_id: str, duration_hours: int = 24) -> Optional[str]:
        """Create user session"""
        try:
            session_id = hashlib.md5(f"{discord_id}_{datetime.now()}".encode()).hexdigest()
            now = datetime.now()
            expires_at = now + timedelta(hours=duration_hours)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_sessions 
                (session_id, discord_id, created_at, expires_at, last_used)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, discord_id, now, expires_at, now))
            
            conn.commit()
            conn.close()
            
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session for {discord_id}: {e}")
            return None
    
    def validate_session(self, session_id: str) -> Optional[str]:
        """Validate session and return Discord ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT discord_id, expires_at FROM user_sessions 
                WHERE session_id = ?
            ''', (session_id,))
            
            row = cursor.fetchone()
            if row:
                discord_id, expires_at = row
                if datetime.fromisoformat(expires_at) > datetime.now():
                    # Update last used
                    cursor.execute('''
                        UPDATE user_sessions SET last_used = ? WHERE session_id = ?
                    ''', (datetime.now(), session_id))
                    conn.commit()
                    conn.close()
                    return discord_id
                else:
                    # Session expired
                    cursor.execute('DELETE FROM user_sessions WHERE session_id = ?', (session_id,))
                    conn.commit()
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Failed to validate session {session_id}: {e}")
            return None
    
    def update_user_preferences(self, discord_id: str, preferences: Dict[str, Any]) -> bool:
        """Update user preferences"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE discord_users 
                SET preferences = ?, last_active = ?
                WHERE discord_id = ?
            ''', (json.dumps(preferences), datetime.now(), discord_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update preferences for {discord_id}: {e}")
            return False
    
    def get_user_stats(self, discord_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            stats = {
                "total_uploads": 0,
                "total_folders": 0,
                "total_storage_bytes": 0,
                "last_upload": None,
                "nsfw_uploads": 0
            }
            
            # Get folder count
            folders = self.get_user_folders(discord_id)
            stats["total_folders"] = len(folders)
            
            # Get upload stats from Chevereto client
            if self.chevereto_client:
                uploads = self.chevereto_client.get_user_uploads(discord_id)
                stats["total_uploads"] = len(uploads)
                
                if uploads:
                    stats["last_upload"] = uploads[0]["upload_timestamp"]
                    stats["total_storage_bytes"] = sum(u["file_size"] for u in uploads)
                    stats["nsfw_uploads"] = sum(1 for u in uploads if u["nsfw_detected"])
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats for {discord_id}: {e}")
            return {}
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM user_sessions WHERE expires_at < ?
            ''', (datetime.now(),))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted} expired sessions")
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0

class DiscordImageHandler:
    """
    Handles Discord-specific image operations
    """
    
    def __init__(self, user_manager: DiscordUserManager, chevereto_client: CheveretoClient):
        self.user_manager = user_manager
        self.chevereto_client = chevereto_client
    
    async def handle_discord_upload(self, discord_id: str, image_path: str, 
                                   folder_name: str = None, title: str = None,
                                   description: str = None, tags: List[str] = None,
                                   nsfw_detected: bool = False) -> Dict[str, Any]:
        """Handle image upload from Discord user"""
        
        # Get user
        user = self.user_manager.get_discord_user(discord_id)
        if not user:
            return {"success": False, "error": "User not registered"}
        
        # Get folder/album
        album_id = None
        if folder_name:
            folders = self.user_manager.get_user_folders(discord_id)
            folder = next((f for f in folders if f["folder_name"] == folder_name), None)
            if folder:
                album_id = folder["chevereto_album_id"]
        else:
            # Use default folder
            default_folder = self.user_manager.get_default_folder(discord_id)
            if default_folder:
                album_id = default_folder["chevereto_album_id"]
        
        # Upload image
        result = await self.chevereto_client.upload_image(
            image_path, discord_id, album_id, title, description, tags, nsfw_detected
        )
        
        if result["success"]:
            # Update user activity
            self.user_manager.get_discord_user(discord_id)  # This updates last_active
            
            # Add Discord-specific info
            result["discord_user"] = {
                "id": discord_id,
                "username": user["username"],
                "folder": folder_name or "Default"
            }
        
        return result
    
    def generate_share_embed(self, upload_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Discord embed for image share"""
        if not upload_result["success"]:
            return {
                "title": "Upload Failed",
                "description": upload_result.get("error", "Unknown error"),
                "color": 0xff0000
            }
        
        user_info = upload_result.get("discord_user", {})
        
        embed = {
            "title": "Image Uploaded Successfully",
            "description": f"Uploaded by {user_info.get('username', 'Unknown')}",
            "color": 0x00ff00,
            "image": {"url": upload_result["url"]},
            "fields": [
                {"name": "Filename", "value": upload_result["filename"], "inline": True},
                {"name": "Folder", "value": user_info.get("folder", "Default"), "inline": True},
                {"name": "Service", "value": upload_result["hosting_service"].title(), "inline": True}
            ],
            "footer": {"text": f"Upload ID: {upload_result.get('upload_id', 'N/A')}"},
            "timestamp": datetime.now().isoformat()
        }
        
        if upload_result.get("nsfw_detected"):
            embed["fields"].append({"name": "⚠️ NSFW", "value": "Content filtered", "inline": True})
        
        return embed

# Factory function
def create_discord_integration(chevereto_config: CheveretoConfig) -> tuple[DiscordUserManager, DiscordImageHandler]:
    """Create Discord integration components"""
    chevereto_client = CheveretoClient(chevereto_config)
    user_manager = DiscordUserManager(chevereto_client=chevereto_client)
    image_handler = DiscordImageHandler(user_manager, chevereto_client)
    
    return user_manager, image_handler