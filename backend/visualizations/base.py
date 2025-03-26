"""
Base visualization class that defines the common interface and functionality
for all visualization types.
"""

import os
import logging
from typing import Dict, Any, Optional
import matplotlib
# Force non-interactive backend to avoid issues in headless environments
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

class BaseVisualizer:
    """
    Base class for all visualization modules.
    
    This defines the interface that all visualization modules should implement
    and provides common utility methods.
    """
    
    def __init__(self, project_name: str, logger: logging.Logger):
        """
        Initialize the base visualizer.
        
        Args:
            project_name: Name of the project being analyzed
            logger: Logger instance for logging
        """
        self.project_name = project_name
        self.logger = logger
        
        # Set up output directory
        self.output_dir = os.path.join("docs", self.project_name.lower().replace(" ", "_"))
        self.logger.info(f"Initializing visualizer with output directory: {self.output_dir}")
        
        # Ensure output directory exists
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            self.logger.info(f"Created/verified output directory: {self.output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create output directory {self.output_dir}: {str(e)}")
            raise
        
        # Verify matplotlib backend
        self._verify_matplotlib_backend()
        
        # Log initialization
        self.logger.debug(f"Initialized {self.__class__.__name__} for project: {project_name}")
        self.logger.debug(f"Output directory: {self.output_dir}")
    
    def _verify_matplotlib_backend(self):
        """Verify matplotlib is using a non-interactive backend."""
        current_backend = plt.get_backend()
        self.logger.debug(f"Matplotlib using backend: {current_backend}")
        
        # If using an interactive backend, try to switch to Agg
        if current_backend in ['TkAgg', 'Qt5Agg', 'MacOSX']:
            try:
                self.logger.warning(f"Switching from interactive backend {current_backend} to Agg")
                plt.switch_backend('Agg')
                self.logger.info(f"Successfully switched to backend: {plt.get_backend()}")
            except Exception as e:
                self.logger.error(f"Failed to switch matplotlib backend: {str(e)}")
    
    def create(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a visualization based on the provided configuration and data.
        
        This method must be implemented by all child classes.
        
        Args:
            vis_type: Type of visualization to create
            config: Configuration for the visualization
            data: Data to visualize
            
        Returns:
            Dictionary containing visualization result information
        """
        raise NotImplementedError("Child classes must implement the create method")
    
    def validate_output_dir(self) -> bool:
        """
        Validate that the output directory exists and is writable.
        
        Returns:
            True if the directory is valid and writable, False otherwise
        """
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir, exist_ok=True)
                self.logger.info(f"Created output directory: {self.output_dir}")
            
            # Test if directory is writable by creating a test file
            test_file = os.path.join(self.output_dir, ".test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            
            self.logger.info(f"Validated output directory: {self.output_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Output directory validation failed: {str(e)}")
            return False
    
    def get_safe_filename(self, vis_type: str) -> str:
        """Generate a safe and unique filename for the visualization."""
        # Clean the visualization type
        safe_name = vis_type.lower().replace(" ", "_")
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create filename with visualization type and timestamp
        filename = f"{safe_name}_{timestamp}.png"
        
        return filename
    
    def verify_file_saved(self, file_path: str) -> bool:
        """
        Verify that a file was successfully saved and is readable.
        
        Args:
            file_path: Path to the file to verify
            
        Returns:
            True if the file exists and is readable, False otherwise
        """
        self.logger.debug(f"Verifying file was saved: {file_path}")
        
        # Check output directory exists
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            self.logger.error(f"Output directory does not exist: {dir_path}")
            try:
                os.makedirs(dir_path, exist_ok=True)
                self.logger.info(f"Created output directory: {dir_path}")
            except Exception as e:
                self.logger.error(f"Failed to create output directory: {str(e)}")
                return False
        
        # Check file exists
        if not os.path.exists(file_path):
            self.logger.error(f"File does not exist: {file_path}")
            return False
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            self.logger.error(f"File exists but is empty: {file_path}")
            return False
        
        # Log file size
        file_size_kb = file_size / 1024
        self.logger.info(f"File saved successfully: {file_path} ({file_size_kb:.1f} KB)")
        
        return True 