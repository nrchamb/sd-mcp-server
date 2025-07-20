#!/usr/bin/env python3
"""
Model management tools - only loaded when needed
"""

import json
from typing import Dict, Any, List

# Dependencies injected by lazy loader
sd_client = None

def set_dependencies(client):
    """Set dependencies when module is loaded"""
    global sd_client
    sd_client = client

async def get_models() -> str:
    """Get list of available Stable Diffusion models"""
    try:
        models = await sd_client.get_models()
        
        # Group models by type for better organization
        model_groups = {
            "checkpoint": [],
            "lora": [],
            "vae": [],
            "embedding": [],
            "other": []
        }
        
        for model in models:
            model_type = model.get("type", "other").lower()
            if model_type in model_groups:
                model_groups[model_type].append(model)
            else:
                model_groups["other"].append(model)
        
        return json.dumps({
            "total_models": len(models),
            "groups": model_groups,
            "summary": {
                "checkpoints": len(model_groups["checkpoint"]),
                "loras": len(model_groups["lora"]),
                "vaes": len(model_groups["vae"]),
                "embeddings": len(model_groups["embedding"]),
                "other": len(model_groups["other"])
            }
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to get models: {str(e)}"})

async def load_checkpoint(model_name: str) -> str:
    """Load a specific model checkpoint"""
    try:
        # Get current model first for comparison
        current_model = await sd_client.get_current_model()
        current_name = current_model.get("model_name", "none")
        
        if current_name == model_name:
            return json.dumps({
                "status": "already_loaded",
                "model_name": model_name,
                "message": f"Model '{model_name}' is already loaded"
            })
        
        # Load the new model
        result = await sd_client.load_checkpoint(model_name)
        
        if result.get("success"):
            # Get model info after loading
            new_model = await sd_client.get_current_model()
            
            return json.dumps({
                "status": "success",
                "previous_model": current_name,
                "new_model": model_name,
                "model_info": new_model,
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

async def get_current_model() -> str:
    """Get currently loaded model information"""
    try:
        model_info = await sd_client.get_current_model()
        
        # Detect model format and get constraints
        model_name = model_info.get("model_name", "unknown")
        model_format = sd_client._detect_model_format(model_name)
        constraints = sd_client._get_model_constraints(model_format)
        
        return json.dumps({
            "current_model": model_info,
            "format_info": {
                "detected_format": model_format.value,
                "optimal_resolution": f"{constraints.default_resolution[0]}x{constraints.default_resolution[1]}",
                "recommended_steps": constraints.recommended_steps,
                "recommended_cfg": constraints.recommended_cfg,
                "supported_resolutions": constraints.supported_resolutions
            }
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to get current model: {str(e)}"})

async def get_model_info(model_name: str) -> str:
    """Get detailed information about a specific model"""
    try:
        models = await sd_client.get_models()
        
        # Find the specific model
        target_model = None
        for model in models:
            if model.get("name") == model_name or model.get("model_name") == model_name:
                target_model = model
                break
        
        if not target_model:
            return json.dumps({
                "error": f"Model '{model_name}' not found",
                "available_models": [m.get("name", m.get("model_name", "unknown")) for m in models[:10]]
            })
        
        # Detect format and get constraints
        model_format = sd_client._detect_model_format(model_name)
        constraints = sd_client._get_model_constraints(model_format)
        
        return json.dumps({
            "model_info": target_model,
            "format_analysis": {
                "detected_format": model_format.value,
                "optimal_resolution": f"{constraints.default_resolution[0]}x{constraints.default_resolution[1]}",
                "recommended_steps": constraints.recommended_steps,
                "recommended_cfg": constraints.recommended_cfg,
                "supported_resolutions": constraints.supported_resolutions
            },
            "usage_tips": {
                "best_for": sd_client._get_model_use_cases(model_format),
                "performance_notes": sd_client._get_performance_notes(model_format)
            }
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to get model info: {str(e)}"})

async def list_model_formats() -> str:
    """List all detected model formats and their characteristics"""
    try:
        models = await sd_client.get_models()
        format_analysis = {}
        
        for model in models:
            model_name = model.get("name", model.get("model_name", "unknown"))
            model_format = sd_client._detect_model_format(model_name)
            format_name = model_format.value
            
            if format_name not in format_analysis:
                constraints = sd_client._get_model_constraints(model_format)
                format_analysis[format_name] = {
                    "count": 0,
                    "models": [],
                    "characteristics": {
                        "optimal_resolution": f"{constraints.default_resolution[0]}x{constraints.default_resolution[1]}",
                        "recommended_steps": constraints.recommended_steps,
                        "recommended_cfg": constraints.recommended_cfg,
                        "supported_resolutions": constraints.supported_resolutions
                    }
                }
            
            format_analysis[format_name]["count"] += 1
            format_analysis[format_name]["models"].append(model_name)
        
        return json.dumps({
            "format_summary": format_analysis,
            "total_formats": len(format_analysis),
            "total_models": len(models)
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to analyze model formats: {str(e)}"})