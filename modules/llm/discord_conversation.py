"""
Discord Conversation Manager - LLM Integration
Handles Discord → LLM conversations with personality switching and context isolation

CONVERSATION MODES:
1. /chat command - Explicit chat requests
2. @mention - Bot responds to mentions
3. Thread conversations - Continuous context in threads
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import discord
from discord.ext import commands

from .llm_manager import LLMManager
from .llm_database import LLMDatabase
from .base_provider import LLMMessage, MessageRole
from .prompt_enhancement import ChatImageIntegration

logger = logging.getLogger('DiscordConversation')

class PersonalityView(discord.ui.View):
    """Interactive personality switching buttons"""
    
    def __init__(self, conversation_manager, user_id: str, personalities: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.conversation_manager = conversation_manager
        self.user_id = user_id
        
        # Add personality buttons immediately
        self._add_personality_buttons(personalities)
    
    def _add_personality_buttons(self, personalities: List[Dict[str, Any]]):
        """Add buttons for each available personality"""
        # Limit to 5 personalities per row, max 25 total (Discord limit)
        for i, personality in enumerate(personalities[:25]):
            button = discord.ui.Button(
                label=personality['display_name'],
                emoji=personality['emoji'],
                style=discord.ButtonStyle.secondary,
                custom_id=f"personality_{personality['name']}",
                row=i // 5
            )
            button.callback = self._create_personality_callback(personality['name'])
            self.add_item(button)
    
    def _create_personality_callback(self, personality_name: str):
        """Create callback function for personality button"""
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ You can only change your own personality!", ephemeral=True)
                return
            
            # Update personality
            success = await self.conversation_manager.db.update_user_personality(self.user_id, personality_name)
            
            if success:
                personality = await self.conversation_manager.db.get_personality(personality_name)
                await interaction.response.send_message(
                    f"✅ Personality changed to **{personality['display_name']}** {personality['emoji']}\n"
                    f"_{personality['description']}_", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Could not change personality (it may be locked by an admin)", 
                    ephemeral=True
                )
        
        return callback

class DiscordConversationManager:
    """Manages Discord → LLM conversations with context isolation and personality switching"""
    
    def __init__(self, config: Dict[str, Any], db_path: str = "discord_llm.db", mcp_server_caller=None):
        self.config = config
        self.llm_manager = LLMManager(config)
        self.db = LLMDatabase(db_path, config)
        
        # Initialize chat-image integration
        self.chat_image_integration = ChatImageIntegration(self.llm_manager, mcp_server_caller)
        
        # Rate limiting settings from config
        self.rate_limit_chat = int(config.get('CHAT_RATE_LIMIT_PER_MINUTE', 10))
        self.rate_limit_generate = int(config.get('GENERATE_RATE_LIMIT_PER_MINUTE', 5))
        
        # Admin user IDs (should be configured in MCP.json)
        admin_ids = config.get('DISCORD_ADMIN_IDS', '')
        self.admin_ids = set(admin_ids.split(',')) if admin_ids else set()
        
        logger.info(f"[ConversationManager] Initialized with {len(self.admin_ids)} admin(s)")
        logger.info(f"[ConversationManager] LLM Provider: {self.llm_manager.get_provider_info()}")
        logger.info(f"[ConversationManager] Image Integration: {'Enabled' if self.chat_image_integration.integration_enabled else 'Disabled'}")
    
    async def is_admin(self, user_id: str) -> bool:
        """Check if user is an admin"""
        return user_id in self.admin_ids
    
    async def check_user_permissions(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """Check if user can use LLM features. Returns (allowed, reason)"""
        # Check moderation status
        status = await self.db.check_user_status(user_id)
        
        if status['status'] == 'suspended':
            return False, f"Account suspended: {status.get('reason', 'No reason provided')}"
        
        if status['status'] == 'timeout':
            if status.get('timeout_until'):
                try:
                    timeout_until = datetime.fromisoformat(status['timeout_until'])
                    if datetime.now() < timeout_until:
                        return False, f"Timed out until: {timeout_until.strftime('%Y-%m-%d %H:%M:%S')}"
                except:
                    pass
        
        # Check rate limiting
        allowed, seconds_until_reset = await self.db.check_rate_limit(user_id, 'chat', self.rate_limit_chat)
        if not allowed:
            return False, f"Rate limited. Try again in {seconds_until_reset} seconds."
        
        return True, None
    
    async def get_user_personality(self, user_id: str) -> Dict[str, Any]:
        """Get user's current personality settings"""
        user_settings = await self.db.get_user_settings(user_id)
        personality_name = user_settings.get('personality', 'default')
        
        personality = await self.db.get_personality(personality_name)
        if not personality:
            # Fallback to default if personality not found
            personality = await self.db.get_personality('default')
        
        return personality or {
            'name': 'default',
            'display_name': 'Default Assistant',
            'system_prompt': 'You are a helpful AI assistant.',
            'description': 'Standard assistant',
            'emoji': '🤖'
        }
    
    async def handle_chat_command(self, interaction: discord.Interaction, message: str) -> None:
        """Handle /chat slash command"""
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        
        # Check permissions
        allowed, reason = await self.check_user_permissions(user_id)
        if not allowed:
            await interaction.followup.send(f"❌ {reason}", ephemeral=True)
            return
        
        # Generate context key
        context_key = self.db.generate_context_key(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            thread_id=getattr(interaction.channel, 'parent_id', None) if isinstance(interaction.channel, discord.Thread) else None,
            user_id=interaction.user.id if not interaction.guild_id else None
        )
        
        # Get conversation response
        response = await self._get_llm_response(user_id, context_key, message)
        
        # Record rate limit action
        await self.db.record_action(user_id, 'chat', context_key)
        
        # Send response and handle image generation
        if response.success:
            # Check if this is an image generation response
            generation_data = response.metadata.get('generation_data') if hasattr(response, 'metadata') and response.metadata else None
            
            # Split long responses if needed
            chunks = self._split_response(response.content)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.followup.send(chunk)
            
            # Handle image generation if requested
            if generation_data and generation_data.get('action') == 'generate':
                await self._trigger_image_generation(interaction, generation_data, user_id)
            
        else:
            await interaction.followup.send(f"❌ **Error:** {response.error}")
    
    async def handle_mention(self, message: discord.Message) -> None:
        """Handle bot mentions in regular messages"""
        user_id = str(message.author.id)
        
        # Check permissions
        allowed, reason = await self.check_user_permissions(user_id)
        if not allowed:
            await message.reply(f"❌ {reason}")
            return
        
        # Extract message content (remove bot mention)
        content = message.content
        for mention in message.mentions:
            if mention.bot:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
        content = content.strip()
        
        if not content:
            await message.reply("👋 Hi! Ask me something!")
            return
        
        # Generate context key
        context_key = self.db.generate_context_key(
            guild_id=message.guild.id if message.guild else None,
            channel_id=message.channel.id,
            thread_id=message.channel.id if isinstance(message.channel, discord.Thread) else None,
            user_id=message.author.id if not message.guild else None
        )
        
        # Show typing indicator
        async with message.channel.typing():
            # Get conversation response
            response = await self._get_llm_response(user_id, context_key, content)
        
        # Record rate limit action
        await self.db.record_action(user_id, 'chat', context_key)
        
        # Send response
        if response.success:
            chunks = self._split_response(response.content)
            for chunk in chunks:
                await message.reply(chunk)
        else:
            await message.reply(f"❌ **Error:** {response.error}")
    
    async def handle_thread_message(self, message: discord.Message) -> None:
        """Handle messages in threads where bot is active"""
        # Only respond in threads where bot has been mentioned or used /chat
        thread_context_key = f"thread_{message.channel.id}"
        
        # Check if bot has any conversation history in this thread
        history = await self.db.get_conversation_history(thread_context_key, limit=1)
        if not history:
            return  # Bot hasn't been active in this thread
        
        user_id = str(message.author.id)
        
        # Check permissions
        allowed, reason = await self.check_user_permissions(user_id)
        if not allowed:
            return  # Don't spam threads with error messages
        
        # Get conversation response
        async with message.channel.typing():
            response = await self._get_llm_response(user_id, thread_context_key, message.content)
        
        # Record rate limit action
        await self.db.record_action(user_id, 'chat', thread_context_key)
        
        # Send response
        if response.success:
            chunks = self._split_response(response.content)
            for chunk in chunks:
                await message.reply(chunk)
    
    async def _get_llm_response(self, user_id: str, context_key: str, user_message: str) -> Any:
        """Get LLM response with conversation history and personality"""
        try:
            # Get user personality
            personality = await self.get_user_personality(user_id)
            
            # Get conversation history
            user_settings = await self.db.get_user_settings(user_id)
            max_context = user_settings.get('max_context_messages', 20)
            history = await self.db.get_conversation_history(context_key, limit=max_context)
            
            # Build message list
            messages = []
            
            # Add system prompt with personality
            messages.append(LLMMessage(
                role=MessageRole.SYSTEM,
                content=personality['system_prompt']
            ))
            
            # Add conversation history
            for msg in history:
                if msg['role'] == 'user':
                    messages.append(LLMMessage(role=MessageRole.USER, content=msg['content']))
                elif msg['role'] == 'assistant':
                    messages.append(LLMMessage(role=MessageRole.ASSISTANT, content=msg['content']))
            
            # Add current user message
            messages.append(LLMMessage(role=MessageRole.USER, content=user_message))
            
            # Check for image generation intent before normal LLM response
            chat_response, generation_data = await self.chat_image_integration.process_chat_message(user_message, user_id)
            
            if chat_response:
                # Use personality-specific image injection if available
                if generation_data and generation_data.get('action') in ['generate', 'suggest']:
                    image_prompt = personality.get('image_injection_prompt')
                    if image_prompt:
                        # Replace the system message with image injection prompt
                        image_messages = []
                        image_messages.append(LLMMessage(role=MessageRole.SYSTEM, content=image_prompt))
                        
                        # Add conversation history
                        for msg in history:
                            if msg['role'] == 'user':
                                image_messages.append(LLMMessage(role=MessageRole.USER, content=msg['content']))
                            elif msg['role'] == 'assistant':
                                image_messages.append(LLMMessage(role=MessageRole.ASSISTANT, content=msg['content']))
                        
                        # Add current message with image generation context
                        image_messages.append(LLMMessage(role=MessageRole.USER, content=f"Create an enhanced image prompt for: {user_message}"))
                        
                        # Get enhanced response with personality-specific image injection
                        image_response = await self.llm_manager.chat(
                            image_messages,
                            temperature=0.3,  # Lower temperature for more consistent image prompts
                            max_tokens=500
                        )
                        
                        if image_response.success:
                            # Use the enhanced prompt for image generation
                            if 'params' in generation_data:
                                generation_data['params']['prompt'] = image_response.content.strip()
                            
                            # Update the chat response to include the enhanced prompt
                            chat_response = f"🎨 **Enhanced with {personality['display_name']} style!**\n\n**Prompt:** {image_response.content.strip()}\n\n⏳ Starting generation..."
                
                # Store the image-related conversation
                await self.db.add_message(context_key, user_id, 'user', user_message)
                await self.db.add_message(context_key, user_id, 'assistant', chat_response)
                
                # Create custom response object with generation data
                from .base_provider import LLMResponse
                response = LLMResponse(
                    content=chat_response,
                    success=True,
                    provider="image_integration",
                    metadata={'generation_data': generation_data}
                )
                return response
            
            # Get regular LLM response
            response = await self.llm_manager.chat(
                messages,
                temperature=user_settings.get('temperature', 0.7),
                max_tokens=2000
            )
            
            # Store conversation in database
            await self.db.add_message(context_key, user_id, 'user', user_message)
            if response.success:
                await self.db.add_message(context_key, user_id, 'assistant', response.content)
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting LLM response: {e}")
            from .base_provider import LLMResponse
            return LLMResponse(
                content="Sorry, I encountered an error processing your request.",
                success=False,
                provider="error",
                error=str(e)
            )
    
    def _split_response(self, content: str, max_length: int = 2000) -> List[str]:
        """Split long responses into Discord-compatible chunks"""
        if len(content) <= max_length:
            return [content]
        
        chunks = []
        remaining = content
        
        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break
            
            # Find a good break point (sentence, paragraph, or space)
            break_point = max_length
            for delimiter in ['\n\n', '. ', '! ', '? ', '\n', ' ']:
                last_delimiter = remaining.rfind(delimiter, 0, max_length)
                if last_delimiter > max_length // 2:  # Don't break too early
                    break_point = last_delimiter + len(delimiter)
                    break
            
            chunks.append(remaining[:break_point].strip())
            remaining = remaining[break_point:].strip()
        
        return chunks
    
    # ============ ADMIN COMMANDS ============
    
    async def timeout_user(self, admin_user_id: str, target_user_id: str, minutes: int, reason: str) -> Tuple[bool, str]:
        """Admin command: timeout user for specified minutes"""
        if not await self.is_admin(admin_user_id):
            return False, "You are not authorized to use admin commands."
        
        if minutes <= 0 or minutes > 10080:  # Max 1 week
            return False, "Timeout must be between 1 minute and 1 week (10080 minutes)."
        
        success = await self.db.timeout_user(target_user_id, minutes, reason, admin_user_id)
        if success:
            return True, f"User <@{target_user_id}> timed out for {minutes} minutes. Reason: {reason}"
        else:
            return False, "Failed to timeout user."
    
    async def suspend_user(self, admin_user_id: str, target_user_id: str, reason: str) -> Tuple[bool, str]:
        """Admin command: suspend user indefinitely"""
        if not await self.is_admin(admin_user_id):
            return False, "You are not authorized to use admin commands."
        
        success = await self.db.suspend_user(target_user_id, reason, admin_user_id)
        if success:
            return True, f"User <@{target_user_id}> suspended. Reason: {reason}"
        else:
            return False, "Failed to suspend user."
    
    async def lock_personality(self, admin_user_id: str, target_user_id: str, personality: str) -> Tuple[bool, str]:
        """Admin command: lock user to specific personality"""
        if not await self.is_admin(admin_user_id):
            return False, "You are not authorized to use admin commands."
        
        # Check if personality exists
        personality_data = await self.db.get_personality(personality)
        if not personality_data:
            available = await self.db.get_all_personalities()
            personality_list = ", ".join([p['name'] for p in available])
            return False, f"Personality '{personality}' not found. Available: {personality_list}"
        
        success = await self.db.lock_personality(target_user_id, personality, admin_user_id)
        if success:
            return True, f"User <@{target_user_id}> locked to personality '{personality_data['display_name']}' {personality_data['emoji']}"
        else:
            return False, "Failed to lock personality."
    
    async def get_personality_view(self, user_id: str) -> PersonalityView:
        """Get personality switching view for user"""
        personalities = await self.db.get_all_personalities()
        return PersonalityView(self, user_id, personalities)
    
    async def _trigger_image_generation(self, interaction: discord.Interaction, generation_data: Dict[str, Any], user_id: str) -> None:
        """Trigger image generation from LLM conversation"""
        try:
            if not self.chat_image_integration.mcp_server_caller:
                await interaction.followup.send("❌ Image generation not available (no MCP server connection)")
                return
            
            # Check rate limits for generation
            allowed, seconds_until_reset = await self.db.check_rate_limit(user_id, 'generate', self.rate_limit_generate)
            if not allowed:
                await interaction.followup.send(f"🕒 Generation rate limited. Try again in {seconds_until_reset} seconds.")
                return
            
            # Get parameters from generation data
            params = generation_data.get('params', {})
            enhanced_prompt = generation_data.get('enhanced_prompt')
            
            # Use sensible defaults if parameters missing
            generation_params = {
                'prompt': params.get('prompt', 'beautiful landscape'),
                'negative_prompt': params.get('negative_prompt', 'low quality, blurry'),
                'steps': params.get('steps', 25),
                'width': params.get('width', 512),
                'height': params.get('height', 512),
                'cfg_scale': params.get('cfg_scale', 8),
                'user_id': user_id
            }
            
            # Record generation action for rate limiting
            await self.db.record_action(user_id, 'generate')
            
            # Call MCP server to generate image
            result = await self.chat_image_integration.mcp_server_caller('generate_image', **generation_params)
            
            if result.get('success'):
                # Send success message with image info
                image_info = result.get('result', {})
                response_text = f"✅ **Image Generated Successfully!**\n"
                
                if enhanced_prompt:
                    response_text += f"**Enhanced Prompt:** {enhanced_prompt.enhanced_prompt}\n"
                    if enhanced_prompt.confidence > 0.7:
                        response_text += f"**Confidence:** {enhanced_prompt.confidence:.0%} 🎯\n"
                
                if image_info.get('image_url'):
                    response_text += f"**Link:** {image_info['image_url']}\n"
                
                response_text += f"**Parameters:** {params.get('steps', 25)} steps, CFG {params.get('cfg_scale', 8)}"
                
                await interaction.followup.send(response_text)
                
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                await interaction.followup.send(f"❌ **Generation Failed:** {error_msg}")
                
        except Exception as e:
            logger.error(f"Error triggering image generation: {e}")
            await interaction.followup.send(f"❌ **Generation Error:** {e}")
    
    async def enhance_prompt(self, prompt: str, context: Optional[str] = None):
        """Public method to enhance prompts for external use"""
        return await self.chat_image_integration.enhance_user_prompt(prompt, context)