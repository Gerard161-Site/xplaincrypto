from typing import Dict, Any, List, Optional, Callable
import logging
import traceback
import json
import os
from datetime import datetime

class ErrorReporter:
    """Manages error reporting, categorization, and handling."""
    
    ERROR_CATEGORIES = {
        "api_error": {
            "severity": "warning",
            "retry_allowed": True,
            "user_message": "Data source connection issue. Using fallback data."
        },
        "research_error": {
            "severity": "warning",
            "retry_allowed": True,
            "user_message": "Research retrieval issue. Using available information."
        },
        "processing_error": {
            "severity": "error",
            "retry_allowed": True,
            "user_message": "Error processing report data. Please try again."
        },
        "system_error": {
            "severity": "critical",
            "retry_allowed": False,
            "user_message": "System error occurred. Our team has been notified."
        }
    }
    
    def __init__(self, logger: logging.Logger, config_path: Optional[str] = None):
        self.logger = logger
        self.errors = []
        self.error_subscribers = []
        
        # Load custom error categories if config exists
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    custom_categories = json.load(f)
                    self.ERROR_CATEGORIES.update(custom_categories)
                    self.logger.info(f"Loaded custom error categories from {config_path}")
            except Exception as e:
                self.logger.warning(f"Failed to load error categories from {config_path}: {str(e)}")
    
    def report_error(self, error: Exception, category: str = "system_error", 
                    context: Dict[str, Any] = None, component: str = None) -> str:
        """
        Report an error with categorization and context.
        Returns the error_id for reference.
        """
        error_id = f"err_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(error)}"
        
        # Get category details or default
        category_info = self.ERROR_CATEGORIES.get(category, self.ERROR_CATEGORIES["system_error"])
        severity = category_info["severity"]
        
        # Build error record
        error_record = {
            "error_id": error_id,
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "category": category,
            "severity": severity,
            "component": component,
            "context": context or {},
            "retry_allowed": category_info["retry_allowed"],
            "user_message": category_info["user_message"]
        }
        
        # Log based on severity
        log_message = f"Error in {component or 'unknown'}: {str(error)} [ID: {error_id}]"
        if severity == "critical":
            self.logger.critical(log_message, exc_info=True)
        elif severity == "error":
            self.logger.error(log_message, exc_info=True)
        elif severity == "warning":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
            
        # Store error
        self.errors.append(error_record)
        
        # Notify subscribers
        self._notify_subscribers(error_record)
            
        return error_id
    
    def _notify_subscribers(self, error_record: Dict[str, Any]):
        """Notify all subscribers of a new error."""
        for subscriber in self.error_subscribers:
            try:
                import asyncio
                import inspect
                
                # Check if the subscriber is a coroutine function
                if inspect.iscoroutinefunction(subscriber):
                    # Create a task to run the coroutine
                    asyncio.create_task(subscriber(error_record))
                else:
                    # Call it directly if it's a regular function
                    subscriber(error_record)
            except Exception as e:
                self.logger.error(f"Error notifying error subscriber: {str(e)}")
    
    def get_user_message(self, error_id: str) -> str:
        """Get the user-friendly message for a reported error."""
        for error in self.errors:
            if error["error_id"] == error_id:
                return error["user_message"]
        return "An unknown error occurred."
    
    def can_retry(self, error_id: str) -> bool:
        """Check if the error allows retry."""
        for error in self.errors:
            if error["error_id"] == error_id:
                return error["retry_allowed"]
        return False
    
    def subscribe(self, callback: Callable):
        """Add a subscriber to error events."""
        self.error_subscribers.append(callback)
        return len(self.error_subscribers) - 1
    
    def unsubscribe(self, subscription_id: int):
        """Remove an error subscriber."""
        if 0 <= subscription_id < len(self.error_subscribers):
            del self.error_subscribers[subscription_id]
            return True
        return False
    
    def get_errors_by_component(self, component: str) -> List[Dict[str, Any]]:
        """Get all errors for a specific component."""
        return [e for e in self.errors if e["component"] == component]
    
    def get_errors_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all errors of a specific category."""
        return [e for e in self.errors if e["category"] == category]
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent errors."""
        return sorted(self.errors, key=lambda e: e["timestamp"], reverse=True)[:limit] 