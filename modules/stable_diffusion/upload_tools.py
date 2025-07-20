#!/usr/bin/env python3
"""
Upload management tools - only loaded when needed
"""

import json
from datetime import datetime

# Dependencies injected by lazy loader
image_uploader = None

def set_dependencies(uploader):
    """Set dependencies when module is loaded"""
    global image_uploader
    image_uploader = uploader

async def upload_image(
    image_path: str,
    user_id: str = "",
    album_name: str = ""
) -> str:
    """Upload image to Chevereto with fallback to local"""
    try:
        result = await image_uploader.upload_enhanced(
            image_path,
            user_id=user_id,
            album_name=album_name or f"Upload_{datetime.now().strftime('%Y%m%d')}"
        )
        
        return json.dumps({
            "upload_result": result,
            "success": result.get("success", False),
            "public_url": result.get("public_url"),
            "service_used": result.get("service_used"),
            "album_info": result.get("album_info"),
            "timestamp": datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Upload failed: {str(e)}",
            "image_path": image_path,
            "timestamp": datetime.now().isoformat()
        })

async def bulk_upload(
    image_paths: list,
    user_id: str = "",
    album_name: str = ""
) -> str:
    """Upload multiple images in batch"""
    try:
        results = []
        album_name = album_name or f"Bulk_Upload_{datetime.now().strftime('%Y%m%d')}"
        
        for i, image_path in enumerate(image_paths):
            result = await image_uploader.upload_enhanced(
                image_path,
                user_id=user_id,
                album_name=album_name
            )
            
            results.append({
                "index": i,
                "image_path": image_path,
                "result": result
            })
        
        successful_uploads = [r for r in results if r["result"].get("success")]
        failed_uploads = [r for r in results if not r["result"].get("success")]
        
        return json.dumps({
            "bulk_upload_complete": True,
            "total_images": len(image_paths),
            "successful": len(successful_uploads),
            "failed": len(failed_uploads),
            "results": results,
            "album_name": album_name,
            "timestamp": datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Bulk upload failed: {str(e)}",
            "image_paths": image_paths
        })

async def get_upload_history(limit: int = 20) -> str:
    """Get recent upload history"""
    try:
        # Note: This would need to be implemented in the uploader
        # For now, return a placeholder
        return json.dumps({
            "message": "Upload history not yet implemented",
            "suggestion": "Check your Chevereto dashboard for upload history"
        })
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to get upload history: {str(e)}"
        })

async def test_upload_services() -> str:
    """Test connectivity to upload services"""
    try:
        # Test Chevereto connection
        chevereto_test = await image_uploader.test_chevereto_connection()
        
        return json.dumps({
            "service_tests": {
                "chevereto": chevereto_test,
                "local_fallback": {"available": True, "message": "Local storage always available"}
            },
            "overall_status": "healthy" if chevereto_test.get("success") else "chevereto_unavailable_local_fallback_ok",
            "timestamp": datetime.now().isoformat()
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Service test failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })