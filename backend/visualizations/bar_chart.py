"""
Enhanced bar chart visualizer for XplainCrypto with PDF optimization.
This module provides advanced bar chart visualization capabilities specifically optimized for
cryptocurrency metrics visualization in PDF reports.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
from datetime import datetime
from matplotlib.colors import LinearSegmentedColormap
import logging
from .base import BaseVisualizer

# Configure logging
logger = logging.getLogger(__name__)

class BarChartVisualizer(BaseVisualizer):
    """Enhanced bar chart visualizer with PDF optimization."""
    
    def __init__(self, theme: str = "dark", pdf_optimized: bool = True):
        """
        Initialize the bar chart visualizer.
        
        Args:
            theme: Color theme to use ('dark' or 'light')
            pdf_optimized: Whether to optimize for PDF output
        """
        super().__init__(theme, pdf_optimized)
    
    def plot_market_dominance(self, data: Dict[str, float], title: str = "Market Dominance"):
        """
        Create a bar chart showing market dominance of different cryptocurrencies.
        
        Args:
            data: Dictionary mapping cryptocurrency names to market dominance percentages
            title: Chart title
            
        Returns:
            The created figure
        """
        # Sort data by value in descending order
        sorted_data = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))
        
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Get colors from palette
        colors = self.color_palettes[self.theme]["primary"]
        
        # Plot horizontal bars
        bars = self.ax.barh(list(sorted_data.keys()), list(sorted_data.values()), 
                           color=[colors[i % len(colors)] for i in range(len(sorted_data))])
        
        # Add value labels to the bars
        for bar in bars:
            width = bar.get_width()
            label_x_pos = width + 0.5
            self.ax.text(label_x_pos, bar.get_y() + bar.get_height()/2, f'{width:.1f}%',
                       va='center', color=self.color_palettes[self.theme]["text"])
        
        # Set labels and title
        self.ax.set_xlabel('Market Dominance (%)', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Format axes
        self.ax.tick_params(axis='both', colors=self.color_palettes[self.theme]["text"])
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_token_distribution(self, data: Dict[str, float], title: str = "Token Distribution"):
        """
        Create a horizontal stacked bar chart showing token distribution.
        
        Args:
            data: Dictionary mapping category names to percentages
            title: Chart title
            
        Returns:
            The created figure
        """
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 4))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Get colors from palette
        colors = self.color_palettes[self.theme]["primary"]
        
        # Plot horizontal stacked bar
        categories = list(data.keys())
        values = list(data.values())
        
        # Calculate positions for the stacked bars
        positions = [0]
        for value in values[:-1]:
            positions.append(positions[-1] + value)
        
        # Plot each segment
        for i, (category, value) in enumerate(zip(categories, values)):
            color_idx = i % len(colors)
            self.ax.barh(["Token Distribution"], [value], left=positions[i], 
                        color=colors[color_idx], label=category)
            
            # Add percentage labels in the middle of each segment
            if value >= 5:  # Only add label if segment is large enough
                label_x_pos = positions[i] + value/2
                self.ax.text(label_x_pos, 0, f'{category}\n{value:.1f}%',
                           ha='center', va='center', color='white', fontweight='bold')
        
        # Remove y-axis labels and ticks
        self.ax.set_yticks([])
        self.ax.set_yticklabels([])
        
        # Set labels and title
        self.ax.set_xlabel('Percentage (%)', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Format axes
        self.ax.tick_params(axis='x', colors=self.color_palettes[self.theme]["text"])
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
        
        # Add legend, timestamp, and watermark
        self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=len(categories),
                      framealpha=0.8, facecolor=self.color_palettes[self.theme]["background"],
                      edgecolor=self.color_palettes[self.theme]["grid"], 
                      labelcolor=self.color_palettes[self.theme]["text"])
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_comparison_bars(self, categories: List[str], data_sets: List[Dict[str, Any]], 
                            title: str = "Comparison"):
        """
        Create a grouped bar chart for comparing multiple data sets across categories.
        
        Args:
            categories: List of category names
            data_sets: List of dictionaries with 'name' and 'values' (list matching categories)
            title: Chart title
            
        Returns:
            The created figure
        """
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Calculate positions for the grouped bars
        n_datasets = len(data_sets)
        bar_width = 0.8 / n_datasets
        
        # Plot each data set as a group of bars
        for i, data_set in enumerate(data_sets):
            name = data_set['name']
            values = data_set['values']
            
            # Calculate positions for this group
            positions = np.arange(len(categories)) - 0.4 + (i + 0.5) * bar_width
            
            # Get color from palette
            color_idx = i % len(self.color_palettes[self.theme]["primary"])
            color = self.color_palettes[self.theme]["primary"][color_idx]
            
            # Plot the bars
            bars = self.ax.bar(positions, values, bar_width, label=name, color=color)
            
            # Add value labels to the bars
            for bar in bars:
                height = bar.get_height()
                self.ax.text(bar.get_x() + bar.get_width()/2, height + 0.1,
                           f'{height:.1f}', ha='center', va='bottom',
                           color=self.color_palettes[self.theme]["text"], fontsize=9)
        
        # Set x-axis ticks and labels
        self.ax.set_xticks(np.arange(len(categories)))
        self.ax.set_xticklabels(categories, rotation=45, ha='right',
                              color=self.color_palettes[self.theme]["text"])
        
        # Set labels and title
        self.ax.set_ylabel('Value', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Format axes
        self.ax.tick_params(axis='both', colors=self.color_palettes[self.theme]["text"])
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
        
        # Add legend, timestamp, and watermark
        self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=n_datasets,
                      framealpha=0.8, facecolor=self.color_palettes[self.theme]["background"],
                      edgecolor=self.color_palettes[self.theme]["grid"], 
                      labelcolor=self.color_palettes[self.theme]["text"])
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_risk_matrix(self, risks: List[Dict[str, Any]], title: str = "Risk Assessment Matrix"):
        """
        Create a risk assessment matrix visualization.
        
        Args:
            risks: List of dictionaries with 'name', 'impact' (1-5), and 'likelihood' (1-5)
            title: Chart title
            
        Returns:
            The created figure
        """
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Define risk zones
        risk_zones = np.zeros((5, 5))
        
        # Low risk (green)
        risk_zones[0, 0:2] = 1
        risk_zones[1, 0] = 1
        
        # Medium risk (yellow)
        risk_zones[0, 2:5] = 2
        risk_zones[1, 1:3] = 2
        risk_zones[2, 0:2] = 2
        risk_zones[3, 0] = 2
        
        # High risk (orange)
        risk_zones[1, 3:5] = 3
        risk_zones[2, 2:4] = 3
        risk_zones[3, 1:3] = 3
        risk_zones[4, 0:2] = 3
        
        # Critical risk (red)
        risk_zones[2, 4] = 4
        risk_zones[3, 3:5] = 4
        risk_zones[4, 2:5] = 4
        
        # Create custom colormap for risk zones
        colors = [self.color_palettes[self.theme]["positive"],  # Low risk
                 self.color_palettes[self.theme]["neutral"],   # Medium risk
                 "#ff9f43",                                    # High risk
                 self.color_palettes[self.theme]["negative"]]  # Critical risk
        cmap = LinearSegmentedColormap.from_list("risk_cmap", colors, N=4)
        
        # Plot risk zones
        im = self.ax.imshow(risk_zones, cmap=cmap, origin='lower', extent=[0.5, 5.5, 0.5, 5.5])
        
        # Plot risk points
        for risk in risks:
            name = risk['name']
            impact = risk['impact']
            likelihood = risk['likelihood']
            
            # Add some jitter to prevent overlapping
            jitter_x = np.random.uniform(-0.1, 0.1)
            jitter_y = np.random.uniform(-0.1, 0.1)
            
            # Plot point
            self.ax.plot(likelihood + jitter_x, impact + jitter_y, 'o', 
                       markersize=12, color='white', markeredgecolor='black')
            
            # Add label
            self.ax.annotate(name, (likelihood + jitter_x, impact + jitter_y),
                           xytext=(5, 5), textcoords='offset points',
                           color=self.color_palettes[self.theme]["text"],
                           fontsize=9, fontweight='bold')
        
        # Set axis limits and labels
        self.ax.set_xlim(0.5, 5.5)
        self.ax.set_ylim(0.5, 5.5)
        self.ax.set_xlabel('Likelihood', fontsize=12, color=self.color_palettes[self.theme]["text"])
        self.ax.set_ylabel('Impact', fontsize=12, color=self.color_palettes[self.theme]["text"])
        
        # Set ticks
        self.ax.set_xticks(np.arange(1, 6))
        self.ax.set_yticks(np.arange(1, 6))
        self.ax.tick_params(axis='both', colors=self.color_palettes[self.theme]["text"])
        
        # Add grid
        self.ax.grid(True, linestyle='-', alpha=0.3, color=self.color_palettes[self.theme]["grid"])
        
        # Add risk zone labels
        self.ax.text(1.5, 1, "LOW", ha='center', va='center', color='black', fontweight='bold')
        self.ax.text(2.5, 2, "MEDIUM", ha='center', va='center', color='black', fontweight='bold')
        self.ax.text(3.5, 3, "HIGH", ha='center', va='center', color='black', fontweight='bold')
        self.ax.text(4.5, 4.5, "CRITICAL", ha='center', va='center', color='black', fontweight='bold')
        
        # Set title
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
