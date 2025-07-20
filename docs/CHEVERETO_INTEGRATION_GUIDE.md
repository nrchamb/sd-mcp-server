# Chevereto Integration Guide

## Overview

The Chevereto integration provides a comprehensive image hosting solution with Discord user support, user-specific folders, and seamless fallback to local storage. This system extends the existing MCP image upload functionality to support public URLs through Chevereto image hosting.

## Features

### ✅ Completed Features

1. **Chevereto API Integration**
   - User-based API key authentication
   - Album/folder management
   - Public URL generation
   - Error handling and fallback

2. **Discord User Management**
   - User registration and authentication
   - User-specific folders/albums
   - Session management
   - Upload history tracking

3. **Enhanced Upload System**
   - Multi-service support (Chevereto → Local fallback)
   - NSFW detection and filtering
   - Automatic service selection
   - Backward compatibility

4. **User Folder System**
   - Create custom folders for each Discord user
   - Default folder assignment
   - Album management through Chevereto
   - Local folder organization

## Architecture

```
Enhanced Image Upload System
├── Chevereto Client (Primary)
│   ├── User API Key Management
│   ├── Album Creation & Management
│   ├── Public URL Generation
│   └── Error Handling
├── Discord Integration (User Layer)
│   ├── User Registration
│   ├── Folder Management
│   ├── Session Handling
│   └── Statistics Tracking
└── Local Storage (Fallback)
    ├── User-specific directories
    ├── Local file serving
    └── Compatibility with existing system
```

## Configuration

### Environment Variables

```bash
# Chevereto Configuration
CHEVERETO_BASE_URL=https://your-chevereto-domain.com
CHEVERETO_ADMIN_API_KEY=your_admin_api_key
CHEVERETO_GUEST_API_KEY=your_guest_api_key
CHEVERETO_TIMEOUT=30
CHEVERETO_MAX_FILE_SIZE=52428800
CHEVERETO_FALLBACK_TO_LOCAL=true

# Discord Integration
ENABLE_DISCORD=true

# Legacy Support
LEGACY_UPLOAD_URL=https://your-legacy-service.com/upload
NSFW_FILTER=true
```

### Quick Setup

1. **Install Chevereto** on your server
2. **Get API Keys** from Chevereto admin panel
3. **Configure environment variables**
4. **Initialize the system**:

```python
from config.chevereto_config import create_enhanced_uploader

uploader = create_enhanced_uploader()
```

## Usage Examples

### Basic Upload with Public URL

```python
import asyncio
from config.chevereto_config import create_enhanced_uploader

async def basic_upload():
    uploader = create_enhanced_uploader()
    
    result = await uploader.upload_enhanced("my_image.png")
    
    if result["success"]:
        print(f"Public URL: {result['url']}")
        print(f"Service: {result['hosting_service']}")
```

### Discord User Upload with Folders

```python
async def discord_upload():
    uploader = create_enhanced_uploader()
    
    # Register Discord user
    uploader.register_discord_user(
        discord_id="123456789",
        username="myusername",
        chevereto_api_key="user_api_key_here"
    )
    
    # Create user folder
    uploader.create_discord_user_folder(
        discord_id="123456789",
        folder_name="AI Art",
        description="My AI generated artwork"
    )
    
    # Upload to user's folder
    result = await uploader.upload_enhanced(
        image_path="generated_image.png",
        discord_id="123456789",
        folder_name="AI Art",
        title="My Generated Image",
        description="Created with Stable Diffusion",
        tags=["ai", "art", "stable-diffusion"]
    )
    
    if result["success"]:
        print(f"Public URL: {result['url']}")
        print(f"User: {result['discord_user']['username']}")
        print(f"Folder: {result['discord_user']['folder']}")
```

### User Management

```python
# Get user info
user_info = uploader.get_discord_user_info("123456789")
print(f"User: {user_info['username']}")
print(f"Folders: {len(user_info['folders'])}")

# Get user statistics
stats = uploader.get_discord_user_stats("123456789")
print(f"Total uploads: {stats['total_uploads']}")
print(f"Storage used: {stats['total_storage_bytes']} bytes")

# Get user folders
folders = uploader.get_discord_user_folders("123456789")
for folder in folders:
    print(f"Folder: {folder['folder_name']} ({folder['description']})")
```

## Integration with Existing SD MCP

### Update SD MCP Server

```python
# In your SD MCP server file
from modules.stable_diffusion.uploader import ImageUploader
from modules.stable_diffusion.chevereto_client import CheveretoConfig

# Initialize enhanced uploader
chevereto_config = CheveretoConfig(
    base_url=os.getenv("CHEVERETO_BASE_URL"),
    guest_api_key=os.getenv("CHEVERETO_GUEST_API_KEY"),
    fallback_to_local=True
)

uploader = ImageUploader(
    chevereto_config=chevereto_config,
    enable_discord=True,
    nsfw_filter=True
)

# Use in your MCP tools
@server.tool()
async def upload_to_web_server_enhanced(image_path: str, discord_id: str = None, 
                                       folder_name: str = None, title: str = None) -> str:
    """Enhanced upload with Discord support and public URLs"""
    
    result = await uploader.upload_enhanced(
        image_path=image_path,
        discord_id=discord_id,
        folder_name=folder_name,
        title=title
    )
    
    return json.dumps(result, indent=2)
```

### New MCP Tools

```python
@server.tool()
async def register_discord_user(discord_id: str, username: str, 
                               chevereto_api_key: str = None) -> str:
    """Register Discord user for image hosting"""
    result = uploader.register_discord_user(discord_id, username, chevereto_api_key)
    return json.dumps(result)

@server.tool()
async def create_user_folder(discord_id: str, folder_name: str, 
                           description: str = "") -> str:
    """Create folder for Discord user"""
    folder_id = uploader.create_discord_user_folder(discord_id, folder_name, description)
    return json.dumps({"folder_id": folder_id, "success": folder_id is not None})

@server.tool()
async def get_user_folders(discord_id: str) -> str:
    """Get user's folders"""
    folders = uploader.get_discord_user_folders(discord_id)
    return json.dumps(folders, indent=2)

@server.tool()
async def test_hosting_services() -> str:
    """Test all hosting services"""
    results = await uploader.test_hosting_services()
    return json.dumps(results, indent=2)
```

## Service Priority

The system automatically selects the best available hosting service:

1. **Discord Integration** (if discord_id provided)
   - Uses user's Chevereto API key
   - Uploads to user's specified folder
   - Generates public Chevereto URL

2. **Chevereto Direct** (if user_id provided)
   - Uses user's API key from database
   - Uploads to user's default album
   - Generates public Chevereto URL

3. **Guest Chevereto** (if guest API key configured)
   - Uses guest API key
   - Uploads to public gallery
   - Generates public Chevereto URL

4. **Local Storage** (fallback)
   - Saves to user-specific local directory
   - Serves via local file server
   - Returns localhost URL

## Database Schema

### Discord Users
```sql
CREATE TABLE discord_users (
    discord_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    chevereto_api_key TEXT,
    default_album_id TEXT,
    preferences TEXT,
    created_at TIMESTAMP,
    last_active TIMESTAMP
);
```

### User Folders
```sql
CREATE TABLE user_folders (
    folder_id TEXT PRIMARY KEY,
    discord_id TEXT NOT NULL,
    folder_name TEXT NOT NULL,
    chevereto_album_id TEXT,
    description TEXT,
    is_default BOOLEAN DEFAULT 0,
    created_at TIMESTAMP
);
```

### Upload History
```sql
CREATE TABLE uploads (
    upload_id TEXT PRIMARY KEY,
    user_id TEXT,
    filename TEXT NOT NULL,
    chevereto_url TEXT NOT NULL,
    local_path TEXT,
    album_id TEXT,
    upload_timestamp TIMESTAMP,
    file_size INTEGER,
    nsfw_detected BOOLEAN DEFAULT 0
);
```

## Testing

Run the comprehensive test suite:

```bash
# Set environment variables
export CHEVERETO_BASE_URL="https://your-chevereto.com"
export CHEVERETO_GUEST_API_KEY="your_guest_key"

# Run tests
python test_chevereto_integration.py
```

The test suite covers:
- Chevereto API connectivity
- User registration and management
- Folder creation and management
- Image upload workflows
- Discord integration
- Service fallback behavior

## Troubleshooting

### Common Issues

1. **Chevereto Connection Failed**
   - Check CHEVERETO_BASE_URL is accessible
   - Verify API key is valid
   - Ensure Chevereto API is enabled

2. **Upload Fails with 403**
   - Check API key permissions
   - Verify album_id belongs to user
   - Ensure file size is within limits

3. **Local Fallback Always Used**
   - Check Chevereto configuration
   - Verify network connectivity
   - Check API key validity

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

1. **API Key Storage**
   - Store user API keys securely
   - Consider encryption for sensitive data
   - Implement key rotation

2. **File Upload Security**
   - Validate file types
   - Implement size limits
   - Enable NSFW filtering

3. **User Authentication**
   - Implement proper Discord OAuth
   - Use session management
   - Add rate limiting

## Future Enhancements

1. **Multi-tenancy Support**
   - Multiple Chevereto instances
   - Load balancing
   - Regional hosting

2. **Advanced Features**
   - Batch uploads
   - Image optimization
   - CDN integration

3. **Analytics & Monitoring**
   - Upload statistics
   - Performance metrics
   - Usage tracking

## Support

For issues and feature requests:
1. Check the test suite output
2. Review logs for error details
3. Verify configuration settings
4. Test individual components

---

**Version**: 1.0  
**Last Updated**: 2025-07-16  
**Compatibility**: Chevereto V4+, Discord API, MCP Protocol