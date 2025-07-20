"""
Gemini (Google) Provider - MINIMAL STUB FOR USER CONFIGURATION
Users must add their own API key and customize as needed
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
from .base_provider import BaseLLMProvider, LLMMessage, LLMResponse, MessageRole

# TODO: Users should install google-generativeai package: pip install google-generativeai
# import google.generativeai as genai

class GeminiProvider(BaseLLMProvider):
    """Gemini (Google) provider - USER MUST CONFIGURE"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # TODO: Users must provide their API key in MCP.json:
        # "GEMINI_API_KEY": "your-api-key-here"
        # "GEMINI_MODEL": "gemini-1.5-pro" (or gemini-1.5-flash, etc.)
        
        self.api_key = config.get("GEMINI_API_KEY", "")
        self.default_model_name = config.get("GEMINI_MODEL", "gemini-1.5-pro")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required in MCP configuration")
    
    async def chat(self, messages: List[LLMMessage], max_tokens: Optional[int] = None, temperature: Optional[float] = None, **kwargs) -> LLMResponse:
        """TODO: Implement Gemini chat completion"""
        # Example implementation structure:
        # genai.configure(api_key=self.api_key)
        # model = genai.GenerativeModel(kwargs.get("model", self.default_model_name))
        # 
        # # Convert messages - Gemini has different format
        # chat_history = []
        # current_message = ""
        # for msg in messages:
        #     if msg.role == MessageRole.USER:
        #         current_message = msg.content
        #     elif msg.role == MessageRole.ASSISTANT:
        #         chat_history.append({"role": "user", "parts": [current_message]})
        #         chat_history.append({"role": "model", "parts": [msg.content]})
        #
        # chat = model.start_chat(history=chat_history)
        # response = await chat.send_message_async(
        #     current_message,
        #     generation_config=genai.types.GenerationConfig(
        #         max_output_tokens=max_tokens,
        #         temperature=temperature
        #     )
        # )
        # return LLMResponse(...)
        
        return LLMResponse(
            content="Gemini provider not implemented - please configure",
            success=False,
            provider="gemini",
            error="Provider requires user configuration"
        )
    
    async def chat_stream(self, messages: List[LLMMessage], max_tokens: Optional[int] = None, temperature: Optional[float] = None, **kwargs) -> AsyncGenerator[str, None]:
        """TODO: Implement Gemini streaming"""
        yield "[Gemini streaming not implemented - please configure]"
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """TODO: Implement Gemini model listing"""
        # Example static list - users should implement dynamic fetching
        return [
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
            {"id": "gemini-pro", "name": "Gemini Pro"}
        ]
    
    async def health_check(self) -> bool:
        """TODO: Implement Gemini health check"""
        return False
    
    @property
    def default_model(self) -> str:
        return self.default_model_name