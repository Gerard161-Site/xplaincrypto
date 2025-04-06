"""
Enhanced line chart visualizer for XplainCrypto with PDF optimization and real-time data support.
This module provides advanced line chart visualization capabilities specifically optimized for
cryptocurrency price and metric visualization in PDF reports.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
from datetime import datetime, timedelta
from matplotlib.colors import LinearSegmentedColormap
import logging
from .base import BaseVisualizer

# Configure logging
logger = logging.getLogger(__name__)

class LineChartVisualizer(BaseVisualizer):
    """Enhanced line chart visualizer with PDF optimization and real-time data support."""
    
    def __init__(self, theme: str = "dark", pdf_optimized: bool = True):
        """
        Initialize the line chart visualizer.
        
        Args:
            theme: Color theme to use ('dark' or 'light')
            pdf_optimized: Whether to optimize for PDF output
        """
        super().__init__(theme, pdf_optimized)
    
    def plot_price_chart(self, data: List[Dict[str, Any]], title: str = "Price Chart", 
                        show_volume: bool = True, add_indicators: bool = True,
                        moving_averages: List[int] = None):
        """
        Create a price chart with optional volume and indicators.
        
        Args:
            data: List of data points with 'timestamp', 'price', and optionally 'volume'
            title: Chart title
            show_volume: Whether to show volume bars
            add_indicators: Whether to add technical indicators
            moving_averages: List of periods for moving averages (e.g., [7, 30, 90])
            
        Returns:
            The created figure
        """
        # Convert data to DataFrame for easier manipulation
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Create figure with appropriate size
        if show_volume:
            # Create figure with two subplots (price and volume)
            self.fig, (self.ax, volume_ax) = plt.subplots(2, 1, figsize=(12, 8), 
                                                         gridspec_kw={'height_ratios': [3, 1]},
                                                         sharex=True)
            self.fig.subplots_adjust(hspace=0)
        else:
            # Create figure with just price
            self.fig, self.ax = plt.subplots(figsize=(12, 6))
        
        # Set background colors
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Plot price line with gradient fill
        line_color = self.color_palettes[self.theme]["primary"][0]
        fill_color = self.color_palettes[self.theme]["primary"][0]
        
        # Plot the price line
        line = self.ax.plot(df['timestamp'], df['price'], color=line_color, linewidth=2.5, label='Price')
        
        # Add gradient fill below the line
        min_price = df['price'].min()
        self.ax.fill_between(df['timestamp'], df['price'], min_price, 
                           color=fill_color, alpha=0.2)
        
        # Add moving averages if requested
        if add_indicators and moving_averages:
            for period in moving_averages:
                if len(df) > period:
                    ma_col = f'MA_{period}'
                    df[ma_col] = df['price'].rolling(window=period).mean()
                    color_idx = moving_averages.index(period) % len(self.color_palettes[self.theme]["primary"])
                    ma_color = self.color_palettes[self.theme]["primary"][color_idx]
                    self.ax.plot(df['timestamp'], df[ma_col], color=ma_color, 
                               linewidth=1.5, label=f'{period}-day MA')
        
        # Format the price axis
        self.ax.set_ylabel('Price', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.tick_params(axis='y', colors=self.color_palettes[self.theme]["text"])
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
        
        # Add volume subplot if requested
        if show_volume and 'volume' in df.columns:
            volume_ax.bar(df['timestamp'], df['volume'], color=self.color_palettes[self.theme]["accent"], 
                         alpha=0.7, width=0.8)
            volume_ax.set_ylabel('Volume', fontsize=12, color=self.color_palettes[self.theme]["text"])
            volume_ax.tick_params(axis='y', colors=self.color_palettes[self.theme]["text"])
            volume_ax.tick_params(axis='x', colors=self.color_palettes[self.theme]["text"])
            volume_ax.set_facecolor(self.color_palettes[self.theme]["background"])
            volume_ax.grid(True, linestyle='--', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
            
            # Format x-axis dates
            volume_ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            volume_ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        else:
            # Format x-axis dates on the main axis
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            self.ax.tick_params(axis='x', colors=self.color_palettes[self.theme]["text"])
        
        # Add title and legend
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        self.ax.legend(loc='upper left', framealpha=0.8, facecolor=self.color_palettes[self.theme]["background"],
                      edgecolor=self.color_palettes[self.theme]["grid"], 
                      labelcolor=self.color_palettes[self.theme]["text"])
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_comparison_chart(self, data_sets: List[Dict[str, Any]], title: str = "Comparison Chart",
                             normalize: bool = True):
        """
        Create a comparison chart with multiple data series.
        
        Args:
            data_sets: List of dictionaries with 'name', 'timestamps', and 'values'
            title: Chart title
            normalize: Whether to normalize values to percentage change from start
            
        Returns:
            The created figure
        """
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Plot each data series
        for i, data_set in enumerate(data_sets):
            name = data_set['name']
            timestamps = pd.to_datetime(data_set['timestamps'])
            values = np.array(data_set['values'])
            
            # Normalize to percentage change if requested
            if normalize and len(values) > 0:
                start_value = values[0]
                values = [(v / start_value - 1) * 100 for v in values]
            
            # Get color from palette
            color_idx = i % len(self.color_palettes[self.theme]["primary"])
            color = self.color_palettes[self.theme]["primary"][color_idx]
            
            # Plot the line
            self.ax.plot(timestamps, values, color=color, linewidth=2.5, label=name)
        
        # Set labels and title
        if normalize:
            self.ax.set_ylabel('Percentage Change (%)', fontsize=12, color=self.color_palettes[self.theme]["text"])
        else:
            self.ax.set_ylabel('Value', fontsize=12, color=self.color_palettes[self.theme]["text"])
        
        self.ax.set_xlabel('Date', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Format axes
        self.ax.tick_params(axis='both', colors=self.color_palettes[self.theme]["text"])
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
        
        # Format x-axis dates
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        
        # Add legend, timestamp, and watermark
        self.ax.legend(loc='best', framealpha=0.8, facecolor=self.color_palettes[self.theme]["background"],
                      edgecolor=self.color_palettes[self.theme]["grid"], 
                      labelcolor=self.color_palettes[self.theme]["text"])
        self.add_timestamp()
        self.add_watermark()
        
        # Add zero line for normalized charts
        if normalize:
            self.ax.axhline(y=0, color=self.color_palettes[self.theme]["grid"], linestyle='-', alpha=0.5)
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_correlation_chart(self, data: Dict[str, List[float]], title: str = "Correlation Matrix"):
        """
        Create a correlation matrix heatmap.
        
        Args:
            data: Dictionary mapping asset names to price lists (all lists must be same length)
            title: Chart title
            
        Returns:
            The created figure
        """
        # Convert data to DataFrame
        df = pd.DataFrame(data)
        
        # Calculate correlation matrix
        corr_matrix = df.corr()
        
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Create custom colormap for correlation values
        colors = [self.color_palettes[self.theme]["negative"], 
                 self.color_palettes[self.theme]["background"], 
                 self.color_palettes[self.theme]["positive"]]
        cmap = LinearSegmentedColormap.from_list("correlation_cmap", colors, N=100)
        
        # Plot heatmap
        im = self.ax.imshow(corr_matrix, cmap=cmap, vmin=-1, vmax=1)
        
        # Add colorbar
        cbar = self.fig.colorbar(im, ax=self.ax)
        cbar.ax.tick_params(colors=self.color_palettes[self.theme]["text"])
        
        # Set ticks and labels
        tick_labels = list(data.keys())
        self.ax.set_xticks(np.arange(len(tick_labels)))
        self.ax.set_yticks(np.arange(len(tick_labels)))
        self.ax.set_xticklabels(tick_labels, rotation=45, ha="right", 
                              color=self.color_palettes[self.theme]["text"])
        self.ax.set_yticklabels(tick_labels, color=self.color_palettes[self.theme]["text"])
        
        # Add correlation values in cells
        for i in range(len(tick_labels)):
            for j in range(len(tick_labels)):
                value = corr_matrix.iloc[i, j]
                text_color = "white" if abs(value) > 0.5 else "black"
                self.ax.text(j, i, f"{value:.2f}", ha="center", va="center", 
                           color=text_color, fontweight="bold")
        
        # Add title
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_token_metrics(self, timestamps: List[datetime], metrics: Dict[str, List[float]], 
                          title: str = "Token Metrics"):
        """
        Create a multi-line chart for token metrics.
        
        Args:
            timestamps: List of datetime objects
            metrics: Dictionary mapping metric names to value lists
            title: Chart title
            
        Returns:
            The created figure
        """
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Plot each metric
        for i, (metric_name, values) in enumerate(metrics.items()):
            # Get color from palette
            color_idx = i % len(self.color_palettes[self.theme]["primary"])
            color = self.color_palettes[self.theme]["primary"][color_idx]
            
            # Plot the line
            self.ax.plot(timestamps, values, color=color, linewidth=2.5, label=metric_name)
        
        # Set labels and title
        self.ax.set_ylabel('Value', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.set_xlabel('Date', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Format axes
        self.ax.tick_params(axis='both', colors=self.color_palettes[self.theme]["text"])
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
        
        # Format x-axis dates
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        
        # Add legend, timestamp, and watermark
        self.ax.legend(loc='best', framealpha=0.8, facecolor=self.color_palettes[self.theme]["background"],
                      edgecolor=self.color_palettes[self.theme]["grid"], 
                      labelcolor=self.color_palettes[self.theme]["text"])
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
