import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from .models import GenerateImageInput, ProgressResponse
from .sd_client import SDClient

class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class GenerationJob:
    def __init__(self, job_id: str, params: GenerateImageInput, priority: int = 5):
        self.job_id = job_id
        self.params = params
        self.priority = priority
        self.status = JobStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.result: Optional[List[Dict[str, Any]]] = None
        self.progress: float = 0.0

class QueueManager:
    def __init__(self, sd_client: Optional[SDClient] = None, max_concurrent: int = 1):
        self.sd_client = sd_client or SDClient()
        self.max_concurrent = max_concurrent
        self.jobs: Dict[str, GenerationJob] = {}
        self.queue: List[str] = []  # Job IDs in order
        self.running: Dict[str, asyncio.Task] = {}
        self._processing = False
    
    def enqueue_generation(self, params: GenerateImageInput, priority: int = 5) -> str:
        """Add a generation job to the queue"""
        job_id = str(uuid.uuid4())
        job = GenerationJob(job_id, params, priority)
        
        self.jobs[job_id] = job
        
        # Insert based on priority (higher priority = lower number = earlier in queue)
        inserted = False
        for i, queued_id in enumerate(self.queue):
            if self.jobs[queued_id].priority > priority:
                self.queue.insert(i, job_id)
                inserted = True
                break
        
        if not inserted:
            self.queue.append(job_id)
        
        # Start processing if not already running
        if not self._processing:
            asyncio.create_task(self._process_queue())
        
        return job_id
    
    async def _process_queue(self):
        """Process jobs in the queue"""
        self._processing = True
        
        try:
            while self.queue or self.running:
                # Start new jobs if we have capacity
                while (len(self.running) < self.max_concurrent and 
                       self.queue and 
                       len(self.running) < self.max_concurrent):
                    
                    job_id = self.queue.pop(0)
                    job = self.jobs[job_id]
                    
                    if job.status == JobStatus.PENDING:
                        job.status = JobStatus.IN_PROGRESS
                        job.started_at = datetime.now()
                        
                        task = asyncio.create_task(self._execute_job(job))
                        self.running[job_id] = task
                
                # Wait for at least one job to complete
                if self.running:
                    done, pending = await asyncio.wait(
                        self.running.values(), 
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Clean up completed tasks
                    completed_jobs = []
                    for job_id, task in list(self.running.items()):
                        if task in done:
                            completed_jobs.append(job_id)
                            del self.running[job_id]
                    
                await asyncio.sleep(0.1)  # Small delay to prevent tight loop
                
        finally:
            self._processing = False
    
    async def _execute_job(self, job: GenerationJob):
        """Execute a single generation job"""
        try:
            result = await self.sd_client.generate_image(job.params)
            job.result = [{"path": r.path, "parameters": r.parameters} for r in result]
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            
        except Exception as e:
            job.error_message = str(e)
            job.status = JobStatus.FAILED
            job.progress = 0.0
        
        finally:
            job.completed_at = datetime.now()
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "priority": job.priority,
            "progress": job.progress,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "result": job.result
        }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get overall queue status"""
        pending_count = len([j for j in self.jobs.values() if j.status == JobStatus.PENDING])
        in_progress_count = len([j for j in self.jobs.values() if j.status == JobStatus.IN_PROGRESS])
        completed_count = len([j for j in self.jobs.values() if j.status == JobStatus.COMPLETED])
        failed_count = len([j for j in self.jobs.values() if j.status == JobStatus.FAILED])
        
        return {
            "queue_length": len(self.queue),
            "running_jobs": len(self.running),
            "max_concurrent": self.max_concurrent,
            "total_jobs": len(self.jobs),
            "pending": pending_count,
            "in_progress": in_progress_count,
            "completed": completed_count,
            "failed": failed_count,
            "is_processing": self._processing
        }
    
    async def get_current_progress(self) -> Optional[ProgressResponse]:
        """Get progress of currently running SD job"""
        if not self.running:
            return None
        
        try:
            return await self.sd_client.get_progress()
        except Exception:
            return None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status == JobStatus.PENDING:
            # Remove from queue
            if job_id in self.queue:
                self.queue.remove(job_id)
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            return True
        
        elif job.status == JobStatus.IN_PROGRESS:
            # Cancel running task
            task = self.running.get(job_id)
            if task:
                task.cancel()
                del self.running[job_id]
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                return True
        
        return False
    
    def clear_completed_jobs(self, older_than_hours: int = 24) -> int:
        """Clear completed/failed jobs older than specified hours"""
        cutoff = datetime.now().timestamp() - (older_than_hours * 3600)
        cleared_count = 0
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                job.completed_at and job.completed_at.timestamp() < cutoff):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            cleared_count += 1
        
        return cleared_count
    
    def get_job_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent job history"""
        sorted_jobs = sorted(
            self.jobs.values(), 
            key=lambda j: j.created_at, 
            reverse=True
        )
        
        return [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "priority": job.priority,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "prompt": job.params.prompt[:100] + "..." if len(job.params.prompt) > 100 else job.params.prompt,
                "error_message": job.error_message
            }
            for job in sorted_jobs[:limit]
        ]