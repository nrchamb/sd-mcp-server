"""
Claude (Anthropic) Provider - MINIMAL STUB FOR USER CONFIGURATION
Users must add their own API key and customize as needed
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
from .base_provider import BaseLLMProvider, LLMMessage, LLMResponse, MessageRole

# TODO: Users should install anthropic package: pip install anthropic
# from anthropic import AsyncAnthropic

class ClaudeProvider(BaseLLMProvider):
    """Claude (Anthropic) provider - USER MUST CONFIGURE"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # TODO: Users must provide their API key in MCP.json:
        # "CLAUDE_API_KEY": "your-api-key-here"
        # "CLAUDE_MODEL": "claude-3-5-sonnet-20241022" (or claude-3-opus-20240229, etc.)
        # "CLAUDE_MAX_TOKENS": 4096
        
        self.api_key = config.get("CLAUDE_API_KEY", "")
        self.default_model_name = config.get("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        self.max_tokens = config.get("CLAUDE_MAX_TOKENS", 4096)
        
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY is required in MCP configuration")
    
    async def chat(self, messages: List[LLMMessage], max_tokens: Optional[int] = None, temperature: Optional[float] = None, **kwargs) -> LLMResponse:
        """TODO: Implement Claude chat completion"""
        # Example implementation structure:
        # client = AsyncAnthropic(api_key=self.api_key)
        # 
        # # Convert messages - Claude has different format for system messages
        # system_message = None
        # chat_messages = []
        # for msg in messages:
        #     if msg.role == MessageRole.SYSTEM:
        #         system_message = msg.content
        #     else:
        #         chat_messages.append({"role": msg.role.value, "content": msg.content})
        #
        # response = await client.messages.create(
        #     model=kwargs.get("model", self.default_model_name),
        #     max_tokens=max_tokens or self.max_tokens,
        #     temperature=temperature,
        #     system=system_message,
        #     messages=chat_messages
        # )
        # return LLMResponse(...)
        
        return LLMResponse(
            content="Claude provider not implemented - please configure",
            success=False,
            provider="claude",
            error="Provider requires user configuration"
        )
    
    async def chat_stream(self, messages: List[LLMMessage], max_tokens: Optional[int] = None, temperature: Optional[float] = None, **kwargs) -> AsyncGenerator[str, None]:
        """TODO: Implement Claude streaming"""
        yield "[Claude streaming not implemented - please configure]"
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """TODO: Implement Claude model listing"""
        # Claude doesn't have a models endpoint, return static list
        return [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"}
        ]
    
    async def health_check(self) -> bool:
        """TODO: Implement Claude health check"""
        return False
    
    @property
    def default_model(self) -> str:
        return self.default_model_name