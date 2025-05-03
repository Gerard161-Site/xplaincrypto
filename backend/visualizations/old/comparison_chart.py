import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional, Union
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime, timedelta

from .base import BaseVisualizer
from backend.utils.plotly_styler import PlotlyStyler
from backend.utils.style_utils import StyleManager
from backend.utils.cache_utils import CacheManager

class ComparisonChartVisualizer(BaseVisualizer):
    """Creates comparison chart visualizations using Plotly"""
    
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, logger=None):
        """
        Initialize the comparison chart visualizer
        
        Args:
            theme: Visual theme to use
            pdf_optimized: Whether to optimize for PDF output
            project_name: Project name for labeling
            logger: Optional logger instance
        """
        super().__init__(theme, pdf_optimized, project_name, logger)
        self.project_name = project_name or "default"
        self.logger = logger or logging.getLogger(__name__)
        self.cache_manager = CacheManager(project_name=self.project_name)
        self.style_manager = StyleManager(logger=self.logger)
        self.styler = PlotlyStyler(theme=theme, project_name=self.project_name, logger=self.logger)
        
        # Get visualization config
        self.viz_config = self.style_manager.get_visualization_config()
        
        # Set figure dimensions
        self.figure_config = self.viz_config.get("figure", {})
        self.width = self.figure_config.get("width", 5) * 2 * 100  # Convert from inches to pixels
        self.height = self.figure_config.get("height", 3.5) * 100  # Convert from inches to pixels
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any], is_mobile: bool = False) -> Dict[str, Any]:
        """
        Create a comparison chart visualization
        
        Args:
            viz_type: Type of chart (competitor_comparison_chart, etc.)
            config: Visualization configuration
            data: Data for visualization
            is_mobile: Whether this is for mobile view
            
        Returns:
            Dictionary with visualization metadata
        """
        project_name = config.get("project_name", self.project_name) or "default"
        output_dir = os.path.join("docs", project_name)
        os.makedirs(output_dir, exist_ok=True)
        
        layout_config = self.get_layout_config(is_mobile)
        title = config.get("title", viz_type.replace("_", " ").title())
        output_filename = config.get("output_filename") or f"{project_name}_{viz_type}.png"
        output_path = os.path.join(output_dir, output_filename)
        
        # Get chart width and height
        width = layout_config.get("width", self.width)
        height = layout_config.get("height", self.height)
        
        # Source and note
        source = config.get("source", "XplainCrypto Research")
        note = config.get("note", "")
        
        if viz_type == "competitor_comparison_chart":
            # Load comparison data from cache
            comparison_data = self._load_comparison_data_from_cache(viz_type)
            if not comparison_data:
                self.logger.warning(f"No comparison data found in cache for {project_name}")
                
                # Generate sample comparison data for demonstration
                metrics, projects, values = self._generate_sample_comparison_data()
                
                # Create a grouped bar chart
                fig = go.Figure()
                
                # Add a bar trace for each metric
                for i, metric in enumerate(metrics):
                    fig.add_trace(go.Bar(
                        x=projects,
                        y=[values[j][i] for j in range(len(projects))],
                        name=metric
                    ))
            else:
                # Process the real comparison data
                metrics = comparison_data.get("metrics", [])
                projects = comparison_data.get("projects", [])
                values = comparison_data.get("values", [])
                
                # Create a grouped bar chart
                fig = go.Figure()
                
                # Add a bar trace for each metric
                for i, metric in enumerate(metrics):
                    fig.add_trace(go.Bar(
                        x=projects,
                        y=[values[j][i] for j in range(len(projects))],
                        name=metric
                    ))
            
            # Apply styling
            fig = self.styler.apply_layout(fig, title, width, height)
            fig = self.styler.style_bar_chart(
                fig,
                x_title=config.get("x_title", "Projects"),
                y_title=config.get("y_title", "Values")
            )
            
            # Add watermark if needed
            if config.get("watermark", True):
                fig = self.styler.add_watermark(fig)
            
            # Add source
            if source:
                fig = self.styler.add_source_annotation(fig, source)
            
            # Add note if provided
            if note:
                fig = self.styler.add_note_annotation(fig, note)
            
            # Save the figure
            pio.write_image(fig, output_path, scale=2)
            
            # Return visualization metadata
            return {
                "title": title,
                "type": "comparison_chart",
                "path": output_path,
                "width": width,
                "height": height,
                "source": source,
                "note": note,
                "projects": projects,
                "metrics": metrics
            }
            
        else:
            # Generic comparison chart for other types
            self.logger.warning(f"Unrecognized comparison chart type: {viz_type}")
            
            # Generate sample comparison data for demonstration
            metrics, categories, values = self._generate_sample_comparison_data()
            
            # Create a grouped bar chart
            fig = go.Figure()
            
            # Add a bar trace for each metric
            for i, metric in enumerate(metrics):
                fig.add_trace(go.Bar(
                    x=categories,
                    y=[values[j][i] for j in range(len(categories))],
                    name=metric
                ))
            
            # Apply styling
            fig = self.styler.apply_layout(fig, f"Sample {title}", width, height)
            fig = self.styler.style_bar_chart(
                fig,
                x_title=config.get("x_title", "Categories"),
                y_title=config.get("y_title", "Values")
            )
            
            # Add watermark
            fig = self.styler.add_watermark(fig, "SAMPLE DATA")
            
            # Add note explaining this is sample data
            fig = self.styler.add_note_annotation(
                fig, 
                "This is a sample visualization with generated data. Replace with actual data in production."
            )
            
            # Save the figure
            pio.write_image(fig, output_path, scale=2)
            
            # Return visualization metadata
            return {
                "title": f"Sample {title}",
                "type": "sample_comparison_chart",
                "path": output_path,
                "width": width,
                "height": height,
                "source": "Sample Data",
                "note": "Sample visualization with generated data",
                "is_sample": True
            }
    
    def _load_comparison_data_from_cache(self, viz_type: str) -> Optional[Dict[str, Any]]:
        """
        Load comparison data from cache
        
        Args:
            viz_type: Type of comparison chart
            
        Returns:
            Dictionary with comparison data or None if not found
        """
        try:
            project_name = self.project_name.lower()
            
            # Check if we have cached data for this project and chart type
            if viz_type == "competitor_comparison_chart":
                cache_key = f"{project_name}_competitor_comparison"
                
                if self.cache_manager.has_cache(cache_key):
                    return self.cache_manager.read_cache(cache_key)
                
                # If project-specific data not found, try loading a template
                template_key = "competitor_comparison_template"
                if self.cache_manager.has_cache(template_key):
                    return self.cache_manager.read_cache(template_key)
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error loading comparison data from cache: {e}")
            return None
    
    def _generate_sample_comparison_data(self) -> tuple:
        """
        Generate sample comparison data for demonstration
        
        Returns:
            Tuple of (metrics, categories, values)
        """
        # Sample metrics, categories, and values
        metrics = ["TVL", "Market Cap", "Volume"]
        categories = [self.project_name, "Competitor A", "Competitor B", "Competitor C"]
        
        # Generate random values
        values = []
        for _ in range(len(categories)):
            category_values = []
            for i in range(len(metrics)):
                if i == 0:  # TVL
                    value = np.random.uniform(100, 5000)
                elif i == 1:  # Market Cap
                    value = np.random.uniform(500, 10000)
                else:  # Volume
                    value = np.random.uniform(50, 1000)
                category_values.append(value)
            values.append(category_values)
        
        return metrics, categories, values
    
    def get_layout_config(self, is_mobile: bool = False) -> Dict[str, Any]:
        """
        Get layout configuration based on device type
        
        Args:
            is_mobile: Whether this is for mobile display
            
        Returns:
            Layout configuration dictionary
        """
        chart_sizes = self.viz_config.get("chart_sizes", {})
        if is_mobile:
            mobile_sizes = chart_sizes.get("mobile", {})
            return {
                "width": mobile_sizes.get("width", 350),
                "height": mobile_sizes.get("height", 250)
            }
        else:
            desktop_sizes = chart_sizes.get("desktop", {})
            return {
                "width": desktop_sizes.get("width", self.width),
                "height": desktop_sizes.get("height", self.height)
            }