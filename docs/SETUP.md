# Complete Setup Guide 🚀

## Prerequisites

- **Python 3.12+** 
- **`uv`** package manager ([Installation Guide](https://docs.astral.sh/uv/getting-started/installation/))
- **4GB+ RAM** (8GB+ recommended for SD WebUI)
- **NVIDIA GPU** (recommended for SD WebUI performance)


### Minimum Setup
1. Automatic1111's SD Web UI
2. LM Studio

{
  "mcpServers": {
    "SD_MCP_Server": {
      "command": "/Users/<user>/.local/bin/uv",
      "args": [
        "--directory",
        "<AbsolutePath>",
        "run",
        "scripts/mcp_servers/sd_mcp_server.py"
      ],
      "env": {
        "SD_BASE_URL": "http://192.168.1.20:9977",
        "IMAGE_OUT_PATH": "<AbsolutePath>",
      },
      "timeout": 600000
    }
  }
}

### Complete MCP Example

{
  "mcpServers": {
    "SD_MCP_Server": {
      "command": "/Users/<user>/.local/bin/uv",
      "args": [
        "--directory",
        "<AbsolutePath>",
        "run",
        "scripts/mcp_servers/sd_mcp_server.py"
      ],
      "env": {
        "SD_BASE_URL": "",
        "SD_WEBUI_USERNAME": "",
        "SD_WEBUI_PASSWORD": "",
        "IMAGE_OUT_PATH": "<AbsolutePath>",
        "NSFW_FILTER": "true",
        "CHEVERETO_BASE_URL": "",
        "CHEVERETO_USER_API_KEY": "",
        "CHEVERETO_GUEST_API_KEY": "",
        "CHEVERETO_TIMEOUT": "30",
        "CHEVERETO_MAX_FILE_SIZE": "52428800",
        "CHEVERETO_FALLBACK_TO_LOCAL": "true",
        "ENABLE_DISCORD": "true",
        "DISCORD_BOT_TOKEN": "",
        "CHAT_LLM_PROVIDER": "lmstudio",
        "LM_STUDIO_BASE_URL": "",
        "LM_STUDIO_DEFAULT_MODEL": "",
        "LM_STUDIO_TIMEOUT": "60",
        "CHAT_RATE_LIMIT_PER_MINUTE": "10",
        "GENERATE_RATE_LIMIT_PER_MINUTE": "5",
        "DISCORD_ADMIN_IDS": "",
        "LLM_AUTO_CLEAN_ENABLED": "true",
        "LLM_AUTO_CLEAN_METHOD": "days",
        "LLM_AUTO_CLEAN_DAYS": "7",
        "LLM_AUTO_CLEAN_LAUNCHES": "10",
        "MCP_HTTP_HOST": "127.0.0.1",
        "MCP_HTTP_PORT": "8000",
        "NUDENET_THRESHOLD_FACE": "1.0",
        "NUDENET_THRESHOLD_BREAST_EXPOSED": "0.1",
        "NUDENET_THRESHOLD_BREAST_COVERED": "1.0",
        "NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": "0.1",
        "NUDENET_THRESHOLD_BUTTOCKS_COVERED": "1.0",
        "NUDENET_THRESHOLD_GENITALIA_EXPOSED": "0.1",
        "NUDENET_THRESHOLD_GENITALIA_COVERED": "1.0",
        "NUDENET_THRESHOLD_FEET": "1.0",
        "NUDENET_THRESHOLD_ARMPITS": "1.0",
        "NUDENET_THRESHOLD_BELLY": "1.0",
        "NUDENET_THRESHOLD_BACK": "1.0",
        "NUDENET_EXPAND_HORIZONTAL": "1.0",
        "NUDENET_EXPAND_VERTICAL": "1.0",
        "NUDENET_FILTER_TYPE": "Variable blur",
        "NUDENET_BLUR_RADIUS": "25",
        "NUDENET_BLUR_STRENGTH_CURVE": "2",
        "NUDENET_PIXELATION_FACTOR": "15",
        "NUDENET_FILL_COLOR": "#000000",
        "NUDENET_MASK_SHAPE": "Ellipse",
        "NUDENET_MASK_BLEND_RADIUS": "10",
        "NUDENET_RECTANGLE_ROUND_RADIUS": "0",
        "NUDENET_NMS_THRESHOLD": "0.5"
      },
      "timeout": 600000
    }
  }
}

## Installation Steps

### 1. Clone and Setup Project

```bash
git clone https://github.com/nrchamb/sd-mcp-server.git
cd sd-mcp-server
uv sync
python scripts/init_databases.py
```

### 2. Required Components

#### LM Studio Setup

**Installation:**
1. Download from [LM Studio](https://lmstudio.ai/)
2. Download a model
3. Start the local server (defaults to `http://localhost:1234`)

**MCP Configuration:**
Create or edit `~/.cache/lm-studio/mcp.json`:

```json
{
  "mcpServers": {
    "SD_MCP_Server": {
      "command": "/Users/your-username/.local/bin/uv",
      "args": [
        "--directory", 
        "/path/to/your/sd-mcp-server", 
        "run", 
        "scripts/mcp_servers/sd_mcp_server.py"
      ],
      "env": {
        "SD_BASE_URL": "http://localhost:7860",
        "IMAGE_OUT_PATH": "/path/to/local/images",
        "LM_STUDIO_BASE_URL": "http://localhost:1234"
      }
    }
  }
}
```

**Test:** Open LM Studio chat and try: "generate an image of a sunset"

#### Stable Diffusion WebUI Setup

**Installation:**
```bash
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui
./webui.sh --api --listen --port 7860
```

**Requirements:**
- **Always start with `--api` flag** for MCP integration
- Place Stable Diffusion models in `models/Stable-diffusion/`
- Download at least one SD model (e.g., from HuggingFace or CivitAI)
- Disable API authentication for local use

**Test Connection:**
```bash
curl http://localhost:7860/sdapi/v1/samplers
```

### 3. Test Your Setup

**Using GUI Testing Tool (Recommended):**
```bash
python gui_tester.py
```

The GUI provides comprehensive testing for:
- SD WebUI connectivity
- MCP tools functionality  
- Configuration validation
- Component status monitoring

**Manual Testing:**
```bash
# Test MCP server directly
uv run scripts/mcp_servers/sd_mcp_server.py

# Test Discord bot (if configured)
python start_discord_bot.py
```

## Optional Components

### 🖼️ Chevereto Image Hosting

**What it provides:**
- **Permanent image hosting** with public URLs
- **User accounts** for Discord users  
- **Guest uploads** with 30-minute expiry
- **Fallback to local storage** when service unavailable

**Setup:**
1. Deploy Chevereto instance or use existing service
2. Add to your MCP configuration:

```json
"env": {
  "CHEVERETO_BASE_URL": "https://your-instance.com",
  "CHEVERETO_USER_API_KEY": "your_personal_key",
  "CHEVERETO_GUEST_API_KEY": "your_guest_key",
  "CHEVERETO_FALLBACK_TO_LOCAL": "true"
}
```

**Behavior without Chevereto:**
- Images save locally to `IMAGE_OUT_PATH`
- HTTP server serves images at `http://localhost:8000/images/`
- All functionality works, just without external hosting

### 🛡️ NudeNet Content Filtering

**What it provides:**
- **NSFW detection** with configurable thresholds per body part
- **Automatic censoring** of inappropriate content
- **Detailed logging** of detection results

**Setup:**
```bash
cd stable-diffusion-webui/extensions
git clone https://github.com/w-e-w/sd-webui-nudenet-nsfw-censor.git
```

**Configuration:**
```json
"env": {
  "NSFW_FILTER": "true",
  "NUDENET_THRESHOLD_BREAST_EXPOSED": "0.1",
  "NUDENET_THRESHOLD_GENITALIA_EXPOSED": "0.1",
  "NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": "0.1",
  "NUDENET_FILTER_TYPE": "Variable blur",
  "NUDENET_BLUR_RADIUS": "25"
}
```

**See [NudeNet Configuration Guide](nudenet_threshold_configuration.md) for detailed threshold settings.**

### 🤖 Discord Bot

**What it provides:**
- **Multi-personality LLM chat** (6 built-in personalities)
- **Image generation** via slash commands and natural language
- **User management** and moderation tools
- **Per-user conversation isolation** (channels, threads, DMs)

**Setup:**
1. Create Discord application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create bot, copy token
3. Invite with permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`, `Attach Files`

**Configuration:**
Add to your MCP configuration:
```json
"env": {
  "ENABLE_DISCORD": "true",
  "DISCORD_BOT_TOKEN": "your_discord_bot_token",
  "CHAT_RATE_LIMIT_PER_MINUTE": "10",
  "GENERATE_RATE_LIMIT_PER_MINUTE": "5"
}
```

**Start the bot:**
```bash
python start_discord_bot.py
```

**Commands:**
- `/sd-generate` - Direct image generation
- `/personality` - Switch AI personalities  
- `/chat` - Chat with current personality
- `/clear-chat` - Clear conversation history

**Behavior without Discord:**
- MCP server works normally for LM Studio integration
- All core SD functionality remains available

## Complete Configuration Reference

### **Required Variables**
These are the minimum variables needed for basic functionality:

| Variable | Description | Default |
|----------|-------------|---------|
| `SD_BASE_URL` | Stable Diffusion WebUI URL | `http://localhost:7860` |
| `IMAGE_OUT_PATH` | Local image output directory | `/tmp/images` |

### **Core Optional Variables**
These enhance functionality but aren't required:

| Variable | Description | Default |
|----------|-------------|---------|
| `LM_STUDIO_BASE_URL` | LM Studio API URL | `http://localhost:1234` |
| `SD_WEBUI_USERNAME` | SD WebUI auth username | None |
| `SD_WEBUI_PASSWORD` | SD WebUI auth password | None |

### **Discord Integration**
| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_DISCORD` | Enable Discord bot functionality | `false` |
| `DISCORD_BOT_TOKEN` | Discord bot token | None |
| `CHAT_RATE_LIMIT_PER_MINUTE` | Chat rate limit per user | `10` |
| `GENERATE_RATE_LIMIT_PER_MINUTE` | Image generation rate limit | `5` |
| `DISCORD_ADMIN_IDS` | Comma-separated admin user IDs | None |

### **Image Hosting (Chevereto)**
| Variable | Description | Default |
|----------|-------------|---------|
| `CHEVERETO_BASE_URL` | Chevereto instance URL | None |
| `CHEVERETO_USER_API_KEY` | Personal/shared API key | None |
| `CHEVERETO_GUEST_API_KEY` | Guest upload API key | None |
| `CHEVERETO_FALLBACK_TO_LOCAL` | Enable local fallback | `true` |
| `MCP_HTTP_HOST` | HTTP server host for local images | `127.0.0.1` |
| `MCP_HTTP_PORT` | HTTP server port for local images | `8000` |

### **Content Filtering (NudeNet)**
| Variable | Description | Default |
|----------|-------------|---------|
| `NSFW_FILTER` | Enable NudeNet filtering | `false` |
| `NUDENET_THRESHOLD_BREAST_EXPOSED` | Detection threshold for exposed breasts | `0.1` |
| `NUDENET_THRESHOLD_GENITALIA_EXPOSED` | Detection threshold for exposed genitalia | `0.1` |
| `NUDENET_THRESHOLD_BUTTOCKS_EXPOSED` | Detection threshold for exposed buttocks | `0.1` |
| `NUDENET_FILTER_TYPE` | Censoring method (`Variable blur`, `Pixelation`, `Solid fill`) | `Variable blur` |
| `NUDENET_BLUR_RADIUS` | Blur radius for filtering | `25` |

### **LLM Management**
| Variable | Description | Default |
|----------|-------------|---------|
| `CHAT_LLM_PROVIDER` | LLM provider (`lmstudio`, `openai`, `claude`) | `lmstudio` |
| `LLM_AUTO_CLEAN_ENABLED` | Auto-cleanup old conversations | `true` |
| `LLM_AUTO_CLEAN_METHOD` | Cleanup method (`days` or `launches`) | `days` |
| `LLM_AUTO_CLEAN_DAYS` | Days to keep conversations | `7` |

## Sample Configurations

### **Minimal Setup** (Core SD functionality only)
```json
{
  "mcpServers": {
    "SD_MCP_Server": {
      "command": "/Users/your-username/.local/bin/uv",
      "args": ["--directory", "/path/to/sd-mcp-server", "run", "scripts/mcp_servers/sd_mcp_server.py"],
      "env": {
        "SD_BASE_URL": "http://localhost:7860",
        "IMAGE_OUT_PATH": "/path/to/local/images"
      }
    }
  }
}
```

### **Full Featured Setup** (All optional components)
```json
{
  "mcpServers": {
    "SD_MCP_Server": {
      "command": "/Users/your-username/.local/bin/uv",
      "args": ["--directory", "/path/to/sd-mcp-server", "run", "scripts/mcp_servers/sd_mcp_server.py"],
      "env": {
        "SD_BASE_URL": "http://localhost:7860",
        "IMAGE_OUT_PATH": "/path/to/local/images",
        "LM_STUDIO_BASE_URL": "http://localhost:1234",
        "ENABLE_DISCORD": "true",
        "DISCORD_BOT_TOKEN": "your_discord_token",
        "CHEVERETO_BASE_URL": "https://your-chevereto.com",
        "CHEVERETO_USER_API_KEY": "your_user_key",
        "CHEVERETO_GUEST_API_KEY": "your_guest_key",
        "NSFW_FILTER": "true",
        "NUDENET_THRESHOLD_BREAST_EXPOSED": "0.1",
        "NUDENET_THRESHOLD_GENITALIA_EXPOSED": "0.1",
        "NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": "0.1"
      }
    }
  }
}
```

## Testing Your Setup

### **GUI Testing Tool** (Recommended)
The project includes a comprehensive testing tool:

```bash
python gui_tester.py
```

**Features:**
- **System Status Dashboard** - Real-time component monitoring
- **SD WebUI Testing** - Image generation with progress tracking  
- **NudeNet Testing** - NSFW filtering with before/after comparison
- **Chevereto Upload Testing** - Guest and personal API testing
- **MCP Tools Testing** - Direct tool execution and validation
- **Configuration Validation** - Check MCP.json setup

### **Manual Testing**

**LM Studio Integration:**
1. Start LM Studio with a loaded model
2. Open chat interface  
3. Try: "Generate an image of a sunset"
4. Expected: Image generated and displayed

**Discord Bot:**
```bash
python start_discord_bot.py
```
Then test commands:
- `/sd-generate prompt:"sunset"` - Image generation
- `/personality` - Switch AI personalities
- `/chat hello` - Chat with current personality

## Data Storage & Privacy

**What gets stored locally:**
- **SQLite databases** in project directory:
  - `discord_llm.db` - Conversation history (unencrypted)
  - `chevereto_users.db` - User API keys (unencrypted)
  - `lora_database.db` - LoRA metadata and search cache
- **Generated images** - `IMAGE_OUT_PATH` directory or uploaded to Chevereto
- **Logs** - Console output (no persistent log files)

**🚨 Important Security Note:**
This is a **local development tool**. API keys and conversations are stored unencrypted in SQLite databases. Don't use for sensitive data or in shared environments.

## Troubleshooting

### **Common Issues**

**"MCP server not responding":**
1. Check `uv` is installed and in PATH
2. Verify project directory path in MCP config is correct
3. Check SD WebUI is running with `--api` flag
4. Use GUI testing tool to validate configuration

**"Discord commands not appearing":**
1. Restart Discord client completely
2. Check bot has `applications.commands` permission
3. Verify bot token is correct in configuration
4. Check console for error messages

**"Image generation fails":**
1. Verify SD WebUI is accessible: `curl http://localhost:7860/sdapi/v1/samplers`
2. Check SD WebUI has at least one model loaded
3. Check console for API error messages
4. Test with GUI testing tool's SD WebUI tab

**"Database errors":**
1. Run: `python scripts/init_databases.py`
2. Check directory write permissions
3. Delete corrupt `.db` files and re-initialize

### **Getting Help**

1. **Use the GUI testing tool** - It provides detailed diagnostics
2. **Check console output** - Look for specific error messages
3. **Validate configuration** - Use the config validation feature in GUI
4. **Test components individually** - Isolate the failing component

All configuration is via environment variables - no hardcoded values in the code.
