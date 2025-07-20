"""
Base LLM Provider Interface
Abstract base class that all LLM providers must implement
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user" 
    ASSISTANT = "assistant"

@dataclass
class LLMMessage:
    """Standardized message format for all LLM providers"""
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = None

@dataclass 
class LLMResponse:
    """Standardized response format for all LLM providers"""
    content: str
    success: bool
    provider: str
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = self.__class__.__name__.replace('Provider', '').lower()
    
    @abstractmethod
    async def chat(
        self, 
        messages: List[LLMMessage], 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """Send a chat completion request"""
        pass
    
    @abstractmethod
    async def chat_stream(
        self, 
        messages: List[LLMMessage], 
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Send a streaming chat completion request"""
        pass
    
    @abstractmethod
    async def get_models(self) -> List[Dict[str, Any]]:
        """Get list of available models"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and healthy"""
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider"""
        pass
    
    def create_message(self, role: MessageRole, content: str, **metadata) -> LLMMessage:
        """Helper to create properly formatted messages"""
        return LLMMessage(role=role, content=content, metadata=metadata)
    
    def system_message(self, content: str, **metadata) -> LLMMessage:
        """Helper to create system messages"""
        return self.create_message(MessageRole.SYSTEM, content, **metadata)
    
    def user_message(self, content: str, **metadata) -> LLMMessage:
        """Helper to create user messages"""
        return self.create_message(MessageRole.USER, content, **metadata)
    
    def assistant_message(self, content: str, **metadata) -> LLMMessage:
        """Helper to create assistant messages"""
        return self.create_message(MessageRole.ASSISTANT, content, **metadata)