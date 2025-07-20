#!/usr/bin/env python3
"""
Queue management tools - only loaded when needed
"""

import json
from datetime import datetime

# Dependencies injected by lazy loader
queue_manager = None

def set_dependencies(manager):
    """Set dependencies when module is loaded"""
    global queue_manager
    queue_manager = manager

async def get_queue_status() -> str:
    """Get current queue status and progress"""
    try:
        status = await queue_manager.get_queue_status()
        
        return json.dumps({
            "queue_status": status,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "active_jobs": status.get("active_jobs", 0),
                "pending_jobs": status.get("pending_jobs", 0),
                "completed_today": status.get("completed_today", 0)
            }
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to get queue status: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

async def get_queue_history(limit: int = 10) -> str:
    """Get recent queue history"""
    try:
        history = await queue_manager.get_queue_history(limit)
        
        return json.dumps({
            "recent_jobs": history,
            "total_returned": len(history),
            "limit_applied": limit
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to get queue history: {str(e)}"
        })

async def cancel_job(job_id: str) -> str:
    """Cancel a specific job in the queue"""
    try:
        result = await queue_manager.cancel_job(job_id)
        
        return json.dumps({
            "job_id": job_id,
            "cancel_result": result,
            "success": result.get("success", False),
            "message": result.get("message", "")
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to cancel job: {str(e)}",
            "job_id": job_id
        })

async def clear_completed_jobs() -> str:
    """Clear completed jobs from queue history"""
    try:
        result = await queue_manager.clear_completed_jobs()
        
        return json.dumps({
            "clear_result": result,
            "success": result.get("success", False),
            "jobs_cleared": result.get("jobs_cleared", 0),
            "message": result.get("message", "")
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "error": f"Failed to clear completed jobs: {str(e)}"
        })