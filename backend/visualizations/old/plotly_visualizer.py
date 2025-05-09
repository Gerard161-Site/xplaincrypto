import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from datetime import datetime

from backend.utils.plotly_styler import PlotlyStyler
from backend.utils.style_utils import StyleManager
from backend.utils.cache_utils import CacheManager

class PlotlyVisualizer:
    """Base class for all Plotly-based visualizations"""
    
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, style_manager: Optional[StyleManager] = None, logger=None):
        """
        Initialize the Plotly visualizer
        
        Args:
            theme: Visual theme to use ('light' or 'dark')
            pdf_optimized: Whether to optimize for PDF output
            project_name: Project name for output files
            style_manager: Optional style manager for consistent styling
            logger: Optional logger instance
        """
        self.theme = theme
        self.pdf_optimized = pdf_optimized
        self.project_name = project_name or 'default'
        self.style_manager = style_manager or StyleManager()
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize plotly styler
        self.styler = PlotlyStyler(theme=theme, project_name=project_name, logger=self.logger)
        
        # Initialize cache manager
        self.cache_manager = CacheManager(project_name=self.project_name)
        self.cache_dir = self.cache_manager.cache_dir
        
        # Output directory for visualizations
        self.output_dir = os.path.join("docs", self.project_name.lower())
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Flag to track if real data is being used
        self.using_real_data = False
        
        # Get visualization config
        self.viz_config = self.style_manager.get_visualization_config()
        
        # Set figure dimensions
        self.figure_config = self.viz_config.get("figure", {})
        self.width = self.figure_config.get("width", 5) * 2 * 100  # Convert from inches to pixels
        self.height = self.figure_config.get("height", 3.5) * 100  # Convert from inches to pixels
        
        # Theme colors from style_manager
        self.theme_colors = self._get_theme_colors()
    
    def _get_theme_colors(self) -> Dict[str, Any]:
        """Get theme colors from the style config."""
        vis_config = self.style_manager.style_config.get("visualization", {})
        themes = vis_config.get("themes", {})
        theme_colors = themes.get(self.theme, {})
        
        # Default colors if theme not found
        default_colors = {
            "light": {
                "background": "#ffffff",
                "text": "#333333",
                "accent": "#3366cc",
                "accent_palette": ["#3366cc", "#dc3912", "#ff9900", "#109618", "#990099", "#0099c6", "#dd4477", "#66aa00"],
                "grid": "#dddddd",
                "primary": ["#1E88E5", "#26A69A", "#D81B60", "#FFB300", "#607D8B"],
                "positive": "#66BB6A",
                "negative": "#D81B60"
            },
            "dark": {
                "background": "#202124",
                "text": "#e8eaed",
                "accent": "#8ab4f8", 
                "accent_palette": ["#8ab4f8", "#f28b82", "#fdd663", "#81c995", "#d7aefb", "#78d9ec", "#ff8bcb", "#b9e769"],
                "grid": "#3c4043",
                "primary": ["#1E88E5", "#26A69A", "#D81B60", "#FFB300", "#607D8B"],
                "positive": "#66BB6A",
                "negative": "#D81B60"
            }
        }
        
        if not theme_colors:
            self.logger.warning(f"Theme '{self.theme}' not found in config, using defaults")
            return default_colors.get(self.theme, default_colors["light"])
        
        return theme_colors
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a visualization based on the type.
        This implementation should be overridden by specific visualizer classes.
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating visualization: {viz_type} for {self.project_name}")
            
            # Default implementation creates an error message visualization
            fig = go.Figure()
            fig.add_annotation(
                text="Visualization not implemented",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=14, color="#FF5252")
            )
            fig.update_layout(
                title=config.get("title", viz_type.replace("_", " ").title()),
                width=self.width,
                height=self.height
            )
            
            # Output path
            output_filename = config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            fig.write_image(output_path, scale=2)
            
            return {
                "success": True,
                "file_path": output_path,
                "title": config.get("title", viz_type.replace("_", " ").title()),
                "message": "Default visualization created"
            }
        except Exception as e:
            self.logger.error(f"Error creating visualization: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_error_chart(self, message: str, output_path: str) -> Dict[str, Any]:
        """
        Create an error message visualization.
        
        Args:
            message: Error message to display
            output_path: Path to save the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            fig = go.Figure()
            fig.add_annotation(
                text=message,
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=14, color="#FF5252")
            )
            fig.update_layout(
                width=self.width,
                height=self.height
            )
            
            # Create parent directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save the figure
            fig.write_image(output_path, scale=2)
            
            return {
                "success": False,
                "file_path": output_path,
                "error": message
            }
        except Exception as e:
            self.logger.error(f"Error creating error visualization: {str(e)}")
            return {
                "success": False,
                "error": f"Error creating error visualization: {str(e)}"
            }
    
    def get_layout_config(self, is_mobile: bool = False) -> Dict[str, Any]:
        """
        Get layout configuration based on device type.
        
        Args:
            is_mobile: Whether the visualization is for mobile
            
        Returns:
            Layout configuration dictionary
        """
        chart_sizes = self.viz_config.get("chart_sizes", {})
        if is_mobile:
            mobile_sizes = chart_sizes.get("mobile", {})
            return {
                "width": mobile_sizes.get("width", 350),
                "height": mobile_sizes.get("height", 250),
                "margin": dict(l=10, r=10, t=50, b=50)
            }
        else:
            desktop_sizes = chart_sizes.get("desktop", {})
            return {
                "width": desktop_sizes.get("width", self.width),
                "height": desktop_sizes.get("height", self.height),
                "margin": dict(l=50, r=50, t=80, b=80)
            }
    
    def _extract_data_from_cache(self, data_type: str, retry_sources: List[str] = None) -> Any:
        """
        Extract data from cache files.
        
        Args:
            data_type: Type of data to extract (e.g., 'tvl', 'price')
            retry_sources: List of sources to try in order
            
        Returns:
            Extracted data or None if not found
        """
        retry_sources = retry_sources or ["defillama", "coinmarketcap", "coingecko", "tokenomics"]
        
        for source in retry_sources:
            try:
                # Try to load using cache manager
                cache_data = self.cache_manager.load(source, data_type, self.project_name.lower())
                if cache_data:
                    self.logger.info(f"Loaded {data_type} data from {source} cache")
                    return cache_data
                
                # Try looking for files directly if cache manager fails
                source_dir = os.path.join(self.output_dir, "cache", source)
                if os.path.exists(source_dir):
                    for filename in os.listdir(source_dir):
                        if data_type.lower() in filename.lower() and filename.endswith('.json'):
                            try:
                                with open(os.path.join(source_dir, filename), 'r') as f:
                                    file_data = json.load(f)
                                    self.logger.info(f"Loaded {data_type} data from {filename}")
                                    return file_data
                            except:
                                continue
            except Exception as e:
                self.logger.error(f"Error extracting {data_type} data from {source}: {str(e)}")
                continue
        
        self.logger.warning(f"No {data_type} data found in any cache source")
        return None
    
    def _convert_to_dataframe(self, data: Any) -> Optional[pd.DataFrame]:
        """
        Convert data to a pandas DataFrame for visualization.
        
        Args:
            data: Input data in various formats
            
        Returns:
            Pandas DataFrame or None if conversion fails
        """
        try:
            # Extract the data field if present
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            
            # Handle empty data
            if not data:
                return None
            
            # If already a DataFrame, return it
            if isinstance(data, pd.DataFrame):
                return data
            
            # Handle different formats
            if isinstance(data, list):
                # List of dictionaries
                if all(isinstance(item, dict) for item in data):
                    return pd.DataFrame(data)
                
                # List of lists (e.g., [[timestamp, value], ...])
                if all(isinstance(item, (list, tuple)) for item in data):
                    if len(data[0]) == 2:
                        df = pd.DataFrame(data, columns=["date", "value"])
                        # Convert timestamp to datetime if needed
                        if pd.api.types.is_numeric_dtype(df["date"]):
                            df["date"] = pd.to_datetime(df["date"], unit='s')
                        return df
            
            # Handle dictionary formats
            if isinstance(data, dict):
                # Check for common formats
                if "tvl" in data and isinstance(data["tvl"], list):
                    return pd.DataFrame(data["tvl"])
                
                # Dictionary with simple key-value pairs
                if not any(isinstance(v, (dict, list)) for v in data.values()):
                    return pd.DataFrame(list(data.items()), columns=["label", "value"])
                
                # Try a simple flattening approach for nested dictionary
                flat_data = {}
                for key, value in data.items():
                    if not isinstance(value, (dict, list)):
                        flat_data[key] = value
                
                if flat_data:
                    return pd.DataFrame([flat_data])
            
            # If all conversions fail
            return None
            
        except Exception as e:
            self.logger.error(f"Error converting to DataFrame: {str(e)}")
            return None
    
    def _format_value(self, value: Any, is_currency: bool = False, is_percentage: bool = False, 
                     precision: int = 2, compact: bool = True) -> str:
        """
        Format a numeric value for display.
        
        Args:
            value: Value to format
            is_currency: Whether to format as currency
            is_percentage: Whether to format as percentage
            precision: Decimal precision
            compact: Whether to use compact notation (K, M, B)
            
        Returns:
            Formatted string
        """
        if value is None or pd.isna(value):
            return "N/A"
        
        try:
            value = float(value)
            
            # Handle percentage
            if is_percentage:
                # Ensure value is in percentage form (0-100)
                if abs(value) < 1 and not is_currency:  # Avoid treating small currency values as percentages
                    value *= 100
                return f"{value:.{precision}f}%"
            
            # Handle currency and large numbers
            if is_currency:
                prefix = "$"
            else:
                prefix = ""
            
            # Compact notation
            if compact:
                if abs(value) >= 1_000_000_000:
                    return f"{prefix}{value/1_000_000_000:.{precision}f}B"
                elif abs(value) >= 1_000_000:
                    return f"{prefix}{value/1_000_000:.{precision}f}M"
                elif abs(value) >= 1_000:
                    return f"{prefix}{value/1_000:.{precision}f}K"
            
            # Standard notation
            return f"{prefix}{value:.{precision}f}"
            
        except (ValueError, TypeError):
            return str(value) 