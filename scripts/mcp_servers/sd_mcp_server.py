#!/usr/bin/env python3
"""
Fixed Lazy-Loading Stable Diffusion MCP Server
Proper MCP tool registration with lazy loading.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from mcp.server.fastmcp import FastMCP
import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SD_MCP_Lazy')

# Initialize MCP server
mcp = FastMCP("SD_Web_MCP_Lazy_Fixed")

# Load configuration from environment (MCP.json env vars)
SD_BASE_URL = os.getenv("SD_BASE_URL", "http://localhost:7860")
IMAGE_OUT_PATH = os.getenv("IMAGE_OUT_PATH", "/tmp/images")

# Collect environment config
env_config = {
    "SD_BASE_URL": SD_BASE_URL,
    "IMAGE_OUT_PATH": IMAGE_OUT_PATH,
    "NSFW_FILTER": os.getenv("NSFW_FILTER", "false"),
    "UPLOAD_URL": os.getenv("UPLOAD_URL"),
    "SD_WEBUI_USERNAME": os.getenv("SD_WEBUI_USERNAME", ""),
    "SD_WEBUI_PASSWORD": os.getenv("SD_WEBUI_PASSWORD", ""),
    "CHEVERETO_BASE_URL": os.getenv("CHEVERETO_BASE_URL"),
    "CHEVERETO_USER_API_KEY": os.getenv("CHEVERETO_USER_API_KEY"),
    "CHEVERETO_GUEST_API_KEY": os.getenv("CHEVERETO_GUEST_API_KEY"),
    "CHEVERETO_ADMIN_API_KEY": os.getenv("CHEVERETO_ADMIN_API_KEY"),
    "ENABLE_DISCORD": os.getenv("ENABLE_DISCORD", "false"),
    "CHEVERETO_FALLBACK_TO_LOCAL": os.getenv("CHEVERETO_FALLBACK_TO_LOCAL", "true"),
    # NudeNet threshold configuration
    "NUDENET_THRESHOLD_FACE": float(os.getenv("NUDENET_THRESHOLD_FACE", "1.0")),
    "NUDENET_THRESHOLD_BREAST_EXPOSED": float(os.getenv("NUDENET_THRESHOLD_BREAST_EXPOSED", "0.6")),
    "NUDENET_THRESHOLD_BREAST_COVERED": float(os.getenv("NUDENET_THRESHOLD_BREAST_COVERED", "1.0")),
    "NUDENET_THRESHOLD_BUTTOCKS_EXPOSED": float(os.getenv("NUDENET_THRESHOLD_BUTTOCKS_EXPOSED", "0.6")),
    "NUDENET_THRESHOLD_BUTTOCKS_COVERED": float(os.getenv("NUDENET_THRESHOLD_BUTTOCKS_COVERED", "1.0")),
    "NUDENET_THRESHOLD_GENITALIA_EXPOSED": float(os.getenv("NUDENET_THRESHOLD_GENITALIA_EXPOSED", "0.3")),
    "NUDENET_THRESHOLD_GENITALIA_COVERED": float(os.getenv("NUDENET_THRESHOLD_GENITALIA_COVERED", "1.0")),
    "NUDENET_THRESHOLD_FEET": float(os.getenv("NUDENET_THRESHOLD_FEET", "1.0")),
    "NUDENET_THRESHOLD_BELLY": float(os.getenv("NUDENET_THRESHOLD_BELLY", "1.0")),
    "NUDENET_THRESHOLD_ARMPITS": float(os.getenv("NUDENET_THRESHOLD_ARMPITS", "1.0")),
    "NUDENET_THRESHOLD_BACK": float(os.getenv("NUDENET_THRESHOLD_BACK", "1.0")),
    "NUDENET_THRESHOLD_DEFAULT": float(os.getenv("NUDENET_THRESHOLD_DEFAULT", "0.8")),
    # NudeNet additional configuration
    "NUDENET_BLUR_RADIUS": int(os.getenv("NUDENET_BLUR_RADIUS", "10")),
    "NUDENET_BLUR_STRENGTH_CURVE": int(os.getenv("NUDENET_BLUR_STRENGTH_CURVE", "3")),
    "NUDENET_PIXELATION_FACTOR": int(os.getenv("NUDENET_PIXELATION_FACTOR", "5")),
    "NUDENET_FILL_COLOR": os.getenv("NUDENET_FILL_COLOR", "#000000"),
    "NUDENET_MASK_SHAPE": os.getenv("NUDENET_MASK_SHAPE", "Ellipse"),
    "NUDENET_MASK_BLEND_RADIUS": int(os.getenv("NUDENET_MASK_BLEND_RADIUS", "10")),
    "NUDENET_RECTANGLE_ROUND_RADIUS": int(os.getenv("NUDENET_RECTANGLE_ROUND_RADIUS", "0")),
    "NUDENET_NMS_THRESHOLD": float(os.getenv("NUDENET_NMS_THRESHOLD", "0.5")),
    "NUDENET_FILTER_TYPE": os.getenv("NUDENET_FILTER_TYPE", "Variable blur"),
    "NUDENET_EXPAND_HORIZONTAL": float(os.getenv("NUDENET_EXPAND_HORIZONTAL", "1.0")),
    "NUDENET_EXPAND_VERTICAL": float(os.getenv("NUDENET_EXPAND_VERTICAL", "1.0"))
}

# Global components - initialized only when first tool is called
_components_initialized = False
_sd_client = None
_lora_manager = None
_queue_manager = None  
_image_uploader = None
_content_guide_manager = None
_auth_manager = None

def _initialize_components():
    """Initialize SD components only when first needed"""
    global _components_initialized, _sd_client, _lora_manager, _queue_manager
    global _image_uploader, _content_guide_manager, _auth_manager
    
    if _components_initialized:
        return
    
    logger.info("🚀 Initializing SD components...")
    
    # Import heavy modules only when needed
    from modules.stable_diffusion import SDClient, LoRAManager, QueueManager
    from modules.stable_diffusion.auth_manager import create_auth_manager_from_env
    from config.chevereto_config import create_enhanced_uploader
    from modules.stable_diffusion.content_guide_tools import ContentGuideManager
    
    # Initialize core components (required)
    try:
        _auth_manager = create_auth_manager_from_env(env_config)
        _sd_client = SDClient(base_url=SD_BASE_URL, auth_manager=_auth_manager, nudenet_config=env_config)
        _lora_manager = LoRAManager(sd_client=_sd_client)
        _queue_manager = QueueManager(sd_client=_sd_client)
        logger.info("✅ Core SD components initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize core SD components: {e}")
        raise
    
    # Initialize optional components (graceful failure)
    try:
        _image_uploader = create_enhanced_uploader(env_config)
        logger.info("✅ Image uploader initialized")
    except Exception as e:
        logger.warning(f"⚠️ Image uploader initialization failed: {e}")
        logger.info("📝 Images will be stored locally only")
        _image_uploader = None
    
    try:
        _content_guide_manager = ContentGuideManager("modules/stable_diffusion/content_mapping.db")
        logger.info("✅ Content guide manager initialized")
    except Exception as e:
        logger.warning(f"⚠️ Content guide manager initialization failed: {e}")
        _content_guide_manager = None
    
    _components_initialized = True
    logger.info("✅ SD MCP Server initialized with available components")

# === Resources ===

@mcp.resource("sd://tool-manifest")
async def tool_manifest() -> Dict[str, Any]:
    """Get manifest of all available tools"""
    return {
        "total_tools": 8,  # Count of tools below
        "components_initialized": _components_initialized,
        "model_fix_version": "2025-01-18-fixed",
        "nudenet_disabled": "2025-01-18-workflow-fix",
        "server_file": __file__,
        "environment": {
            "sd_base_url": SD_BASE_URL,
            "image_out_path": IMAGE_OUT_PATH,
            "chevereto_enabled": bool(env_config.get("CHEVERETO_BASE_URL")),
            "discord_enabled": env_config.get("ENABLE_DISCORD") == "true"
        },
        "tools": [
            "generate_image", "get_models", "load_checkpoint", "search_loras",
            "get_queue_status", "upload_image", "start_guided_generation", "get_current_model"
        ]
    }

# === Core Tools - Properly Defined ===

@mcp.tool()
async def generate_image(
    prompt: str,
    negative_prompt: str = "",
    steps: int = 25,
    width: int = 1024,
    height: int = 1024,
    cfg_scale: float = 7.0,
    sampler_name: str = "Euler",
    seed: int = -1,
    upload: bool = True,
    user_id: str = "",
    album_name: str = "",
    enhance_prompt: bool = False
) -> str:
    """Generate an image using Stable Diffusion with comprehensive parameters"""
    _initialize_components()
    
    try:
        # Import GenerateImageInput model
        from modules.stable_diffusion.models import GenerateImageInput
        
        # Handle prompt enhancement if requested
        original_prompt = prompt
        enhanced_prompt = prompt
        enhancement_applied = False
        
        if enhance_prompt:
            try:
                # Analyze the prompt for enhancement suggestions
                analysis = _content_guide_manager.analyze_prompt_detailed(prompt)
                suggestions = analysis.get("enhancement_suggestions", [])
                
                # Apply automatic enhancements based on missing categories
                enhancements = []
                
                for suggestion in suggestions:
                    if suggestion["type"] == "quality_missing":
                        enhancements.append("high quality, detailed")
                    elif suggestion["type"] == "style_missing":
                        enhancements.append("photorealistic")
                    elif suggestion["type"] == "lighting_missing":
                        enhancements.append("natural lighting")
                
                if enhancements:
                    enhanced_prompt = f"{prompt}, {', '.join(enhancements)}"
                    enhancement_applied = True
                    
            except Exception as e:
                logger.warning(f"Prompt enhancement failed: {e}, using original prompt")
        
        # Create GenerateImageInput object (not dict!)
        params = GenerateImageInput(
            prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
            steps=steps,
            width=width,
            height=height,
            cfg_scale=cfg_scale,
            sampler_name=sampler_name,
            seed=seed,
            output_path=IMAGE_OUT_PATH
        )
        
        # Generate image - returns List[GenerationResult]
        results = await _sd_client.generate_image(params)
        
        if not results:
            return json.dumps({"error": "No images generated"})
        
        # Get first result
        result = results[0]
        
        response = {
            "status": "success",
            "local_path": result.path,
            "parameters_used": result.parameters,
            "input_params": params.model_dump(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Add prompt enhancement information if it was applied
        if enhance_prompt:
            response["prompt_enhancement"] = {
                "requested": True,
                "applied": enhancement_applied,
                "original_prompt": original_prompt,
                "enhanced_prompt": enhanced_prompt if enhancement_applied else original_prompt
            }
        
        # Upload if requested
        if upload and result.path:
            if _image_uploader:
                try:
                    print(f"[MCP] Starting upload for: {result.path}")
                    upload_result = await _image_uploader.upload_enhanced(
                        result.path,
                        sd_client=_sd_client,  # Enable NSFW detection and censoring
                        user_id=user_id,
                        folder_name=album_name or f"Generated_{datetime.now().strftime('%Y%m%d')}"
                    )
                    print(f"[MCP] Upload completed: {upload_result.get('success', False)}")
                    
                    if upload_result.get("success"):
                        response["upload"] = {
                            "success": True,
                            "public_url": upload_result.get("url"),  # Fixed: use 'url' not 'public_url'
                            "service_used": upload_result.get("hosting_service"),  # Fixed: use 'hosting_service'
                            "upload_mode": upload_result.get("upload_mode", "unknown"),
                            "expiry_note": upload_result.get("expiry_note", "unknown"),
                            "upload_id": upload_result.get("upload_id"),
                            "filename": upload_result.get("filename"),
                            "nsfw_detected": upload_result.get("nsfw_detected", False)
                        }
                    else:
                        response["upload"] = {
                            "success": False,
                            "error": upload_result.get("error"),
                            "fallback_used": True
                        }
                except Exception as upload_error:
                    response["upload"] = {
                        "success": False,
                        "error": f"Upload failed: {str(upload_error)}",
                        "fallback_path": result.path
                    }
            else:
                # No uploader available
                response["upload"] = {
                    "success": False,
                    "error": "Image uploader not available (Chevereto not configured)",
                    "fallback_path": result.path,
                    "local_only": True
                }
        
        return json.dumps(response, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Generation failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

@mcp.tool()
async def get_models() -> str:
    """Get list of available Stable Diffusion models"""
    _initialize_components()
    
    try:
        models = await _sd_client.get_models()
        
        # Organize models by folders and fix path handling
        model_folders = {}
        model_list = []
        
        for model in models:
            if hasattr(model, 'model_name'):
                model_name = model.model_name  # Flattened name from API
                title = getattr(model, 'title', model.model_name)
                filename = getattr(model, 'filename', '')
                hash_val = getattr(model, 'hash', '')
                
                # Reconstruct proper model name from title if it has folder structure
                if '\\' in title and '.safetensors' in title:
                    # Extract folder and filename from title
                    title_parts = title.split('\\')
                    if len(title_parts) >= 2:
                        folder = title_parts[0]
                        filename_part = title_parts[1].split(' [')[0] if ' [' in title_parts[1] else title_parts[1]
                        # Reconstruct proper model name for loading (with backslash)
                        proper_model_name = f"{folder}\\{filename_part}"
                        model_file = filename_part
                    else:
                        folder = "Root"
                        proper_model_name = model_name
                        model_file = title.split(' [')[0] if ' [' in title else title
                else:
                    folder = "Root"
                    proper_model_name = model_name
                    model_file = title.split(' [')[0] if ' [' in title else title
                
                model_info = {
                    "name": proper_model_name,  # Use reconstructed path for loading
                    "display_name": model_file,  # Just the filename for display
                    "folder": folder,
                    "title": title,
                    "filename": filename,
                    "hash": hash_val,
                    "api_name": model_name  # Keep original API name for reference
                }
                
                # Group by folder
                if folder not in model_folders:
                    model_folders[folder] = []
                model_folders[folder].append(model_info)
                
            elif isinstance(model, dict):
                model_info = model
                folder = "Root"
                if folder not in model_folders:
                    model_folders[folder] = []
                model_folders[folder].append(model_info)
            else:
                model_info = {"name": str(model), "folder": "Root"}
                if "Root" not in model_folders:
                    model_folders["Root"] = []
                model_folders["Root"].append(model_info)
            
            model_list.append(model_info)
        
        # Sort folders and models within folders
        sorted_folders = {}
        for folder, folder_models in model_folders.items():
            sorted_models = sorted(folder_models, key=lambda x: x.get('display_name', x.get('name', '')))
            sorted_folders[folder] = sorted_models
        
        return json.dumps({
            "total_models": len(model_list),
            "models": model_list,
            "folders": sorted_folders,
            "folder_summary": {folder: len(models) for folder, models in sorted_folders.items()},
            "usage_tip": "Use the 'name' field for load_checkpoint() - paths with backslashes reconstructed from title",
            "model_fix_version": "2025-01-18-fixed"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to get models: {str(e)}"})

@mcp.tool()
async def load_checkpoint(model_name: str) -> str:
    """Load a specific model checkpoint"""
    _initialize_components()
    
    try:
        # Get current model first
        current_model = await _sd_client.get_current_model()
        current_name = current_model.get("model_name", "none") if current_model else "none"
        
        if current_name == model_name:
            return json.dumps({
                "status": "already_loaded",
                "model_name": model_name,
                "message": f"Model '{model_name}' is already loaded"
            })
        
        # Load the new model
        result = await _sd_client.load_checkpoint(model_name)
        
        if result.get("success"):
            return json.dumps({
                "status": "success",
                "previous_model": current_name,
                "new_model": model_name,
                "load_time": result.get("load_time"),
                "message": f"Successfully loaded model: {model_name}"
            }, indent=2)
        else:
            return json.dumps({
                "status": "failed",
                "model_name": model_name,
                "error": result.get("error", "Unknown error occurred"),
                "current_model": current_name
            })
            
    except Exception as e:
        return json.dumps({
            "status": "error",
            "model_name": model_name,
            "error": f"Failed to load checkpoint: {str(e)}"
        })

@mcp.tool()
async def get_current_model() -> str:
    """Get currently loaded model information"""
    _initialize_components()
    
    try:
        model_info = await _sd_client.get_current_model()
        
        if model_info:
            # model_info is a dict, not an object
            return json.dumps({
                "model_name": model_info.get("model_name", "Unknown"),
                "model_hash": model_info.get("model_hash", "Unknown"),
                "model_sha256": model_info.get("model_sha256", "Unknown"),
                "status": "loaded"
            }, indent=2)
        else:
            return json.dumps({
                "status": "no_model_loaded", 
                "message": "No model currently loaded"
            })
        
    except Exception as e:
        return json.dumps({"error": f"Failed to get current model: {str(e)}"})

@mcp.tool()
async def search_loras(query: str, limit: int = 10) -> str:
    """Search for LoRA models"""
    _initialize_components()
    
    try:
        # Use the correct method signature - search_loras_smart supports limit parameter
        results = _lora_manager.search_loras_smart(query, max_results=limit)
        
        return json.dumps({
            "query": query,
            "results": results,
            "total_found": len(results),
            "limit_applied": limit
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"LoRA search failed: {str(e)}",
            "query": query
        })

@mcp.tool()
async def get_queue_status() -> str:
    """Get current queue status and progress"""
    _initialize_components()
    
    try:
        # Use the correct method - get_queue_status is not async
        status = _queue_manager.get_queue_status()
        
        return json.dumps({
            "queue_status": status,
            "timestamp": datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to get queue status: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

@mcp.tool()
async def upload_image(
    image_path: str,
    user_id: str = "",
    album_name: str = ""
) -> str:
    """Upload image to Chevereto with fallback to local"""
    _initialize_components()
    
    try:
        result = await _image_uploader.upload_enhanced(
            image_path,
            sd_client=None,  # Disable NSFW detection to avoid workflow issues
            user_id=user_id,
            folder_name=album_name or f"Upload_{datetime.now().strftime('%Y%m%d')}"
        )
        
        return json.dumps({
            "upload_result": result,
            "success": result.get("success", False),
            "public_url": result.get("url"),  # Fixed: use 'url' not 'public_url'
            "service_used": result.get("hosting_service"),  # Fixed: use 'hosting_service'
            "upload_id": result.get("upload_id"),
            "filename": result.get("filename"),
            "timestamp": datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Upload failed: {str(e)}",
            "image_path": image_path,
            "timestamp": datetime.now().isoformat()
        })

@mcp.tool()
async def start_guided_generation(prompt: str) -> str:
    """Start guided generation workflow with model selection"""
    _initialize_components()
    
    try:
        # Get current model
        current_model = await _sd_client.get_current_model()
        current_name = current_model.get("model_name", "none") if current_model else "none"
        
        # Get available models  
        models = await _sd_client.get_models()
        model_options = []
        
        for i, model in enumerate(models[:10]):  # Limit to first 10
            if hasattr(model, 'model_name'):
                model_name = model.model_name
            elif hasattr(model, 'title'):
                model_name = model.title
            else:
                model_name = f"Model_{i}"
            
            model_options.append({
                "index": i + 1,
                "name": model_name,
                "current": model_name == current_name
            })
        
        workflow_steps = {
            "step_0": {
                "title": "🎯 Model Selection (Required)",
                "description": "Choose your model before generation",
                "current_model": current_name,
                "available_models": model_options,
                "instructions": [
                    "Review the available models above",
                    "Choose by using load_checkpoint tool: load_checkpoint(model_name='[name]')",
                    "Or continue with current model"
                ],
                "next_action": "SELECT_MODEL"
            }
        }
        
        return json.dumps({
            "status": "workflow_started",
            "prompt": prompt,
            "current_step": "step_0",
            "workflow": workflow_steps,
            "message": "🎯 Please select a model before generation.",
            "next_steps": [
                f"Use load_checkpoint to change model",
                f"Then use generate_image with your prompt"
            ]
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to start guided generation: {str(e)}",
            "fallback": "Try using generate_image() directly with your prompt"
        })

@mcp.tool()
async def analyze_prompt(prompt: str) -> str:
    """Analyze prompt content and provide enhancement suggestions"""
    _initialize_components()
    
    try:
        # Use our content guide manager for detailed analysis
        analysis = _content_guide_manager.analyze_prompt_detailed(prompt)
        
        # Format results for user-friendly display
        result = {
            "original_prompt": prompt,
            "analysis": {
                "total_meaningful_words": analysis["total_words"],
                "categorized_words": len(analysis["categorized_words"]),
                "uncategorized_words": len(analysis["uncategorized_words"]),
                "categories_found": analysis["categories_found"]
            },
            "word_breakdown": {
                "categorized": analysis["categorized_words"],
                "uncategorized": analysis["uncategorized_words"],
                "filtered_words": analysis.get("filtered_words", [])
            },
            "enhancement_suggestions": analysis["enhancement_suggestions"],
            "safety_assessment": analysis["safety_assessment"],
            "recommended_enhancements": []
        }
        
        # Generate specific enhancement recommendations
        suggestions = analysis["enhancement_suggestions"]
        for suggestion in suggestions:
            if suggestion["type"] == "style_missing":
                result["recommended_enhancements"].append(
                    f"Add style keywords: {', '.join(suggestion['examples'][:3])}"
                )
            elif suggestion["type"] == "quality_missing":
                result["recommended_enhancements"].append(
                    f"Add quality descriptors: {', '.join(suggestion['examples'][:3])}"
                )
            elif suggestion["type"] == "lighting_missing":
                result["recommended_enhancements"].append(
                    f"Specify lighting: {', '.join(suggestion['examples'][:2])}"
                )
        
        # Safety warnings
        if analysis["safety_assessment"]["level"] != "safe":
            result["warnings"] = analysis["safety_assessment"]["recommendations"]
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to analyze prompt: {str(e)}",
            "original_prompt": prompt,
            "fallback_analysis": "Content analysis unavailable"
        })

if __name__ == "__main__":
    logger.info("🚀 Starting Fixed Lazy-Loading SD MCP Server")
    logger.info("💡 Components will initialize on first tool use")
    
    mcp.run()