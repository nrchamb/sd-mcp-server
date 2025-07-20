"""
Configuration module for SD MCP Server

Provides centralized configuration management, including MCP.json path handling
and environment variable loading.
"""

from .mcp_config import MCPConfig, get_mcp_config, load_mcp_environment

__all__ = ['MCPConfig', 'get_mcp_config', 'load_mcp_environment']