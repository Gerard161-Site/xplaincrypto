import logging
from typing import Dict, Optional

class ProgressTracker:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.jobs: Dict[str, Dict[str, Any]] = {}
    
    def start_tracking(self, project_name: str, total_steps: int):
        self.jobs[project_name] = {
            "total_steps": total_steps,
            "completed_steps": 0,
            "progress": 0.0,
            "status": "running"
        }
        self.logger.info(f"Started tracking job {project_name} with {total_steps} total steps")
    
    def update_progress(self, project_name: str, step_name: str, percentage: float, message: str):
        if project_name not in self.jobs:
            self.logger.warning(f"Job {project_name} not found")
            return
        percentage = min(100.0, percentage)  # Cap at 100%
        self.jobs[project_name]["progress"] = percentage
        self.logger.info(f"Progress: {step_name} - {percentage:.1f}% complete: {message}")
    
    def mark_step_completed(self, project_name: str, step_name: str):
        if project_name not in self.jobs:
            self.logger.warning(f"Job {project_name} not found")
            return
        self.jobs[project_name]["completed_steps"] += 1
        progress = min(100.0, (self.jobs[project_name]["completed_steps"] / self.jobs[project_name]["total_steps"]) * 100)
        self.jobs[project_name]["progress"] = progress
        self.logger.info(f"Progress: {step_name} - {progress:.1f}% complete: Completed {step_name}")
    
    def complete(self):
        for project_name, job in self.jobs.items():
            job["status"] = "completed"
            job["progress"] = 100.0
            self.logger.info(f"Job {project_name} completed")