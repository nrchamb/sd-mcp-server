#!/usr/bin/env python3
"""
Core generation tools - only loaded when needed
"""

import json
import os
from typing import Dict, Any
from datetime import datetime

# These will be injected by the lazy loader
sd_client = None
image_uploader = None
content_guide_manager = None

def set_dependencies(client, uploader, content_manager):
    """Set dependencies when module is loaded"""
    global sd_client, image_uploader, content_guide_manager
    sd_client = client
    image_uploader = uploader  
    content_guide_manager = content_manager

async def generate_image(
    prompt: str,
    negative_prompt: str = "",
    steps: int = 20,
    width: int = 512,
    height: int = 512,
    cfg_scale: float = 7.0,
    sampler: str = "DPM++ 2M",
    upload: bool = True,
    seed: int = -1,
    denoising_strength: float = 0.75,
    lora_weights: Dict[str, float] = None,
    user_id: str = "",
    album_name: str = ""
) -> str:
    """Generate an image using Stable Diffusion with comprehensive parameters"""
    try:
        # Create generation parameters
        params = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler,
            "seed": seed,
            "denoising_strength": denoising_strength
        }
        
        # Add LoRA weights if provided
        if lora_weights:
            params["lora_weights"] = lora_weights
        
        # Generate image
        result = await sd_client.generate_image(params)
        
        if result.get("error"):
            return json.dumps({"error": result["error"]})
        
        response = {
            "status": "success",
            "generation_id": result.get("generation_id"),
            "local_path": result.get("local_path"),
            "generation_time": result.get("generation_time"),
            "parameters_used": result.get("parameters"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Upload if requested
        if upload and result.get("local_path"):
            try:
                upload_result = await image_uploader.upload_enhanced(
                    result["local_path"],
                    user_id=user_id,
                    album_name=album_name or f"Generated_{datetime.now().strftime('%Y%m%d')}"
                )
                
                if upload_result.get("success"):
                    response["upload"] = {
                        "success": True,
                        "public_url": upload_result.get("public_url"),
                        "service_used": upload_result.get("service_used"),
                        "album_info": upload_result.get("album_info")
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
                    "fallback_path": result.get("local_path")
                }
        
        return json.dumps(response, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Generation failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

async def generate_image_batch(
    prompts: list,
    shared_params: Dict[str, Any] = None,
    upload: bool = True,
    user_id: str = "",
    album_name: str = ""
) -> str:
    """Generate multiple images in batch"""
    try:
        results = []
        shared_params = shared_params or {}
        
        for i, prompt in enumerate(prompts):
            params = {
                "prompt": prompt,
                **shared_params
            }
            
            result = await generate_image(
                upload=upload,
                user_id=user_id,
                album_name=album_name or f"Batch_{datetime.now().strftime('%Y%m%d')}",
                **params
            )
            
            results.append({
                "index": i,
                "prompt": prompt,
                "result": json.loads(result)
            })
        
        return json.dumps({
            "status": "batch_complete",
            "total_images": len(prompts),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Batch generation failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })