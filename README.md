# SD MCP Server 🎨

A comprehensive **Model Context Protocol (MCP)** server that integrates **Stable Diffusion**, **LLM conversation management**, and **Discord bot functionality**. This project enables AI assistants to generate images, manage conversations with personality switching, and provide intelligent content moderation.

**NOTE**: 

> All features have been run through a slew of programic tests to confirm functionality and then again with limited data. If you experience any problems, raise an issue.

> The intention of the Content Classification is to recognize new words, classify them and relate them to other prompts or models used in similar generations. It is rudimentary at the moment, but there is the intention to grow it.

> There are 'Stubs' for other LLM Providers. LM Studio is the intended target, but if you visit the /modeules/llm/ folder, you will find files that have minimum setup to connect, but no function. Just add your API key to the MCP.json and build out your tools.

> I could have created a separate configuration file for everything and I may go back and rework how the information is populated. However, the intention was for the MCP.json to be the source or all configurable information to prevent you from having to hunt it down.

> There is a GUI-Based Testing Tool that will let you test and of the main functions and connections. Open the target folder and launch gui_tester.py. If you have issues, run the .bat or .sh files to launch into the appropriate environment.

> This was tested on Gemma3-8B. The tools take up about 900-1000 tokens in the LLM's memory. It's light enough that you can still generate and get results with a 4096 token context window.

## ✨ Features

### 🎨 **Stable Diffusion Integration**
- **Direct SD WebUI integration** with model/LoRA management
- **Intelligent prompt enhancement** with LLM-powered optimization
- **Advanced content filtering** with NudeNet integration
- **Queue management** with status tracking and prioritization

### 🤖 **Discord Bot Integration**
- **Multi-personality LLM chat** with 6 built-in personalities
- **Per-user conversation isolation** (channels, threads, DMs)
- **On-the-fly image generation** from chat messages
- **Admin moderation tools** (timeouts, personality locks, suspensions)

### 🖼️ **Image Hosting & Management**
- **Chevereto integration** for permanent image hosting
- **Guest upload system** with 30-minute auto-cleanup
- **User account management** with Discord integration
- **Fallback to local hosting** when external services unavailable

### 🧠 **LLM Provider Support**
- **LM Studio integration** (primary)
- **OpenAI, Claude, Gemini** support (extensible)
- **Thinking tag filtering** for clean responses
- **Conversation memory** with auto-cleanup options

## 🚀 Quick Start

### Prerequisites
- **Python 3.12+** with `uv` package manager

- [**Stable Diffusion WebUI** running locally](https://github.com/AUTOMATIC1111/stable-diffusion-webui)

- [**LM Studio** for LLM functionality](https://lmstudio.ai/)

- [**Discord bot token** (optional, for Discord integration)](https://discord.com/developers/applications)

- [**Nudenet Censor** - SD Web UI Extension (Optional, for image censoring)](https://github.com/w-e-w/sd-webui-nudenet-nsfw-censor)

- [**Cheverto** (Optional, Local Image Hosting)](https://chevereto.com/)


### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/nrchamb/sd-mcp-server.git
   cd sd-mcp-server
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Initialize databases**
   ```bash
   python scripts/init_databases.py
   ```

4. **Test your setup** (Recommended)
   ```bash
   python gui_tester.py
   ```
   The GUI testing tool provides comprehensive validation of all components and configuration.

5. **Start the system**
   ```bash
   # Option 1: Discord bot with MCP server
   python start_discord_bot.py
   
   # Option 2: MCP server only (for LM Studio integration)
   uv run scripts/mcp_servers/sd_mcp_server.py
   
   # Option 3: HTTP server for local image serving
   python mcp_http_server.py
   ```

## ⚙️ Configuration

### Core MCP Configuration
Edit your LM Studio `mcp.json` file (typically at `~/.cache/lm-studio/mcp.json`):

```json
{
  "mcpServers": {
    "SD_MCP_Server": {
      "command": "/path/to/uv",
      "args": ["--directory", "/path/to/sd-mcp-server", "run", "scripts/mcp_servers/sd_mcp_server.py"],
      "env": {
        "SD_BASE_URL": "http://localhost:7860",
        "IMAGE_OUT_PATH": "/path/to/local/images",
        "LM_STUDIO_BASE_URL": "http://localhost:1234",
        "CHEVERETO_BASE_URL": "https://your-chevereto-instance.com",
        "CHEVERETO_USER_API_KEY": "your_user_api_key",
        "CHEVERETO_GUEST_API_KEY": "your_guest_api_key",
        "DISCORD_BOT_TOKEN": "your_discord_token",
        "ENABLE_DISCORD": "true"
      }
    }
  }
}
```

### Environment Variables

#### **Required Variables**
| Variable | Description | Default |
|----------|-------------|---------|
| `SD_BASE_URL` | Stable Diffusion WebUI URL | `http://localhost:7860` |
| `IMAGE_OUT_PATH` | Local image output directory | `/tmp/images` |

#### **Optional Variables** *(System works without these)*
| Variable | Description | Default |
|----------|-------------|---------|
| `SD_WEBUI_USERNAME` | SD WebUI authentication username | None |
| `SD_WEBUI_PASSWORD` | SD WebUI authentication password | None |
| `LM_STUDIO_BASE_URL` | LM Studio API URL | `http://localhost:1234` |
| `CHEVERETO_BASE_URL` | Image hosting service URL | None |
| `CHEVERETO_USER_API_KEY` | Personal/shared API key | None |
| `CHEVERETO_GUEST_API_KEY` | Guest upload API key (30min expiry) | None |
| `DISCORD_BOT_TOKEN` | Discord bot token | None |
| `ENABLE_DISCORD` | Enable Discord integration | `false` |
| `NSFW_FILTER` | Enable NudeNet content filtering | `false` |
| `CHAT_RATE_LIMIT_PER_MINUTE` | Chat rate limit per user | `10` |
| `LLM_AUTO_CLEAN_ENABLED` | Auto-cleanup old conversations | `true` |

#### **Minimal Configuration** *(Core SD functionality only)*
For basic Stable Diffusion functionality without optional services:
```json
{
  "mcpServers": {
    "SD_MCP_Server": {
      "command": "/path/to/uv",
      "args": ["--directory", "/path/to/sd-mcp-server", "run", "scripts/mcp_servers/sd_mcp_server.py"],
      "env": {
        "SD_BASE_URL": "http://localhost:7860",
        "IMAGE_OUT_PATH": "/path/to/local/images"
      }
    }
  }
}
```

#### **Graceful Fallback Behavior**
- **Missing Chevereto config**: Images save locally with clear error messages
- **Missing Discord config**: Discord features disabled, core SD unaffected  
- **Missing authentication**: System works in "no auth required" mode
- **Missing LLM config**: LLM features unavailable, image generation continues
- **All core MCP tools work** without optional services

## 🎭 Personality System

### Built-in Personalities
- 🎉 **Fun Discord Bot** - Playful, teasing personality (default)
- 🥺 **UwU Bot** - Kawaii, adorable responses
- 😏 **Sarcastic Bot** - Witty, sarcastic humor
- 💼 **Professional Assistant** - Business-focused, formal
- 🤝 **Helpful Assistant** - Direct, informative
- 🎨 **Creative Companion** - Imaginative, artistic

### Usage
```
/personality          # Switch personalities
/chat <message>       # Chat with current personality
/clear-chat          # Clear conversation history
```

## 🖼️ Image Generation

### Discord Commands
```
/sd-generate         # Direct image generation
/sd-assist           # Guided generation with LLM
generate a sunset    # Natural language in chat
```

### Automatic Enhancement
The system automatically detects image generation requests in chat and:
1. **Switches to image personality** temporarily
2. **Enhances the prompt** using LLM
3. **Generates the image** via SD WebUI
4. **Reverts to chat personality**

## 🛠️ Development

### Project Structure
```
sd-mcp-server/
├── gui_tester.py                     # GUI testing tool for development
├── discord_bot.py                    # Main Discord bot
├── start_discord_bot.py              # Launcher script
├── mcp_http_server.py               # HTTP MCP server
├── modules/
│   ├── stable_diffusion/            # SD integration & Chevereto client
│   └── llm/                         # LLM providers & conversation
├── scripts/
│   ├── mcp_servers/                 # MCP server implementations
│   │   └── sd_mcp_server.py         # Main MCP server
│   └── init_databases.py            # Database initialization
├── config/                          # Configuration helpers
├── docs/                           # Documentation
└── utils/                          # Utility scripts
```

### 🧪 GUI Testing Tool

The project includes a comprehensive GUI testing tool (`gui_tester.py`) for development and validation:

**Features:**
- **System Status Dashboard** - Real-time component monitoring
- **Database Management** - LoRA and conversation database tools
![alt text](https://github.com/nrchamb/sd-mcp-server/blob/main/assets/DebugTools_SystemStatus.png "System Status")

- **SD WebUI Testing** - Image generation with progress tracking
- **NudeNet Testing** - NSFW filtering with before/after comparison
![alt text](https://github.com/nrchamb/sd-mcp-server/blob/main/assets/DebugTools_Nudenet.png "Nudenet Testing")
  
- **Chevereto Upload Testing** - Guest and personal API testing
![alt text]( "Upload Testing")
  
- **MCP Tools Testing** - Direct tool execution and parameter validation
![alt text](https://github.com/nrchamb/sd-mcp-server/blob/main/assets/DebugTools_SystemStatus.png "MCP Tool Testing")
  


**Usage:**
```bash
python gui_tester.py
```

### Adding New Personalities
Personalities are stored in the SQLite database. To add custom personalities:

```python
# Add to modules/llm/llm_database.py personalities table
INSERT INTO personalities (name, display_name, system_prompt, image_injection_prompt, description, emoji, category) 
VALUES ('custom', 'Custom Bot', 'Your system prompt...', 'Image generation prompt...', 'Description', '🤖', 'chat');
```

### Extending LLM Providers
Create new providers by extending `BaseLLMProvider`:

```python
# modules/llm/your_provider.py
class YourLLMProvider(BaseLLMProvider):
    async def chat(self, messages, **kwargs):
        # Implement your provider logic
        pass
```

## 📚 Documentation

### Setup & Configuration
- **[Complete Setup Guide](docs/SETUP.md)** - Step-by-step installation and configuration
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and data flow
- **[Database Structure](docs/DATABASE.md)** - Complete database schema and relationships

### Feature Documentation  
- **[Discord Integration](docs/DISCORD.md)** - Commands, personalities, and user management
- **[Content Classification](docs/CONTENT_SYSTEM.md)** - Dynamic content analysis and categorization system
- **[LoRA Intelligence](docs/LORA_SYSTEM.md)** - Smart LoRA selection and management

### Developer Resources
- **[Developer Guide](docs/DEVELOPER.md)** - Adding new features, providers, and commands
- **[Legacy Docs](docs/)** - Additional integration guides and configurations

## 🔧 Troubleshooting

### 🎯 First Step: Use the GUI Testing Tool

**Before troubleshooting manually, run the GUI testing tool:**
```bash
python gui_tester.py
```

The GUI provides:
- **Real-time system status** for all components
- **Automated testing** of SD WebUI, MCP tools, and uploads
- **Configuration validation** with detailed error messages
- **Component isolation** to identify specific issues

### Common Issues

**Discord commands not appearing:**
- Restart Discord client completely
- Check bot permissions (applications.commands)
- Verify MCP.json configuration
- Use GUI tool's "Discord Bot Status" monitoring

**LLM features unavailable:**
- Check LM Studio is running on correct port
- Verify `LM_STUDIO_BASE_URL` in configuration
- Ensure model is loaded in LM Studio
- Test with GUI tool's MCP Tools tab

**Image generation failures:**
- Verify SD WebUI is accessible with GUI testing tool
- Check `SD_BASE_URL` configuration
- Ensure SD WebUI API is enabled (--api flag)
- Test image generation in GUI tool's SD WebUI tab

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Automatic1111** - Stable Diffusion WebUI
- **LM Studio** - Local LLM hosting
- **Chevereto** - Image hosting platform
- **Discord.py** - Discord bot framework
- **Model Context Protocol** - AI assistant integration standard

---

**Made with ❤️ for the AI art community**
