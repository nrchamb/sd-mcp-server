#!/usr/bin/env python3
"""
Authentication Manager for Various API Services
Provides abstraction layer for different authentication methods
"""

import base64
import hashlib
import httpx
import asyncio
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

@dataclass
class AuthCredentials:
    """Base authentication credentials"""
    service: str
    auth_type: str  # "basic", "api_key", "token", "session"

@dataclass
class BasicAuthCredentials:
    """Basic username/password authentication"""
    service: str
    username: str
    password: str
    auth_type: str = "basic"

@dataclass
class APIKeyCredentials:
    """API key authentication"""
    service: str
    api_key: str
    header_name: str = "X-API-Key"
    auth_type: str = "api_key"

@dataclass
class TokenAuthCredentials:
    """Token-based authentication"""
    service: str
    token: str
    token_type: str = "Bearer"
    auth_type: str = "token"

@dataclass
class SessionAuthCredentials:
    """Session-based authentication"""
    service: str
    session_id: str
    cookie_name: str = "session"
    auth_type: str = "session"

class AuthProvider(ABC):
    """Abstract base class for authentication providers"""
    
    @abstractmethod
    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Authenticate the client"""
        pass
    
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        pass
    
    @abstractmethod
    def get_cookies(self) -> Dict[str, str]:
        """Get authentication cookies"""
        pass

class BasicAuthProvider(AuthProvider):
    """Basic authentication provider"""
    
    def __init__(self, credentials: BasicAuthCredentials):
        self.credentials = credentials
        self._auth_header = None
    
    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Set up basic authentication"""
        if not self.credentials.username or not self.credentials.password:
            return True  # No auth required
        
        # Create basic auth header
        auth_string = f"{self.credentials.username}:{self.credentials.password}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        self._auth_header = f"Basic {auth_b64}"
        
        logger.info(f"[Auth] Basic auth configured for {self.credentials.service}")
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        if self._auth_header:
            return {"Authorization": self._auth_header}
        return {}
    
    def get_cookies(self) -> Dict[str, str]:
        """Get authentication cookies"""
        return {}

class APIKeyAuthProvider(AuthProvider):
    """API key authentication provider"""
    
    def __init__(self, credentials: APIKeyCredentials):
        self.credentials = credentials
    
    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Set up API key authentication"""
        if not self.credentials.api_key:
            return True  # No auth required
        
        logger.info(f"[Auth] API key auth configured for {self.credentials.service}")
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        if self.credentials.api_key:
            return {self.credentials.header_name: self.credentials.api_key}
        return {}
    
    def get_cookies(self) -> Dict[str, str]:
        """Get authentication cookies"""
        return {}

class TokenAuthProvider(AuthProvider):
    """Token authentication provider"""
    
    def __init__(self, credentials: TokenAuthCredentials):
        self.credentials = credentials
    
    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Set up token authentication"""
        if not self.credentials.token:
            return True  # No auth required
        
        logger.info(f"[Auth] Token auth configured for {self.credentials.service}")
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        if self.credentials.token:
            return {"Authorization": f"{self.credentials.token_type} {self.credentials.token}"}
        return {}
    
    def get_cookies(self) -> Dict[str, str]:
        """Get authentication cookies"""
        return {}

class SessionAuthProvider(AuthProvider):
    """Session authentication provider"""
    
    def __init__(self, credentials: SessionAuthCredentials):
        self.credentials = credentials
    
    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Set up session authentication"""
        if not self.credentials.session_id:
            return True  # No auth required
        
        logger.info(f"[Auth] Session auth configured for {self.credentials.service}")
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        return {}
    
    def get_cookies(self) -> Dict[str, str]:
        """Get authentication cookies"""
        if self.credentials.session_id:
            return {self.credentials.cookie_name: self.credentials.session_id}
        return {}

class GradioAuthProvider(AuthProvider):
    """Gradio-specific authentication for SD WebUI"""
    
    def __init__(self, username: str, password: str, base_url: str):
        self.username = username
        self.password = password
        self.base_url = base_url
        self.session_cookies = {}
    
    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Authenticate with Gradio interface"""
        if not self.username or not self.password:
            logger.info("[Auth] No Gradio auth credentials provided")
            return True  # No auth required
        
        try:
            logger.info(f"[Auth] Attempting Gradio authentication for {self.base_url}")
            
            # Step 1: Get the main page to see if login is required
            main_response = await client.get(self.base_url)
            logger.info(f"[Auth] Main page status: {main_response.status_code}")
            
            # Check if authentication is required by looking for Gradio config
            page_text = main_response.text.lower()
            auth_required = (
                "login" in page_text or 
                main_response.status_code == 401 or
                '"auth_required":true' in page_text or
                '"auth_required": true' in page_text
            )
            
            if auth_required:
                logger.info("[Auth] Login required, attempting authentication")
                
                # Step 2: Try different login endpoints and methods
                login_endpoints = [
                    "/login",
                    "/api/login", 
                    ""  # Main page POST
                ]
                
                for endpoint in login_endpoints:
                    login_url = f"{self.base_url.rstrip('/')}{endpoint}"
                    logger.info(f"[Auth] Trying login endpoint: {login_url}")
                    
                    # Try form data
                    login_data = {
                        "username": self.username,
                        "password": self.password
                    }
                    
                    try:
                        response = await client.post(login_url, data=login_data)
                        logger.info(f"[Auth] Login attempt status: {response.status_code}")
                        
                        if response.status_code in [200, 302]:  # Success or redirect
                            # Store all cookies from the response
                            self.session_cookies.update(dict(response.cookies))
                            
                            # Verify authentication by checking main page again
                            verify_response = await client.get(self.base_url)
                            if verify_response.status_code == 200 and "login" not in verify_response.text.lower():
                                logger.info("[Auth] Gradio authentication successful")
                                return True
                                
                    except Exception as login_error:
                        logger.debug(f"[Auth] Login attempt failed: {login_error}")
                        continue
                
                # If all login attempts failed
                logger.error("[Auth] All login attempts failed")
                return False
            else:
                logger.info("[Auth] No login required, authentication not necessary")
                return True
                
        except Exception as e:
            logger.error(f"[Auth] Gradio authentication error: {e}")
            return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        return {}
    
    def get_cookies(self) -> Dict[str, str]:
        """Get authentication cookies"""
        return self.session_cookies

class AuthManager:
    """Central authentication manager for multiple services"""
    
    def __init__(self):
        self.providers: Dict[str, AuthProvider] = {}
    
    def add_provider(self, service: str, provider: AuthProvider):
        """Add authentication provider for a service"""
        self.providers[service] = provider
        logger.info(f"[AuthManager] Added {provider.__class__.__name__} for {service}")
    
    def add_basic_auth(self, service: str, username: str, password: str):
        """Add basic authentication for a service"""
        credentials = BasicAuthCredentials(service=service, username=username, password=password)
        provider = BasicAuthProvider(credentials)
        self.add_provider(service, provider)
    
    def add_api_key_auth(self, service: str, api_key: str, header_name: str = "X-API-Key"):
        """Add API key authentication for a service"""
        credentials = APIKeyCredentials(service=service, api_key=api_key, header_name=header_name)
        provider = APIKeyAuthProvider(credentials)
        self.add_provider(service, provider)
    
    def add_token_auth(self, service: str, token: str, token_type: str = "Bearer"):
        """Add token authentication for a service"""
        credentials = TokenAuthCredentials(service=service, token=token, token_type=token_type)
        provider = TokenAuthProvider(credentials)
        self.add_provider(service, provider)
    
    def add_gradio_auth(self, service: str, username: str, password: str, base_url: str):
        """Add Gradio authentication for SD WebUI"""
        provider = GradioAuthProvider(username, password, base_url)
        self.add_provider(service, provider)
    
    async def authenticate_service(self, service: str, client: httpx.AsyncClient) -> bool:
        """Authenticate a specific service"""
        if service not in self.providers:
            logger.info(f"[AuthManager] No auth provider for {service}")
            return True
        
        provider = self.providers[service]
        return await provider.authenticate(client)
    
    def get_auth_headers(self, service: str) -> Dict[str, str]:
        """Get authentication headers for a service"""
        if service not in self.providers:
            return {}
        
        return self.providers[service].get_headers()
    
    def get_auth_cookies(self, service: str) -> Dict[str, str]:
        """Get authentication cookies for a service"""
        if service not in self.providers:
            return {}
        
        return self.providers[service].get_cookies()
    
    async def create_authenticated_client(self, service: str, **client_kwargs) -> httpx.AsyncClient:
        """Create an authenticated HTTP client for a service"""
        # Get base headers and cookies
        headers = self.get_auth_headers(service)
        cookies = self.get_auth_cookies(service)
        
        # Merge with provided headers/cookies
        if 'headers' in client_kwargs:
            headers.update(client_kwargs['headers'])
        if 'cookies' in client_kwargs:
            cookies.update(client_kwargs['cookies'])
        
        client_kwargs['headers'] = headers
        client_kwargs['cookies'] = cookies
        
        # For basic auth, use httpx.BasicAuth if credentials available
        if service in self.providers:
            provider = self.providers[service]
            if isinstance(provider, BasicAuthProvider) and provider.credentials.username and provider.credentials.password:
                client_kwargs['auth'] = httpx.BasicAuth(provider.credentials.username, provider.credentials.password)
        
        # Create client (don't authenticate here to avoid client reuse issues)
        client = httpx.AsyncClient(**client_kwargs)
        
        return client
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get authentication status for all services"""
        status = {}
        
        for service, provider in self.providers.items():
            status[service] = {
                "provider_type": provider.__class__.__name__,
                "auth_type": getattr(provider, 'credentials', None) and provider.credentials.auth_type,
                "has_auth": bool(provider.get_headers() or provider.get_cookies())
            }
        
        return status

def create_auth_manager_from_env(env_dict: Dict[str, str]) -> AuthManager:
    """Create authentication manager from environment configuration"""
    auth_manager = AuthManager()
    
    # SD WebUI Authentication (try Gradio auth first, then Basic Auth)
    sd_username = env_dict.get("SD_WEBUI_USERNAME", "")
    sd_password = env_dict.get("SD_WEBUI_PASSWORD", "")
    sd_base_url = env_dict.get("SD_BASE_URL", "")
    
    if sd_username and sd_password:
        # Use Gradio auth for --gradio-auth setups
        auth_manager.add_gradio_auth("sd_webui", sd_username, sd_password, sd_base_url)
    
    # Chevereto Authentication
    chevereto_api_key = env_dict.get("CHEVERETO_GUEST_API_KEY", "")
    if chevereto_api_key:
        auth_manager.add_api_key_auth("chevereto", chevereto_api_key)
    
    chevereto_admin_key = env_dict.get("CHEVERETO_ADMIN_API_KEY", "")
    if chevereto_admin_key:
        auth_manager.add_api_key_auth("chevereto_admin", chevereto_admin_key)
    
    logger.info(f"[AuthManager] Created auth manager with {len(auth_manager.providers)} providers")
    return auth_manager

# Example usage
if __name__ == "__main__":
    async def test_auth_manager():
        # Test configuration
        env_config = {
            "SD_WEBUI_USERNAME": "admin",
            "SD_WEBUI_PASSWORD": "password",
            "SD_BASE_URL": "http://localhost:7860",
            "CHEVERETO_GUEST_API_KEY": "test_key"
        }
        
        # Create auth manager
        auth_manager = create_auth_manager_from_env(env_config)
        
        # Test client creation
        async with await auth_manager.create_authenticated_client("sd_webui") as client:
            # Test authenticated request
            response = await client.get("http://localhost:7860/api/v1/sd-models")
            print(f"SD WebUI Response: {response.status_code}")
        
        # Check status
        status = auth_manager.get_service_status()
        print(f"Auth Status: {status}")
    
    asyncio.run(test_auth_manager())