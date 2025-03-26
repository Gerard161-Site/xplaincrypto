"""
Line chart visualization module.

This module provides the LineChartVisualizer class for creating line chart visualizations
for price history, volume, TVL, and other time-series data.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

from backend.visualizations.base import BaseVisualizer

class LineChartVisualizer(BaseVisualizer):
    """
    Specialized visualizer for line charts.
    
    Handles creation of line charts for time-series data such as price history,
    trading volume, TVL, and other metrics over time.
    """
    
    def create(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a line chart visualization based on the provided configuration and data.
        
        Args:
            vis_type: Type of visualization (e.g., price_history_chart)
            config: Configuration for the visualization
            data: Data to visualize
            
        Returns:
            Dictionary containing visualization result information
        """
        self.logger.info(f"Creating line chart: {vis_type}")
        
        # Validate output directory
        if not self.validate_output_dir():
            return {"error": "Invalid output directory"}
        
        # Get the data field from config
        data_field = config.get("data_field", "")
        
        # Get the data based on chart type
        series_data, data_field = self._get_chart_data(vis_type, data_field, data)
        if not series_data:
            return {"error": f"No data available for {vis_type}"}
        
        # Validate data
        if not isinstance(series_data, (list, tuple)) or len(series_data) < 2:
            return {"error": f"Insufficient data points for {vis_type}"}
        
        # Create the chart
        try:
            # Set up figure with appropriate dimensions
            plt.figure(figsize=(6.5, 3.5))
            
            # Plot the data
            start_value, end_value, min_value, max_value = self._plot_data(series_data)
            
            # Set labels and styles
            self._set_chart_style(vis_type, config)
            
            # Save the chart
            file_path = self._save_chart(vis_type)
            if not file_path:
                return {"error": f"Failed to save chart for {vis_type}"}
            
            # Calculate percent change
            percent_change = 0
            if start_value and end_value:
                percent_change = ((end_value - start_value) / start_value) * 100
            
            # Return the result
            return {
                "file_path": file_path,
                "title": config.get("title", vis_type.replace("_", " ").title()),
                "data_summary": {
                    "start_value": start_value,
                    "end_value": end_value,
                    "min_value": min_value,
                    "max_value": max_value,
                    "data_points": len(series_data),
                    "percent_change": percent_change,
                    "data_field": data_field
                }
            }
        except Exception as e:
            self.logger.error(f"Error creating line chart: {str(e)}", exc_info=True)
            plt.close()
            return {"error": f"Failed to create line chart: {str(e)}"}
    
    def _get_chart_data(self, vis_type: str, data_field: str, data: Dict[str, Any]) -> Tuple[List, str]:
        """
        Get the appropriate data for the chart based on visualization type.
        
        Args:
            vis_type: Type of visualization
            data_field: Field name from config
            data: Data dictionary
            
        Returns:
            Tuple of (data series, field name used)
        """
        # Define alternative field names based on chart type
        alternative_fields = []
        
        if vis_type == "price_history_chart":
            alternative_fields = ["prices", "price_history", "price_data"]
        elif vis_type == "volume_chart" or vis_type == "liquidity_trends_chart":
            alternative_fields = ["total_volumes", "volume_history", "volumes"]
        elif vis_type == "tvl_chart":
            alternative_fields = ["tvl_history", "tvl_data"]
        
        # Try the specified field first
        if data_field in data and data[data_field]:
            self.logger.info(f"Using data from field '{data_field}' for {vis_type}")
            return data[data_field], data_field
        
        # Try alternative fields
        for field in alternative_fields:
            if field in data and data[field]:
                self.logger.info(f"Using data from alternative field '{field}' for {vis_type}")
                return data[field], field
        
        # No valid data found
        self.logger.error(f"No data found for {vis_type} in fields: {[data_field] + alternative_fields}")
        return [], ""
    
    def _plot_data(self, series_data: List) -> Tuple[float, float, float, float]:
        """
        Plot the data based on its format.
        
        Args:
            series_data: Data to plot
            
        Returns:
            Tuple of (start_value, end_value, min_value, max_value)
        """
        start_value = end_value = min_value = max_value = 0
        
        # Handle different data formats
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
            plt.plot(timestamps, values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
            plt.fill_between(timestamps, values, color='#1f77b4', alpha=0.1)
            start_value = values[0] if values else 0
            end_value = values[-1] if values else 0
            min_value = min(values) if values else 0
            max_value = max(values) if values else 0
            
        elif isinstance(series_data[0], (list, tuple)) and len(series_data[0]) >= 2:
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
                
        return start_value, end_value, min_value, max_value
    
    def _set_chart_style(self, vis_type: str, config: Dict[str, Any]) -> None:
        """
        Set the chart style based on visualization type and configuration.
        
        Args:
            vis_type: Type of visualization
            config: Visualization configuration
        """
        # Set title
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title, pad=10, fontsize=12, fontfamily='Times New Roman')
        
        # Set axis labels based on visualization type
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
        
        # Add grid and layout
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
    
    def _save_chart(self, vis_type: str) -> str:
        """
        Save the chart to a file.
        
        Args:
            vis_type: Type of visualization
            
        Returns:
            File path if successful, empty string otherwise
        """
        # Generate filename
        filename = self.get_safe_filename(vis_type)
        file_path = os.path.join(self.output_dir, filename)
        
        self.logger.info(f"Saving line chart to: {file_path}")
        self.logger.debug(f"Output directory: {self.output_dir}")
        self.logger.debug(f"Current working directory: {os.getcwd()}")
        
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Force non-interactive backend
            import matplotlib
            current_backend = plt.get_backend()
            self.logger.debug(f"Current matplotlib backend: {current_backend}")
            if current_backend != 'Agg':
                self.logger.info(f"Switching matplotlib backend from {current_backend} to Agg")
                matplotlib.use('Agg')
            
            # Save the figure
            self.logger.debug(f"Attempting to save figure to {file_path}")
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            self.logger.debug(f"plt.savefig completed for {file_path}")
            plt.close()
            
            # Verify the file was saved correctly
            if self.verify_file_saved(file_path):
                return file_path
                
            self.logger.error(f"Failed to verify file was saved: {file_path}")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error saving chart: {str(e)}", exc_info=True)
            plt.close()
            return ""

    def create_visualization(self, data: Dict[str, Any], title: str) -> str:
        """
        Create a line chart visualization using the provided data.
        
        Args:
            data: Data to visualize
            title: Title for the visualization
            
        Returns:
            File path if successful, empty string otherwise
        """
        self.logger.info(f"Creating line chart visualization: {title}")
        
        # Validate output directory
        if not self.validate_output_dir():
            self.logger.error("Output directory validation failed")
            return ""
        
        # Extract data series from the data
        series_data = []
        for data_field in ["prices", "price_history", "price_data", "total_volumes", "volume_history", "tvl_history"]:
            if data_field in data and data[data_field]:
                series_data = data[data_field]
                self.logger.info(f"Using data from field '{data_field}' for line chart")
                break
        
        # If no data series found, check for basic metrics that we can chart
        if not series_data:
            # Create simple bar chart-like data for basic metrics
            if "current_price" in data or "market_cap" in data or "24h_volume" in data or "tvl" in data:
                basic_data = []
                if "current_price" in data:
                    basic_data.append(("Price", data["current_price"]))
                if "market_cap" in data:
                    basic_data.append(("Market Cap (B)", data["market_cap"] / 1000000000))
                if "24h_volume" in data:
                    basic_data.append(("24h Volume (M)", data["24h_volume"] / 1000000))
                if "tvl" in data:
                    basic_data.append(("TVL (M)", data["tvl"] / 1000000))
                    
                series_data = basic_data
                self.logger.info(f"Created basic metrics series with {len(basic_data)} data points")
        
        # If still no data, but data is a list, use it directly
        if not series_data and isinstance(data, list) and len(data) > 0:
            series_data = data
            self.logger.info("Using direct list data for line chart")
        
        # Validate data
        if not series_data or not isinstance(series_data, (list, tuple)) or len(series_data) < 2:
            self.logger.error(f"Insufficient data points for line chart: {len(series_data) if series_data else 0} points")
            return ""
        
        try:
            # Set up figure with appropriate dimensions
            plt.figure(figsize=(6.5, 3.5))
            
            # Plot the data
            x_values = []
            y_values = []
            
            # Handle different data formats
            if all(isinstance(item, tuple) and len(item) == 2 for item in series_data):
                # Data is a list of (label, value) tuples - create a bar chart
                x_values = [item[0] for item in series_data]
                y_values = [item[1] for item in series_data]
                plt.bar(x_values, y_values, color='#1f77b4', alpha=0.7)
                plt.xticks(rotation=45)
                plt.grid(True, alpha=0.3)
                
            elif isinstance(series_data[0], (int, float)):
                # Simple array of values
                x_values = list(range(len(series_data)))
                y_values = series_data
                plt.plot(x_values, y_values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(x_values, y_values, color='#1f77b4', alpha=0.1)
                
            elif isinstance(series_data[0], dict) and 'timestamp' in series_data[0] and 'value' in series_data[0]:
                # Array of objects with timestamp and value
                x_values = [item.get('timestamp') for item in series_data]
                y_values = [item.get('value', 0) for item in series_data]
                plt.plot(x_values, y_values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(x_values, y_values, color='#1f77b4', alpha=0.1)
                
            elif isinstance(series_data[0], (list, tuple)) and len(series_data[0]) >= 2:
                # Array of [timestamp, value] pairs
                x_values = [item[0] for item in series_data]
                y_values = [item[1] for item in series_data]
                
                # Convert timestamps if they're in milliseconds
                if x_values and isinstance(x_values[0], (int, float)) and x_values[0] > 1e10:
                    x_values = [ts/1000 for ts in x_values]
                
                plt.plot(x_values, y_values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(x_values, y_values, color='#1f77b4', alpha=0.1)
            
            # Format x-axis as dates if timestamps
            if x_values and isinstance(x_values[0], (int, float)) and x_values[0] > 1e8:
                plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: 
                    datetime.fromtimestamp(x).strftime('%m/%d')))
            
            # Set title and labels
            plt.title(title, pad=10, fontsize=12)
            plt.xlabel("Time", labelpad=10)
            plt.ylabel("Value", labelpad=10)
            
            # Add grid and layout
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Save the chart
            filename = self.get_safe_filename(title)
            file_path = os.path.join(self.output_dir, filename)
            
            self.logger.info(f"Saving line chart to: {file_path}")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Force non-interactive backend
            import matplotlib
            current_backend = plt.get_backend()
            self.logger.debug(f"Current matplotlib backend: {current_backend}")
            if current_backend != 'Agg':
                self.logger.info(f"Switching matplotlib backend from {current_backend} to Agg")
                matplotlib.use('Agg')
                
            # Save the figure
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # Verify the file was saved correctly
            if self.verify_file_saved(file_path):
                return file_path
            
            self.logger.error(f"Failed to verify file was saved: {file_path}")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error creating line chart: {str(e)}", exc_info=True)
            plt.close()
            return "" 