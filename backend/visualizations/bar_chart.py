import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd

import plotly.graph_objects as go

from .base_visualizer import BaseVisualizer

class BarChartVisualizer(BaseVisualizer):
    """
    Visualizer for bar charts displaying categorical data.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the bar chart visualizer."""
        super().__init__(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a bar chart visualization.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        try:
            # This is a placeholder implementation that should be expanded with actual bar chart visualization logic
            self.logger.info(f"Creating bar chart visualization: {viz_type}")
            
            # Extract bar chart data
            bar_data = self._extract_bar_data(data, viz_type)
            
            if not bar_data:
                return False, "", f"No bar chart data available for {viz_type}"
            
            # Create figure
            fig = go.Figure()
            
            # Add bar trace - simplified for skeleton
            if isinstance(bar_data, dict):
                fig.add_trace(go.Bar(
                    x=list(bar_data.keys()),
                    y=list(bar_data.values()),
                    marker_color=self.colors.get("primary", "#2196f3")
                ))
            elif isinstance(bar_data, list) and all(isinstance(item, dict) for item in bar_data):
                # Assume list of dicts with 'name' and 'value' keys
                names = [item.get('name', f"Item {i}") for i, item in enumerate(bar_data)]
                values = [item.get('value', 0) for item in bar_data]
                fig.add_trace(go.Bar(
                    x=names,
                    y=values,
                    marker_color=self.colors.get("primary", "#2196f3")
                ))
            else:
                return False, "", f"Unsupported bar chart data format for {viz_type}"
            
            # Update layout
            title = viz_config.get("title", f"{self.project_name} {viz_type.replace('_', ' ').title()}")
            source = viz_config.get("source", "Various Sources")
            
            fig.update_layout(
                title=title,
                width=self.width,
                height=self.height,
                paper_bgcolor=self.colors.get("background", "#ffffff"),
                plot_bgcolor=self.colors.get("background", "#ffffff"),
                margin=dict(l=50, r=50, t=80, b=50),
                xaxis=dict(
                    title=viz_config.get("x_axis_title", "Category"),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor=self.colors.get("grid", "#dddddd")
                ),
                yaxis=dict(
                    title=viz_config.get("y_axis_title", "Value"),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor=self.colors.get("grid", "#dddddd")
                )
            )
            
            # Add data source annotation
            fig.add_annotation(
                text=f"Source: {source}",
                xref="paper", yref="paper",
                x=0.01, y=-0.12,
                showarrow=False,
                font=dict(size=10, color="#808080"),
                align="left"
            )
            
            # Generate output path
            output_filename = viz_config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Export as PNG using kaleido
            fig.write_image(output_path, scale=2)
            
            return True, output_path, "Bar chart created successfully"
            
        except Exception as e:
            error_msg = f"Error creating bar chart: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
    
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the data can be used for a bar chart.
        
        Args:
            data: Data to check
            viz_type: Type of visualization
            
        Returns:
            True if usable, False otherwise
        """
        if not super().check_data_usability(data, viz_type):
            return False
        
        # For bar charts, we need categorical data
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                # Check for metrics or comparison data that could be shown as bars
                if any(key in source_data for key in ['metrics', 'comparison', 'ranking']):
                    return True
                    
                # Check for generic dict data that could be shown as bars
                if any(isinstance(value, (int, float)) for value in source_data.values()):
                    return True
        
        return False
    
    def _extract_bar_data(self, data: Dict[str, Any], viz_type: str) -> Any:
        """Extract bar chart data based on visualization type."""
        # This is a placeholder implementation
        # TODO: Implement proper bar chart data extraction logic
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                # Look for metrics or comparison data
                for key in ['metrics', 'comparison', 'ranking']:
                    if key in source_data:
                        return source_data[key]
                        
                # If no specific metrics found, return any dict with numeric values
                if any(isinstance(value, (int, float)) for value in source_data.values()):
                    return {k: v for k, v in source_data.items() if isinstance(v, (int, float))}
        
        return None 