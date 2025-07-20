import httpx
import os
import mimetypes
import hashlib
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
import sys
import logging

# Add scripts directory to path to import dynamic_upload_manager
sys.path.append(str(Path(__file__).parent.parent.parent / "scripts" / "upload"))
try:
    from dynamic_upload_manager import DynamicUploadManager
except ImportError:
    # Fallback if dynamic_upload_manager is not available
    DynamicUploadManager = None

# Import Chevereto integration
try:
    from .chevereto_client import CheveretoClient, CheveretoConfig
    from .discord_integration import DiscordUserManager, DiscordImageHandler
except ImportError:
    CheveretoClient = None
    CheveretoConfig = None
    DiscordUserManager = None
    DiscordImageHandler = None

logger = logging.getLogger(__name__)

class ImageUploader:
    def __init__(self, upload_url: Optional[str] = None, nsfw_filter: bool = True,
                 chevereto_config: Optional[CheveretoConfig] = None, 
                 enable_discord: bool = False):
        self.upload_url = upload_url
        self.nsfw_filter = nsfw_filter
        self.enable_discord = enable_discord
        
        # Initialize dynamic upload manager (legacy)
        if upload_url and DynamicUploadManager:
            # Extract base URL from upload URL
            if "/images/upload" in upload_url:
                base_url = upload_url.replace("/images/upload", "")
                self.dynamic_manager = DynamicUploadManager(base_url=base_url)
            else:
                self.dynamic_manager = None
        else:
            self.dynamic_manager = None
        
        # Initialize Chevereto integration
        self.chevereto_client = None
        self.discord_user_manager = None
        self.discord_image_handler = None
        
        if chevereto_config and CheveretoClient:
            try:
                self.chevereto_client = CheveretoClient(chevereto_config)
                logger.info("Chevereto client initialized successfully")
                
                if enable_discord and DiscordUserManager:
                    self.discord_user_manager = DiscordUserManager(chevereto_client=self.chevereto_client)
                    self.discord_image_handler = DiscordImageHandler(
                        self.discord_user_manager, self.chevereto_client
                    )
                    logger.info("Discord integration initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Chevereto integration: {e}")
                self.chevereto_client = None
    
    async def upload_to_web_server(self, image_path: str, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Upload image to web server and return accessible URL"""
        if not self.upload_url:
            return {
                "success": False,
                "error": "No upload URL configured",
                "local_path": image_path
            }
        
        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": f"Image file not found: {image_path}"
            }
        
        try:
            # Prepare file for upload
            filename = custom_name or os.path.basename(image_path)
            mime_type, _ = mimetypes.guess_type(image_path)
            
            with open(image_path, 'rb') as f:
                files = {
                    'file': (filename, f, mime_type or 'image/png')
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(self.upload_url, files=files)
                    response.raise_for_status()
                    
                    result = response.json()
                    return {
                        "success": True,
                        "url": result.get("url"),
                        "filename": filename,
                        "local_path": image_path,
                        "upload_response": result
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "local_path": image_path
            }
    
    async def upload_with_nsfw_check(self, image_path: str, sd_client, custom_name: Optional[str] = None, nsfw_detected: bool = False) -> Dict[str, Any]:
        """Upload image with NSFW checking and return LOCAL URL"""
        
        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": f"Image file not found: {image_path}"
            }
        
        try:
            # Step 1: NudeNet NSFW detection and censoring (only if enabled and not already processed)
            if self.nsfw_filter and not nsfw_detected and sd_client:
                print(f"[Upload] NSFW filter enabled, checking image...")
                nsfw_result = await sd_client.nudenet_censor(image_path, save_original=True)
                
                if not nsfw_result["success"]:
                    # Fallback: use original image if NudeNet is unavailable
                    error_msg = nsfw_result.get('error', 'Unknown error')
                    print(f"[Upload] NudeNet check failed: {error_msg}")
                    
                    # Check for specific error types and provide helpful feedback
                    if "404" in error_msg or "not available" in error_msg:
                        print(f"[Upload] NudeNet extension not installed or enabled - using original image")
                    elif "'NoneType' object has no attribute 'startswith'" in error_msg:
                        print(f"[Upload] Detected known NudeNet extension bug - using original image")
                    elif "500" in error_msg:
                        print(f"[Upload] NudeNet server error (may need restart) - using original image")
                    else:
                        print(f"[Upload] NudeNet unavailable ({error_msg}) - using original image")
                    
                    # Create safe fallback result
                    nsfw_result = {
                        "success": True,
                        "has_nsfw": False,
                        "censored_image": "",
                        "original_image": "",
                        "detection_classes": [],
                        "confidence_scores": [],
                        "fallback_reason": error_msg
                    }
            else:
                print(f"[Upload] NSFW filter disabled, skipping check")
                nsfw_result = {
                    "success": True,
                    "has_nsfw": False,
                    "censored_image": "",
                    "original_image": "",
                    "detection_classes": [],
                    "confidence_scores": []
                }
            
            # Step 2: Decide which image to upload
            has_nsfw = nsfw_result.get("has_nsfw", False)
            
            if has_nsfw and nsfw_result.get("censored_image"):
                # Use censored version
                import base64
                censored_b64 = nsfw_result["censored_image"]
                if censored_b64.startswith("data:image/"):
                    censored_b64 = censored_b64.split(",")[1]
                upload_image_data = base64.b64decode(censored_b64)
                upload_type = "censored"
                print(f"[Upload] NSFW content detected - uploading censored version")
            else:
                # Use original image
                with open(image_path, 'rb') as f:
                    upload_image_data = f.read()
                upload_type = "original"
                print(f"[Upload] Using original image")
            
            # Step 3: Try Chevereto upload first, then fallback to local
            file_hash = self._generate_content_hash(upload_image_data)
            filename = custom_name or f"sd_{file_hash[:8]}.png"
            
            # Try Chevereto upload if available
            if self.chevereto_client:
                try:
                    # Save temporary file for Chevereto upload
                    temp_dir = Path("/tmp/temp_images")
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    temp_path = temp_dir / filename
                    
                    with open(temp_path, 'wb') as f:
                        f.write(upload_image_data)
                    
                    print(f"[Upload] Attempting Chevereto upload...")
                    chevereto_result = await self.chevereto_client.upload_image(
                        str(temp_path), 
                        title=f"AI Generated Image - {upload_type.title()}",
                        description="Generated via Stable Diffusion",
                        nsfw_detected=has_nsfw
                    )
                    
                    # Clean up temp file
                    os.remove(temp_path)
                    
                    if chevereto_result["success"]:
                        print(f"[Upload] Chevereto upload successful: {chevereto_result['url']}")
                        return {
                            "success": True,
                            "url": chevereto_result["url"],
                            "filename": chevereto_result["filename"],
                            "file_hash": file_hash,
                            "nsfw_detected": has_nsfw,
                            "upload_type": upload_type,
                            "hosting_service": "chevereto",
                            "detection_classes": nsfw_result.get("detection_classes", []),
                            "confidence_scores": nsfw_result.get("confidence_scores", []),
                            "local_path": str(temp_path)
                        }
                    else:
                        print(f"[Upload] Chevereto upload failed: {chevereto_result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"[Upload] Chevereto upload exception: {e}")
            
            # Fallback to local upload
            print(f"[Upload] Using local fallback upload...")
            upload_dir = Path("/tmp/uploaded_images")
            upload_dir.mkdir(parents=True, exist_ok=True)
            upload_path = upload_dir / filename
            
            # Save the image to web-accessible location
            with open(upload_path, 'wb') as f:
                f.write(upload_image_data)
            
            os.chmod(upload_path, 0o644)
            
            # Generate LOCAL URL (served by simple file server)
            local_url = f"http://localhost:8081/{filename}"
            
            print(f"[Upload] Image uploaded to: {upload_path}")
            print(f"[Upload] Local URL: {local_url}")
            print(f"[Upload] File size: {len(upload_image_data)} bytes")
            
            return {
                "success": True,
                "url": local_url,
                "filename": filename,
                "file_hash": file_hash,
                "nsfw_detected": has_nsfw,
                "upload_type": upload_type,
                "hosting_service": "local",
                "detection_classes": nsfw_result.get("detection_classes", []),
                "confidence_scores": nsfw_result.get("confidence_scores", []),
                "local_path": str(upload_path)
            }
        
        except Exception as e:
            print(f"[Upload] Upload failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_with_chevereto(self, image_path: str, user_id: str = None,
                                   album_id: str = None, title: str = None,
                                   description: str = None, tags: List[str] = None,
                                   nsfw_detected: bool = False) -> Dict[str, Any]:
        """Upload image using Chevereto with optional user authentication"""
        if not self.chevereto_client:
            # Fallback to local upload
            return await self.upload_with_nsfw_check(image_path, None, os.path.basename(image_path), nsfw_detected)
        
        try:
            result = await self.chevereto_client.upload_image(
                image_path, user_id, album_id, title, description, tags, nsfw_detected
            )
            
            # Add compatibility fields for existing code
            if result["success"]:
                result["filename"] = result.get("filename", os.path.basename(image_path))
                result["local_path"] = image_path
                result["upload_type"] = "chevereto"
                result["hosting_service"] = result.get("hosting_service", "chevereto")
            
            return result
            
        except Exception as e:
            logger.error(f"Chevereto upload failed: {e}")
            # Fallback to local upload
            return await self.upload_with_nsfw_check(image_path, None, os.path.basename(image_path), nsfw_detected)
    
    async def upload_from_discord(self, image_path: str, discord_id: str,
                                 folder_name: str = None, title: str = None,
                                 description: str = None, tags: List[str] = None,
                                 nsfw_detected: bool = False) -> Dict[str, Any]:
        """Upload image from Discord user with user-specific folder management"""
        if not self.discord_image_handler:
            return {"success": False, "error": "Discord integration not enabled"}
        
        try:
            result = await self.discord_image_handler.handle_discord_upload(
                discord_id, image_path, folder_name, title, description, tags, nsfw_detected
            )
            
            # Add compatibility fields
            if result["success"]:
                result["filename"] = result.get("filename", os.path.basename(image_path))
                result["local_path"] = image_path
                result["upload_type"] = "discord"
            
            return result
            
        except Exception as e:
            logger.error(f"Discord upload failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def upload_enhanced(self, image_path: str, sd_client=None, 
                             user_id: str = None, discord_id: str = None,
                             folder_name: str = None, title: str = None,
                             description: str = None, tags: List[str] = None,
                             custom_name: str = None) -> Dict[str, Any]:
        """
        Enhanced upload method that supports all hosting options
        Chooses the best available hosting service based on configuration
        """
        if not os.path.exists(image_path):
            return {"success": False, "error": "Image file not found"}
        
        # Step 1: NSFW detection (if enabled)
        nsfw_detected = False
        original_image_path = image_path
        if self.nsfw_filter and sd_client:
            print(f"[Enhanced Upload] NSFW filter enabled, checking image...")
            nsfw_result = await sd_client.nudenet_censor(image_path, save_original=True)
            if nsfw_result.get("success"):
                nsfw_detected = nsfw_result.get("has_nsfw", False)
                print(f"[Enhanced Upload] NudeNet result: NSFW detected = {nsfw_detected}")
                
                # Use censored version if NSFW detected
                if nsfw_detected and nsfw_result.get("censored_image"):
                    # Save censored version temporarily
                    import base64
                    import tempfile
                    censored_b64 = nsfw_result["censored_image"]
                    if censored_b64.startswith("data:image/"):
                        censored_b64 = censored_b64.split(",")[1]
                    
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                        temp_file.write(base64.b64decode(censored_b64))
                        image_path = temp_file.name
                        print(f"[Enhanced Upload] Using censored version: {image_path}")
            else:
                # Handle NudeNet failure gracefully
                error_msg = nsfw_result.get('error', 'Unknown error')
                print(f"[Enhanced Upload] NudeNet check failed: {error_msg}")
                if "404" in error_msg or "not available" in error_msg:
                    print(f"[Enhanced Upload] NudeNet extension not installed - using original image")
                else:
                    print(f"[Enhanced Upload] NudeNet unavailable - using original image")
        else:
            print(f"[Enhanced Upload] NSFW filter disabled, skipping check")
        
        # Step 2: Choose hosting service based on priority
        
        # Priority 1: Discord integration (if discord_id provided)
        if discord_id and self.discord_image_handler:
            result = await self.upload_from_discord(
                image_path, discord_id, folder_name, title, description, tags, nsfw_detected
            )
            if result["success"]:
                return result
        
        # Priority 2: Chevereto with user authentication
        if self.chevereto_client:
            result = await self.upload_with_chevereto(
                image_path, user_id, None, title, description, tags, nsfw_detected
            )
            if result["success"]:
                return result
        
        # Priority 3: Legacy local upload - pass nsfw_detected to avoid double processing
        return await self.upload_with_nsfw_check(image_path, sd_client, custom_name, nsfw_detected)
    
    def register_discord_user(self, discord_id: str, username: str, 
                             discriminator: str = None, chevereto_api_key: str = None) -> Dict[str, Any]:
        """Register Discord user for image hosting"""
        if not self.discord_user_manager:
            return {"success": False, "error": "Discord integration not enabled"}
        
        return self.discord_user_manager.register_discord_user(
            discord_id, username, discriminator, chevereto_api_key=chevereto_api_key
        )
    
    def get_discord_user_info(self, discord_id: str) -> Optional[Dict[str, Any]]:
        """Get Discord user information"""
        if not self.discord_user_manager:
            return None
        
        return self.discord_user_manager.get_discord_user(discord_id)
    
    def create_discord_user_folder(self, discord_id: str, folder_name: str, 
                                  description: str = "") -> Optional[str]:
        """Create folder for Discord user"""
        if not self.discord_user_manager:
            return None
        
        return self.discord_user_manager.create_user_folder(discord_id, folder_name, description)
    
    def get_discord_user_folders(self, discord_id: str) -> List[Dict[str, Any]]:
        """Get Discord user's folders"""
        if not self.discord_user_manager:
            return []
        
        return self.discord_user_manager.get_user_folders(discord_id)
    
    def get_discord_user_stats(self, discord_id: str) -> Dict[str, Any]:
        """Get Discord user statistics"""
        if not self.discord_user_manager:
            return {}
        
        return self.discord_user_manager.get_user_stats(discord_id)
    
    async def test_hosting_services(self) -> Dict[str, Any]:
        """Test all available hosting services"""
        results = {
            "local": {"available": True, "message": "Local storage always available"},
            "chevereto": {"available": False, "message": "Not configured"},
            "discord": {"available": False, "message": "Not configured"}
        }
        
        # Test Chevereto
        if self.chevereto_client:
            chevereto_test = await self.chevereto_client.test_connection()
            results["chevereto"] = {
                "available": chevereto_test["success"],
                "message": chevereto_test.get("message") or chevereto_test.get("error", "Unknown")
            }
        
        # Test Discord integration
        if self.discord_user_manager:
            results["discord"] = {
                "available": True,
                "message": "Discord integration enabled"
            }
        
        return results
    
    def _generate_content_hash(self, content: bytes) -> str:
        """Generate MD5 hash of content for unique naming"""
        return hashlib.md5(content).hexdigest()
    
    def create_shareable_link(self, image_path: str, base_url: str) -> str:
        """Create a shareable link for locally stored image"""
        filename = os.path.basename(image_path)
        return f"{base_url.rstrip('/')}/images/{filename}"
    
    def organize_output_images(self, images: list, output_dir: str, 
                              organize_by: str = "date") -> Dict[str, list]:
        """Organize generated images into subdirectories"""
        organized = {}
        
        for image_info in images:
            image_path = image_info.get("path", "")
            if not os.path.exists(image_path):
                continue
            
            # Determine organization folder
            if organize_by == "date":
                from datetime import datetime
                folder_name = datetime.now().strftime("%Y-%m-%d")
            elif organize_by == "prompt":
                # Use first 50 chars of prompt, sanitized
                prompt = image_info.get("parameters", {}).get("prompt", "unknown")
                folder_name = "".join(c for c in prompt[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
                if not folder_name:
                    folder_name = "unknown"
            else:
                folder_name = organize_by
            
            # Create target directory
            target_dir = os.path.join(output_dir, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            
            # Move file
            filename = os.path.basename(image_path)
            new_path = os.path.join(target_dir, filename)
            
            try:
                os.rename(image_path, new_path)
                image_info["path"] = new_path
                
                if folder_name not in organized:
                    organized[folder_name] = []
                organized[folder_name].append(image_info)
                
            except Exception as e:
                print(f"Failed to move {image_path} to {new_path}: {e}")
        
        return organized
    
    def cleanup_old_images(self, directory: str, days_old: int = 7) -> int:
        """Clean up images older than specified days"""
        if not os.path.exists(directory):
            return 0
        
        import time
        cutoff_time = time.time() - (days_old * 24 * 3600)
        cleaned_count = 0
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    file_path = os.path.join(root, file)
                    if os.path.getmtime(file_path) < cutoff_time:
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                        except Exception as e:
                            print(f"Failed to remove {file_path}: {e}")
        
        return cleaned_count
    
    def get_image_info(self, image_path: str) -> Dict[str, Any]:
        """Get detailed information about an image file"""
        if not os.path.exists(image_path):
            return {"error": "File not found"}
        
        try:
            from PIL import Image
            
            with Image.open(image_path) as img:
                stat = os.stat(image_path)
                
                return {
                    "filename": os.path.basename(image_path),
                    "path": image_path,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "dimensions": img.size,
                    "mode": img.mode,
                    "format": img.format,
                    "created": stat.st_ctime,
                    "modified": stat.st_mtime
                }
        
        except Exception as e:
            return {
                "filename": os.path.basename(image_path),
                "path": image_path,
                "error": str(e)
            }