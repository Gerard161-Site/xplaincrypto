import os
import json
import logging
from typing import Dict, Any, List, Optional
import matplotlib
# Set non-interactive backend first to avoid GUI issues
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime
from langchain_openai import ChatOpenAI
import random
import time
import textwrap
from matplotlib.patches import Rectangle
from backend.utils.style_utils import StyleManager
import matplotlib.patheffects as path_effects
from matplotlib.table import Table
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import copy
import math
import re
import io
import base64
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from PIL import Image as PILImage
from pathlib import Path

class VisualizationAgent:
    def __init__(self, project_name: str, logger: logging.Logger, llm: Optional[ChatOpenAI] = None):
        self.project_name = project_name
        self.logger = logger
        self.llm = llm or ChatOpenAI(temperature=0)
        
        # Set up output directory
        self.output_dir = os.path.join("docs", self.project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize style manager
        self.style_manager = StyleManager(logger)
        self.style_manager.configure_matplotlib()
        self.vis_config = self.style_manager.get_visualization_config()
        self.colors = self.style_manager.get_colors()
        
        # Load visualization configuration
        self.visualization_config = self._load_visualization_config()
        
        with open(os.path.join(self.output_dir, '.gitkeep'), 'w') as f:
            pass
        
        # Track already generated visualizations to avoid duplicates
        self.generated_visualizations = set()
    
    def _load_visualization_config(self) -> Dict:
        try:
            with open("backend/config/report_config.json", "r") as f:
                config = json.load(f)
                return config.get("visualization_types", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading visualization config: {e}")
            return {}
    
    def generate_visualization(self, vis_type: str, data: Dict[str, Any], skip_expensive_descriptions: bool = False, use_real_data_only: bool = False) -> Dict[str, Any]:
        self.logger.info(f"Generating visualization: {vis_type}")
        
        # Store the use_real_data_only flag as an instance variable
        self.use_real_data_only = use_real_data_only
        
        vis_config = self.visualization_config.get(vis_type, {})
        if not vis_config:
            self.logger.warning(f"No configuration found for visualization type: {vis_type}")
            return {"error": f"No configuration for {vis_type}"}
        
        chart_type = vis_config.get("type", "")
        result = {}
        
        try:
            self.logger.debug(f"Input data for {vis_type}: {data}")
            if chart_type == "line_chart":
                result = self._generate_line_chart(vis_type, vis_config, data)
            elif chart_type == "bar_chart":
                result = self._generate_bar_chart(vis_type, vis_config, data)
            elif chart_type == "pie_chart":
                result = self._generate_pie_chart(vis_type, vis_config, data)
            elif chart_type == "table":
                result = self._generate_table(vis_type, vis_config, data)
            elif chart_type == "timeline":
                result = self._generate_timeline(vis_type, vis_config, data)
            else:
                self.logger.warning(f"Unsupported chart type: {chart_type}")
                return {"error": f"Unsupported chart type: {chart_type}"}
            
            if result and isinstance(result, dict):
                if "file_path" in result and os.path.exists(result["file_path"]):
                    result["absolute_path"] = os.path.abspath(result["file_path"])
                    if self.llm and not skip_expensive_descriptions:
                        description = self._generate_description(vis_type, vis_config, data, result)
                        result["description"] = description
                    self.logger.info(f"Successfully generated {vis_type} at {result['file_path']}")
                elif "error" in result:
                    # Specific error was already logged by the visualization method
                    self.logger.warning(f"Error generating {vis_type}: {result['error']}")
                    return {"error": result["error"]}
                else:
                    error_msg = f"Generated visualization file does not exist: {result.get('file_path', 'No path')}"
                    self.logger.warning(error_msg)
                    return {"error": f"Failed to create visualization file for {vis_type}"}
            else:
                error_msg = f"Invalid result format for {vis_type}"
                self.logger.warning(error_msg)
                return {"error": f"Failed to generate {vis_type}"}
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating {vis_type}: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def _generate_line_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a line chart visualization"""
        data_field = config.get("data_field", "")
        self.logger.debug(f"Looking for data field: {data_field} in {vis_type}")
        
        # Look for data in the specified field and alternative field names
        alternative_fields = []
        
        # Add alternative field names based on chart type
        if vis_type == "price_history_chart":
            alternative_fields = ["prices", "price_history", "price_data"]
        elif vis_type == "volume_chart" or vis_type == "liquidity_trends_chart":
            alternative_fields = ["total_volumes", "volume_history", "volumes"]
        elif vis_type == "tvl_chart":
            alternative_fields = ["tvl_history", "tvl_data"]
            
        # Try direct field first
        if data_field in data and data[data_field]:
            series_data = data[data_field]
            self.logger.info(f"Using data from field '{data_field}' for {vis_type}")
        else:
            # Try alternative fields
            found_field = None
            for field in alternative_fields:
                if field in data and data[field]:
                    series_data = data[field]
                    found_field = field
                    self.logger.info(f"Using data from alternative field '{field}' for {vis_type}")
                    break
                    
            if not found_field:
                # No valid data found - do not generate this chart
                error_msg = f"No data found for {vis_type} in any of these fields: {[data_field] + alternative_fields}"
                self.logger.error(error_msg)
                return {"error": error_msg}
        
        # Validate that we have usable data
        if not series_data or not isinstance(series_data, (list, tuple)) or len(series_data) < 2:
            return {"error": f"Insufficient data points for {vis_type}"}
            
        # Create the chart with standardized figure size to match text width
        plt.figure(figsize=(6.5, 3.5))  # Further reduced from 7.0 to 6.5
        start_value = end_value = min_value = max_value = 0
        data_points = len(series_data)
        
        try:
            # Plot based on data format
            if isinstance(series_data[0], (int, float)):
                # Simple array of values
                plt.plot(series_data, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(range(len(series_data)), series_data, color='#1f77b4', alpha=0.1)
                start_value = series_data[0]
                end_value = series_data[-1]
                min_value = min(series_data)
                max_value = max(series_data)
                
            elif isinstance(series_data[0], dict) and 'timestamp' in series_data[0] and 'value' in series_data[0]:
                # Array of objects with timestamp and value
                timestamps = [item.get('timestamp') for item in series_data]
                values = [item.get('value', 0) for item in series_data]
                plt.plot(timestamps, values, marker='o', linestyle='-', color='#1f77b4', alpha=0.7)
                start_value = values[0] if values else 0
                end_value = values[-1] if values else 0
                min_value = min(values) if values else 0
                max_value = max(values) if values else 0
                
            elif isinstance(series_data[0], list) and len(series_data[0]) >= 2:
                # Array of [timestamp, value] pairs
                timestamps = [item[0] for item in series_data]
                values = [item[1] for item in series_data]
                
                # Convert timestamps if they're in milliseconds
                if timestamps and timestamps[0] > 1e10:
                    timestamps = [ts/1000 for ts in timestamps]
                
                plt.plot(timestamps, values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(timestamps, values, color='#1f77b4', alpha=0.1)
                start_value = values[0] if values else 0
                end_value = values[-1] if values else 0
                min_value = min(values) if values else 0
                max_value = max(values) if values else 0
                
                # Format x-axis as dates
                plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: 
                    datetime.fromtimestamp(x).strftime('%m/%d') if x > 1e8 else str(int(x))))
            else:
                return {"error": f"Unsupported data format for {vis_type}"}
                
        except Exception as e:
            self.logger.error(f"Error plotting data for {vis_type}: {str(e)}")
            return {"error": f"Failed to plot chart: {str(e)}"}
        
        # Add chart labels and styling
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title, pad=10, fontsize=12, fontfamily='Times New Roman')
        
        if vis_type == "price_history_chart":
            plt.xlabel("Time", labelpad=10)
            plt.ylabel("Price (USD)", labelpad=10)
        elif vis_type == "volume_chart" or vis_type == "liquidity_trends_chart":
            plt.xlabel("Time", labelpad=10)
            plt.ylabel("Volume (USD)", labelpad=10)
        elif vis_type == "tvl_chart":
            plt.xlabel("Time", labelpad=10)
            plt.ylabel("TVL (USD)", labelpad=10)
        else:
            plt.xlabel("Time", labelpad=10)
            plt.ylabel("Value", labelpad=10)
        
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save with consistent filename without timestamp
        filename = f"{vis_type}.png"
        file_path = os.path.join(self.output_dir, filename)
        plt.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        # Calculate percent change
        percent_change = 0
        if start_value and end_value:
            percent_change = ((end_value - start_value) / start_value) * 100
            
        return {
            "file_path": file_path,
            "title": title,
            "data_summary": {
                "start_value": start_value,
                "end_value": end_value,
                "min_value": min_value,
                "max_value": max_value,
                "data_points": data_points,
                "percent_change": percent_change
            }
        }
    
    def _generate_bar_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a bar chart visualization"""
        data_fields = config.get("data_fields", []) or [config.get("data_field", "")]
        if not data_fields or not any(field in data and data[field] for field in data_fields):
            self.logger.warning(f"No data available for fields: {data_fields}, using synthetic data")
            if vis_type == "competitor_comparison_chart":
                return self._generate_competitor_chart(vis_type, config, data)
            categories = ["Category 1", "Category 2", "Category 3"]
            values = [("Value", [random.randint(10, 100) for _ in range(3)])]
        else:
            if vis_type == "competitor_comparison_chart":
                return self._generate_competitor_chart(vis_type, config, data)
            categories = []
            values = []
            available_fields = [field for field in data_fields if field in data and data[field]]
            if "categories" in data and available_fields:
                categories = data.get("categories", [])
                for field in available_fields:
                    values.append((field, data[field]))
            else:
                categories = ["Category 1", "Category 2", "Category 3"]
                values = [(field, data[field][:3] if isinstance(data[field], list) else [random.randint(10, 100) for _ in range(3)]) for field in available_fields]
        
        plt.figure(figsize=(6.5, 3.5))  # Further reduced from 7.0 to 6.5
        width = 0.8 / max(len(values), 1)
        for i, (field_name, field_values) in enumerate(values):
            if len(field_values) != len(categories):
                field_values = field_values[:len(categories)] + [0] * (len(categories) - len(field_values))
            x_positions = np.arange(len(categories)) - (len(values) - 1) * width / 2 + i * width
            
            # Cap the width for better visual presentation
            bar_width = min(width, 0.4)
            
            # Use a consistent color palette
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
            color = colors[i % len(colors)]
            
            bars = plt.bar(x_positions, field_values, width=bar_width, 
                    label=field_name.replace("_", " ").title(), 
                    color=color, alpha=0.7)
            
            # Add data labels above bars
            for j, (x, v) in enumerate(zip(x_positions, field_values)):
                if v >= 1e9:
                    label = f"${v/1e9:.1f}B"
                elif v >= 1e6:
                    label = f"${v/1e6:.1f}M"
                else:
                    label = f"${v:.1f}"
                plt.text(x, v + (max(field_values) * 0.03 if any(field_values) else 0.5), 
                         label, ha='center', fontsize=8)
        
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title, pad=10, fontsize=12, fontfamily='Times New Roman')
        plt.xticks(np.arange(len(categories)), categories, rotation=45, ha="right")
        plt.ylabel("Value", labelpad=10)
        plt.legend()
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        
        # Save with consistent filename without timestamp
        filename = f"{vis_type}.png"
        file_path = os.path.join(self.output_dir, filename)
        plt.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return {
            "file_path": file_path,
            "title": title,
            "data_summary": {"categories": categories, "values": values}
        }
    
    def _generate_competitor_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a competitor comparison visualization"""
        competitors = data.get("competitors", {})
        
        # Debug logging
        self.logger.debug(f"Generating competitor chart with data keys: {list(data.keys())}")
        if competitors:
            self.logger.debug(f"Found {len(competitors)} competitors: {list(competitors.keys())}")
        
        # Check if we have market cap and price change data
        has_market_cap = "market_cap" in data and data["market_cap"] is not None
        has_price_change = any(pc_field in data for pc_field in ["price_change_percentage_24h", "percent_change_24h"])
        has_competitors = bool(competitors) and len(competitors) > 0
        
        # Check if competitor data has required fields
        comp_has_market_cap = has_competitors and all("market_cap" in comp and comp["market_cap"] is not None for comp in competitors.values())
        comp_has_price_change = has_competitors and all(any(pc_field in comp for pc_field in ["price_change_percentage_24h", "percent_change_24h"]) 
                                                    for comp in competitors.values())
        
        self.logger.debug(f"Data check: Market cap: {has_market_cap}, Price change: {has_price_change}, Competitors: {has_competitors}")
        self.logger.debug(f"Competitor data check: Market cap: {comp_has_market_cap}, Price change: {comp_has_price_change}")
        
        # First check if we have all required data
        if not has_market_cap or not has_price_change or not has_competitors or not comp_has_market_cap or not comp_has_price_change:
            self.logger.warning("Insufficient competitor data found, using synthetic data")
            names = [self.project_name, "Ethereum", "Solana"]
            market_caps = [1e9, 5e11, 5e10]
            price_changes = [5.0, 2.0, -1.0]
        else:
            # Use real data
            self.logger.info(f"Using real data for competitor comparison with {len(competitors)} competitors")
            
            # Get project price change
            if "price_change_percentage_24h" in data:
                price_change = data["price_change_percentage_24h"]
            elif "percent_change_24h" in data:
                price_change = data["percent_change_24h"]
            else:
                price_change = 0.0
                
            # Limit to top 4 competitors by market cap to ensure a readable chart
            sorted_competitors = sorted(
                competitors.items(), 
                key=lambda x: x[1].get("market_cap", 0),
                reverse=True
            )[:4]
            
            names = [self.project_name] + [comp[0] for comp in sorted_competitors]
            market_caps = [data.get("market_cap", 0)] + [comp[1].get("market_cap", 0) for comp in sorted_competitors]
            
            # Get competitor price changes
            comp_price_changes = []
            for _, comp in sorted_competitors:
                if "price_change_percentage_24h" in comp:
                    comp_price_changes.append(comp["price_change_percentage_24h"])
                elif "percent_change_24h" in comp:
                    comp_price_changes.append(comp["percent_change_24h"])
                else:
                    comp_price_changes.append(0.0)
                    
            price_changes = [price_change] + comp_price_changes
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.5, 3.5))  # Further reduced from 7.0 to 6.5
        y_pos = range(len(names))
        
        # Market cap chart
        ax1.barh(y_pos, market_caps, align='center', color='#1f77b4', alpha=0.7)
        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(names)
        ax1.invert_yaxis()
        ax1.set_xlabel('Market Cap (USD)', labelpad=10)
        ax1.set_title('Market Capitalization', pad=15)
        ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x/1e9:.1f}B' if x >= 1e9 else f'${x/1e6:.1f}M'))
        ax1.grid(True, alpha=0.3, axis='x')
        
        # Add data labels to the bars
        for i, v in enumerate(market_caps):
            ax1.text(v + (max(market_caps) * 0.02), i, f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.1f}M", va='center', fontsize=8)
        
        # Price change chart
        colors = ['green' if x >= 0 else 'red' for x in price_changes]
        ax2.bar(names, price_changes, align='center', color=colors, alpha=0.7)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax2.set_ylabel('24h Change (%)', labelpad=10)
        ax2.set_title('24h Price Change', pad=15)
        ax2.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45, ha='right')
        
        # Add data labels to the bars
        for i, v in enumerate(price_changes):
            ax2.text(i, v + (max(abs(min(price_changes)), abs(max(price_changes))) * 0.05), 
                    f"{v:.1f}%", ha='center', fontsize=8,
                    color='black')
        
        plt.tight_layout()
        filename = f"{vis_type}.png"
        file_path = os.path.join(self.output_dir, filename)
        plt.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        title = config.get("title", "Competitor Comparison")
        return {
            "file_path": file_path,
            "title": title,
            "data_summary": {"competitors": len(names), "project": self.project_name}
        }
    
    def _generate_pie_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a pie chart visualization"""
        # Get styling from StyleManager
        chart_style = self.vis_config.get("charts", {}).get("pie_chart", {})
        colors_config = self.colors
        
        data_field = config.get("data_field", "")
        
        # Special handling for token distribution pie charts
        if "token_distribution" in vis_type.lower():
            # Try various field names that might contain token distribution data
            possible_token_fields = [
                "token_distribution", 
                "token_allocation",
                "tokenomics_distribution", 
                "supply_allocation",
                "token_supply_distribution"
            ]
            
            found_data = False
            # Check if any of these fields exist in the data
            for field in possible_token_fields:
                if field in data and data[field]:
                    data_field = field
                    found_data = True
                    self.logger.info(f"Found token distribution data in field '{field}' for {vis_type}")
                    break
            
            # If no data found, create realistic token distribution data
            if not found_data:
                self.logger.warning(f"No token distribution data found for {vis_type}, using realistic sample data")
                sample_token_distribution = {
                    "Team & Advisors": 15,
                    "Foundation": 20,
                    "Ecosystem Growth": 25,
                    "Community": 30,
                    "Investors": 10
                }
                data[data_field] = sample_token_distribution
        
        if data_field not in data or not data[data_field]:
            self.logger.warning(f"Data field '{data_field}' not found or empty for {vis_type}, using synthetic data")
            if "token_distribution" in vis_type.lower():
                labels = ["Team & Advisors", "Foundation", "Ecosystem Growth", "Community", "Investors"]
                sizes = [15, 20, 25, 30, 10]
            else:
                labels = ["Category A", "Category B", "Category C", "Category D"]
                sizes = [20, 30, 25, 25]
        else:
            distribution_data = data[data_field]
            if isinstance(distribution_data, dict):
                labels = list(distribution_data.keys())
                sizes = list(distribution_data.values())
            elif isinstance(distribution_data, list) and all(isinstance(item, dict) for item in distribution_data):
                labels = [item["label"] for item in distribution_data] if all("label" in item for item in distribution_data) else ["Category A", "Category B", "Category C", "Category D"]
                sizes = [item["value"] for item in distribution_data] if all("value" in item for item in distribution_data) else [20, 30, 25, 25]
            else:
                self.logger.warning(f"Unexpected data format for {vis_type}, using fallback data")
                if "token_distribution" in vis_type.lower():
                    labels = ["Team & Advisors", "Foundation", "Ecosystem Growth", "Community", "Investors"]
                    sizes = [15, 20, 25, 30, 10]
                else:
                    labels = ["Category A", "Category B", "Category C", "Category D"]
                    sizes = [20, 30, 25, 25]
        
        # Ensure label and size data quality
        if len(labels) != len(sizes):
            self.logger.warning(f"Mismatch in data length for {vis_type}: {len(labels)} labels vs {len(sizes)} values")
            min_len = min(len(labels), len(sizes))
            labels = labels[:min_len]
            sizes = sizes[:min_len]
        
        if len(labels) == 0:
            self.logger.warning(f"No data points for {vis_type}, using default data")
            if "token_distribution" in vis_type.lower():
                labels = ["Team & Advisors", "Foundation", "Ecosystem Growth", "Community", "Investors"]
                sizes = [15, 20, 25, 30, 10]
            else:
                labels = ["Category A", "Category B", "Category C", "Category D"]
                sizes = [20, 30, 25, 25]
        
        # Get chart dimensions from style config
        figure_width = chart_style.get("width", 6.5)
        figure_height = chart_style.get("height", 3.5)
        plt.figure(figsize=(figure_width, figure_height))
        
        # Add explosion to highlight the largest segment if specified in style config
        use_explode = chart_style.get("explode_largest", True)
        explode_amount = chart_style.get("explode_amount", 0.1)
        explode = [explode_amount if i == sizes.index(max(sizes)) and use_explode else 0 for i in range(len(sizes))]
        
        # Get color scheme from style config
        max_colors = chart_style.get("max_colors", 8)
        color_indices = np.linspace(0, 1, min(max_colors, len(sizes)))
        
        # Select color scheme based on chart type and style config
        if "token_distribution" in vis_type.lower():
            color_scheme = chart_style.get("token_distribution_colormap", "tab10")
        else:
            color_scheme = chart_style.get("default_colormap", "Paired")
            
        try:
            colors = plt.cm.get_cmap(color_scheme)(color_indices)
        except:
            # Fallback to safe colormaps if the specified one isn't available
            colors = plt.cm.tab10(color_indices) if "token_distribution" in vis_type.lower() else plt.cm.Paired(color_indices)
        
        # Get other pie chart styling from config
        shadow = chart_style.get("shadow", False)
        start_angle = chart_style.get("start_angle", 90)
        autopct_format = chart_style.get("autopct_format", '%1.1f%%')
        edge_color = chart_style.get("edge_color", "white")
        edge_width = chart_style.get("edge_width", 1)
        
        # Create the pie chart with styling from config
        plt.pie(sizes, 
                explode=explode,
                labels=None, 
                autopct=autopct_format, 
                startangle=start_angle, 
                colors=colors,
                shadow=shadow,
                wedgeprops={'edgecolor': edge_color, 'linewidth': edge_width})
        
        plt.axis('equal')  # Equal aspect ratio ensures the pie chart is circular
        
        # Calculate total for percentage display
        total = sum(sizes)
        
        # Format legend based on style config
        legend_format = chart_style.get("legend_format", "{label}: {percentage:.1f}%")
        legend_labels = [legend_format.format(label=label, value=size, percentage=(size/total*100)) 
                         for label, size in zip(labels, sizes)]
        
        # Get legend position from style config
        legend_loc = chart_style.get("legend_location", "best")
        legend_bbox = chart_style.get("legend_bbox", (1, 1))
        plt.legend(legend_labels, loc=legend_loc, bbox_to_anchor=legend_bbox)
        
        # Use a more specific title for token distribution
        if "token_distribution" in vis_type.lower():
            title = f"{self.project_name} Token Distribution"
        else:
            title = config.get("title", vis_type.replace("_", " ").title())
        
        # Apply title styling from config
        title_fontsize = chart_style.get("title_fontsize", 12)
        title_pad = chart_style.get("title_pad", 10)
        plt.title(title, pad=title_pad, fontsize=title_fontsize)
        
        # Save with consistent filename without timestamp
        filename = f"{vis_type}.png"
        file_path = os.path.join(self.output_dir, filename)
        
        # Get save parameters from style config
        dpi = chart_style.get("dpi", 300)
        bbox_inches = chart_style.get("bbox_inches", 'tight')
        plt.savefig(file_path, dpi=dpi, bbox_inches=bbox_inches)
        plt.close()
        
        # Create a more descriptive title for the visualization
        if "token_distribution" in vis_type.lower():
            description = f"{self.project_name} Token Distribution"
        else:
            description = title
        
        return {
            "file_path": file_path,
            "title": title,
            "description": description,
            "data_summary": {"labels": labels, "values": sizes, "total": total}
        }
    
    def _generate_description(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any], result: Dict[str, Any]) -> str:
        if not self.llm:
            return f"{vis_type.replace('_', ' ').title()} for {self.project_name}"
        
        template = config.get("description_template", "{title} showing {description}")
        context = {
            "title": config.get("title", vis_type.replace("_", " ").title()),
            "description": "data visualization",
            "project_name": self.project_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_summary": result.get("data_summary", {})
        }
        
        if "error" in result:
            return f"Error generating {vis_type.replace('_', ' ').title()}: {result['error']}"
        
        if vis_type == "price_history_chart":
            context["trend_description"] = f"a trend from ${context['data_summary'].get('start_value', 0):.2f} to ${context['data_summary'].get('end_value', 0):.2f}"
            context["description"] = context["trend_description"]
        elif vis_type == "volume_chart":
            context["volume_description"] = "synthetic volume trends" if not data.get("volume_history") else "actual volume trends"
            context["description"] = context["volume_description"]
        elif vis_type == "tvl_chart":
            context["tvl_description"] = "synthetic TVL trends" if not data.get("tvl_history") else "actual TVL trends"
            context["description"] = context["tvl_description"]
        elif vis_type == "liquidity_trends_chart":
            context["liquidity_description"] = "synthetic liquidity trends" if not data.get("volume_history") else "actual liquidity trends"
            context["description"] = context["liquidity_description"]
        elif vis_type == "competitor_comparison_chart":
            context["metrics_description"] = "synthetic competitor metrics" if not data.get("competitors") else f"market metrics for {context['data_summary'].get('competitors', 0)} competitors"
            context["description"] = context["metrics_description"]
        
        try:
            return template.format(**context)
        except KeyError as e:
            self.logger.warning(f"Template formatting failed for {vis_type}: {e}, using fallback")
            return f"{context['title']} for {self.project_name}"

    def _prepare_table_data(self, data, fields, source_field_prefix="", default_values=None):
        """Helper function to prepare data without source column"""
        if default_values is None:
            default_values = {}
            
        # Extract values for each field, ignoring source information
        values = []
        for field in fields:
            if field in data and data[field] is not None:
                values.append(data[field])
            elif field in default_values:
                values.append(default_values[field])
            else:
                values.append("N/A")
                
        return values

    def _create_html_table(self, headers, data, title):
        """For backward compatibility - now just calls _create_table_image"""
        # Strip source column if present
        if len(headers) > 0 and headers[-1].lower() == "source":
            headers = headers[:-1]
            data = [row[:-1] for row in data]
            
        return self._create_table_image(headers, data, title)

    def _create_table_image(self, headers, data_rows, title, output_path):
        """Creates a table image with styling from the style configuration"""
        # Get table styling from the style manager
        table_style = self.vis_config.get("tables", {})
        
        # Table dimensions
        figure_width = table_style.get("width", 10)
        figure_height = table_style.get("height", 6)
        
        # Create figure and axis
        fig = plt.figure(figsize=(figure_width, figure_height))
        ax = fig.add_subplot(111)
        ax.axis('tight')
        ax.axis('off')
        
        # Calculate dynamic table size based on data
        num_rows = len(data_rows) + 1  # Add 1 for header
        row_height = table_style.get("row_height", 0.5)
        if row_height == 'auto':
            row_height = min(0.5, 3.0 / max(num_rows, 1))
        
        # Convert any numeric values to strings for consistent display
        string_data = [[str(cell) for cell in row] for row in data_rows]
        
        # Create the table
        table = ax.table(
            cellText=string_data,
            colLabels=headers,
            loc='center',
            cellLoc=table_style.get("cell_alignment", 'center')
        )
        
        # Apply style to the table
        table.auto_set_font_size(False)
        table.set_fontsize(table_style.get("font_size", 12))
        table.scale(table_style.get("scale_x", 1.2), table_style.get("scale_y", 1.5))
        
        # Style the header row
        header_bg_color = table_style.get("header_bg_color", '#4472C4')
        header_text_color = table_style.get("header_text_color", 'white')
        
        for i, key in enumerate(headers):
            header_cell = table[(0, i)]
            header_cell.set_facecolor(header_bg_color)
            header_cell.set_text_props(color=header_text_color)
            
            # Optional: Add bold to header
            if table_style.get("bold_header", True):
                header_cell.get_text().set_fontweight('bold')
        
        # Style alternating rows if specified
        if table_style.get("alternating_row_colors", True):
            row_colors = table_style.get("row_colors", ['#f5f5f5', 'white'])
            for i, row in enumerate(range(1, len(data_rows) + 1)):
                for j, col in enumerate(range(len(headers))):
                    cell = table[(row, col)]
                    cell.set_facecolor(row_colors[i % len(row_colors)])
        
        # Add border lines if specified
        if table_style.get("show_grid", True):
            table.set_fontsize(table_style.get("font_size", 12))
            line_width = table_style.get("line_width", 1)
            table_edge_color = table_style.get("edge_color", 'black')
            
            # Apply edgecolor to all cells
            for cell in table._cells.values():
                cell.set_edgecolor(table_edge_color)
                cell.set_linewidth(line_width)
        
        # Set title
        title_fontsize = table_style.get("title_fontsize", 14)
        title_pad = table_style.get("title_pad", 0.9)
        plt.title(title, fontsize=title_fontsize, y=title_pad)
        
        # Use provided output path instead of creating one
        file_path = output_path
        
        self.logger.debug(f"Saving table image to: {file_path}")
        self.logger.debug(f"Output directory: {os.path.dirname(file_path)} exists: {os.path.exists(os.path.dirname(file_path))}")
        
        # Save parameters
        dpi = table_style.get("dpi", 300)
        bbox_inches = table_style.get("bbox_inches", 'tight')
        
        try:
            plt.savefig(file_path, dpi=dpi, bbox_inches=bbox_inches)
            self.logger.debug(f"Image saved successfully to {file_path}")
        except Exception as e:
            self.logger.error(f"Error saving figure: {str(e)}")
            plt.close()
            return None
            
        plt.close()
        
        # Verify the image was actually created
        if not os.path.exists(file_path):
            self.logger.error(f"Failed to create visualization file for {title}: {file_path}")
            return None
        
        return file_path
    
    def _generate_table(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a table (as an image and markdown)."""
        try:
            # Extract data fields from config
            data_fields = config.get("data_fields", [])
            if not data_fields:
                self.logger.warning(f"No data fields specified for {vis_type}")
                return {"error": "No data fields specified"}
            
            # Log what we're trying to generate
            self.logger.info(f"Generating table for {vis_type} with fields: {', '.join(data_fields)}")
            
            # Set title from config or infer from visualization type
            title = config.get("title", vis_type.replace("_", " ").title())
            
            # Use vis_type for filename to ensure consistency
            filename = f"{vis_type}.png"
            output_path = os.path.join(self.output_dir, filename)
            self.logger.info(f"Will save table to {output_path}")
            
            # Extract and format table data
            table_data = {}
            
            # Handle different data formats
            if all(field in data for field in data_fields):
                # Format 1: data contains each field directly
                self.logger.info(f"Using direct field data for table {vis_type}")
                table_data = {field: data[field] for field in data_fields if field in data}
            elif "items" in data and isinstance(data["items"], list) and len(data["items"]) > 0:
                # Format 2: data contains a list of items with properties
                self.logger.info(f"Using items list data for table {vis_type} with {len(data['items'])} rows")
                items = data["items"]
                
                for field in data_fields:
                    if any(field in item for item in items):
                        table_data[field] = [item.get(field, "") for item in items]
            
            # If we don't have valid data, create sample data based on the visualization type
            if not table_data or all(len(value) == 0 for value in table_data.values() if isinstance(value, list)):
                self.logger.warning(f"No valid data found for table {vis_type}, checking data sources")
                
                # Check if we've been asked to not use synthetic data
                if hasattr(self, 'use_real_data_only') and self.use_real_data_only:
                    # For essential tables, we can generate with partial data if available
                    if "supply_metrics" in vis_type.lower():
                        # Only continue if at least one supply metric is available
                        has_valid_supply_data = any(field in data and data[field] is not None 
                                                for field in ["max_supply", "total_supply", "circulating_supply"])
                        if not has_valid_supply_data:
                            self.logger.warning(f"No valid supply data available for {vis_type}")
                            return {"error": f"No valid supply data available for {vis_type}"}
                    
                    elif "basic_metrics" in vis_type.lower():
                        # Only continue if at least current_price is available
                        if "current_price" not in data or data["current_price"] is None:
                            self.logger.warning(f"No valid price data available for {vis_type}")
                            return {"error": f"No valid price data available for {vis_type}"}
                    
                    # For non-essential tables, don't generate with synthetic data
                    elif not any(vis_type.lower().endswith(essential) for essential in ["_metrics", "_table"]):
                        self.logger.warning(f"Skipping {vis_type} as it requires synthetic data")
                        return {"error": f"No valid data available for {vis_type} and synthetic data is disabled"}
                
                # Get sample data from sample data provider in style config if available
                table_samples = self.vis_config.get("sample_data", {}).get("tables", {})
                sample_data = table_samples.get(vis_type, None)
                
                if sample_data:
                    table_data = copy.deepcopy(sample_data)
                    self.logger.info(f"Using sample data from style config for {vis_type}")
                else:
                    # Handle different table types with appropriate synthetic data
                    if "supply_metrics" in vis_type.lower():
                        table_data = {
                            "metric": ["Maximum Supply", "Total Supply", "Circulating Supply", "Burned Tokens", "Market Cap"],
                            "value": [
                                f"<b>{int(data.get('max_supply')):,}</b>" if data.get('max_supply') is not None else "<b>N/A</b>",
                                f"<b>{int(data.get('total_supply')):,}</b>" if data.get('total_supply') is not None else "<b>N/A</b>",
                                f"<b>{int(data.get('circulating_supply')):,}</b>" if data.get('circulating_supply') is not None else "<b>N/A</b>",
                                "<b>N/A</b>", # Burned tokens - use N/A since this is usually synthetic
                                f"<b>${int((data.get('circulating_supply', 0) or 0) * (data.get('current_price', 0) or 0)):,}</b>" if (data.get('circulating_supply') is not None and data.get('current_price') is not None) else "<b>N/A</b>"
                            ]
                        }
                    elif "basic_metrics" in vis_type.lower():
                        table_data = {
                            "metric": ["Current Price", "24h Change", "7d Change", "Trading Volume (24h)", "Market Rank"],
                            "value": [
                                f"<b>${data.get('current_price'):.2f}</b>" if data.get('current_price') is not None else "<b>N/A</b>",
                                f"<b>{data.get('price_change_24h'):.2f}%</b>" if data.get('price_change_24h') is not None else "<b>N/A</b>",
                                f"<b>{data.get('price_change_7d'):.2f}%</b>" if data.get('price_change_7d') is not None else "<b>N/A</b>",
                                f"<b>${data.get('volume_24h'):,}</b>" if data.get('volume_24h') is not None else "<b>N/A</b>",
                                f"<b>#{data.get('market_cap_rank')}</b>" if data.get('market_cap_rank') is not None else "<b>N/A</b>"
                            ]
                        }
                    elif "risks" in vis_type.lower():
                        table_data = {
                            "risk_type": ["Risk Analysis"],
                            "risk_description": ["No risk data available"],
                            "risk_level": ["N/A"]
                        }
                    elif "opportunities" in vis_type.lower():
                        table_data = {
                            "opportunity_type": ["Opportunity Analysis"],
                            "opportunity_description": ["No opportunity data available"]
                        }
                    elif "developer_tools" in vis_type.lower():
                        table_data = {
                            "tool_name": ["N/A"],
                            "description": ["No developer tools data available"],
                            "link": ["N/A"]
                        }
                    elif "security_audits" in vis_type.lower():
                        table_data = {
                            "audit_date": ["N/A"],
                            "auditor": ["N/A"],
                            "findings": ["No audit data available"],
                            "status": ["N/A"]
                        }
                    elif "user_experience" in vis_type.lower():
                        table_data = {
                            "metric": ["User Experience Data"],
                            "value": ["N/A"],
                            "source": ["No data available"]
                        }
                    elif "governance" in vis_type.lower():
                        table_data = {
                            "aspect": ["Governance Data"],
                            "description": ["No governance data available"]
                        }
                    elif "team" in vis_type.lower():
                        table_data = {
                            "name": ["N/A"],
                            "role": ["N/A"],
                            "background": ["No team data available"]
                        }
                    elif "partnerships" in vis_type.lower():
                        table_data = {
                            "partner": ["N/A"],
                            "partnership_type": ["N/A"],
                            "details": ["No partnership data available"]
                        }
                    else:
                        # Generic fallback for any other table
                        self.logger.warning(f"Using generic fallback data for unknown table type: {vis_type}")
                        table_data = {
                            "category": ["Data Category"],
                            "value": ["N/A"],
                            "description": [f"No data available for {vis_type}"]
                        }
            
            # Ensure table data has proper length consistency
            max_len = max([len(values) if isinstance(values, list) else 1 for values in table_data.values()], default=0)
            
            for key, value in table_data.items():
                if not isinstance(value, list):
                    table_data[key] = [value] * max_len
                elif len(value) < max_len:
                    table_data[key] = value + [""] * (max_len - len(value))
            
            # Get headers and formatted data
            headers = list(table_data.keys())
            data_rows = []
            
            for i in range(max_len):
                row = []
                for header in headers:
                    val = table_data[header][i] if i < len(table_data[header]) else ""
                    row.append(str(val))
                data_rows.append(row)
            
            # Create the actual table image - pass the output path directly
            img_path = self._create_table_image(headers, data_rows, title, output_path)
            
            # Verify the image was actually created
            if img_path is None or not os.path.exists(img_path):
                self.logger.error(f"Failed to create table image for {title}")
                return {"error": f"Failed to create visualization file for {vis_type}"}
            
            # Create markdown table as fallback
            markdown_table = "| " + " | ".join(headers) + " |\n"
            markdown_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            
            for row in data_rows:
                markdown_table += "| " + " | ".join(row) + " |\n"
            
            return {
                "file_path": img_path,
                "title": title,
                "markdown": markdown_table,
                "headers": headers,
                "data": data_rows
            }
            
        except Exception as e:
            self.logger.error(f"Error generating table: {str(e)}", exc_info=True)
            return {"error": f"Failed to generate table: {str(e)}"}
    
    def _generate_timeline(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        # Get timeline styling from the style manager
        timeline_style = self.vis_config.get("charts", {}).get("timeline", {})
        
        data_fields = config.get("data_fields", ["milestone_date", "milestone_description"])
        if not data_fields or len(data_fields) < 2 or not data.get("roadmap") and not data.get("milestones"):
            self.logger.warning(f"No timeline data found for {vis_type}, using synthetic data")
            timeline_items = [
                {"milestone_date": "2025-01-01", "milestone_description": "Launch"},
                {"milestone_date": "2025-06-01", "milestone_description": "Feature Update"},
                {"milestone_date": "2025-12-01", "milestone_description": "Expansion"}
            ]
        else:
            timeline_items = data.get("roadmap", []) or data.get("milestones", [])
            date_field, desc_field = data_fields[:2]
            timeline_items = sorted(timeline_items, key=lambda x: x.get(date_field, ""))
        
        # Get figure dimensions from style config
        figure_width = timeline_style.get("width", 6.5)
        figure_height = timeline_style.get("height", 3.5)
        plt.figure(figsize=(figure_width, figure_height))
        
        dates = [item.get(data_fields[0], "") for item in timeline_items]
        descriptions = [item.get(data_fields[1], "") for item in timeline_items]
        y_positions = range(len(dates))
        
        # Get styling for timeline elements
        marker_size = timeline_style.get("marker_size", 12)
        line_width = timeline_style.get("line_width", 2)
        line_color = timeline_style.get("line_color", '#1f77b4')
        
        # Add a horizontal connecting line for the timeline
        plt.plot([0] * len(dates), y_positions, 'o-', 
                markersize=marker_size, 
                color=line_color, 
                linewidth=line_width)
        
        # Get text styling
        text_fontsize = timeline_style.get("text_fontsize", 12)
        text_fontweight = timeline_style.get("text_fontweight", "normal")
        text_offset = timeline_style.get("text_offset", 0.1)
        
        for i, (date, desc) in enumerate(zip(dates, descriptions)):
            plt.text(text_offset, i, f"{date}: {desc}", 
                    fontsize=text_fontsize, 
                    verticalalignment='center', 
                    fontweight=text_fontweight)
        
        # Get title styling
        title = config.get("title", vis_type.replace("_", " ").title())
        title_fontsize = timeline_style.get("title_fontsize", 12)
        title_pad = timeline_style.get("title_pad", 10)
        plt.title(title, pad=title_pad, fontsize=title_fontsize)
        
        # Remove axis ticks and grid based on style config
        plt.yticks([])
        plt.xticks([])
        plt.grid(timeline_style.get("show_grid", False))
        plt.tight_layout()
        
        # Save the timeline
        filename = f"{vis_type}.png"
        file_path = os.path.join(self.output_dir, filename)
        
        # Get save parameters from style config
        dpi = timeline_style.get("dpi", 300)
        bbox_inches = timeline_style.get("bbox_inches", 'tight')
        plt.savefig(file_path, dpi=dpi, bbox_inches=bbox_inches)
        plt.close()
        
        return {
            "file_path": file_path,
            "title": title,
            "data_summary": {"milestones": len(timeline_items), "earliest": dates[0], "latest": dates[-1]}
        }

def visualization_agent(state, llm, logger, config=None) -> Dict:
    """
    Create visualizations based on available data and report configuration.
    This agent now runs after the writer, ensuring all research data is available.
    """
    try:
        project_name = state.project_name
        logger.info(f"Visualization agent starting for {project_name}")
        state.update_progress(f"Generating visualizations for {project_name}...")
        
        # Get configuration
        fast_mode = config.get("fast_mode", False) if config else False
        limit_charts = config.get("limit_charts", False) if config else False
        use_report_config = config.get("use_report_config", True) if config else True
        skip_expensive_descriptions = config.get("skip_expensive_descriptions", False) if config else False
        
        # Track which visualizations have already been generated to prevent duplicates
        already_generated = set()
        if hasattr(state, 'visualizations') and state.visualizations:
            already_generated = set(state.visualizations.keys())
            logger.info(f"Found {len(already_generated)} existing visualizations: {already_generated}")
        
        # Create agent
        vis_agent = VisualizationAgent(project_name, logger, llm)
        
        # Clear existing generated visualizations set to prevent incorrect tracking
        vis_agent.generated_visualizations = set()
        
        # Load report configuration to determine which visualizations to create
        if not hasattr(state, 'report_config') or not state.report_config:
            try:
                with open("backend/config/report_config.json", "r") as f:
                    state.report_config = json.load(f)
                logger.info("Loaded report configuration from file")
            except Exception as e:
                logger.warning(f"Could not load report configuration: {str(e)}")
                state.report_config = {}
        
        if not state.report_config:
            logger.warning("No report configuration available, using default visualizations")
        
        # Combine all data sources for visualizations
        visualization_data = {}
        data_source_count = 0
        
        # Check if we have API data and add it
        api_data_added = False
        
        # Include API data with verbose logging
        if hasattr(state, 'coingecko_data') and state.coingecko_data:
            visualization_data.update(state.coingecko_data)
            data_source_count += 1
            api_data_added = True
            logger.info(f"Added CoinGecko data with {len(state.coingecko_data)} fields")
            logger.debug(f"CoinGecko data keys: {list(state.coingecko_data.keys())}")
        
        if hasattr(state, 'coinmarketcap_data') and state.coinmarketcap_data:
            visualization_data.update(state.coinmarketcap_data)
            data_source_count += 1
            api_data_added = True
            logger.info(f"Added CoinMarketCap data with {len(state.coinmarketcap_data)} fields")
            logger.debug(f"CoinMarketCap data keys: {list(state.coinmarketcap_data.keys())}")
        
        if hasattr(state, 'defillama_data') and state.defillama_data:
            visualization_data.update(state.defillama_data)
            data_source_count += 1
            api_data_added = True
            logger.info(f"Added DeFiLlama data with {len(state.defillama_data)} fields")
            logger.debug(f"DeFiLlama data keys: {list(state.defillama_data.keys())}")
        
        # Include combined data if available
        if hasattr(state, 'data') and state.data:
            visualization_data.update(state.data)
            data_source_count += 1
            api_data_added = True
            logger.info(f"Added combined data with {len(state.data)} fields")
            logger.debug(f"Combined data keys: {list(state.data.keys())}")
        
        # Add research data - should be fully populated now since writer has run
        if hasattr(state, 'research_data') and state.research_data:
            visualization_data.update(state.research_data)
            data_source_count += 1
            logger.info(f"Added Research data with {len(state.research_data)} fields")
            logger.debug(f"Research data keys: {list(state.research_data.keys())}")
        
        # Check if we have data sources information available (from Phase 2)
        if hasattr(state, 'data_sources') and state.data_sources:
            # Extract values only (we're not using sources in visualizations anymore)
            for key, source_info in state.data_sources.items():
                if isinstance(source_info, dict) and 'value' in source_info:
                    visualization_data[key] = source_info['value']
            
            data_source_count += 1
            logger.info(f"Added values from {len(state.data_sources)} data sources")
            logger.debug(f"Data sources keys: {list(state.data_sources.keys())}")
        
        # Warn if no data was found at all
        if data_source_count == 0:
            logger.warning("No data sources found in state! Visualizations will use synthetic data.")
            
            # Add minimal project information to ensure some charts can be created
            visualization_data["project_name"] = project_name
            visualization_data["project_ticker"] = project_name.upper()
        elif not api_data_added:
            logger.warning("No API data found. This may cause issues with data-dependent charts.")
        
        # Add essential data that might be missing for required visualizations
        # Token Distribution
        if "token_allocation" not in visualization_data:
            logger.warning("Adding synthetic token_allocation data since it's missing")
            visualization_data["token_allocation"] = {
                "No Data Available": 100
            }
        
        # Supply metrics
        if "max_supply" not in visualization_data:
            # Look for this field in multiple possible locations
            max_supply = None
            
            # Try CoinGecko data
            if hasattr(state, 'coingecko_data') and state.coingecko_data:
                if 'max_supply' in state.coingecko_data and state.coingecko_data['max_supply'] is not None:
                    max_supply = state.coingecko_data['max_supply']
                    logger.info(f"Found max_supply in CoinGecko data: {max_supply}")
                
            # Also try CoinMarketCap data
            if max_supply is None and hasattr(state, 'coinmarketcap_data') and state.coinmarketcap_data:
                if 'max_supply' in state.coinmarketcap_data and state.coinmarketcap_data['max_supply'] is not None:
                    max_supply = state.coinmarketcap_data['max_supply']
                    logger.info(f"Found max_supply in CoinMarketCap data: {max_supply}")
            
            # Also look in data object
            if max_supply is None and 'max_supply' in state.data and state.data['max_supply'] is not None:
                max_supply = state.data['max_supply']
                logger.info(f"Found max_supply in state.data: {max_supply}")
            
            # If still not found, use default
            if max_supply is None:
                logger.warning("Adding synthetic max_supply data since it's missing")
                max_supply = 1000000000
            
            # Store the found or default value
            visualization_data["max_supply"] = max_supply
            
        # Similar approach for circulating_supply
        if "circulating_supply" not in visualization_data:
            circulating_supply = None
            
            # Try CoinGecko data
            if hasattr(state, 'coingecko_data') and state.coingecko_data:
                if 'circulating_supply' in state.coingecko_data and state.coingecko_data['circulating_supply'] is not None:
                    circulating_supply = state.coingecko_data['circulating_supply']
                    logger.info(f"Found circulating_supply in CoinGecko data: {circulating_supply}")
            
            # Also try CoinMarketCap data
            if circulating_supply is None and hasattr(state, 'coinmarketcap_data') and state.coinmarketcap_data:
                if 'circulating_supply' in state.coinmarketcap_data and state.coinmarketcap_data['circulating_supply'] is not None:
                    circulating_supply = state.coinmarketcap_data['circulating_supply']
                    logger.info(f"Found circulating_supply in CoinMarketCap data: {circulating_supply}")
            
            # Also look in data object
            if circulating_supply is None and 'circulating_supply' in state.data and state.data['circulating_supply'] is not None:
                circulating_supply = state.data['circulating_supply']
                logger.info(f"Found circulating_supply in state.data: {circulating_supply}")
            
            # If still not found, derive from max_supply
            if circulating_supply is None:
                max_supply = visualization_data.get("max_supply", 1000000000)
                logger.warning("Adding synthetic circulating_supply data since it's missing")
                circulating_supply = int(max_supply * 0.4)
            
            # Store the found or default value
            visualization_data["circulating_supply"] = circulating_supply
            
        # Similar approach for total_supply
        if "total_supply" not in visualization_data:
            total_supply = None
            
            # Try CoinGecko data
            if hasattr(state, 'coingecko_data') and state.coingecko_data:
                if 'total_supply' in state.coingecko_data and state.coingecko_data['total_supply'] is not None:
                    total_supply = state.coingecko_data['total_supply']
                    logger.info(f"Found total_supply in CoinGecko data: {total_supply}")
            
            # Also try CoinMarketCap data
            if total_supply is None and hasattr(state, 'coinmarketcap_data') and state.coinmarketcap_data:
                if 'total_supply' in state.coinmarketcap_data and state.coinmarketcap_data['total_supply'] is not None:
                    total_supply = state.coinmarketcap_data['total_supply']
                    logger.info(f"Found total_supply in CoinMarketCap data: {total_supply}")
            
            # Also look in data object
            if total_supply is None and 'total_supply' in state.data and state.data['total_supply'] is not None:
                total_supply = state.data['total_supply']
                logger.info(f"Found total_supply in state.data: {total_supply}")
            
            # If still not found, derive from max_supply
            if total_supply is None:
                max_supply = visualization_data.get("max_supply", 1000000000)
                logger.warning("Adding synthetic total_supply data since it's missing")
                total_supply = int(max_supply * 0.7)
            
            # Store the found or default value
            visualization_data["total_supply"] = total_supply
        
        # Developer tools data
        if "tool_name" not in visualization_data:
            logger.warning("Adding synthetic developer tools data since it's missing")
            visualization_data["tool_name"] = ["N/A"]
            visualization_data["description"] = ["No developer tools data available"]
            visualization_data["link"] = ["N/A"]
            
        # Security audits data
        if "audit_date" not in visualization_data:
            logger.warning("Adding synthetic security audit data since it's missing")
            visualization_data["audit_date"] = ["N/A"]
            visualization_data["auditor"] = ["N/A"]
            visualization_data["findings"] = ["No audit data available"]
            visualization_data["status"] = ["N/A"]
        
        # User experience metrics
        if "metric" not in visualization_data:
            logger.warning("Adding synthetic user experience metrics since they're missing")
            visualization_data["metric"] = ["User Experience Data"]
            visualization_data["value"] = ["N/A"]
            visualization_data["source"] = ["No data available"]
        
        # Log data available for debugging
        logger.info(f"Data preparation complete with {len(visualization_data)} total fields")
        logger.debug(f"Available data fields: {list(visualization_data.keys())}")
        
        # Determine which visualizations to create based on the report configuration
        sections = state.report_config.get("sections", [])
        visualization_list = []
        visualization_types = state.report_config.get("visualization_types", {})
        logger.debug(f"Config has {len(visualization_types)} visualization types defined")
        
        # Map all visualizations needed by sections
        section_vis_mapping = {}
        for section in sections:
            section_vis = section.get("visualizations", [])
            if section_vis:
                section_vis_mapping[section.get("title", "Unknown")] = section_vis
                visualization_list.extend(section_vis)
        
        # Remove duplicates while preserving order
        seen = set()
        visualization_list = [x for x in visualization_list if not (x in seen or seen.add(x))]
        
        # Filter out already generated visualizations
        visualization_list = [x for x in visualization_list if x not in already_generated]
        
        # In limit_charts mode, limit to max 5 in fast mode to save time
        if limit_charts and fast_mode and len(visualization_list) > 5:
            logger.info(f"Limiting charts to 5 (from {len(visualization_list)}) in fast mode")
            visualization_list = visualization_list[:5]
        
        logger.info(f"Preparing to generate {len(visualization_list)} visualizations")
        
        # Initialize visualizations dict if needed
        if not hasattr(state, 'visualizations') or state.visualizations is None:
            state.visualizations = {}
        
        visualizations_by_type = state.visualizations.copy()
        logger.debug(f"Starting with {len(visualizations_by_type)} existing visualizations")
        
        # Essential visualizations that must be generated even with synthetic data
        essential_visualizations = [
            "token_distribution_pie", 
            "supply_metrics_table", 
            "basic_metrics_table",
            "developer_tools_table", 
            "security_audits_table", 
            "user_experience_metrics"
        ]
        
        # Generate visualizations
        for vis_type in visualization_list:
            # Skip if this visualization has already been generated
            if vis_type in already_generated or vis_type in vis_agent.generated_visualizations:
                logger.info(f"Skipping already generated visualization: {vis_type}")
                continue
                
            # Add to tracking set to prevent duplicates
            vis_agent.generated_visualizations.add(vis_type)
            
            # Get config for this visualization type
            vis_config = visualization_types.get(vis_type, {})
            
            # Track if this visualization is essential
            is_essential = any(essential_name in vis_type.lower() for essential_name in essential_visualizations)
            
            # Check if the required data fields exist for this visualization
            required_fields = vis_config.get("data_fields", [])
            
            # Check for missing data fields
            missing_fields = [field for field in required_fields 
                             if field not in visualization_data 
                             or visualization_data[field] is None 
                             or (isinstance(visualization_data[field], str) and not visualization_data[field].strip())]
            
            # Skip generation if missing fields and not marked as allowing synthetic data
            # If it's an essential visualization, mark it so but don't use synthetic data
            if missing_fields:
                if not vis_config.get("allow_synthetic", False) and not is_essential:
                    logger.warning(f"Skipping {vis_type} because required data fields are missing: {missing_fields}")
                    continue
                elif is_essential:
                    logger.warning(f"Important visualization {vis_type} has missing data: {missing_fields}. " +
                                  "Will attempt to generate with real data only.")
            
            # Generate the visualization with better error handling
            try:
                state.update_progress(f"Generating visualization: {vis_type}")
                logger.info(f"Generating visualization: {vis_type}")
                
                # Always use real data only
                # This will be handled at the individual visualization level
                # so failure of one visualization won't affect others
                use_real_data = True
                
                # Pass the flag
                result = vis_agent.generate_visualization(vis_type, visualization_data, skip_expensive_descriptions, use_real_data)
                
                if "error" in result:
                    logger.warning(f"Error generating {vis_type}: {result['error']}")
                    # Don't add unsuccessful visualizations to the state
                else:
                    # Check explicitly for a valid file path
                    if "file_path" in result and os.path.exists(result["file_path"]):
                        visualizations_by_type[vis_type] = result
                        logger.info(f"Successfully generated {vis_type} and added to state")
                    else:
                        logger.warning(f"Generated visualization has invalid path: {result.get('file_path', 'None')}")
            except Exception as e:
                logger.error(f"Exception generating {vis_type}: {str(e)}", exc_info=True)
        
        # Store visualization results in state
        state.visualizations = visualizations_by_type
        
        # Map visualizations to sections
        section_visualizations = {}
        for section_title, vis_types in section_vis_mapping.items():
            section_visualizations[section_title] = {}
            for vis_type in vis_types:
                if vis_type in visualizations_by_type:
                    section_visualizations[section_title][vis_type] = visualizations_by_type[vis_type]
        
        # Store section visualizations in state if needed
        if hasattr(state, 'section_visualizations'):
            state.section_visualizations = section_visualizations
        
        state.update_progress(f"Generated {len(visualizations_by_type)} visualizations successfully")
        logger.info(f"Visualization agent completed with {len(visualizations_by_type)} visualizations")
        
        # Return the updated state
        return state
    except Exception as e:
        logger.error(f"Error in visualization agent: {str(e)}", exc_info=True)
        # Make sure we don't lose the state object in case of error
        state.update_progress(f"Error generating visualizations: {str(e)}")
        # Initialize visualizations if not already done
        if not hasattr(state, 'visualizations'):
            state.visualizations = {}
        return state