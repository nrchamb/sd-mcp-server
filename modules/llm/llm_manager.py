"""
LLM Manager - Provider Switching and Management
Handles provider selection based on MCP configuration

IMPORTANT: Two separate provider types:
1. CHAT_LLM_PROVIDER - For Discord chat/conversation (user choice)
2. IMAGE_LLM_PROVIDER - For SD integration (ALWAYS LM Studio for local integration)
"""

from typing import Dict, Any, Optional, List
from .base_provider import BaseLLMProvider, LLMMessage, LLMResponse
from .lmstudio_provider import LMStudioProvider
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider

class LLMManager:
    """Manages LLM providers with separate chat and image generation providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Chat provider (user configurable)
        self.chat_provider: Optional[BaseLLMProvider] = None
        self.chat_provider_name = config.get("CHAT_LLM_PROVIDER", "lmstudio").lower()
        
        # Image generation provider (ALWAYS LM Studio for local integration)
        self.image_provider: Optional[LMStudioProvider] = None
        self.image_provider_name = "lmstudio"  # Always LM Studio
        
        # Initialize providers
        self._initialize_chat_provider()
        self._initialize_image_provider()
    
    def _initialize_chat_provider(self) -> None:
        """Initialize the chat LLM provider based on configuration switch"""
        try:
            if self.chat_provider_name == "lmstudio":
                print(f"[LLM Chat] Initializing LM Studio provider...")
                self.chat_provider = LMStudioProvider(self.config)
                
            elif self.chat_provider_name == "openai":
                print(f"[LLM Chat] Initializing OpenAI provider...")
                self.chat_provider = OpenAIProvider(self.config)
                
            elif self.chat_provider_name == "claude":
                print(f"[LLM Chat] Initializing Claude provider...")
                self.chat_provider = ClaudeProvider(self.config)
                
            elif self.chat_provider_name == "gemini":
                print(f"[LLM Chat] Initializing Gemini provider...")
                self.chat_provider = GeminiProvider(self.config)
                
            else:
                print(f"[LLM Chat] ❌ Unknown provider: {self.chat_provider_name}")
                print(f"[LLM Chat] Available providers: lmstudio, openai, claude, gemini")
                print(f"[LLM Chat] Falling back to LM Studio...")
                self.chat_provider = LMStudioProvider(self.config)
                
            print(f"[LLM Chat] ✅ Provider '{self.chat_provider_name}' initialized successfully")
            
        except Exception as e:
            print(f"[LLM Chat] ❌ Failed to initialize provider '{self.chat_provider_name}': {e}")
            print(f"[LLM Chat] Falling back to disabled state")
            self.chat_provider = None
    
    def _initialize_image_provider(self) -> None:
        """Initialize the image generation LLM provider (ALWAYS LM Studio)"""
        try:
            print(f"[LLM Image] Initializing LM Studio provider for SD integration...")
            self.image_provider = LMStudioProvider(self.config)
            print(f"[LLM Image] ✅ LM Studio provider initialized for image generation")
            
        except Exception as e:
            print(f"[LLM Image] ❌ Failed to initialize LM Studio provider: {e}")
            print(f"[LLM Image] Image generation LLM features will be disabled")
            self.image_provider = None
    
    # ============ CHAT METHODS (User-configurable provider) ============
    
    async def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """Send a chat request using the active chat provider"""
        if not self.chat_provider:
            return LLMResponse(
                content="Chat LLM provider not available",
                success=False,
                provider="none",
                error="No chat LLM provider initialized"
            )
        
        return await self.chat_provider.chat(messages, **kwargs)
    
    async def simple_chat(self, user_message: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """Simple chat interface for single message conversations"""
        if not self.chat_provider:
            return LLMResponse(
                content="Chat LLM provider not available",
                success=False,
                provider="none",
                error="No chat LLM provider initialized"
            )
        
        messages = []
        
        # Add system message if provided
        if system_prompt:
            messages.append(self.chat_provider.system_message(system_prompt))
        
        # Add user message
        messages.append(self.chat_provider.user_message(user_message))
        
        return await self.chat_provider.chat(messages, **kwargs)
    
    async def chat_health_check(self) -> bool:
        """Check if the chat provider is healthy"""
        if not self.chat_provider:
            return False
        
        return await self.chat_provider.health_check()
    
    async def get_chat_models(self) -> List[Dict[str, Any]]:
        """Get available models from the chat provider"""
        if not self.chat_provider:
            return []
        
        return await self.chat_provider.get_models()
    
    # ============ IMAGE GENERATION METHODS (Always LM Studio) ============
    
    async def enhance_prompt(self, user_prompt: str, **kwargs) -> LLMResponse:
        """Use LM Studio to enhance SD prompts for better image generation"""
        if not self.image_provider:
            return LLMResponse(
                content=user_prompt,  # Return original if no LLM
                success=False,
                provider="none",
                error="Image LLM provider not available"
            )
        
        system_prompt = """You are an expert at creating detailed prompts for Stable Diffusion image generation.
Your job is to enhance user prompts to create better, more detailed images while preserving the user's intent.

Rules:
1. Keep the core concept from the user's prompt
2. Add artistic style, lighting, composition details
3. Include quality tags like "masterpiece, best quality, highly detailed"
4. Suggest appropriate aspect ratios or settings if relevant
5. Keep the enhanced prompt under 200 words
6. Focus on visual details that will improve the final image

Return ONLY the enhanced prompt, no explanations."""
        
        return await self.image_provider.chat([
            self.image_provider.system_message(system_prompt),
            self.image_provider.user_message(f"Enhance this Stable Diffusion prompt: {user_prompt}")
        ], **kwargs)
    
    async def analyze_image_result(self, prompt: str, generation_info: Dict[str, Any]) -> LLMResponse:
        """Use LM Studio to analyze image generation results and suggest improvements"""
        if not self.image_provider:
            return LLMResponse(
                content="Image analysis not available",
                success=False,
                provider="none",
                error="Image LLM provider not available"
            )
        
        system_prompt = """You are an expert at analyzing Stable Diffusion image generation results.
Given a prompt and generation info, provide helpful feedback and suggestions.

Focus on:
1. How the prompt could be improved
2. Settings adjustments (steps, CFG, sampler)
3. Style or composition suggestions
4. Alternative approaches

Keep responses concise and actionable."""
        
        info_text = f"Prompt: {prompt}\nGeneration Info: {generation_info}"
        
        return await self.image_provider.chat([
            self.image_provider.system_message(system_prompt),
            self.image_provider.user_message(f"Analyze this image generation: {info_text}")
        ])
    
    async def image_health_check(self) -> bool:
        """Check if the image LLM provider (LM Studio) is healthy"""
        if not self.image_provider:
            return False
        
        return await self.image_provider.health_check()
    
    # ============ GENERAL INFO METHODS ============
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about both providers"""
        return {
            "chat_provider": {
                "name": self.chat_provider_name,
                "available": self.chat_provider is not None,
                "class": self.chat_provider.__class__.__name__ if self.chat_provider else None,
                "default_model": self.chat_provider.default_model if self.chat_provider else None
            },
            "image_provider": {
                "name": self.image_provider_name,
                "available": self.image_provider is not None,
                "class": self.image_provider.__class__.__name__ if self.image_provider else None,
                "default_model": self.image_provider.default_model if self.image_provider else None
            }
        }
    
    @staticmethod
    def get_available_providers() -> List[str]:
        """Get list of all available chat providers"""
        return ["lmstudio", "openai", "claude", "gemini"]
    
    @staticmethod
    def get_mcp_config_example() -> Dict[str, str]:
        """Get example MCP configuration for LLM providers"""
        return {
            # Chat provider selection (CONFIGURABLE)
            "CHAT_LLM_PROVIDER": "lmstudio",  # Options: lmstudio, openai, claude, gemini
            
            # NOTE: Image generation ALWAYS uses LM Studio for local integration
            
            # LM Studio configuration (FULLY IMPLEMENTED)
            "LM_STUDIO_URL": "http://localhost:1234",
            "LM_STUDIO_DEFAULT_MODEL": "",  # Auto-detect current model
            "LM_STUDIO_TIMEOUT": "60",
            
            # OpenAI configuration (USER MUST IMPLEMENT)
            "OPENAI_API_KEY": "your-openai-api-key",
            "OPENAI_MODEL": "gpt-3.5-turbo",
            "OPENAI_BASE_URL": "https://api.openai.com/v1",
            
            # Claude configuration (USER MUST IMPLEMENT)
            "CLAUDE_API_KEY": "your-claude-api-key",
            "CLAUDE_MODEL": "claude-3-5-sonnet-20241022",
            "CLAUDE_MAX_TOKENS": "4096",
            
            # Gemini configuration (USER MUST IMPLEMENT)
            "GEMINI_API_KEY": "your-gemini-api-key",
            "GEMINI_MODEL": "gemini-1.5-pro"
        }