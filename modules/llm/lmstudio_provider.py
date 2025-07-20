"""
LM Studio Provider Implementation - FULLY IMPLEMENTED
Connects to LM Studio via OpenAI-compatible API
"""

import httpx
import json
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from .base_provider import BaseLLMProvider, LLMMessage, LLMResponse, MessageRole

class LMStudioProvider(BaseLLMProvider):
    """LM Studio LLM provider implementation - COMPLETE"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("LM_STUDIO_BASE_URL", config.get("LM_STUDIO_URL", "http://localhost:1234")).rstrip('/')
        self.api_key = config.get("LM_STUDIO_API_KEY", "not-needed")  # LM Studio doesn't require real API key
        self.default_model_name = config.get("LM_STUDIO_DEFAULT_MODEL", "")
        self.timeout = int(config.get("LM_STUDIO_TIMEOUT", 60))
        
    async def chat(
        self, 
        messages: List[LLMMessage], 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """Send a chat completion request to LM Studio"""
        try:
            # Convert our message format to OpenAI format
            openai_messages = [
                {"role": msg.role.value, "content": msg.content}
                for msg in messages
            ]
            
            # Build request payload
            payload = {
                "model": kwargs.get("model", self.default_model_name),
                "messages": openai_messages,
                "stream": False
            }
            
            # Add optional parameters
            if max_tokens:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature
                
            # Add any additional LM Studio specific parameters
            if "top_p" in kwargs:
                payload["top_p"] = kwargs["top_p"]
            if "frequency_penalty" in kwargs:
                payload["frequency_penalty"] = kwargs["frequency_penalty"]
            if "presence_penalty" in kwargs:
                payload["presence_penalty"] = kwargs["presence_penalty"]
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract response content
                if data.get("choices") and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    
                    # Filter out thinking tags while preserving the actual response
                    content = self._filter_thinking_tags(content)
                    
                    return LLMResponse(
                        content=content,
                        success=True,
                        provider="lmstudio",
                        model=data.get("model"),
                        usage=data.get("usage"),
                        metadata={
                            "finish_reason": data["choices"][0].get("finish_reason"),
                            "response_data": data
                        }
                    )
                else:
                    return LLMResponse(
                        content="",
                        success=False,
                        provider="lmstudio",
                        error="No choices returned from LM Studio"
                    )
                    
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            return LLMResponse(
                content="",
                success=False,
                provider="lmstudio",
                error=error_msg
            )
        except Exception as e:
            return LLMResponse(
                content="",
                success=False,
                provider="lmstudio",
                error=str(e)
            )
    
    async def chat_stream(
        self, 
        messages: List[LLMMessage], 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Send a streaming chat completion request to LM Studio"""
        try:
            # Convert our message format to OpenAI format
            openai_messages = [
                {"role": msg.role.value, "content": msg.content}
                for msg in messages
            ]
            
            # Build request payload
            payload = {
                "model": kwargs.get("model", self.default_model_name),
                "messages": openai_messages,
                "stream": True
            }
            
            # Add optional parameters
            if max_tokens:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature
                
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            
                            if data_str.strip() == "[DONE]":
                                break
                                
                            try:
                                data = json.loads(data_str)
                                if data.get("choices") and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue  # Skip malformed JSON
                                
        except Exception as e:
            yield f"[Error: {str(e)}]"
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from LM Studio"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                data = response.json()
                
                return data.get("data", [])
                
        except Exception as e:
            print(f"[LMStudio] Failed to get models: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check if LM Studio is available and healthy"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception:
            return False
    
    @property
    def default_model(self) -> str:
        """Get the default model for LM Studio"""
        return self.default_model_name
    
    async def get_current_model(self) -> Optional[str]:
        """Get the currently loaded model in LM Studio"""
        models = await self.get_models()
        if models:
            # LM Studio typically returns the currently loaded model first
            return models[0].get("id", "")
        return None
    
    def _filter_thinking_tags(self, content: str) -> str:
        """Filter out thinking tags from LLM response while preserving the actual content"""
        import re
        
        # Remove thinking tags and their content
        # This handles both <think>...</think> and <thinking>...</thinking>
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)
        
        # Clean up any extra whitespace that might be left
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Remove excessive line breaks
        content = content.strip()
        
        return content