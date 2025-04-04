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
        self.logger.info(f"Creating line chart: {vis_type}")
        
        if not self.validate_output_dir():
            return {"error": "Invalid output directory"}
        
        data_field = config.get("data_field", "")
        series_data, data_field = self._get_chart_data(vis_type, data_field, data)
        if not series_data:
            return {"error": f"No data available for {vis_type}"}
        
        if not isinstance(series_data, (list, tuple)) or len(series_data) < 2:
            return {"error": f"Insufficient data points for {vis_type}: {len(series_data)} points"}
        
        if not all(isinstance(item, (list, tuple)) and len(item) >= 2 for item in series_data):
            return {"error": f"Invalid data format for {vis_type}: Expected [timestamp, value] pairs"}
        
        try:
            plt.figure(figsize=(6.5, 3.5))
            start_value, end_value, min_value, max_value = self._plot_data(series_data)
            self._set_chart_style(vis_type, config)
            file_path = self._save_chart(vis_type)
            if not file_path:
                return {"error": f"Failed to save chart for {vis_type}"}
            
            percent_change = 0
            if start_value and end_value and start_value != 0:
                percent_change = ((end_value - start_value) / start_value) * 100
            
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
        alternative_fields = []
        
        if vis_type == "price_history_chart":
            alternative_fields = ["prices", "price_history", "price_data"]
        elif vis_type == "volume_chart" or vis_type == "liquidity_trends_chart":
            alternative_fields = ["total_volumes", "volume_history", "volumes"]
        elif vis_type == "tvl_chart":
            alternative_fields = ["tvl_history", "tvl_data"]
        
        if data_field in data and data[data_field]:
            self.logger.info(f"Using data from field '{data_field}' for {vis_type}")
            return data[data_field], data_field
        
        for field in alternative_fields:
            if field in data and data[field]:
                self.logger.info(f"Using data from alternative field '{field}' for {vis_type}")
                return data[field], field
        
        self.logger.error(f"No data found for {vis_type} in fields: {[data_field] + alternative_fields}")
        return [], ""
    
    def _plot_data(self, series_data: List) -> Tuple[float, float, float, float]:
        timestamps = [item[0] for item in series_data]
        values = [item[1] for item in series_data]
        
        if timestamps and timestamps[0] > 1e10:
            timestamps = [ts/1000 for ts in timestamps]
        
        values = [float(v) if v is not None else 0 for v in values]
        
        plt.plot(timestamps, values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
        plt.fill_between(timestamps, values, color='#1f77b4', alpha=0.1)
        
        start_value = values[0] if values else 0
        end_value = values[-1] if values else 0
        min_value = min(values) if values else 0
        max_value = max(values) if values else 0
        
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: 
            datetime.fromtimestamp(x).strftime('%m/%d') if x > 1e8 else str(int(x))))
        plt.gca().tick_params(axis='both', which='major', labelsize=10, labelrotation=45, labelright=False, labeltop=False, labelbottom=True, labelleft=True)
        
        return start_value, end_value, min_value, max_value
    
    def _set_chart_style(self, vis_type: str, config: Dict[str, Any]) -> None:
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title, pad=10, fontsize=12, fontfamily='Times New Roman')
        
        if vis_type == "price_history_chart":
            plt.xlabel("Time", labelpad=10, fontfamily='Times New Roman')
            plt.ylabel("Price (USD)", labelpad=10, fontfamily='Times New Roman')
        elif vis_type == "volume_chart" or vis_type == "liquidity_trends_chart":
            plt.xlabel("Time", labelpad=10, fontfamily='Times New Roman')
            plt.ylabel("Volume (USD)", labelpad=10, fontfamily='Times New Roman')
        elif vis_type == "tvl_chart":
            plt.xlabel("Time", labelpad=10, fontfamily='Times New Roman')
            plt.ylabel("TVL (USD)", labelpad=10, fontfamily='Times New Roman')
        else:
            plt.xlabel("Time", labelpad=10, fontfamily='Times New Roman')
            plt.ylabel("Value", labelpad=10, fontfamily='Times New Roman')
        
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
    
    def _save_chart(self, vis_type: str) -> str:
        filename = self.get_safe_filename(vis_type)
        file_path = os.path.join(self.output_dir, filename)
        
        self.logger.info(f"Saving line chart to: {file_path}")
        self.logger.debug(f"Output directory: {self.output_dir}")
        self.logger.debug(f"Current working directory: {os.getcwd()}")
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            import matplotlib
            current_backend = plt.get_backend()
            self.logger.debug(f"Current matplotlib backend: {current_backend}")
            if current_backend != 'Agg':
                self.logger.info(f"Switching matplotlib backend from {current_backend} to Agg")
                matplotlib.use('Agg')
            
            self.logger.debug(f"Attempting to save figure to {file_path}")
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            self.logger.debug(f"plt.savefig completed for {file_path}")
            plt.close()
            
            if self.verify_file_saved(file_path):
                return file_path
                
            self.logger.error(f"Failed to verify file was saved: {file_path}")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error saving chart: {str(e)}", exc_info=True)
            plt.close()
            return ""

    def create_visualization(self, data: Dict[str, Any], title: str) -> str:
        self.logger.info(f"Creating line chart visualization: {title}")
        
        if not self.validate_output_dir():
            self.logger.error("Output directory validation failed")
            return ""
        
        series_data = []
        for data_field in ["prices", "price_history", "price_data", "total_volumes", "volume_history", "tvl_history"]:
            if data_field in data and data[data_field]:
                series_data = data[data_field]
                self.logger.info(f"Using data from field '{data_field}' for line chart")
                break
        
        if not series_data:
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
        
        if not series_data and isinstance(data, list) and len(data) > 0:
            series_data = data
            self.logger.info("Using direct list data for line chart")
        
        if not series_data or not isinstance(series_data, (list, tuple)) or len(series_data) < 2:
            self.logger.error(f"Insufficient data points for line chart: {len(series_data) if series_data else 0} points")
            return ""
        
        try:
            plt.figure(figsize=(6.5, 3.5))
            x_values = []
            y_values = []
            
            if all(isinstance(item, tuple) and len(item) == 2 for item in series_data):
                x_values = [item[0] for item in series_data]
                y_values = [item[1] for item in series_data]
                plt.bar(x_values, y_values, color='#1f77b4', alpha=0.7)
                plt.xticks(rotation=45)
                plt.grid(True, alpha=0.3)
                
            elif isinstance(series_data[0], (int, float)):
                x_values = list(range(len(series_data)))
                y_values = series_data
                plt.plot(x_values, y_values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(x_values, y_values, color='#1f77b4', alpha=0.1)
                
            elif isinstance(series_data[0], dict) and 'timestamp' in series_data[0] and 'value' in series_data[0]:
                x_values = [item.get('timestamp') for item in series_data]
                y_values = [item.get('value', 0) for item in series_data]
                plt.plot(x_values, y_values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(x_values, y_values, color='#1f77b4', alpha=0.1)
                
            elif isinstance(series_data[0], (list, tuple)) and len(series_data[0]) >= 2:
                x_values = [item[0] for item in series_data]
                y_values = [item[1] for item in series_data]
                
                if x_values and isinstance(x_values[0], (int, float)) and x_values[0] > 1e10:
                    x_values = [ts/1000 for ts in x_values]
                
                plt.plot(x_values, y_values, marker='o', markersize=4, linestyle='-', color='#1f77b4', alpha=0.7)
                plt.fill_between(x_values, y_values, color='#1f77b4', alpha=0.1)
            
            if x_values and isinstance(x_values[0], (int, float)) and x_values[0] > 1e8:
                plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: 
                    datetime.fromtimestamp(x).strftime('%m/%d')))
            
            plt.title(title, pad=10, fontsize=12, fontfamily='Times New Roman')
            plt.xlabel("Time", labelpad=10, fontfamily='Times New Roman')
            plt.ylabel("Value", labelpad=10, fontfamily='Times New Roman')
            
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            filename = self.get_safe_filename(title)
            file_path = os.path.join(self.output_dir, filename)
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            import matplotlib
            current_backend = plt.get_backend()
            self.logger.debug(f"Current matplotlib backend: {current_backend}")
            if current_backend != 'Agg':
                self.logger.info(f"Switching matplotlib backend from {current_backend} to Agg")
                matplotlib.use('Agg')
                
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            if self.verify_file_saved(file_path):
                return file_path
            
            self.logger.error(f"Failed to verify file was saved: {file_path}")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error creating line chart: {str(e)}", exc_info=True)
            plt.close()
            return ""