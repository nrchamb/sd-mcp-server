#!/usr/bin/env python3
"""
MCP Configuration Utility

Centralized MCP.json path management and configuration loading.
Provides a single source of truth for MCP.json location across the entire codebase.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class MCPConfig:
    """
    Centralized MCP.json configuration manager
    
    Handles auto-detection, path configuration, and environment variable loading
    from MCP.json files across different platforms and installations.
    """
    
    def __init__(self, custom_path: Optional[str] = None):
        """
        Initialize MCP configuration manager
        
        Args:
            custom_path: Optional custom path to MCP.json file
        """
        self._mcp_path: Optional[Path] = None
        self._env_vars: Dict[str, str] = {}
        self._loaded = False
        
        if custom_path:
            self.set_mcp_path(custom_path)
        else:
            self.auto_detect_mcp_path()
    
    @property
    def mcp_path(self) -> Optional[Path]:
        """Get current MCP.json path"""
        return self._mcp_path
    
    @property
    def env_vars(self) -> Dict[str, str]:
        """Get loaded environment variables"""
        return self._env_vars.copy()
    
    @property
    def is_loaded(self) -> bool:
        """Check if MCP.json has been successfully loaded"""
        return self._loaded
    
    def set_mcp_path(self, path: str) -> bool:
        """
        Set custom MCP.json path
        
        Args:
            path: Path to MCP.json file
            
        Returns:
            bool: True if path is valid and accessible
        """
        try:
            mcp_path = Path(path)
            if mcp_path.exists() and mcp_path.is_file():
                self._mcp_path = mcp_path
                self._loaded = False  # Reset loaded status
                logger.info(f"MCP.json path set to: {mcp_path}")
                return True
            else:
                logger.warning(f"MCP.json path does not exist: {mcp_path}")
                return False
        except Exception as e:
            logger.error(f"Error setting MCP.json path: {e}")
            return False
    
    def get_common_mcp_paths(self) -> List[Path]:
        """
        Get list of common MCP.json file locations
        
        Returns:
            List[Path]: Common paths where MCP.json might be located
        """
        home = Path.home()
        
        return [
            # LM Studio default locations
            home / ".cache" / "lm-studio" / "mcp.json",  # Linux/macOS default
            home / "AppData" / "Roaming" / "LM Studio" / "mcp.json",  # Windows
            home / "Library" / "Application Support" / "LM Studio" / "mcp.json",  # macOS alternative
            home / ".config" / "lm-studio" / "mcp.json",  # Linux alternative
            
            # Development/local locations
            Path.cwd() / "mcp.json",  # Current working directory
            Path.cwd().parent / "mcp.json",  # Parent directory
            
            # Environment variable override
            Path(os.getenv("MCP_JSON_PATH", "/nonexistent")),
            
            # User-specific path from CLAUDE.md (if it exists)
            Path("/Users/nickchamberlain/.cache/lm-studio/mcp.json"),
        ]
    
    def auto_detect_mcp_path(self) -> bool:
        """
        Auto-detect MCP.json file location
        
        Returns:
            bool: True if MCP.json file was found and set
        """
        logger.info("Auto-detecting MCP.json location...")
        
        # Check environment variable first
        env_path = os.getenv("MCP_JSON_PATH")
        if env_path:
            logger.info(f"Using MCP_JSON_PATH environment variable: {env_path}")
            if self.set_mcp_path(env_path):
                return True
        
        # Check common locations
        for path in self.get_common_mcp_paths():
            if path.exists() and path.is_file():
                logger.info(f"Found MCP.json at: {path}")
                self._mcp_path = path
                return True
        
        logger.warning("No MCP.json file found in common locations")
        logger.info("Set MCP_JSON_PATH environment variable or use custom path")
        return False
    
    def load_config(self) -> bool:
        """
        Load configuration from MCP.json file
        
        Returns:
            bool: True if configuration was loaded successfully
        """
        if not self._mcp_path:
            logger.error("No MCP.json path configured")
            return False
        
        try:
            with open(self._mcp_path, 'r') as f:
                mcp_config = json.load(f)
            
            # Extract SD_MCP_Server environment variables
            sd_server = mcp_config.get("mcpServers", {}).get("SD_MCP_Server", {})
            env_vars = sd_server.get("env", {})
            
            if env_vars:
                self._env_vars = {k: str(v) for k, v in env_vars.items()}
                logger.info(f"Loaded {len(self._env_vars)} environment variables from MCP.json")
                self._loaded = True
                return True
            else:
                logger.warning("No SD_MCP_Server environment variables found in MCP.json")
                return False
                
        except FileNotFoundError:
            logger.error(f"MCP.json file not found: {self._mcp_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP.json: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading MCP.json: {e}")
            return False
    
    def load_into_environment(self) -> bool:
        """
        Load MCP.json configuration into os.environ
        
        Returns:
            bool: True if environment variables were set successfully
        """
        if not self.load_config():
            return False
        
        # Set environment variables
        for key, value in self._env_vars.items():
            os.environ[key] = value
        
        logger.info(f"Set {len(self._env_vars)} environment variables from MCP.json")
        return True
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get summary of current configuration
        
        Returns:
            Dict[str, Any]: Configuration summary
        """
        return {
            "mcp_path": str(self._mcp_path) if self._mcp_path else None,
            "mcp_exists": self._mcp_path.exists() if self._mcp_path else False,
            "loaded": self._loaded,
            "env_var_count": len(self._env_vars),
            "env_vars": list(self._env_vars.keys()) if self._env_vars else []
        }


# Global instance for easy access
_global_mcp_config: Optional[MCPConfig] = None

def get_mcp_config(custom_path: Optional[str] = None) -> MCPConfig:
    """
    Get global MCP configuration instance
    
    Args:
        custom_path: Optional custom path to MCP.json file
        
    Returns:
        MCPConfig: Global configuration instance
    """
    global _global_mcp_config
    
    if _global_mcp_config is None or custom_path:
        _global_mcp_config = MCPConfig(custom_path)
    
    return _global_mcp_config

def load_mcp_environment(custom_path: Optional[str] = None) -> bool:
    """
    Convenience function to load MCP.json into environment variables
    
    Args:
        custom_path: Optional custom path to MCP.json file
        
    Returns:
        bool: True if environment variables were loaded successfully
    """
    config = get_mcp_config(custom_path)
    return config.load_into_environment()