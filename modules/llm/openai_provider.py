"""
OpenAI Provider - MINIMAL STUB FOR USER CONFIGURATION
Users must add their own API key and customize as needed
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
from .base_provider import BaseLLMProvider, LLMMessage, LLMResponse, MessageRole

# TODO: Users should install openai package: pip install openai
# from openai import AsyncOpenAI

class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider - USER MUST CONFIGURE"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # TODO: Users must provide their API key in MCP.json:
        # "OPENAI_API_KEY": "your-api-key-here"
        # "OPENAI_MODEL": "gpt-4" (or gpt-3.5-turbo, etc.)
        # "OPENAI_BASE_URL": "https://api.openai.com/v1" (optional, for custom endpoints)
        
        self.api_key = config.get("OPENAI_API_KEY", "")
        self.default_model_name = config.get("OPENAI_MODEL", "gpt-3.5-turbo")
        self.base_url = config.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required in MCP configuration")
    
    async def chat(self, messages: List[LLMMessage], max_tokens: Optional[int] = None, temperature: Optional[float] = None, **kwargs) -> LLMResponse:
        """TODO: Implement OpenAI chat completion"""
        # Example implementation structure:
        # client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        # response = await client.chat.completions.create(
        #     model=kwargs.get("model", self.default_model_name),
        #     messages=[{"role": msg.role.value, "content": msg.content} for msg in messages],
        #     max_tokens=max_tokens,
        #     temperature=temperature
        # )
        # return LLMResponse(...)
        
        return LLMResponse(
            content="OpenAI provider not implemented - please configure",
            success=False,
            provider="openai",
            error="Provider requires user configuration"
        )
    
    async def chat_stream(self, messages: List[LLMMessage], max_tokens: Optional[int] = None, temperature: Optional[float] = None, **kwargs) -> AsyncGenerator[str, None]:
        """TODO: Implement OpenAI streaming"""
        yield "[OpenAI streaming not implemented - please configure]"
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """TODO: Implement OpenAI model listing"""
        return []
    
    async def health_check(self) -> bool:
        """TODO: Implement OpenAI health check"""
        return False
    
    @property
    def default_model(self) -> str:
        return self.default_model_name