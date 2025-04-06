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

# Configure logging
logger = logging.getLogger(__name__)

class BaseVisualizer:
    """Base class for all visualizers with PDF optimization."""
    
    def __init__(self, theme: str = "dark", pdf_optimized: bool = True):
        """
        Initialize the base visualizer.
        
        Args:
            theme: Color theme to use ('dark' or 'light')
            pdf_optimized: Whether to optimize for PDF output
        """
        self.theme = theme
        self.pdf_optimized = pdf_optimized
        self.fig = None
        self.ax = None
        
        # Define color palettes optimized for PDF output
        self.color_palettes = {
            "dark": {
                "primary": ["#4361ee", "#3a0ca3", "#7209b7", "#f72585", "#4cc9f0"],
                "accent": "#4cc9f0",
                "background": "#121212",
                "text": "#ffffff",
                "grid": "#333333",
                "positive": "#00b894",
                "negative": "#ff7675",
                "neutral": "#74b9ff"
            },
            "light": {
                "primary": ["#0077b6", "#0096c7", "#00b4d8", "#48cae4", "#90e0ef"],
                "accent": "#03045e",
                "background": "#ffffff",
                "text": "#333333",
                "grid": "#dddddd",
                "positive": "#00b894",
                "negative": "#ff7675",
                "neutral": "#74b9ff"
            }
        }
        
        # Set up the style based on theme
        self._setup_style()
    
    def _setup_style(self):
        """Set up matplotlib style based on theme."""
        plt.style.use('default')
        
        # Get colors for current theme
        colors = self.color_palettes[self.theme]
        
        # Configure matplotlib rcParams for the theme
        mpl.rcParams['figure.facecolor'] = colors["background"]
        mpl.rcParams['axes.facecolor'] = colors["background"]
        mpl.rcParams['axes.edgecolor'] = colors["grid"]
        mpl.rcParams['axes.labelcolor'] = colors["text"]
        mpl.rcParams['xtick.color'] = colors["text"]
        mpl.rcParams['ytick.color'] = colors["text"]
        mpl.rcParams['text.color'] = colors["text"]
        mpl.rcParams['grid.color'] = colors["grid"]
        
        # PDF optimization settings
        if self.pdf_optimized:
            mpl.rcParams['figure.dpi'] = 300
            mpl.rcParams['savefig.dpi'] = 300
            mpl.rcParams['font.size'] = 12
            mpl.rcParams['axes.linewidth'] = 1.5
            mpl.rcParams['lines.linewidth'] = 2.5
            mpl.rcParams['font.family'] = 'sans-serif'
            mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    
    def create_figure(self, figsize: Tuple[float, float] = (10, 6)):
        """Create a new figure with the specified size."""
        self.fig, self.ax = plt.subplots(figsize=figsize)
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        return self.fig, self.ax
    
    def add_title_and_labels(self, title: str, xlabel: str, ylabel: str):
        """Add title and axis labels to the figure."""
        if self.ax:
            self.ax.set_title(title, fontsize=14, fontweight='bold', color=self.color_palettes[self.theme]["text"])
            self.ax.set_xlabel(xlabel, fontsize=12, color=self.color_palettes[self.theme]["text"])
            self.ax.set_ylabel(ylabel, fontsize=12, color=self.color_palettes[self.theme]["text"])
    
    def add_grid(self, alpha: float = 0.3):
        """Add a grid to the figure."""
        if self.ax:
            self.ax.grid(True, linestyle='--', alpha=alpha, color=self.color_palettes[self.theme]["grid"])
    
    def add_legend(self, loc: str = 'best'):
        """Add a legend to the figure."""
        if self.ax:
            self.ax.legend(loc=loc, framealpha=0.8, facecolor=self.color_palettes[self.theme]["background"],
                          edgecolor=self.color_palettes[self.theme]["grid"], 
                          labelcolor=self.color_palettes[self.theme]["text"])
    
    def add_watermark(self, text: str = "XplainCrypto"):
        """Add a watermark to the figure."""
        if self.fig:
            self.fig.text(0.5, 0.5, text, fontsize=40, color=self.color_palettes[self.theme]["grid"],
                         ha='center', va='center', alpha=0.1, rotation=30)
    
    def add_timestamp(self):
        """Add a timestamp to the figure."""
        if self.fig:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.fig.text(0.99, 0.01, f"Generated: {timestamp}", fontsize=8, 
                         color=self.color_palettes[self.theme]["text"], ha='right', va='bottom', alpha=0.7)
    
    def save_figure(self, filename: str, dpi: int = 300):
        """Save the figure to a file."""
        if self.fig:
            self.fig.savefig(filename, dpi=dpi, bbox_inches='tight', 
                           facecolor=self.color_palettes[self.theme]["background"])
            logger.info(f"Saved figure to {filename}")
            return True
        return False
    
    def export_to_pdf(self, filename: str):
        """Export the current chart to PDF."""
        if self.fig:
            self.fig.savefig(filename, format='pdf', dpi=300, bbox_inches='tight',
                           facecolor=self.color_palettes[self.theme]["background"])
            logger.info(f"Exported figure to PDF: {filename}")
            return True
        return False
    
    def get_figure_as_bytes(self, format: str = 'png'):
        """Get the figure as bytes in the specified format."""
        if self.fig:
            buf = io.BytesIO()
            self.fig.savefig(buf, format=format, dpi=300, bbox_inches='tight',
                           facecolor=self.color_palettes[self.theme]["background"])
            buf.seek(0)
            return buf.getvalue()
        return None
    
    def close_figure(self):
        """Close the current figure."""
        if self.fig:
            plt.close(self.fig)
            self.fig = None
            self.ax = None


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
