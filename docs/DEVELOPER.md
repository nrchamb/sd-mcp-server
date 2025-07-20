# Developer Guide 🛠️

## Adding New Features

### Adding New LLM Providers

**1. Create Provider Class**
```python
# modules/llm/your_provider.py
from .base_provider import BaseLLMProvider

class YourLLMProvider(BaseLLMProvider):
    def __init__(self, config: dict):
        self.api_key = config.get("YOUR_API_KEY")
        self.base_url = config.get("YOUR_BASE_URL")
    
    async def chat(self, messages: list, **kwargs) -> str:
        # Implement your API call
        response = await your_api_call(messages)
        return response.content
    
    async def stream_chat(self, messages: list, **kwargs):
        # Optional: implement streaming
        for chunk in your_streaming_api(messages):
            yield chunk
```

**2. Register Provider**
```python
# modules/llm/llm_manager.py
from .your_provider import YourLLMProvider

class LLMManager:
    def __init__(self, config: dict):
        self.providers = {
            "lmstudio": LMStudioProvider,
            "openai": OpenAIProvider,
            "claude": ClaudeProvider,
            "gemini": GeminiProvider,
            "your_provider": YourLLMProvider,  # Add here
        }
```

**3. Add Environment Variables**
```bash
# In your MCP configuration
YOUR_PROVIDER_API_KEY=your_api_key
YOUR_PROVIDER_BASE_URL=https://api.yourprovider.com
LLM_PROVIDER=your_provider  # Set as default
```

### Adding New Discord Commands

**1. Basic Command**
```python
# discord_bot.py
@bot.tree.command(name="your-command", description="Your command description")
@app_commands.describe(param="Parameter description")
async def your_command(interaction: discord.Interaction, param: str):
    await interaction.response.defer()
    
    # Your logic here
    result = do_something(param)
    
    await interaction.followup.send(f"Result: {result}")
```

**2. Admin Command**
```python
@bot.tree.command(name="admin-command", description="Admin only command")
async def admin_command(interaction: discord.Interaction, target: discord.Member):
    # Check admin permissions
    if not bot.conversation_manager.is_admin(str(interaction.user.id)):
        await interaction.response.send_message("❌ Admin only", ephemeral=True)
        return
    
    await interaction.response.defer()
    # Admin logic here
```

**3. Command with LLM Integration**
```python
@bot.tree.command(name="ai-command", description="Command using AI")
async def ai_command(interaction: discord.Interaction, prompt: str):
    if not bot.conversation_manager:
        await interaction.response.send_message("❌ LLM unavailable", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # Get user's personality
    user_id = str(interaction.user.id)
    personality = await bot.conversation_manager.get_user_personality(user_id)
    
    # Generate response
    response = await bot.conversation_manager.generate_response(prompt, personality)
    
    await interaction.followup.send(response)
```

### Adding New MCP Tools

**1. Define Tool Function**
```python
# scripts/mcp_servers/sd_mcp_server.py
@server.call_tool()
async def your_new_tool(
    param1: str,
    param2: int = 10,
    optional_param: Optional[str] = None
) -> str:
    """
    Your tool description
    
    Args:
        param1: Required parameter description
        param2: Optional parameter with default
        optional_param: Optional parameter
    
    Returns:
        Result description
    """
    try:
        # Your tool logic
        result = perform_operation(param1, param2)
        
        return json.dumps({
            "success": True,
            "result": result,
            "param1": param1,
            "param2": param2
        })
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "suggestion": "Check your parameters"
        })
```

**2. Tool with Database Access**
```python
@server.call_tool()
async def database_tool(query: str) -> str:
    """Tool that accesses database"""
    try:
        # Import database module
        from modules.stable_diffusion.content_db import ContentDatabase
        
        db = ContentDatabase()
        results = db.search_content(query)
        
        return json.dumps({
            "success": True,
            "results": results,
            "count": len(results)
        })
    
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
```

### Adding New Personalities

**1. Database Method**
```sql
INSERT INTO personalities (
    name, 
    display_name, 
    system_prompt, 
    image_injection_prompt, 
    description, 
    emoji, 
    category
) VALUES (
    'your_personality',
    'Your Personality Name',
    'You are a helpful assistant with specific traits...',
    'Add specific image generation enhancements...',
    'Description for users',
    '🤖',
    'chat'
);
```

**2. Code Method**
```python
# modules/llm/llm_database.py - in load_default_personalities()
personalities = [
    # ... existing personalities ...
    {
        "name": "your_personality",
        "display_name": "Your Personality",
        "system_prompt": "You are a helpful assistant with...",
        "image_injection_prompt": "Add enhancement: artistic, creative...",
        "description": "Your personality description",
        "emoji": "🤖",
        "category": "chat"
    }
]
```

**3. Personality Guidelines**
- **system_prompt**: Define personality traits, response style, limitations
- **image_injection_prompt**: Enhance image generation with personality-specific terms
- **name**: Use lowercase, underscores (internal identifier)
- **display_name**: User-facing name for Discord
- **emoji**: Single emoji for Discord interface

### Adding New Content Categories

**1. Database Structure**
```sql
-- Add new category
INSERT INTO content_categories (category_path, description, parent_id)
VALUES ('subject/vehicle', 'Vehicle types', 
        (SELECT id FROM content_categories WHERE category_path = 'subject'));

-- Add words to category
INSERT INTO content_words (word, category_id, confidence)
VALUES ('car', (SELECT id FROM content_categories WHERE category_path = 'subject/vehicle'), 1.0),
       ('truck', (SELECT id FROM content_categories WHERE category_path = 'subject/vehicle'), 1.0);
```

**2. Code Method**
```python
# modules/stable_diffusion/content_db.py
def add_vehicle_categories(self):
    categories = [
        ("subject/vehicle", "Vehicle types"),
        ("subject/vehicle/car", "Cars and automobiles"),
        ("subject/vehicle/truck", "Trucks and lorries"),
    ]
    
    words = [
        ("car", "subject/vehicle/car", 1.0),
        ("automobile", "subject/vehicle/car", 0.9),
        ("truck", "subject/vehicle/truck", 1.0),
        ("lorry", "subject/vehicle/truck", 0.8),
    ]
```

## Code Structure

### Module Organization

**`modules/llm/`** - LLM Provider System
- One file per provider
- Common base class with standard interface
- Manager handles provider selection and routing

**`modules/stable_diffusion/`** - SD Integration
- Separate concerns: generation, upload, content analysis
- Database-driven configuration
- Plugin-style LoRA and content systems

**`scripts/mcp_servers/`** - MCP Interface
- Single server file with all tools
- Lazy loading for performance
- Consistent error handling and response format

### Database Design Patterns

**Context Isolation:**
```python
# Generate unique context key for conversation isolation
context_key = f"{guild_id}:{channel_id}:{thread_id}:{user_id}"
```

**Hierarchical Categories:**
```python
# Parent-child relationships in content categories
category_path = "subject/person/hair/color"  # Slash-separated hierarchy
```

**User Configuration:**
```python
# Per-user settings stored in separate tables
user_personalities, personal_api_keys, user_folders
```

### Error Handling Patterns

**MCP Tools:**
```python
try:
    result = perform_operation()
    return json.dumps({"success": True, "result": result})
except SpecificError as e:
    return json.dumps({"success": False, "error": str(e), "suggestion": "Try X"})
except Exception as e:
    return json.dumps({"success": False, "error": str(e)})
```

**Discord Commands:**
```python
try:
    await interaction.response.defer()
    result = await perform_operation()
    await interaction.followup.send(f"✅ {result}")
except Exception as e:
    logger.error(f"Command failed: {e}")
    try:
        await interaction.followup.send(f"❌ Error: {e}")
    except:
        pass  # Interaction already failed
```

### Configuration Patterns

**Environment Variables:**
```python
# Always use environment variables, never hardcode
base_url = os.getenv("SERVICE_BASE_URL")  # No default
timeout = int(os.getenv("SERVICE_TIMEOUT", "30"))  # With default
enabled = os.getenv("FEATURE_ENABLED", "false").lower() == "true"  # Boolean
```

**Database Configuration:**
```python
# Store user preferences in database
SELECT setting_value FROM user_settings 
WHERE user_id = ? AND setting_name = ?
```

## Testing

### Manual Testing

**MCP Tools:**
```bash
# Test MCP server directly
uv run scripts/mcp_servers/sd_mcp_server.py

# Test through LM Studio
# Open chat and try: "generate an image of a cat"
```

**Discord Commands:**
```bash
# Start bot
python start_discord_bot.py

# Test in Discord
/test
/sd-generate prompt:"test image"
/personality
```

**Database Operations:**
```bash
# Check database content
sqlite3 discord_llm.db "SELECT * FROM personalities;"
sqlite3 content_mapping.db "SELECT COUNT(*) FROM content_words;"
```

### Database Testing

**Reset Databases:**
```bash
rm *.db
python scripts/init_databases.py
```

**Manual Data Entry:**
```sql
-- Test personality
INSERT INTO personalities (name, display_name, system_prompt, description, emoji)
VALUES ('test', 'Test Bot', 'You are a test assistant', 'Test personality', '🧪');

-- Test conversation
INSERT INTO conversations (context_key, user_id, role, content, personality_name)
VALUES ('test:test:None:123', '123', 'user', 'Hello', 'test');
```

## Debugging

### Common Issues

**MCP Server Won't Start:**
```bash
# Check Python path
which python
which uv

# Check imports
python -c "from modules.llm.llm_manager import LLMManager"

# Check environment
echo $SD_BASE_URL
```

**Discord Commands Not Appearing:**
```python
# Check command registration
synced = await self.tree.sync()
print(f"Synced {len(synced)} commands")

# Check bot permissions
# Applications.commands scope required
```

**Database Errors:**
```bash
# Check database exists
ls -la *.db

# Check schema
sqlite3 discord_llm.db ".schema personalities"

# Recreate if corrupted
rm discord_llm.db
python scripts/init_databases.py
```

### Logging

**Enable Debug Logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Module-Specific Logging:**
```python
logger = logging.getLogger(__name__)
logger.info("Operation completed")
logger.error(f"Operation failed: {e}")
```

All development follows these patterns - environment-driven configuration, consistent error handling, and database-driven features.