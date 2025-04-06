"""
Enhanced pie chart visualizer for XplainCrypto with PDF optimization.
This module provides advanced pie chart visualization capabilities specifically optimized for
cryptocurrency metrics visualization in PDF reports.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
import logging
from .base import BaseVisualizer

# Configure logging
logger = logging.getLogger(__name__)

class PieChartVisualizer(BaseVisualizer):
    """Enhanced pie chart visualizer with PDF optimization."""
    
    def __init__(self, theme: str = "dark", pdf_optimized: bool = True):
        """
        Initialize the pie chart visualizer.
        
        Args:
            theme: Color theme to use ('dark' or 'light')
            pdf_optimized: Whether to optimize for PDF output
        """
        super().__init__(theme, pdf_optimized)
    
    def plot_token_distribution_pie(self, data: Dict[str, float], title: str = "Token Distribution",
                                   explode_largest: bool = True, donut: bool = True):
        """
        Create a pie chart showing token distribution.
        
        Args:
            data: Dictionary mapping category names to percentages
            title: Chart title
            explode_largest: Whether to explode the largest segment
            donut: Whether to create a donut chart
            
        Returns:
            The created figure
        """
        # Sort data by value in descending order
        sorted_data = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))
        
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Get colors from palette
        colors = self.color_palettes[self.theme]["primary"]
        
        # Create explode array if needed
        explode = None
        if explode_largest:
            explode = [0.1] + [0] * (len(sorted_data) - 1)
        
        # Plot pie chart
        wedges, texts, autotexts = self.ax.pie(
            list(sorted_data.values()),
            labels=list(sorted_data.keys()),
            autopct='%1.1f%%',
            startangle=90,
            explode=explode,
            colors=[colors[i % len(colors)] for i in range(len(sorted_data))],
            wedgeprops={'edgecolor': self.color_palettes[self.theme]["background"], 'linewidth': 1.5},
            textprops={'color': self.color_palettes[self.theme]["text"]}
        )
        
        # Style the percentage text
        for autotext in autotexts:
            autotext.set_fontweight('bold')
        
        # Create donut hole if requested
        if donut:
            # Draw a circle at the center to create a donut chart
            centre_circle = plt.Circle((0, 0), 0.5, fc=self.color_palettes[self.theme]["background"])
            self.ax.add_artist(centre_circle)
            
            # Add total in the center
            total = sum(sorted_data.values())
            self.ax.text(0, 0, f"Total\n{total:.1f}%", ha='center', va='center',
                       fontsize=14, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Set equal aspect ratio
        self.ax.set_aspect('equal')
        
        # Set title
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_market_share_pie(self, data: Dict[str, float], title: str = "Market Share",
                             min_percentage: float = 3.0):
        """
        Create a pie chart showing market share with small segments grouped as "Others".
        
        Args:
            data: Dictionary mapping entity names to market share percentages
            title: Chart title
            min_percentage: Minimum percentage to show as a separate segment
            
        Returns:
            The created figure
        """
        # Sort data by value in descending order
        sorted_data = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))
        
        # Group small segments as "Others"
        main_segments = {}
        others_total = 0
        
        for name, value in sorted_data.items():
            if value >= min_percentage:
                main_segments[name] = value
            else:
                others_total += value
        
        # Add "Others" segment if needed
        if others_total > 0:
            main_segments["Others"] = others_total
        
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Get colors from palette
        colors = self.color_palettes[self.theme]["primary"]
        
        # Plot pie chart
        wedges, texts, autotexts = self.ax.pie(
            list(main_segments.values()),
            labels=list(main_segments.keys()),
            autopct='%1.1f%%',
            startangle=90,
            colors=[colors[i % len(colors)] for i in range(len(main_segments))],
            wedgeprops={'edgecolor': self.color_palettes[self.theme]["background"], 'linewidth': 1.5},
            textprops={'color': self.color_palettes[self.theme]["text"]}
        )
        
        # Style the percentage text
        for autotext in autotexts:
            autotext.set_fontweight('bold')
        
        # Set equal aspect ratio
        self.ax.set_aspect('equal')
        
        # Set title
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_nested_pie(self, inner_data: Dict[str, float], outer_data: Dict[str, Dict[str, float]],
                       title: str = "Nested Distribution"):
        """
        Create a nested pie chart (sunburst) for hierarchical data.
        
        Args:
            inner_data: Dictionary mapping category names to percentages for inner ring
            outer_data: Dictionary mapping inner category names to dictionaries of subcategories
            title: Chart title
            
        Returns:
            The created figure
        """
        # Create figure
        self.fig, self.ax = plt.subplots(figsize=(12, 12))
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Get colors from palette
        colors = self.color_palettes[self.theme]["primary"]
        
        # Plot inner pie
        inner_wedges, inner_texts = self.ax.pie(
            list(inner_data.values()),
            radius=0.7,
            labels=list(inner_data.keys()),
            labeldistance=0.7,
            wedgeprops={'width': 0.4, 'edgecolor': self.color_palettes[self.theme]["background"], 'linewidth': 1.5},
            textprops={'color': self.color_palettes[self.theme]["text"], 'fontweight': 'bold'}
        )
        
        # Create a mapping of inner categories to colors
        inner_colors = {category: colors[i % len(colors)] for i, category in enumerate(inner_data.keys())}
        
        # Prepare data for outer pie
        outer_values = []
        outer_labels = []
        outer_colors = []
        
        # Track the starting angle for each inner segment
        start_angle = 90
        inner_angles = {}
        
        # Calculate angles for inner segments
        total = sum(inner_data.values())
        for category, value in inner_data.items():
            angle = 360 * value / total
            inner_angles[category] = (start_angle, angle)
            start_angle += angle
        
        # Prepare outer segments
        for inner_category, subcategories in outer_data.items():
            if inner_category not in inner_data:
                continue
                
            # Get base color for this category
            base_color = inner_colors[inner_category]
            
            # Create color variations for subcategories
            n_subcategories = len(subcategories)
            for i, (subcategory, value) in enumerate(subcategories.items()):
                outer_values.append(value)
                outer_labels.append(subcategory if value > 5 else '')  # Only label if segment is large enough
                
                # Create a slightly different shade of the base color
                brightness_factor = 0.7 + 0.3 * (i / max(1, n_subcategories - 1))
                r, g, b = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)
                r = min(255, int(r * brightness_factor))
                g = min(255, int(g * brightness_factor))
                b = min(255, int(b * brightness_factor))
                color = f'#{r:02x}{g:02x}{b:02x}'
                outer_colors.append(color)
        
        # Plot outer pie
        outer_wedges, outer_texts = self.ax.pie(
            outer_values,
            radius=1.0,
            labels=outer_labels,
            labeldistance=1.05,
            wedgeprops={'width': 0.3, 'edgecolor': self.color_palettes[self.theme]["background"], 'linewidth': 1.5},
            textprops={'color': self.color_palettes[self.theme]["text"], 'fontsize': 9}
        )
        
        # Set equal aspect ratio
        self.ax.set_aspect('equal')
        
        # Set title
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
    
    def plot_valuation_range(self, current_price: float, valuation_ranges: Dict[str, Tuple[float, float]],
                            title: str = "Valuation Range"):
        """
        Create a pie chart showing different valuation scenarios.
        
        Args:
            current_price: Current price of the token
            valuation_ranges: Dictionary mapping scenario names to (min, max) price tuples
            title: Chart title
            
        Returns:
            The created figure
        """
        # Create figure with two subplots (pie chart and table)
        self.fig, (self.ax, table_ax) = plt.subplots(2, 1, figsize=(10, 12), 
                                                   gridspec_kw={'height_ratios': [3, 1]})
        self.fig.patch.set_facecolor(self.color_palettes[self.theme]["background"])
        self.ax.set_facecolor(self.color_palettes[self.theme]["background"])
        table_ax.set_facecolor(self.color_palettes[self.theme]["background"])
        
        # Get colors from palette
        colors = self.color_palettes[self.theme]["primary"]
        
        # Calculate average values and potential returns for each scenario
        avg_values = {}
        returns = {}
        
        for scenario, (min_val, max_val) in valuation_ranges.items():
            avg = (min_val + max_val) / 2
            avg_values[scenario] = avg
            returns[scenario] = (avg / current_price - 1) * 100
        
        # Sort scenarios by average value
        sorted_scenarios = sorted(avg_values.items(), key=lambda x: x[1])
        scenarios = [s[0] for s in sorted_scenarios]
        avgs = [s[1] for s in sorted_scenarios]
        
        # Plot pie chart of average valuations
        wedges, texts, autotexts = self.ax.pie(
            avgs,
            labels=scenarios,
            autopct='%1.1f%%',
            startangle=90,
            colors=[colors[i % len(colors)] for i in range(len(scenarios))],
            wedgeprops={'edgecolor': self.color_palettes[self.theme]["background"], 'linewidth': 1.5},
            textprops={'color': self.color_palettes[self.theme]["text"]}
        )
        
        # Style the percentage text
        for autotext in autotexts:
            autotext.set_fontweight('bold')
        
        # Create a donut hole
        centre_circle = plt.Circle((0, 0), 0.5, fc=self.color_palettes[self.theme]["background"])
        self.ax.add_artist(centre_circle)
        
        # Add current price in the center
        self.ax.text(0, 0, f"Current\n${current_price:.2f}", ha='center', va='center',
                   fontsize=14, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Set equal aspect ratio
        self.ax.set_aspect('equal')
        
        # Set title for pie chart
        self.ax.set_title(title, fontsize=16, fontweight='bold', color=self.color_palettes[self.theme]["text"])
        
        # Create table with detailed valuation data
        table_data = []
        table_data.append(["Scenario", "Min ($)", "Max ($)", "Avg ($)", "Return (%)"])
        
        for scenario in scenarios:
            min_val, max_val = valuation_ranges[scenario]
            avg = avg_values[scenario]
            ret = returns[scenario]
            
            # Format values
            min_str = f"${min_val:.2f}"
            max_str = f"${max_val:.2f}"
            avg_str = f"${avg:.2f}"
            ret_str = f"{ret:.1f}%"
            
            table_data.append([scenario, min_str, max_str, avg_str, ret_str])
        
        # Create the table
        table = table_ax.table(
            cellText=table_data,
            cellLoc='center',
            loc='center',
            colWidths=[0.25, 0.15, 0.15, 0.15, 0.15]
        )
        
        # Style the table
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)
        
        # Color the header row
        for j, cell in enumerate(table._cells[(0, j)] for j in range(len(table_data[0]))):
            cell.set_facecolor(self.color_palettes[self.theme]["accent"])
            cell.set_text_props(color='white', fontweight='bold')
        
        # Color positive and negative returns
        for i in range(1, len(table_data)):
            ret_cell = table._cells[(i, 4)]
            ret_val = returns[scenarios[i-1]]
            
            if ret_val > 0:
                ret_cell.set_facecolor(self.color_palettes[self.theme]["positive"])
            elif ret_val < 0:
                ret_cell.set_facecolor(self.color_palettes[self.theme]["negative"])
        
        # Hide table axes
        table_ax.axis('off')
        
        # Add timestamp and watermark
        self.add_timestamp()
        self.add_watermark()
        
        # Adjust layout
        plt.tight_layout()
        
        return self.fig
