#!/usr/bin/env python3
"""
HTTP wrapper for MCP server
Provides HTTP endpoints for Discord bot to call MCP tools
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Import MCP server functions
from scripts.mcp_servers.sd_mcp_server import (
    generate_image, get_models, load_checkpoint, get_current_model,
    search_loras, get_queue_status, upload_image, start_guided_generation,
    _initialize_components
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MCP_HTTP_Server')

# Create FastAPI app
app = FastAPI(
    title="SD MCP Server HTTP API",
    description="HTTP wrapper for Stable Diffusion MCP Server",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for uploaded images
@app.get("/images/{filename}")
async def serve_image(filename: str):
    """Serve uploaded images from local storage"""
    upload_dir = Path("/tmp/uploaded_images")
    file_path = upload_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Security check: ensure file is within upload directory
    try:
        file_path.resolve().relative_to(upload_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=str(file_path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"}
    )

# Request models
class GenerateImageRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    steps: int = 25
    width: int = 1024
    height: int = 1024
    cfg_scale: float = 7.0
    sampler_name: str = "Euler"
    seed: int = -1
    upload: bool = True
    user_id: str = ""
    album_name: str = ""

class LoadCheckpointRequest(BaseModel):
    model_name: str

class SearchLorasRequest(BaseModel):
    query: str
    limit: int = 10

class UploadImageRequest(BaseModel):
    image_path: str
    user_id: str = ""
    album_name: str = ""

class GuidedGenerationRequest(BaseModel):
    prompt: str

# Initialize components on startup
@app.on_event("startup")
async def startup_event():
    """Initialize MCP components"""
    logger.info("🚀 Starting MCP HTTP Server...")
    try:
        _initialize_components()
        logger.info("✅ MCP components initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MCP components: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "SD MCP Server HTTP API"}

# MCP tool endpoints
@app.post("/tools/generate_image")
async def generate_image_endpoint(request: GenerateImageRequest):
    """Generate image via MCP server"""
    try:
        logger.info(f"🎨 Generating image: {request.prompt[:50]}...")
        
        result = await generate_image(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            steps=request.steps,
            width=request.width,
            height=request.height,
            cfg_scale=request.cfg_scale,
            sampler_name=request.sampler_name,
            seed=request.seed,
            upload=request.upload,
            user_id=request.user_id,
            album_name=request.album_name
        )
        
        # Parse JSON response from MCP server
        if isinstance(result, str):
            result = json.loads(result)
        
        logger.info(f"✅ Generation completed: {result.get('status', 'unknown')}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@app.get("/tools/get_models")
async def get_models_endpoint():
    """Get available models"""
    try:
        result = await get_models()
        if isinstance(result, str):
            result = json.loads(result)
        return result
    except Exception as e:
        logger.error(f"❌ Failed to get models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")

@app.post("/tools/load_checkpoint")
async def load_checkpoint_endpoint(request: LoadCheckpointRequest):
    """Load model checkpoint"""
    try:
        logger.info(f"🔄 Loading checkpoint: {request.model_name}")
        result = await load_checkpoint(request.model_name)
        if isinstance(result, str):
            result = json.loads(result)
        return result
    except Exception as e:
        logger.error(f"❌ Failed to load checkpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load checkpoint: {str(e)}")

@app.get("/tools/get_current_model")
async def get_current_model_endpoint():
    """Get current model"""
    try:
        result = await get_current_model()
        if isinstance(result, str):
            result = json.loads(result)
        return result
    except Exception as e:
        logger.error(f"❌ Failed to get current model: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get current model: {str(e)}")

@app.post("/tools/search_loras")
async def search_loras_endpoint(request: SearchLorasRequest):
    """Search LoRA models"""
    try:
        result = await search_loras(request.query, request.limit)
        if isinstance(result, str):
            result = json.loads(result)
        return result
    except Exception as e:
        logger.error(f"❌ Failed to search LoRAs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search LoRAs: {str(e)}")

@app.get("/tools/get_queue_status")
async def get_queue_status_endpoint():
    """Get queue status"""
    try:
        result = await get_queue_status()
        if isinstance(result, str):
            result = json.loads(result)
        return result
    except Exception as e:
        logger.error(f"❌ Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")

@app.post("/tools/upload_image")
async def upload_image_endpoint(request: UploadImageRequest):
    """Upload image"""
    try:
        result = await upload_image(request.image_path, request.user_id, request.album_name)
        if isinstance(result, str):
            result = json.loads(result)
        return result
    except Exception as e:
        logger.error(f"❌ Failed to upload image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")

@app.post("/tools/start_guided_generation")
async def start_guided_generation_endpoint(request: GuidedGenerationRequest):
    """Start guided generation"""
    try:
        result = await start_guided_generation(request.prompt)
        if isinstance(result, str):
            result = json.loads(result)
        return result
    except Exception as e:
        logger.error(f"❌ Failed to start guided generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start guided generation: {str(e)}")

# Server info endpoint
@app.get("/info")
async def server_info():
    """Get server information"""
    return {
        "name": "SD MCP Server HTTP API",
        "version": "1.0.0",
        "description": "HTTP wrapper for Stable Diffusion MCP Server",
        "endpoints": {
            "health": "/health",
            "images": "/images/{filename}",
            "generate_image": "/tools/generate_image",
            "get_models": "/tools/get_models",
            "load_checkpoint": "/tools/load_checkpoint",
            "get_current_model": "/tools/get_current_model",
            "search_loras": "/tools/search_loras",
            "get_queue_status": "/tools/get_queue_status",
            "upload_image": "/tools/upload_image",
            "start_guided_generation": "/tools/start_guided_generation"
        }
    }

def main():
    """Main server runner"""
    # Get configuration from environment
    host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_HTTP_PORT", "8000"))
    
    logger.info(f"🚀 Starting MCP HTTP Server on {host}:{port}")
    
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            reload=False
        )
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()