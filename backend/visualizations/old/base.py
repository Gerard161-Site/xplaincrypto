"""
Enhanced visualization module for XplainCrypto with PDF optimization.
This module provides base visualization capabilities with specific optimizations
for PDF output and real-time data integration.
"""

import os
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.figure import Figure
from typing import Dict, Any, List, Optional, Tuple, Union
import logging
import numpy as np
from datetime import datetime, timedelta
import io
import pandas as pd
import traceback
import json
from ...utils.style_utils import StyleManager
from abc import ABC, abstractmethod
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configure logging
logger = logging.getLogger(__name__)

class BaseVisualization(ABC):
    """Base class for all visualizations."""
    
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = 'default', style_manager=None):
        """
        Initialize the base visualization.
        
        Args:
            theme: Visual theme ('light' or 'dark')
            pdf_optimized: Whether to optimize for PDF output
            project_name: Name of the project (e.g., "ONDO")
            style_manager: Optional StyleManager instance for consistent styling
        """
        self.theme = theme
        self.pdf_optimized = pdf_optimized
        self.project_name = project_name
        self.style_manager = style_manager
        self.logger = logging.getLogger(__name__)
        
        # Ensure output directory exists
        self.output_dir = os.path.join('docs', project_name)
        os.makedirs(self.output_dir, exist_ok=True)
    
    @abstractmethod
    def create(self, viz_id: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a visualization.
        
        Args:
            viz_id: Unique identifier for the visualization
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dictionary with:
            {
                'success': bool,
                'path': str,       # Path to the saved visualization
                'message': str     # Status message or error
            }
        """
        pass
    
    def save_figure(self, fig: go.Figure, viz_id: str) -> Tuple[bool, str]:
        """
        Save a plotly figure to file.
        
        Args:
            fig: Plotly figure to save
            viz_id: Visualization ID
            
        Returns:
            Tuple of (success, path)
        """
        try:
            # Set the output path
            output_path = os.path.join(self.output_dir, f"{viz_id}.png")
            
            # Apply TradingView-inspired styling
            if self.style_manager:
                fig = self.style_manager.apply_plotly_style(fig, self.theme)
            
            # Optimize for PDF if needed
            if self.pdf_optimized:
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    plot_bgcolor='white' if self.theme == 'light' else '#1e1e1e',
                    paper_bgcolor='white' if self.theme == 'light' else '#1e1e1e',
                    font=dict(
                        family="Arial, sans-serif",
                        size=10
                    )
                )
            
            # Save the figure
            fig.write_image(output_path, scale=2)
            
            return True, output_path
        
        except Exception as e:
            error_msg = f"Error saving figure: {str(e)}"
            self.logger.error(error_msg)
            return False, ""
    
    def validate_data(self, data: Dict[str, Any], required_keys: List[str]) -> Tuple[bool, str]:
        """
        Validate that data contains all required keys.
        
        Args:
            data: Data dictionary
            required_keys: List of required keys
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        missing_keys = [key for key in required_keys if key not in data]
        
        if missing_keys:
            error_msg = f"Missing required data keys: {', '.join(missing_keys)}"
            return False, error_msg
        
        return True, ""
    
    def format_date_columns(self, df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
        """
        Format date columns in a dataframe.
        
        Args:
            df: Pandas dataframe
            date_cols: List of column names to format as dates
            
        Returns:
            Dataframe with formatted date columns
        """
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        return df
    
    def get_color_palette(self, num_colors: int = 10) -> List[str]:
        """
        Get a color palette for the visualization.
        
        Args:
            num_colors: Number of colors needed
            
        Returns:
            List of color hex codes
        """
        if self.style_manager:
            return self.style_manager.get_colors(num_colors, self.theme)
        
        # Default TradingView-inspired color palettes
        light_palette = [
            '#2962FF', '#0098DB', '#00BCD4', '#00897B', '#4CAF50', 
            '#8BC34A', '#CDDC39', '#FFC107', '#FF9800', '#FF5722'
        ]
        
        dark_palette = [
            '#5B8FF9', '#61DDAA', '#65789B', '#F6BD16', '#7262FD', 
            '#78D3F8', '#9661BC', '#F6903D', '#008685', '#F08BB4'
        ]
        
        palette = light_palette if self.theme == 'light' else dark_palette
        return palette[:num_colors]
    
    def create_empty_figure(self, title: str, error_message: str) -> go.Figure:
        """
        Create an empty figure with an error message when data is missing.
        
        Args:
            title: Figure title
            error_message: Error message to display
            
        Returns:
            Plotly figure
        """
        fig = go.Figure()
        
        # Add text annotation with error message
        fig.add_annotation(
            text=error_message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(
                family="Arial, sans-serif",
                size=14,
                color="#FF5252"  # Red for error
            )
        )
        
        # Set layout with title
        fig.update_layout(
            title=title,
            xaxis=dict(showticklabels=False, showgrid=False),
            yaxis=dict(showticklabels=False, showgrid=False)
        )
        
        return fig

class BaseVisualizer:
    """Base class for all visualizers with PDF optimization."""
    
    def __init__(self, theme: str = None, pdf_optimized: bool = True, logger=None):
        """
        Initialize a base visualizer with common configurations.
        
        Args:
            theme: Color theme to use ('dark' or 'light')
            pdf_optimized: Whether to optimize for PDF output
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Always use light theme for consistent visuals
        self.theme = 'light'
        
        self.logger.info(f"Using visualization theme: {self.theme}")
        
        self.pdf_optimized = pdf_optimized
        self.fig = None
        self.ax = None
        
        # Use StyleManager to load style configuration
        self.style_manager = StyleManager(logger=self.logger)
        self.style_config = self.style_manager.style_config
        
        # Create a reference to the theme-specific colors for easier access
        self._setup_color_palettes()
        
        # Set up matplotlib style based on theme
        self._setup_style()
    
    def _setup_color_palettes(self):
        """Set up color palettes for backward compatibility with existing code."""
        # Get themes from style_config
        vis_config = self.style_config.get("visualization", {})
        themes = vis_config.get("themes", {})
        
        # Create color palettes dictionary for backward compatibility
        self.color_palettes = {
            "light": themes.get("light", {}) or {
                "primary": ["#1E88E5", "#26A69A", "#D81B60", "#FFB300", "#607D8B"],
                "accent": "#1E88E5",
                "background": "#FFFFFF",
                "text": "#333333",
                "grid": "#DDDDDD",
                "positive": "#66BB6A",
                "negative": "#D81B60",
                "neutral": "#607D8B"
            },
            "dark": themes.get("dark", {}) or {
                "primary": ["#1E88E5", "#26A69A", "#D81B60", "#FFB300", "#607D8B"],
                "accent": "#1E88E5",
                "background": "#212121",
                "text": "#FFFFFF",
                "grid": "#444444",
                "positive": "#66BB6A",
                "negative": "#D81B60",
                "neutral": "#607D8B"
            }
        }
    
    def _get_theme_colors(self):
        """Get the color palette for the current theme."""
        vis_config = self.style_config.get("visualization", {})
        themes = vis_config.get("themes", {})
        
        # Get theme colors or use defaults
        if self.theme in themes:
            return themes[self.theme]
        else:
            # Log a warning when falling back to default
            self.logger.warning(f"Theme '{self.theme}' not found in style_config, defaulting to 'light'")
            return themes.get("light", {}) or {
                "primary": ["#1E88E5", "#26A69A", "#D81B60", "#FFB300", "#607D8B"],
                "accent": "#1E88E5",
                "background": "#FFFFFF",
                "text": "#333333",
                "grid": "#DDDDDD",
                "positive": "#66BB6A",
                "negative": "#D81B60",
                "neutral": "#607D8B"
            }
    
    def _setup_style(self):
        """Set up matplotlib style based on theme."""
        plt.style.use('default')
        
        # Configure matplotlib rcParams for the theme
        mpl.rcParams['figure.facecolor'] = self.theme_colors["background"]
        mpl.rcParams['axes.facecolor'] = self.theme_colors["background"]
        mpl.rcParams['axes.edgecolor'] = self.theme_colors["grid"]
        mpl.rcParams['axes.labelcolor'] = self.theme_colors["text"]
        mpl.rcParams['xtick.color'] = self.theme_colors["text"]
        mpl.rcParams['ytick.color'] = self.theme_colors["text"]
        mpl.rcParams['text.color'] = self.theme_colors["text"]
        mpl.rcParams['grid.color'] = self.theme_colors["grid"]
        
        # Get style values from config
        fig_config = self.style_config.get("visualization", {}).get("figure", {})
        font_sizes = self.style_config.get("font_sizes", {})
        mpl_config = self.style_config.get("visualization", {}).get("matplotlib", {})
        
        # Apply PDF optimization settings from style config
        mpl.rcParams['figure.dpi'] = fig_config.get("dpi", 300)
        mpl.rcParams['savefig.dpi'] = fig_config.get("dpi", 300)
        mpl.rcParams['font.size'] = font_sizes.get("body_text", 11)
        mpl.rcParams['axes.linewidth'] = mpl_config.get("axes", {}).get("linewidth", 1.0)
        mpl.rcParams['lines.linewidth'] = mpl_config.get("lines", {}).get("linewidth", 1.5)
        mpl.rcParams['font.family'] = 'sans-serif'
        mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
        
        # Set default figure size from config
        mpl.rcParams['figure.figsize'] = [
            fig_config.get("width", 6.0),
            fig_config.get("height", 4.0)
        ]
        
        # Set other matplotlib parameters from config
        mpl.rcParams['figure.constrained_layout.use'] = True
        mpl.rcParams['figure.autolayout'] = True
        mpl.rcParams['axes.grid'] = True
        mpl.rcParams['grid.alpha'] = mpl_config.get("grid", {}).get("alpha", 0.3)
        mpl.rcParams['legend.fontsize'] = mpl_config.get("legend", {}).get("font_size", 10)

    def create_figure(self, figsize: Tuple[float, float] = None):
        """Create a new figure with the specified size."""
        # Get standard figure size from style config if not specified
        if figsize is None:
            fig_config = self.style_config.get("visualization", {}).get("figure", {})
            width = fig_config.get("width", 6.0)
            height = fig_config.get("height", 4.0)
            figsize = (width, height)
        
        self.fig, self.ax = plt.subplots(figsize=figsize)
        self.fig.patch.set_facecolor(self.theme_colors["background"])
        self.ax.set_facecolor(self.theme_colors["background"])
        return self.fig, self.ax
    
    def add_title_and_labels(self, title: str, xlabel: str, ylabel: str):
        """Add title and axis labels to the figure."""
        if self.ax:
            font_sizes = self.style_config.get("font_sizes", {})
            title_size = font_sizes.get("title", 16)
            label_size = font_sizes.get("body_text", 11)
            
            self.ax.set_title(title, fontsize=title_size, fontweight='bold', color=self.theme_colors["text"])
            self.ax.set_xlabel(xlabel, fontsize=label_size, color=self.theme_colors["text"])
            self.ax.set_ylabel(ylabel, fontsize=label_size, color=self.theme_colors["text"])
    
    def add_grid(self, alpha: float = None):
        """Add a grid to the figure."""
        if self.ax:
            grid_config = self.style_config.get("visualization", {}).get("matplotlib", {}).get("grid", {})
            alpha = alpha or grid_config.get("alpha", 0.3)
            self.ax.grid(True, linestyle='--', alpha=alpha, color=self.theme_colors["grid"])
    
    def add_legend(self, loc: str = None):
        """Add a legend to the figure."""
        if self.ax:
            legend_config = self.style_config.get("visualization", {}).get("matplotlib", {}).get("legend", {})
            loc = loc or legend_config.get("location", "best")
            
            self.ax.legend(
                loc=loc, 
                framealpha=0.8, 
                facecolor=self.theme_colors["background"],
                edgecolor=self.theme_colors["grid"], 
                labelcolor=self.theme_colors["text"],
                fontsize=legend_config.get("font_size", 10)
            )
    
    def add_watermark(self, text: str = "XplainCrypto"):
        """Add a watermark to the figure."""
        if self.fig:
            self.fig.text(0.5, 0.5, text, fontsize=40, color=self.theme_colors["grid"],
                         ha='center', va='center', alpha=0.1, rotation=30)
    
    def add_timestamp(self):
        """Add a timestamp to the figure."""
        if self.fig:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.fig.text(0.99, 0.01, f"Generated: {timestamp}", fontsize=8, 
                         color=self.theme_colors["text"], ha='right', va='bottom', alpha=0.7)
    
    def save_figure(self, filename: str, format: str = 'png', dpi: int = None) -> bool:
        """
        Save the figure to a file.
        
        Args:
            filename: Path to save the figure
            format: File format (png, pdf, svg, etc.)
            dpi: Resolution in dots per inch
            
        Returns:
            True if successful, False otherwise
        """
        if self.fig is None:
            logger.error("No figure to save")
            return False
            
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Get dpi from config if not specified
            if dpi is None:
                dpi = self.style_config.get("visualization", {}).get("figure", {}).get("dpi", 300)
                
            self.fig.tight_layout()
            self.fig.savefig(filename, format=format, dpi=dpi, bbox_inches='tight', 
                          facecolor=self.theme_colors["background"])
            logger.info(f"Saved figure to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving figure: {str(e)}")
            return False
    
    def export_to_pdf(self, filename: str):
        """Export the current chart to PDF."""
        if self.fig:
            pdf_config = self.style_config.get("pdf", {})
            dpi = self.style_config.get("visualization", {}).get("figure", {}).get("dpi", 300)
            
            self.fig.savefig(
                filename, 
                format='pdf', 
                dpi=dpi,
                bbox_inches='tight',
                facecolor=self.theme_colors["background"]
            )
            logger.info(f"Exported figure to PDF: {filename}")
            return True
        return False
    
    def get_figure_as_bytes(self, format: str = 'png'):
        """Get the figure as bytes in the specified format."""
        if self.fig:
            dpi = self.style_config.get("visualization", {}).get("figure", {}).get("dpi", 300)
            
            buf = io.BytesIO()
            self.fig.savefig(
                buf, 
                format=format, 
                dpi=dpi, 
                bbox_inches='tight',
                facecolor=self.theme_colors["background"]
            )
            buf.seek(0)
            return buf.getvalue()
        return None
    
    def close_figure(self):
        """Close the current figure."""
        if self.fig:
            plt.close(self.fig)
            self.fig = None
            self.ax = None
    
    def add_title(self, title, subtitle=None):
        """Add title and optional subtitle to the figure."""
        if not self.ax:
            return
            
        font_sizes = self.style_config.get("font_sizes", {})
        title_size = font_sizes.get("title", 16)
        subtitle_size = font_sizes.get("subsection_heading", 10)
        
        self.ax.set_title(title, fontsize=title_size, fontweight='bold', color=self.theme_colors["text"])
        
        if subtitle:
            self.fig.suptitle(subtitle, fontsize=subtitle_size, color=self.theme_colors["text"], y=0.95)
    
    def infer_missing_data(self, data, required_fields):
        """Infer missing data fields with default values."""
        if not data:
            data = {}
            
        result = data.copy()
        
        # Default values for common fields
        defaults = {
            "x_data": list(range(10)),
            "y_data": [np.random.random() * 100 for _ in range(10)],
            "labels": ["Series 1", "Series 2", "Series 3"],
            "values": [30, 40, 30],
            "dates": pd.date_range(start='1/1/2023', periods=10),
            "price_data": [np.random.random() * 1000 for _ in range(10)],
            "volume_data": [np.random.random() * 10000 for _ in range(10)],
            "correlation_matrix": [[1.0, 0.5, 0.3], [0.5, 1.0, 0.6], [0.3, 0.6, 1.0]],
            "asset_names": ["BTC", "ETH", "SOL"]
        }
        
        for field in required_fields:
            if field not in result:
                if field in defaults:
                    result[field] = defaults[field]
                    logger.info(f"Inferred default value for {field}")
        
        return result

    def add_source_attribution(self, source: str, position: str = 'bottom-right'):
        """
        Add source attribution to the chart.
        
        Args:
            source: Source text to display
            position: Position to display the source (bottom-right, bottom-left)
            
        Returns:
            None
        """
        if not self.fig:
            return
        
        font_size = self.style_config.get("font_sizes", {}).get("caption", 8)
        
        x_pos = 0.99 if position == 'bottom-right' else 0.01
        ha = 'right' if position == 'bottom-right' else 'left'
        
        self.fig.text(
            x_pos, 0.01, 
            f"Source: {source}", 
            fontsize=font_size, 
            color=self.theme_colors["text"], 
            ha=ha, 
            va='bottom', 
            alpha=0.7
        )

    def close(self):
        """
        Close the figure and clean up resources.
        """
        if hasattr(self, 'fig') and self.fig:
            plt.close(self.fig)
            self.fig = None
            self.ax = None
            
    def validate_output_dir(self):
        """Validate and create output directory if needed."""
        try:
            # Set default output directory if not specified
            if not hasattr(self, 'output_dir'):
                if hasattr(self, 'project_name') and self.project_name:
                    self.output_dir = os.path.join("docs", self.project_name.lower().replace(" ", "_"))
                else:
                    self.output_dir = "docs/ondo"  # Default to ondo directory
            
            # Create directory if it doesn't exist
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Test write permissions
            test_file = os.path.join(self.output_dir, ".test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            
            self.logger.info(f"Validated output directory: {self.output_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Error validating output directory: {str(e)}")
            return False


class WebSocketDataProvider:
    """Provider for real-time data via WebSocket connections."""
    
    def __init__(self, endpoint: str = None):
        """
        Initialize the WebSocket data provider.
        
        Args:
            endpoint: WebSocket endpoint URL
        """
        self.endpoint = endpoint
        self.connected = False
        self.data_buffer = []
        
    async def connect(self, endpoint: str = None):
        """
        Connect to the WebSocket endpoint.
        
        Args:
            endpoint: WebSocket endpoint URL (overrides the one set in constructor)
        """
        # This is a placeholder for actual WebSocket connection logic
        # In a real implementation, this would use a library like websockets or socketio
        self.endpoint = endpoint or self.endpoint
        logger.info(f"Connecting to WebSocket endpoint: {self.endpoint}")
        self.connected = True
        
    async def disconnect(self):
        """Disconnect from the WebSocket endpoint."""
        if self.connected:
            logger.info(f"Disconnecting from WebSocket endpoint: {self.endpoint}")
            self.connected = False
            
    async def get_latest_data(self, symbol: str, limit: int = 100):
        """
        Get the latest data for a symbol.
        
        Args:
            symbol: Symbol to get data for (e.g., 'BTC')
            limit: Maximum number of data points to return
            
        Returns:
            List of data points
        """
        # This is a placeholder for actual WebSocket data retrieval
        # In a real implementation, this would return data from the WebSocket connection
        logger.info(f"Getting latest data for {symbol} (limit: {limit})")
        
        # For now, generate some random data for testing
        now = datetime.now()
        data = []
        for i in range(limit):
            timestamp = now - timedelta(minutes=i)
            price = 50000 + np.random.normal(0, 1000)
            volume = np.random.randint(1, 100)
            data.append({
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "price": price,
                "volume": volume
            })
        
        # Return data in reverse order (oldest first)
        return list(reversed(data))
