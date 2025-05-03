from typing import Dict, Any, List, Optional, Union
import os
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class ResearchState:
    """State object for research workflow, holding project info and generated data."""
    
    # Define allowed keys that can be set using __setitem__
    _ALLOWED_KEYS = {
        'project_name', 'query', 'errors', 'data', 'visualizations',
        'visualization_list', 'visualization_data', 'sections',
        'draft', 'final_report', 'report_path', 'progress',
        'timestamp', 'report_config'
    }
    
    def __init__(self, project_name: str = "Unknown Project"):
        """
        Initialize a new research state.
        
        Args:
            project_name: Name of the project being researched
            
        Raises:
            ValueError: If project_name is empty or not a string
        """
        if not isinstance(project_name, str) or not project_name.strip():
            logger.error("Invalid project_name provided")
            raise ValueError("project_name must be a non-empty string")
            
        self.project_name = project_name.strip()
        self.query = ""
        self.errors = []
        self.data = {}
        self.visualizations = {}
        self.visualization_list = []
        self.visualization_data = {}
        self.sections = {}
        self.draft = ""
        self.final_report = ""
        self.report_path = ""
        self.progress = "Initialized"
        self.timestamp = datetime.now().isoformat()
        self.report_config = {}
        
    def update_progress(self, message: str) -> None:
        """
        Update the progress message.
        
        Args:
            message: The progress message to set
        """
        self.progress = message
        logger.info(f"Progress: {message}")
        
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the state by key, with fallback to default.
        
        Args:
            key: The key to lookup
            default: Default value if key not found
            
        Returns:
            The value if found, otherwise the default
        """
        if hasattr(self, key):
            return getattr(self, key)
        return default
    
    def __getitem__(self, key: str) -> Any:
        """
        Dictionary-style access to state attributes.
        
        Args:
            key: The attribute name to access
            
        Returns:
            The attribute value
            
        Raises:
            KeyError: If the attribute doesn't exist
        """
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"'{key}' not found in ResearchState")
    
    def __setitem__(self, key: str, value: Any) -> None:
        """
        Dictionary-style setting of state attributes.
        Only allows setting predefined attributes to prevent accidental overwrites.
        
        Args:
            key: The attribute name to set
            value: The value to set
            
        Raises:
            KeyError: If key is not in allowed_keys
        """
        if key in self._ALLOWED_KEYS:
            setattr(self, key, value)
        else:
            logger.warning(f"Attempted to set invalid state key: {key}")
            raise KeyError(f"Cannot set '{key}' in ResearchState")
        
    def items(self):
        """
        Return state attributes as (key, value) pairs for dict-like access.
        
        Returns:
            Iterator of (key, value) pairs of attributes
        """
        # Return only the attributes that aren't methods or private
        return {k: v for k, v in self.__dict__.items() 
                if not k.startswith('_') and not callable(v)}.items()
    
    def _serialize_value(self, value: Any) -> Any:
        """
        Recursively serialize a value for dictionary conversion.
        
        Args:
            value: The value to serialize
            
        Returns:
            A serialized version of the value that is JSON compatible
        """
        if isinstance(value, (dict, list)):
            if isinstance(value, dict):
                return {k: self._serialize_value(v) for k, v in value.items()}
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, (str, int, float, bool, type(None))):
            return value
        else:
            return str(value)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to a dictionary.
        Recursively serializes all values to ensure they're JSON-compatible.
        
        Returns:
            Dictionary representation of the state
        """
        return {
            k: self._serialize_value(v)
            for k, v in self.__dict__.items()
            if not k.startswith('_') and not callable(v)
        }
    
    def __repr__(self) -> str:
        """
        String representation of the state.
        
        Returns:
            String representation
        """
        return f"ResearchState(project_name='{self.project_name}', progress='{self.progress}')" 