from typing import Dict, Any, Optional, List, Callable
import logging
from datetime import datetime

class ProgressTracker:
    """Manages tracking and reporting of system progress."""
    
    def __init__(self, logger: logging.Logger, verbosity: str = "info"):
        self.logger = logger
        self.verbosity = verbosity
        self.start_time = None
        self.steps_completed = {}
        self.current_step = None
        self.progress_subscribers = []
    
    def start_tracking(self, job_id: str, total_steps: int):
        """Initialize tracking for a new job."""
        self.start_time = datetime.now()
        self.steps_completed = {}
        self.job_id = job_id
        self.total_steps = total_steps
        self._log(f"Started tracking job {job_id} with {total_steps} total steps")
    
    def update_progress(self, step: str, percentage: float, message: str, job_id: str = None):
        """
        Update the progress of a step.
        
        Args:
            step: The step being tracked
            percentage: Progress percentage (0-100)
            message: Progress message
            job_id: Optional job ID to override the default
        """
        # Set step completion
        previous_percentage = self.steps_completed.get(step, 0)
        self.steps_completed[step] = percentage
        
        # Use provided job_id or default
        current_job_id = job_id or getattr(self, 'job_id', 'unknown')
        
        # Determine if this is a new step or significant progress
        is_new_step = step not in self.steps_completed or previous_percentage == 0
        is_significant = percentage - previous_percentage >= 10
        
        # Log based on verbosity and significance
        if self.verbosity == "debug" or is_new_step or is_significant:
            self._log(f"Progress: {step} - {percentage}% complete: {message}")
        
        # Notify subscribers
        self._notify_subscribers(step, percentage, message, current_job_id)
    
    def _log(self, message: str, level: str = "info"):
        """Log a message at the specified level."""
        log_methods = {
            "debug": self.logger.debug,
            "info": self.logger.info,
            "warning": self.logger.warning,
            "error": self.logger.error
        }
        log_method = log_methods.get(level, self.logger.info)
        log_method(message)
    
    def _notify_subscribers(self, step: str, percentage: float, message: str, job_id: str = None):
        """Notify all subscribers of progress updates."""
        progress_data = {
            'step': step,
            'percentage': percentage,
            'message': message,
            'job_id': job_id or getattr(self, 'job_id', 'unknown')
        }
        
        import inspect
        import asyncio
        
        for subscriber in self.progress_subscribers:
            try:
                # Check if the subscriber is a coroutine function
                if inspect.iscoroutinefunction(subscriber):
                    # Create a task for the coroutine instead of calling directly
                    asyncio.create_task(subscriber(progress_data))
                else:
                    # Regular function, call directly
                    subscriber(progress_data)
            except Exception as e:
                self.logger.error(f"Error notifying progress subscriber: {str(e)}")
    
    def subscribe(self, callback: Callable):
        """Add a subscriber to progress updates."""
        self.progress_subscribers.append(callback)
        return len(self.progress_subscribers) - 1  # Return subscription ID
    
    def unsubscribe(self, subscription_id: int):
        """Remove a subscriber."""
        if 0 <= subscription_id < len(self.progress_subscribers):
            del self.progress_subscribers[subscription_id]
            return True
        return False
    
    def complete(self):
        """Mark tracking as complete and return summary statistics."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
        completed_steps = len([s for s, p in self.steps_completed.items() if p >= 100])
        total_steps = getattr(self, 'total_steps', 0)
        
        summary = {
            'job_id': getattr(self, 'job_id', 'unknown'),
            'duration_seconds': duration,
            'steps_completed': completed_steps,
            'total_steps': total_steps,
            'completion_percentage': (completed_steps / total_steps) * 100 if total_steps else 0
        }
        
        self._log(f"Job {summary['job_id']} completed in {duration:.2f} seconds ({summary['completion_percentage']:.1f}% complete)")
        return summary 