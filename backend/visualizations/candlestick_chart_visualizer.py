import os
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.visualizations.plotly_visualizer import PlotlyVisualizer
from backend.utils.style_utils import StyleManager

class CandlestickChartVisualizer(PlotlyVisualizer):
    """
    Visualizer for creating candlestick charts using Plotly.
    """
    
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None,
                 style_manager: Optional[StyleManager] = None, logger=None):
        """
        Initialize the candlestick chart visualizer
        
        Args:
            theme: Visual theme ('light' or 'dark')
            pdf_optimized: Whether to optimize for PDF output
            project_name: Project name for file paths
            style_manager: Optional StyleManager for consistent styling
            logger: Optional logger instance
        """
        super().__init__(theme, pdf_optimized, project_name, style_manager, logger)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a candlestick chart visualization.
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating candlestick chart: {viz_type} for {self.project_name}")
            
            # Load the candlestick visualization class directly
            from backend.visualizations.candlestick_chart import CandlestickChartVisualizer as OriginalCandlestickChart
            
            # Create an instance and delegate to it
            original_visualizer = OriginalCandlestickChart(
                theme=self.theme,
                pdf_optimized=self.pdf_optimized,
                project_name=self.project_name,
                logger=self.logger
            )
            
            # Delegate to the original implementation
            result = original_visualizer.create(viz_type, config, data)
            
            if "error" in result:
                self.logger.error(f"Error in candlestick chart creation: {result['error']}")
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error in candlestick chart creation"),
                    "file_path": ""
                }
            
            # Transform the result to match our expected format
            file_path = result.get("file_path") or result.get("file_paths", {}).get(self.theme, "")
            
            return {
                "success": True,
                "file_path": file_path,
                "title": result.get("title", f"{self.project_name} Candlestick Chart"),
                "type": "candlestick_chart"
            }
            
        except Exception as e:
            self.logger.error(f"Error creating candlestick chart: {str(e)}")
            return self.create_error_chart(
                f"Error creating candlestick chart: {str(e)}",
                os.path.join(self.output_dir, f"{self.project_name.lower()}_{viz_type}.png")
            ) 