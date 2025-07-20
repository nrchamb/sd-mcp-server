#!/usr/bin/env python3
"""
Lazy Tool Loading System for MCP Server
Reduces initial context usage by loading tool definitions without implementation code.
"""

import importlib
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ToolDefinition:
    """Lightweight tool definition without implementation"""
    name: str
    description: str
    parameters: Dict[str, Any]
    group: str
    module_path: str
    function_name: str
    priority: int = 5  # 1=high, 10=low
    dependencies: List[str] = None

@dataclass
class ResourceDefinition:
    """Lightweight resource definition without implementation"""
    name: str
    description: str
    uri: str
    module_path: str
    function_name: str
    group: str

class LazyToolRegistry:
    """Registry for lazy-loaded tools and resources"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.resources: Dict[str, ResourceDefinition] = {}
        self.loaded_modules: Dict[str, Any] = {}
        self.tool_groups: Dict[str, List[str]] = {}
        
    def register_tool(self, tool_def: ToolDefinition):
        """Register a tool definition"""
        self.tools[tool_def.name] = tool_def
        
        # Group tools
        if tool_def.group not in self.tool_groups:
            self.tool_groups[tool_def.group] = []
        self.tool_groups[tool_def.group].append(tool_def.name)
        
    def register_resource(self, resource_def: ResourceDefinition):
        """Register a resource definition"""
        self.resources[resource_def.name] = resource_def
        
    def get_tool_manifest(self) -> Dict[str, Any]:
        """Get lightweight manifest of all tools without loading implementations"""
        return {
            "tools": {
                name: {
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "group": tool.group,
                    "priority": tool.priority
                }
                for name, tool in self.tools.items()
            },
            "resources": {
                name: {
                    "description": resource.description,
                    "uri": resource.uri,
                    "group": resource.group
                }
                for name, resource in self.resources.items()
            },
            "groups": self.tool_groups,
            "stats": {
                "total_tools": len(self.tools),
                "total_resources": len(self.resources),
                "loaded_modules": len(self.loaded_modules)
            }
        }
    
    def load_tool(self, tool_name: str) -> Optional[Callable]:
        """Lazy load a specific tool implementation"""
        if tool_name not in self.tools:
            return None
            
        tool_def = self.tools[tool_name]
        
        # Load module if not already loaded
        if tool_def.module_path not in self.loaded_modules:
            try:
                module = importlib.import_module(tool_def.module_path)
                self.loaded_modules[tool_def.module_path] = module
                logger.info(f"Loaded module: {tool_def.module_path}")
            except ImportError as e:
                logger.error(f"Failed to load module {tool_def.module_path}: {e}")
                return None
        
        # Get function from module
        module = self.loaded_modules[tool_def.module_path]
        if hasattr(module, tool_def.function_name):
            return getattr(module, tool_def.function_name)
        
        logger.error(f"Function {tool_def.function_name} not found in {tool_def.module_path}")
        return None
    
    def load_resource(self, resource_name: str) -> Optional[Callable]:
        """Lazy load a specific resource implementation"""
        if resource_name not in self.resources:
            return None
            
        resource_def = self.resources[resource_name]
        
        # Load module if not already loaded
        if resource_def.module_path not in self.loaded_modules:
            try:
                module = importlib.import_module(resource_def.module_path)
                self.loaded_modules[resource_def.module_path] = module
                logger.info(f"Loaded module: {resource_def.module_path}")
            except ImportError as e:
                logger.error(f"Failed to load module {resource_def.module_path}: {e}")
                return None
        
        # Get function from module
        module = self.loaded_modules[resource_def.module_path]
        if hasattr(module, resource_def.function_name):
            return getattr(module, resource_def.function_name)
        
        logger.error(f"Function {resource_def.function_name} not found in {resource_def.module_path}")
        return None
    
    def preload_group(self, group_name: str):
        """Preload all tools in a specific group"""
        if group_name in self.tool_groups:
            for tool_name in self.tool_groups[group_name]:
                self.load_tool(tool_name)
    
    def get_group_tools(self, group_name: str) -> List[str]:
        """Get all tool names in a group"""
        return self.tool_groups.get(group_name, [])

# Global registry instance
tool_registry = LazyToolRegistry()

def define_sd_tools():
    """Define all SD tools without loading implementations"""
    
    # === Core Generation Tools (Priority 1) ===
    tool_registry.register_tool(ToolDefinition(
        name="generate_image",
        description="Generate an image using Stable Diffusion with comprehensive parameters",
        parameters={
            "prompt": {"type": "string", "description": "Text prompt for image generation"},
            "negative_prompt": {"type": "string", "description": "Negative prompt", "default": ""},
            "steps": {"type": "integer", "description": "Number of sampling steps", "default": 20},
            "width": {"type": "integer", "description": "Image width", "default": 512},
            "height": {"type": "integer", "description": "Image height", "default": 512},
            "cfg_scale": {"type": "number", "description": "CFG scale", "default": 7.0},
            "sampler": {"type": "string", "description": "Sampling method", "default": "DPM++ 2M"},
            "upload": {"type": "boolean", "description": "Auto-upload to Chevereto", "default": True},
            "seed": {"type": "integer", "description": "Random seed", "default": -1},
            "user_id": {"type": "string", "description": "Discord user ID", "default": ""},
            "album_name": {"type": "string", "description": "Album name", "default": ""}
        },
        group="generation",
        module_path="modules.stable_diffusion.core_tools",
        function_name="generate_image",
        priority=1
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="generate_image_batch",
        description="Generate multiple images in batch",
        parameters={
            "prompts": {"type": "array", "description": "List of prompts"},
            "shared_params": {"type": "object", "description": "Shared parameters for all images", "default": {}},
            "upload": {"type": "boolean", "description": "Auto-upload to Chevereto", "default": True},
            "user_id": {"type": "string", "description": "Discord user ID", "default": ""},
            "album_name": {"type": "string", "description": "Album name", "default": ""}
        },
        group="generation",
        module_path="modules.stable_diffusion.core_tools",
        function_name="generate_image_batch",
        priority=2
    ))
    
    # === Model Management Tools (Priority 2) ===
    tool_registry.register_tool(ToolDefinition(
        name="get_models",
        description="Get list of available Stable Diffusion models grouped by type",
        parameters={},
        group="models",
        module_path="modules.stable_diffusion.model_tools",
        function_name="get_models",
        priority=2
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="load_checkpoint",
        description="Load a specific model checkpoint",
        parameters={
            "model_name": {"type": "string", "description": "Name of the model to load"}
        },
        group="models", 
        module_path="modules.stable_diffusion.model_tools",
        function_name="load_checkpoint",
        priority=2
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="get_current_model",
        description="Get currently loaded model information with format analysis",
        parameters={},
        group="models",
        module_path="modules.stable_diffusion.model_tools",
        function_name="get_current_model",
        priority=2
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="get_model_info",
        description="Get detailed information about a specific model",
        parameters={
            "model_name": {"type": "string", "description": "Name of the model to analyze"}
        },
        group="models",
        module_path="modules.stable_diffusion.model_tools",
        function_name="get_model_info",
        priority=3
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="list_model_formats",
        description="List all detected model formats and their characteristics",
        parameters={},
        group="models",
        module_path="modules.stable_diffusion.model_tools",
        function_name="list_model_formats",
        priority=3
    ))
    
    # === LoRA Tools (Priority 3) ===
    tool_registry.register_tool(ToolDefinition(
        name="search_loras",
        description="Search for LoRA models using enhanced parsing",
        parameters={
            "query": {"type": "string", "description": "Search query for LoRA models"},
            "limit": {"type": "integer", "description": "Maximum results", "default": 10}
        },
        group="loras",
        module_path="modules.stable_diffusion.lora_tools", 
        function_name="search_loras",
        priority=3
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="get_all_loras",
        description="Get all available LoRA models grouped by category",
        parameters={},
        group="loras",
        module_path="modules.stable_diffusion.lora_tools",
        function_name="get_all_loras",
        priority=4
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="get_lora_suggestions",
        description="Get LoRA suggestions for a given prompt",
        parameters={
            "prompt": {"type": "string", "description": "Prompt to analyze for LoRA suggestions"}
        },
        group="loras",
        module_path="modules.stable_diffusion.lora_tools",
        function_name="get_lora_suggestions",
        priority=3
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="validate_lora_usage",
        description="Validate LoRA usage in a prompt",
        parameters={
            "prompt_with_loras": {"type": "string", "description": "Prompt containing LoRA syntax to validate"}
        },
        group="loras",
        module_path="modules.stable_diffusion.lora_tools",
        function_name="validate_lora_usage",
        priority=3
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="get_popular_loras",
        description="Get popular/frequently used LoRA models",
        parameters={
            "category": {"type": "string", "description": "LoRA category filter", "default": ""},
            "limit": {"type": "integer", "description": "Maximum results", "default": 20}
        },
        group="loras",
        module_path="modules.stable_diffusion.lora_tools",
        function_name="get_popular_loras",
        priority=4
    ))
    
    # === Queue Management Tools (Priority 4) ===
    tool_registry.register_tool(ToolDefinition(
        name="get_queue_status",
        description="Get current queue status and progress",
        parameters={},
        group="queue",
        module_path="modules.stable_diffusion.queue_tools",
        function_name="get_queue_status", 
        priority=4
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="get_queue_history",
        description="Get recent queue history",
        parameters={
            "limit": {"type": "integer", "description": "Maximum results", "default": 10}
        },
        group="queue",
        module_path="modules.stable_diffusion.queue_tools",
        function_name="get_queue_history",
        priority=5
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="cancel_job",
        description="Cancel a specific job in the queue",
        parameters={
            "job_id": {"type": "string", "description": "ID of the job to cancel"}
        },
        group="queue",
        module_path="modules.stable_diffusion.queue_tools",
        function_name="cancel_job",
        priority=4
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="clear_completed_jobs",
        description="Clear completed jobs from queue history",
        parameters={},
        group="queue",
        module_path="modules.stable_diffusion.queue_tools",
        function_name="clear_completed_jobs",
        priority=5
    ))
    
    # === Upload Tools (Priority 3) ===
    tool_registry.register_tool(ToolDefinition(
        name="upload_image",
        description="Upload image to Chevereto with fallback to local",
        parameters={
            "image_path": {"type": "string", "description": "Path to image file"},
            "user_id": {"type": "string", "description": "Discord user ID", "default": ""},
            "album_name": {"type": "string", "description": "Album name", "default": ""}
        },
        group="upload",
        module_path="modules.stable_diffusion.upload_tools",
        function_name="upload_image",
        priority=3
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="bulk_upload",
        description="Upload multiple images in batch",
        parameters={
            "image_paths": {"type": "array", "description": "List of image file paths"},
            "user_id": {"type": "string", "description": "Discord user ID", "default": ""},
            "album_name": {"type": "string", "description": "Album name", "default": ""}
        },
        group="upload",
        module_path="modules.stable_diffusion.upload_tools",
        function_name="bulk_upload",
        priority=4
    ))
    
    tool_registry.register_tool(ToolDefinition(
        name="test_upload_services",
        description="Test connectivity to upload services",
        parameters={},
        group="upload",
        module_path="modules.stable_diffusion.upload_tools",
        function_name="test_upload_services",
        priority=5
    ))

def define_sd_resources():
    """Define all SD resources without loading implementations"""
    
    tool_registry.register_resource(ResourceDefinition(
        name="supported-resolutions",
        description="Stable Diffusion supported resolutions",
        uri="sd://supported-resolutions",
        module_path="modules.stable_diffusion.resource_tools",
        function_name="supported_resolutions",
        group="info"
    ))
    
    tool_registry.register_resource(ResourceDefinition(
        name="models-summary", 
        description="Summary of available models",
        uri="sd://models-summary",
        module_path="modules.stable_diffusion.resource_tools",
        function_name="models_summary",
        group="info"
    ))

# Initialize tool definitions
define_sd_tools()
define_sd_resources()