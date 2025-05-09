import os
import logging
from typing import Dict, Any, Tuple, Optional

import plotly.graph_objects as go

from .base_visualizer import BaseVisualizer

class ErrorChartVisualizer(BaseVisualizer):
    """
    Visualizer for error charts when other visualizations fail.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the error chart visualizer."""
        super().__init__(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a visualization. For ErrorChartVisualizer, this just calls create_error_chart.
        
        Args:
            viz_type: Type of visualization to create (ignored)
            viz_config: Configuration for the visualization
            data: Data for the visualization (ignored)
            
        Returns:
            Tuple of (success: bool, file_path: str, error_message: str)
        """
        return self.create_error_chart("Unspecified error", viz_config)
    
    def create_error_chart(self, error_message: str, viz_config: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create an error chart when visualization fails.
        
        Args:
            error_message: Error message to display
            viz_config: Visualization configuration
            
        Returns:
            Tuple of (success: bool, file_path: str, error_message: str)
        """
        try:
            # Create a simple figure with error message
            fig = go.Figure()
            
            # Add error annotation
            fig.add_annotation(
                text=error_message,
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="#FF5252")
            )
            
            # Update layout for consistent styling
            fig.update_layout(
                title=viz_config.get("title", "Visualization Error"),
                width=self.width,
                height=self.height,
                paper_bgcolor=self.colors.get("background", "#ffffff"),
                plot_bgcolor=self.colors.get("background", "#ffffff"),
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            # Hide axes
            fig.update_xaxes(visible=False)
            fig.update_yaxes(visible=False)
            
            # Generate output path
            output_filename = viz_config.get("output_filename", f"{self.project_name.lower()}_error")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Export as PNG using kaleido
            fig.write_image(output_path, scale=2)
            
            return False, output_path, error_message
            
        except Exception as e:
            self.logger.error(f"Error creating error chart: {str(e)}")
            return False, "", f"Failed to create error chart: {str(e)}"
    
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the provided data is usable for visualization.
        For ErrorChartVisualizer, this always returns True as we can always create an error chart.
        
        Args:
            data: Data to check (ignored)
            viz_type: Optional visualization type for specific checks (ignored)
            
        Returns:
            True
        """
        return True 