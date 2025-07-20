#!/usr/bin/env python3
"""
Configuration for Chevereto Image Hosting Integration
"""

import os
from typing import Optional
from modules.stable_diffusion.chevereto_client import CheveretoConfig
from modules.stable_diffusion.uploader import ImageUploader

def create_chevereto_config(env_dict: dict = None) -> CheveretoConfig:
    """Create Chevereto configuration from MCP environment dictionary or OS env"""
    if env_dict:
        return CheveretoConfig.from_env_dict(env_dict)
    
    # Fallback to OS environment (for testing)
    return CheveretoConfig(
        base_url=os.getenv("CHEVERETO_BASE_URL"),
        user_api_key=os.getenv("CHEVERETO_USER_API_KEY"),
        admin_api_key=os.getenv("CHEVERETO_ADMIN_API_KEY"),
        timeout=int(os.getenv("CHEVERETO_TIMEOUT", "30")),
        max_file_size=int(os.getenv("CHEVERETO_MAX_FILE_SIZE", str(50 * 1024 * 1024))),
        fallback_to_local=os.getenv("CHEVERETO_FALLBACK_TO_LOCAL", "true").lower() == "true"
    )

def create_enhanced_uploader(env_dict: dict = None) -> ImageUploader:
    """Create enhanced image uploader with Chevereto and Discord support"""
    chevereto_config = create_chevereto_config(env_dict)
    
    # Use MCP env dict or fallback to OS env
    if env_dict:
        upload_url = env_dict.get("UPLOAD_URL")  # Keep existing UPLOAD_URL
        nsfw_filter = env_dict.get("NSFW_FILTER", "true").lower() == "true"
        enable_discord = env_dict.get("ENABLE_DISCORD", "false").lower() == "true"
    else:
        upload_url = os.getenv("LEGACY_UPLOAD_URL")
        nsfw_filter = os.getenv("NSFW_FILTER", "true").lower() == "true"
        enable_discord = os.getenv("ENABLE_DISCORD", "true").lower() == "true"
    
    return ImageUploader(
        upload_url=upload_url,
        nsfw_filter=nsfw_filter,
        chevereto_config=chevereto_config,
        enable_discord=enable_discord
    )

# Example environment variables for .env file
EXAMPLE_ENV_CONFIG = """
# Chevereto Configuration
CHEVERETO_BASE_URL=https://your-chevereto-domain.com
CHEVERETO_ADMIN_API_KEY=your_admin_api_key_here
CHEVERETO_GUEST_API_KEY=your_guest_api_key_here
CHEVERETO_TIMEOUT=30
CHEVERETO_MAX_FILE_SIZE=52428800
CHEVERETO_FALLBACK_TO_LOCAL=true

# Discord Integration
ENABLE_DISCORD=true

# Legacy Support
LEGACY_UPLOAD_URL=https://your-legacy-upload-service.com/upload
NSFW_FILTER=true
"""

# Example usage patterns
USAGE_EXAMPLES = """
# Basic usage with Chevereto
uploader = create_enhanced_uploader()
result = await uploader.upload_enhanced("image.png")

# Discord user upload with folder
result = await uploader.upload_enhanced(
    "image.png", 
    discord_id="123456789",
    folder_name="Stable Diffusion",
    title="My Generated Image",
    description="Generated with SD WebUI"
)

# Register Discord user
uploader.register_discord_user(
    discord_id="123456789",
    username="testuser",
    chevereto_api_key="user_api_key_here"
)

# Create user folder
folder_id = uploader.create_discord_user_folder(
    discord_id="123456789",
    folder_name="AI Art",
    description="My AI generated artwork"
)

# Get user stats
stats = uploader.get_discord_user_stats("123456789")
"""

if __name__ == "__main__":
    print("Chevereto Configuration Example")
    print("=" * 40)
    print("\nEnvironment Variables:")
    print(EXAMPLE_ENV_CONFIG)
    print("\nUsage Examples:")
    print(USAGE_EXAMPLES)