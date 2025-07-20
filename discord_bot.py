#!/usr/bin/env python3
"""
Discord Bot for SD MCP Server
Provides Discord interface for Stable Diffusion image generation
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands
import httpx

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Import existing modules
from modules.stable_diffusion.discord_integration import DiscordUserManager, DiscordImageHandler
from config.chevereto_config import create_enhanced_uploader
from modules.llm.discord_conversation import DiscordConversationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DiscordBot')

class SDDiscordBot(commands.Bot):
    """Discord bot for SD MCP Server integration"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!sd-',
            intents=intents,
            description="Stable Diffusion MCP Server Discord Bot"
        )
        
        # Configuration
        self.config = {
            'mcp_server_url': os.getenv('MCP_SERVER_URL', 'http://127.0.0.1:8000'),
            'max_queue_size': 10,
            'thread_timeout': 3600,  # 1 hour
            'image_timeout': 1800,   # 30 minutes (Chevereto auto-delete)
        }
        
        # Session management
        self.user_sessions = {}
        self.active_threads = {}
        
        # Initialize components
        self.discord_user_manager = None
        self.discord_image_handler = None
        self.image_uploader = None
        self.conversation_manager = None
        
    async def setup_hook(self):
        """Initialize bot components"""
        logger.info("🤖 Setting up Discord bot...")
        
        # Initialize Discord integration
        try:
            # Use existing Chevereto config from environment
            env_config = {
                'CHEVERETO_BASE_URL': os.getenv('CHEVERETO_BASE_URL'),
                'CHEVERETO_USER_API_KEY': os.getenv('CHEVERETO_USER_API_KEY'),
                'CHEVERETO_ADMIN_API_KEY': os.getenv('CHEVERETO_ADMIN_API_KEY'),
                'CHEVERETO_FALLBACK_TO_LOCAL': os.getenv('CHEVERETO_FALLBACK_TO_LOCAL', 'true'),
                'NSFW_FILTER': 'false',  # Let users decide
                'ENABLE_DISCORD': 'true'
            }
            
            self.image_uploader = create_enhanced_uploader(env_config)
            self.discord_user_manager = DiscordUserManager(chevereto_client=self.image_uploader.chevereto_client)
            self.discord_image_handler = DiscordImageHandler(
                self.discord_user_manager, 
                self.image_uploader.chevereto_client
            )
            
            logger.info("✅ Discord integration components initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Discord integration: {e}")
            # Continue without Chevereto integration
            
        # Initialize LLM conversation manager
        try:
            # Get all environment variables for LLM config
            llm_config = {key: value for key, value in os.environ.items()}
            self.conversation_manager = DiscordConversationManager(
                llm_config, 
                mcp_server_caller=self.call_mcp_server
            )
            logger.info("✅ LLM conversation manager initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize LLM conversation manager: {e}")
            # Continue without LLM features
            
        # Sync commands
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} commands")
        except Exception as e:
            logger.error(f"❌ Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Bot is ready"""
        logger.info(f"🚀 {self.user.name} is ready!")
        logger.info(f"🔗 Connected to {len(self.guilds)} guilds")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for /sd-generate and /chat commands"
            )
        )
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages for LLM integration"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Process commands first
        await self.process_commands(message)
        
        # Handle LLM features if available
        if not self.conversation_manager:
            return
        
        try:
            # Check for bot mentions
            if self.user in message.mentions:
                await self.conversation_manager.handle_mention(message)
                return
            
            # Handle thread conversations
            if isinstance(message.channel, discord.Thread):
                await self.conversation_manager.handle_thread_message(message)
                
        except Exception as e:
            logger.error(f"Error handling message for LLM: {e}")
    
    async def create_user_thread(self, interaction: discord.Interaction, command_name: str) -> discord.Thread:
        """Create a thread for user interaction"""
        thread_name = f"🎨 {command_name} - {interaction.user.display_name}"
        
        # Create thread
        thread = await interaction.followup.send(
            f"🎨 **{command_name}** session started for {interaction.user.mention}",
            wait=True
        )
        
        # Convert to thread
        thread = await thread.create_thread(
            name=thread_name,
            auto_archive_duration=60  # 1 hour
        )
        
        # Store thread info
        self.active_threads[thread.id] = {
            'user_id': interaction.user.id,
            'created_at': datetime.now(),
            'command': command_name
        }
        
        return thread
    
    async def call_mcp_server(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call MCP server tool directly (bypass HTTP)"""
        try:
            logger.info(f"🔧 Calling MCP tool: {tool_name}")
            
            # Import MCP functions directly
            from scripts.mcp_servers.sd_mcp_server import (
                generate_image, get_models, load_checkpoint, get_current_model,
                search_loras, get_queue_status, upload_image, start_guided_generation,
                analyze_prompt
            )
            
            # Map tool names to functions
            tool_functions = {
                "generate_image": generate_image,
                "get_models": get_models,
                "load_checkpoint": load_checkpoint,
                "get_current_model": get_current_model,
                "search_loras": search_loras,
                "get_queue_status": get_queue_status,
                "upload_image": upload_image,
                "start_guided_generation": start_guided_generation,
                "analyze_prompt": analyze_prompt
            }
            
            if tool_name not in tool_functions:
                return {
                    "error": f"Unknown tool: {tool_name}",
                    "suggestion": "Check tool name spelling"
                }
            
            # Call the function directly
            func = tool_functions[tool_name]
            result = await func(**kwargs)
            
            # Parse JSON result if it's a string
            if isinstance(result, str):
                import json
                result = json.loads(result)
            
            logger.info(f"✅ MCP tool {tool_name} completed")
            return result
            
        except Exception as e:
            logger.error(f"❌ MCP tool {tool_name} failed: {e}")
            return {
                "error": f"Tool execution failed: {str(e)}",
                "suggestion": "Check MCP server logs and SD WebUI status"
            }

# Create bot instance
bot = SDDiscordBot()

@bot.tree.command(name="sd-generate", description="Generate image directly with Stable Diffusion")
@app_commands.describe(
    prompt="The image prompt",
    negative_prompt="What to avoid in the image",
    steps="Number of generation steps (10-50)",
    width="Image width (512-2048)",
    height="Image height (512-2048)",
    cfg_scale="CFG scale (1-20)"
)
async def sd_generate(
    interaction: discord.Interaction,
    prompt: str,
    negative_prompt: str = "",
    steps: int = 25,
    width: int = 1024,
    height: int = 1024,
    cfg_scale: float = 7.0
):
    """Direct SD generation command"""
    try:
        await interaction.response.defer()
        logger.info(f"🎨 Generation request from {interaction.user}: {prompt}")
    except Exception as e:
        logger.error(f"Failed to defer interaction: {e}")
        return
    
    try:
        # Send immediate response
        await interaction.followup.send(f"🎨 **Generating image...**\n📝 Prompt: `{prompt}`")
        
        # Call MCP server
        result = await bot.call_mcp_server(
            "generate_image",
            prompt=prompt,
            negative_prompt=negative_prompt,
            steps=steps,
            width=width,
            height=height,
            cfg_scale=cfg_scale,
            upload=True,
            user_id=str(interaction.user.id),
            album_name="Discord Bot"
        )
    except Exception as e:
        logger.error(f"Generation process failed: {e}")
        try:
            await interaction.followup.send(f"❌ **Error:** {e}")
        except:
            pass
        return
    
    if "error" in result:
        error_msg = f"❌ **Generation failed:** {result['error']}"
        if "suggestion" in result:
            error_msg += f"\n💡 **Suggestion:** {result['suggestion']}"
        try:
            await interaction.followup.send(error_msg)
        except:
            pass
        return
    
    # Handle successful generation
    try:
        await interaction.followup.send("✅ **Generation completed!**")
        
        # Handle image upload and display
        upload_info = result.get("upload", {})
        local_path = result.get("local_path", "Unknown")
        
        if upload_info.get("success"):
            url = upload_info.get("public_url")
            upload_mode = upload_info.get("upload_mode", "unknown")
            expiry_note = upload_info.get("expiry_note", "unknown")
            service_used = upload_info.get("service_used", "unknown")
            nsfw_detected = upload_info.get("nsfw_detected", False)
            
            # Map service names to user-friendly names
            service_map = {
                "chevereto": "Chevereto",
                "local": "Local Storage", 
                "unknown": "Unknown"
            }
            service_display = service_map.get(service_used, service_used.title())
            
            embed = discord.Embed(
                title="🎨 Generated Image",
                description=f"Prompt: {prompt}",
                color=0x00ff00
            )
            
            # Check if URL is accessible (not localhost)
            if url and not any(localhost in url for localhost in ["localhost", "127.0.0.1", "0.0.0.0"]):
                # Public URL - prioritize Chevereto link over Discord embed
                if service_used == "chevereto":
                    # For Chevereto, show prominent link and optional small preview
                    embed.add_field(name="🖼️ **Image URL**", value=f"**[🔗 Click to View Image]({url})**", inline=False)
                    embed.add_field(name="📋 Direct Link", value=f"`{url}`", inline=False)
                    # Optionally include small thumbnail (comment out if you don't want any preview)
                    # embed.set_thumbnail(url=url)
                else:
                    # Non-Chevereto public URL - use standard embed
                    embed.set_image(url=url)
                    embed.add_field(name="🔗 Link", value=f"[View Image]({url})", inline=True)
            else:
                # Local URL or no URL - upload as attachment
                if local_path and os.path.exists(local_path):
                    file = discord.File(local_path, filename=os.path.basename(local_path))
                    embed.set_image(url=f"attachment://{os.path.basename(local_path)}")
                    await interaction.followup.send(embed=embed, file=file)
                    return
                else:
                    embed.add_field(name="⚠️ Image", value="Local file not accessible", inline=True)
            
            embed.add_field(name="📁 Storage", value=f"{upload_mode.title()}", inline=True)
            embed.add_field(name="⏰ Expiry", value=expiry_note, inline=True)
            embed.add_field(name="🔧 Service", value=service_display, inline=True)
            
            if nsfw_detected:
                embed.add_field(name="🔒 Content", value="NSFW filtered", inline=True)
            
            embed.set_footer(text=f"Generated by {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        else:
            # Upload failed - try to send as attachment if local file exists
            if local_path and os.path.exists(local_path):
                embed = discord.Embed(
                    title="🎨 Generated Image",
                    description=f"Prompt: {prompt}",
                    color=0xff9900
                )
                embed.add_field(name="⚠️ Upload", value="Upload failed, showing local file", inline=True)
                embed.add_field(name="📁 Storage", value="Local only", inline=True)
                embed.set_footer(text=f"Generated by {interaction.user.display_name}")
                
                file = discord.File(local_path, filename=os.path.basename(local_path))
                embed.set_image(url=f"attachment://{os.path.basename(local_path)}")
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send(f"⚠️ Image generated but both upload and local access failed.\n📁 Path: `{local_path}`")
    except Exception as e:
        logger.error(f"Failed to send result: {e}")

@bot.tree.command(name="sd-assist", description="Get AI assistance for Stable Diffusion generation")
@app_commands.describe(prompt="Describe what you want to generate")
async def sd_assist(interaction: discord.Interaction, prompt: str):
    """LLM-assisted SD generation command"""
    await interaction.response.defer()
    
    # Create user thread
    thread = await bot.create_user_thread(interaction, "SD Assist")
    
    # Send initial message
    await thread.send(f"🤖 **AI Assistant activated for {interaction.user.mention}**\n"
                     f"📝 Your request: `{prompt}`\n"
                     f"💭 Let me help you craft the perfect generation...")
    
    # This would integrate with LM Studio/MCP for intelligent assistance
    # For now, provide basic guidance
    await thread.send("🔧 **Coming soon**: LLM-assisted parameter optimization and prompt enhancement!")

@bot.tree.command(name="sd-settings", description="Manage your SD bot settings")
async def sd_settings(interaction: discord.Interaction):
    """User settings management"""
    try:
        await interaction.response.defer(ephemeral=True)
        logger.info(f"⚙️ Settings request from {interaction.user}")
    except Exception as e:
        logger.error(f"Failed to defer settings interaction: {e}")
        return
    
    # Check if user exists
    user_info = None
    if bot.discord_user_manager:
        user_info = bot.discord_user_manager.get_discord_user(str(interaction.user.id))
    
    embed = discord.Embed(
        title="⚙️ Your SD Bot Settings",
        description="Configure your image generation preferences",
        color=0x0099ff
    )
    
    if user_info:
        embed.add_field(name="✅ Account", value="Chevereto account linked", inline=True)
        embed.add_field(name="📁 Folders", value=f"{len(bot.discord_user_manager.get_user_folders(str(interaction.user.id)))}", inline=True)
    else:
        embed.add_field(name="❌ Account", value="No Chevereto account", inline=True)
    
    embed.add_field(name="🔧 Setup", value="Use `/sd-setup` to configure", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="sd-setup", description="Set up your account for image hosting")
async def sd_setup(interaction: discord.Interaction):
    """Account setup for image hosting"""
    await interaction.response.defer(ephemeral=True)
    
    # Get current user mode
    upload_mode = "guest"
    if bot.discord_user_manager and bot.discord_user_manager.chevereto_client:
        upload_mode = bot.discord_user_manager.chevereto_client.get_user_upload_mode(str(interaction.user.id))
    
    embed = discord.Embed(
        title="🔐 Account Setup",
        description="Choose how you want to handle image uploads",
        color=0xff9900
    )
    
    embed.add_field(
        name="📊 Current Mode",
        value=f"**{upload_mode.title()}**",
        inline=True
    )
    
    embed.add_field(
        name="⚠️ Privacy Notice",
        value="Server host can see uploaded images. Guest uploads auto-delete after 30 minutes.",
        inline=False
    )
    
    embed.add_field(
        name="📋 Upload Options",
        value="• **Personal API Key**: Use your own Chevereto account (permanent storage)\n• **Guest Mode**: Anonymous uploads (30min expiry)\n• **Local Only**: No external uploads",
        inline=False
    )
    
    embed.add_field(
        name="🔑 Personal API Key Setup",
        value="1. Login to the image host\n2. Go to @Username → Settings → API\n3. Create API key\n4. Use `/sd-api-key` command",
        inline=False
    )
    
    # Create buttons for setup options
    view = SetupView(bot.discord_user_manager)
    
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="sd-api-key", description="Set your personal Chevereto API key for permanent uploads")
@app_commands.describe(api_key="Your personal Chevereto API key", username="Your Chevereto username (optional)")
async def sd_api_key(interaction: discord.Interaction, api_key: str, username: str = ""):
    """Set personal Chevereto API key"""
    await interaction.response.defer(ephemeral=True)
    
    if not bot.discord_user_manager or not bot.discord_user_manager.chevereto_client:
        await interaction.followup.send("❌ Chevereto integration not available")
        return
    
    # Validate API key format (basic check)
    if len(api_key) < 10:
        await interaction.followup.send("❌ API key appears too short. Please check your key.")
        return
    
    # Store the API key
    success = bot.discord_user_manager.chevereto_client.set_personal_api_key(
        str(interaction.user.id), api_key, username
    )
    
    if success:
        embed = discord.Embed(
            title="✅ Personal API Key Set",
            description="Your personal Chevereto API key has been configured!",
            color=0x00ff00
        )
        embed.add_field(name="📁 Storage", value="Permanent (your account)", inline=True)
        embed.add_field(name="🔐 Account", value=username or "Personal", inline=True)
        embed.add_field(name="⚠️ Security", value="Key stored securely. Use `/sd-remove-key` to remove.", inline=False)
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send("❌ Failed to set API key. Please try again.")

@bot.tree.command(name="sd-remove-key", description="Remove your personal API key (fall back to guest mode)")
async def sd_remove_key(interaction: discord.Interaction):
    """Remove personal API key"""
    await interaction.response.defer(ephemeral=True)
    
    if not bot.discord_user_manager or not bot.discord_user_manager.chevereto_client:
        await interaction.followup.send("❌ Chevereto integration not available")
        return
    
    success = bot.discord_user_manager.chevereto_client.remove_personal_api_key(str(interaction.user.id))
    
    if success:
        embed = discord.Embed(
            title="✅ Personal API Key Removed",
            description="You'll now use guest mode for uploads",
            color=0x00ff00
        )
        embed.add_field(name="📁 Storage", value="Guest mode (30min expiry)", inline=True)
        embed.add_field(name="🔐 Privacy", value="Anonymous uploads", inline=True)
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send("❌ Failed to remove API key. Please try again.")

@bot.tree.command(name="sd-register", description="Register as a test user with dummy account")
async def sd_register(interaction: discord.Interaction):
    """Register user for testing with dummy account"""
    await interaction.response.defer(ephemeral=True)
    
    if not bot.discord_user_manager:
        await interaction.followup.send("❌ User management not available")
        return
    
    # Check if user already registered
    user_info = bot.discord_user_manager.get_discord_user(str(interaction.user.id))
    if user_info:
        embed = discord.Embed(
            title="ℹ️ Already Registered",
            description="You're already registered in the system",
            color=0x0099ff
        )
        embed.add_field(name="👤 Username", value=user_info['username'], inline=True)
        embed.add_field(name="📅 Registered", value=user_info['created_at'][:10], inline=True)
        
        # Check upload mode
        if bot.discord_user_manager.chevereto_client:
            upload_mode = bot.discord_user_manager.chevereto_client.get_user_upload_mode(str(interaction.user.id))
            embed.add_field(name="📁 Upload Mode", value=upload_mode, inline=True)
        
        await interaction.followup.send(embed=embed)
        return
    
    # Register new user
    result = bot.discord_user_manager.register_discord_user(
        discord_id=str(interaction.user.id),
        username=interaction.user.display_name,
        discriminator=str(interaction.user.discriminator) if interaction.user.discriminator != "0" else None,
        avatar_url=str(interaction.user.avatar.url) if interaction.user.avatar else None
    )
    
    if result["success"]:
        embed = discord.Embed(
            title="✅ Registration Successful",
            description="You've been registered for testing!",
            color=0x00ff00
        )
        embed.add_field(name="👤 Username", value=interaction.user.display_name, inline=True)
        embed.add_field(name="🆔 Discord ID", value=str(interaction.user.id), inline=True)
        embed.add_field(name="📁 Upload Mode", value="Guest (30min expiry)", inline=True)
        
        embed.add_field(
            name="🔑 Personal API Key",
            value="Use `/sd-api-key` to set your own Chevereto API key for permanent storage",
            inline=False
        )
        
        embed.add_field(
            name="🧪 Test Commands",
            value="• `/sd-generate` - Generate images\n• `/sd-settings` - View your settings\n• `/sd-api-key` - Set personal API key",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"❌ Registration failed: {result.get('error', 'Unknown error')}")

@bot.tree.command(name="sd-create-dummy-account", description="Create a dummy Chevereto account for testing")
@app_commands.describe(username="Desired username for the dummy account")
async def sd_create_dummy_account(interaction: discord.Interaction, username: str):
    """Create dummy Chevereto account (placeholder for future admin API integration)"""
    await interaction.response.defer(ephemeral=True)
    
    # Validate username
    if len(username) < 3 or len(username) > 20:
        await interaction.followup.send("❌ Username must be 3-20 characters")
        return
    
    if not username.isalnum():
        await interaction.followup.send("❌ Username must contain only letters and numbers")
        return
    
    embed = discord.Embed(
        title="🚧 Feature Under Development",
        description="Automatic account creation is not yet available",
        color=0xff9900
    )
    
    embed.add_field(
        name="🔄 Workaround",
        value="1. Create account manually at the image host\n2. Go to Settings → API to get your API key\n3. Use `/sd-api-key` to set your personal key",
        inline=False
    )
    
    embed.add_field(
        name="💡 Future Plans",
        value="Admin API integration will enable automatic account creation",
        inline=False
    )
    
    embed.add_field(
        name="🆔 Your Info",
        value=f"Discord ID: {interaction.user.id}\nSuggested username: `discord_{interaction.user.id}`",
        inline=False
    )
    
    await interaction.followup.send(embed=embed)

class SetupView(discord.ui.View):
    """Setup buttons for account configuration"""
    
    def __init__(self, user_manager):
        super().__init__(timeout=300)
        self.user_manager = user_manager
    
    @discord.ui.button(label="Auto-Account", style=discord.ButtonStyle.primary, emoji="🔐")
    async def auto_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set up auto account creation"""
        await interaction.response.defer(ephemeral=True)
        
        if self.user_manager:
            # Generate temp password
            import secrets
            temp_password = secrets.token_urlsafe(12)
            
            # Register user
            result = self.user_manager.register_discord_user(
                str(interaction.user.id),
                interaction.user.display_name,
                str(interaction.user.discriminator) if interaction.user.discriminator != "0" else None
            )
            
            if result.get("success"):
                embed = discord.Embed(
                    title="✅ Account Created",
                    description=f"Your account has been created successfully!",
                    color=0x00ff00
                )
                embed.add_field(name="Username", value=f"discord_{interaction.user.id}", inline=True)
                embed.add_field(name="⚠️ Important", value="Save this information - it won't be shown again!", inline=False)
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"❌ Account creation failed: {result.get('error')}")
        else:
            await interaction.followup.send("❌ Account creation not available (Chevereto not configured)")
    
    @discord.ui.button(label="Guest Upload", style=discord.ButtonStyle.secondary, emoji="👤")
    async def guest_upload(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set up guest uploads"""
        await interaction.response.send_message("🔧 Guest upload configuration coming soon!", ephemeral=True)
    
    @discord.ui.button(label="Local Only", style=discord.ButtonStyle.secondary, emoji="💾")
    async def local_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set up local-only mode"""
        await interaction.response.send_message("🔧 Local-only mode configuration coming soon!", ephemeral=True)

# ============ LLM CHAT COMMANDS ============

@bot.tree.command(name="chat", description="Chat with AI assistant")
@app_commands.describe(message="Your message to the AI assistant")
async def chat_command(interaction: discord.Interaction, message: str):
    """Handle /chat slash command for LLM conversations"""
    if not bot.conversation_manager:
        await interaction.response.send_message("❌ LLM features are not available.", ephemeral=True)
        return
    
    try:
        await bot.conversation_manager.handle_chat_command(interaction, message)
    except Exception as e:
        logger.error(f"Error in chat command: {e}")
        try:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
        except:
            pass

@bot.tree.command(name="personality", description="Change your AI personality")
async def personality_command(interaction: discord.Interaction):
    """Show personality selection interface"""
    if not bot.conversation_manager:
        await interaction.response.send_message("❌ LLM features are not available.", ephemeral=True)
        return
    
    try:
        # Get current personality
        user_id = str(interaction.user.id)
        current_personality = await bot.conversation_manager.get_user_personality(user_id)
        
        # Create personality selection view
        view = await bot.conversation_manager.get_personality_view(user_id)
        
        embed = discord.Embed(
            title="🎭 AI Personality Selection",
            description=f"**Current:** {current_personality['display_name']} {current_personality['emoji']}\n_{current_personality['description']}_",
            color=0x7289da
        )
        embed.add_field(
            name="Available Personalities",
            value="Click a button below to switch personalities:",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error in personality command: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="clear-chat", description="Clear your conversation history")
async def clear_chat_command(interaction: discord.Interaction):
    """Clear conversation history for current context"""
    if not bot.conversation_manager:
        await interaction.response.send_message("❌ LLM features are not available.", ephemeral=True)
        return
    
    try:
        # Generate context key for current location
        context_key = bot.conversation_manager.db.generate_context_key(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            thread_id=getattr(interaction.channel, 'parent_id', None) if isinstance(interaction.channel, discord.Thread) else None,
            user_id=interaction.user.id if not interaction.guild_id else None
        )
        
        # Clear conversation
        deleted_count = await bot.conversation_manager.db.clear_conversation(context_key)
        
        if deleted_count > 0:
            await interaction.response.send_message(
                f"✅ Cleared {deleted_count} messages from conversation history.", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "ℹ️ No conversation history found to clear.", 
                ephemeral=True
            )
            
    except Exception as e:
        logger.error(f"Error in clear-chat command: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# ============ ADMIN LLM COMMANDS ============

@bot.tree.command(name="timeout-user", description="[ADMIN] Timeout user from AI features")
@app_commands.describe(
    user="User to timeout",
    minutes="Timeout duration in minutes (1-10080)",
    reason="Reason for timeout"
)
async def timeout_user_command(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str):
    """Admin command to timeout users"""
    if not bot.conversation_manager:
        await interaction.response.send_message("❌ LLM features are not available.", ephemeral=True)
        return
    
    try:
        admin_id = str(interaction.user.id)
        target_id = str(user.id)
        
        success, message = await bot.conversation_manager.timeout_user(admin_id, target_id, minutes, reason)
        
        if success:
            await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error in timeout-user command: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="suspend-user", description="[ADMIN] Suspend user from AI features")
@app_commands.describe(
    user="User to suspend",
    reason="Reason for suspension"
)
async def suspend_user_command(interaction: discord.Interaction, user: discord.Member, reason: str):
    """Admin command to suspend users"""
    if not bot.conversation_manager:
        await interaction.response.send_message("❌ LLM features are not available.", ephemeral=True)
        return
    
    try:
        admin_id = str(interaction.user.id)
        target_id = str(user.id)
        
        success, message = await bot.conversation_manager.suspend_user(admin_id, target_id, reason)
        
        if success:
            await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error in suspend-user command: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="lock-personality", description="[ADMIN] Lock user to specific personality")
@app_commands.describe(
    user="User to lock",
    personality="Personality to lock to (default, uwu, professional, creative, technical)"
)
async def lock_personality_command(interaction: discord.Interaction, user: discord.Member, personality: str):
    """Admin command to lock user personalities"""
    if not bot.conversation_manager:
        await interaction.response.send_message("❌ LLM features are not available.", ephemeral=True)
        return
    
    try:
        admin_id = str(interaction.user.id)
        target_id = str(user.id)
        
        success, message = await bot.conversation_manager.lock_personality(admin_id, target_id, personality)
        
        if success:
            await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error in lock-personality command: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="test", description="Simple test command")
async def test_command(interaction: discord.Interaction):
    """Simple test command to debug Discord integration"""
    try:
        await interaction.response.send_message("✅ Bot is working! This is a test response.", ephemeral=True)
        logger.info(f"🧪 Test command worked for {interaction.user}")
    except Exception as e:
        logger.error(f"❌ Test command failed: {e}")
        try:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
        except:
            pass

def main():
    """Main bot runner"""
    # Get Discord token from environment
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    logger.info("🚀 Starting Discord bot...")
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"❌ Bot failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
