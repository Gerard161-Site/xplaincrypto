import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd

import plotly.graph_objects as go

from .base_visualizer import BaseVisualizer

class ComparisonChartVisualizer(BaseVisualizer):
    """
    Visualizer for comparison charts displaying multiple metrics across different entities.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the comparison chart visualizer."""
        super().__init__(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a comparison chart visualization.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        try:
            # This is a placeholder implementation that should be expanded with actual comparison chart visualization logic
            self.logger.info(f"Creating comparison chart visualization: {viz_type}")
            
            # Extract comparison data
            comparison_data = self._extract_comparison_data(data, viz_type)
            
            if not comparison_data:
                return False, "", f"No comparison data available for {viz_type}"
            
            # Convert to DataFrame if not already
            if not isinstance(comparison_data, pd.DataFrame):
                df = self._convert_to_dataframe(comparison_data)
            else:
                df = comparison_data
                
            if df is None or len(df) == 0:
                return False, "", f"Could not convert data to DataFrame for {viz_type}"
            
            # Create figure
            fig = go.Figure()
            
            # Simplified implementation - just create a grouped bar chart
            for column in df.columns:
                if column != 'name' and column != 'project':
                    fig.add_trace(go.Bar(
                        x=df['name'] if 'name' in df.columns else df['project'] if 'project' in df.columns else df.index,
                        y=df[column],
                        name=column.replace('_', ' ').title(),
                        marker_color=self.colors.get("primary", "#2196f3") if column == df.columns[1] else self.colors.get("accent", "#f44336")
                    ))
            
            # Update layout
            title = viz_config.get("title", f"{self.project_name} Comparison")
            source = viz_config.get("source", "Various Sources")
            
            fig.update_layout(
                title=title,
                width=self.width,
                height=self.height,
                paper_bgcolor=self.colors.get("background", "#ffffff"),
                plot_bgcolor=self.colors.get("background", "#ffffff"),
                margin=dict(l=50, r=50, t=80, b=50),
                barmode='group',
                xaxis=dict(
                    title=viz_config.get("x_axis_title", "Projects"),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor=self.colors.get("grid", "#dddddd")
                ),
                yaxis=dict(
                    title=viz_config.get("y_axis_title", "Value"),
                    showgrid=True,
                    gridwidth=1,
                    gridcolor=self.colors.get("grid", "#dddddd")
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
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
            
            return True, output_path, "Comparison chart created successfully"
            
        except Exception as e:
            error_msg = f"Error creating comparison chart: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
    
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """
        Check if the data can be used for a comparison chart.
        
        Args:
            data: Data to check
            viz_type: Type of visualization
            
        Returns:
            True if usable, False otherwise
        """
        if not super().check_data_usability(data, viz_type):
            return False
        
        # For comparison charts, we need multiple metrics or projects to compare
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                if 'comparison' in source_data and source_data['comparison']:
                    return True
                if 'competitors' in source_data and source_data['competitors']:
                    return True
                if 'projects' in source_data and source_data['projects']:
                    return True
        
        return False
    
    def _extract_comparison_data(self, data: Dict[str, Any], viz_type: str) -> Any:
        """Extract comparison data from input data."""
        # This is a placeholder implementation
        # TODO: Implement proper comparison data extraction logic
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                if 'comparison' in source_data:
                    return source_data['comparison']
                if 'competitors' in source_data:
                    return source_data['competitors']
                if 'projects' in source_data:
                    return source_data['projects']
        
        return None
    
    def _convert_to_dataframe(self, data: Any) -> Optional[pd.DataFrame]:
        """Convert comparison data to a pandas DataFrame."""
        try:
            if isinstance(data, pd.DataFrame):
                return data
            elif isinstance(data, dict):
                # Handle different dict formats
                if all(isinstance(v, dict) for v in data.values()):
                    # Dict of dicts: {project1: {metric1: value1, ...}, ...}
                    return pd.DataFrame.from_dict(data, orient='index').reset_index().rename(columns={'index': 'name'})
                else:
                    # Simple dict: {metric1: value1, ...}
                    return pd.DataFrame.from_dict(data, orient='index', columns=['value']).reset_index().rename(columns={'index': 'metric'})
            elif isinstance(data, list):
                if all(isinstance(item, dict) for item in data):
                    # List of dicts: [{project: name1, metric1: value1, ...}, ...]
                    return pd.DataFrame(data)
            
            self.logger.warning(f"Unsupported data format for comparison chart: {type(data)}")
            return None
        except Exception as e:
            self.logger.error(f"Error converting comparison data to DataFrame: {str(e)}")
            return None 