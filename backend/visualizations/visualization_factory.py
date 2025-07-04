import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import traceback

# Import visualization components
from .candlestick_chart import CandlestickChartVisualizer
from .line_chart import LineChartVisualizer
from .pie_chart import PieChartVisualizer
from .bar_chart import BarChartVisualizer
from .table import TableVisualizer
from .comparison_chart import ComparisonChartVisualizer
from .error_chart import ErrorChartVisualizer

class VisualizationFactory:
    """
    Factory for creating different types of visualizations.
    This centralizes the creation logic and provides a consistent interface.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """
        Initialize the visualization factory.
        
        Args:
            project_name: Name of the project
            style_manager: StyleManager instance for consistent styling
            logger: Optional logger instance
        """
        self.project_name = project_name
        self.style_manager = style_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Define visualization color schemes
        self.colors = self.style_manager.get_colors()
        self.visualization_config = self.style_manager.get_visualization_config()
        
        # Default chart dimensions
        self.width = self.visualization_config.get("width", 900)
        self.height = self.visualization_config.get("height", 600)
        
        # Default theme (light or dark)
        self.theme = "light"
        self.output_dir = os.path.join("reports", self.project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize visualizers
        self.visualizers = {
            # Base visualization types
            "candlestick_chart": CandlestickChartVisualizer(project_name, style_manager, logger),
            "line_chart": LineChartVisualizer(project_name, style_manager, logger),
            "pie_chart": PieChartVisualizer(project_name, style_manager, logger),
            "bar_chart": BarChartVisualizer(project_name, style_manager, logger),
            "table": TableVisualizer(project_name, style_manager, logger),
            "comparison_chart": ComparisonChartVisualizer(project_name, style_manager, logger),
            
            # Mapped visualization types (map to the base types)
            "tvl_chart": LineChartVisualizer(project_name, style_manager, logger),
            "price_chart": CandlestickChartVisualizer(project_name, style_manager, logger),
            "volume_chart": LineChartVisualizer(project_name, style_manager, logger),
            "tokenomics_chart": PieChartVisualizer(project_name, style_manager, logger),
            "chain_distribution_chart": PieChartVisualizer(project_name, style_manager, logger),
            "metrics_table": TableVisualizer(project_name, style_manager, logger),
            "tokenomics_pie_chart": PieChartVisualizer(project_name, style_manager, logger),
            "tvl_milestone_chart": LineChartVisualizer(project_name, style_manager, logger),
            "tvl_phases_chart": LineChartVisualizer(project_name, style_manager, logger),
            "monthly_growth_chart": LineChartVisualizer(project_name, style_manager, logger)
        }
        
        # Special handling for error chart
        self.error_chart = ErrorChartVisualizer(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a visualization of the specified type.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        # Log the visualization creation attempt
        self.logger.info(f"Creating visualization of type: {viz_type}")
        
        # Check if we have a visualizer for this type
        if viz_type not in self.visualizers:
            error_msg = f"Unsupported visualization type: {viz_type}"
            self.logger.error(error_msg)
            # Use error chart as fallback
            return self.error_chart.create_visualization("error_chart", {
                "title": f"Error: {error_msg}",
                "output_filename": f"error_{viz_type}"
            }, {"error_message": error_msg})
        
        # Get the visualizer
        visualizer = self.visualizers[viz_type]
        
        # Check if the data is usable for this visualization type
        if not visualizer.check_data_usability(data, viz_type):
            error_msg = f"Data is not usable for visualization type: {viz_type}"
            self.logger.error(error_msg)
            # Use error chart as fallback
            return self.error_chart.create_visualization("error_chart", {
                "title": f"Error: {error_msg}",
                "output_filename": f"error_{viz_type}"
            }, {"error_message": error_msg})
        
        # Create the visualization
        try:
            success, file_path, message = visualizer.create_visualization(viz_type, viz_config, data)
            if success:
                self.logger.info(f"Successfully created {viz_type} visualization at {file_path}")
            else:
                self.logger.error(f"Failed to create {viz_type} visualization: {message}")
            return success, file_path, message
        except Exception as e:
            error_msg = f"Error creating {viz_type} visualization: {str(e)}"
            self.logger.error(error_msg)
            # Use error chart as fallback
            return self.error_chart.create_visualization("error_chart", {
                "title": f"Error: {error_msg}",
                "output_filename": f"error_{viz_type}"
            }, {"error_message": error_msg})
    
    # Alias for backward compatibility
    def create(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Alias for create_visualization for backward compatibility."""
        return self.create_visualization(viz_type, viz_config, data) 