"""
Bar chart visualization module.

This module provides the BarChartVisualizer class for creating bar chart visualizations
for competitor comparisons, rankings, and other categorical data.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np

from backend.visualizations.base import BaseVisualizer

class BarChartVisualizer(BaseVisualizer):
    """
    Specialized visualizer for bar charts.
    
    Handles creation of bar chart visualizations for competitor comparisons,
    rankings, and other categorical data.
    """
    
    def create(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info(f"Creating bar chart: {vis_type}")
        
        if not self.validate_output_dir():
            return {"error": "Invalid output directory"}
        
        if "competitor" in vis_type.lower():
            return self._create_competitor_chart(vis_type, config, data)
        else:
            return self._create_standard_bar_chart(vis_type, config, data)
    
    def _create_competitor_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        competitors_data = None
        data_field = config.get("data_field", "competitors")
        
        if data_field in data and data[data_field]:
            competitors_data = data[data_field]
            self.logger.info(f"Using competitor data from '{data_field}'")
        elif "competitors" in data and data["competitors"]:
            competitors_data = data["competitors"]
            self.logger.info("Using competitor data from 'competitors' field")
        elif "similar_projects" in data and data["similar_projects"]:
            competitors_data = data["similar_projects"]
            self.logger.info("Using competitor data from 'similar_projects' field")
        
        if not competitors_data:
            self.logger.warning(f"No competitor data found for {vis_type}")
            return {"error": "No competitor data available"}
        
        competitors, metrics = self._extract_competitor_data(competitors_data)
        if not competitors or not metrics:
            self.logger.warning(f"Failed to extract valid competitor data for {vis_type}")
            return {"error": "Invalid competitor data format"}
        
        try:
            plt.figure(figsize=(8, 5))
            bar_width = 0.8 / len(metrics) if len(metrics) > 1 else 0.4
            bar_positions = np.arange(len(competitors))
            
            for i, (metric_name, metric_values) in enumerate(metrics.items()):
                offset = (i - len(metrics)/2 + 0.5) * bar_width
                plt.bar(
                    bar_positions + offset, 
                    metric_values, 
                    width=bar_width, 
                    label=metric_name.replace("_", " ").title(), 
                    alpha=0.7,
                    color=plt.cm.tab10(i % 10)
                )
            
            plt.xticks(bar_positions, competitors, rotation=45, ha='right', fontfamily='Times New Roman')
            if len(metrics) > 1:
                plt.legend(loc='best', frameon=True, fontfamily='Times New Roman')
            
            title = config.get("title", f"{self.project_name} Competitor Comparison")
            plt.title(title, pad=20, fontsize=14, fontfamily='Times New Roman')
            plt.ylabel("Value", labelpad=10, fontfamily='Times New Roman')
            
            plt.tight_layout()
            plt.subplots_adjust(bottom=0.25)
            
            file_path = self._save_chart(vis_type)
            if not file_path:
                return {"error": f"Failed to save chart for {vis_type}"}
            
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "competitors": competitors,
                    "metrics": list(metrics.keys()),
                    "data_field": data_field
                }
            }
        except Exception as e:
            self.logger.error(f"Error creating competitor chart: {str(e)}", exc_info=True)
            plt.close()
            return {"error": f"Failed to create competitor chart: {str(e)}"}
    
    def _create_standard_bar_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        data_field = config.get("data_field", "")
        categories, values, field_used = self._get_chart_data(vis_type, data_field, data)
        if not categories or not values:
            self.logger.warning(f"No valid data found for {vis_type}")
            return {"error": f"No valid data available for {vis_type}"}
        
        try:
            plt.figure(figsize=(7, 5))
            bars = plt.bar(
                range(len(categories)), 
                values, 
                width=0.6, 
                align='center',
                alpha=0.7,
                color=plt.cm.tab10(np.linspace(0, 1, len(categories)))
            )
            
            plt.xticks(range(len(categories)), categories, rotation=45, ha='right', fontfamily='Times New Roman')
            
            for bar in bars:
                height = bar.get_height()
                plt.text(
                    bar.get_x() + bar.get_width()/2., 
                    height + 0.02 * max(values),
                    f'{height:.1f}' if isinstance(height, float) else f'{height}',
                    ha='center', va='bottom', fontsize=10, rotation=0, fontfamily='Times New Roman'
                )
            
            title = config.get("title", vis_type.replace("_", " ").title())
            plt.title(title, pad=20, fontsize=14, fontfamily='Times New Roman')
            plt.ylabel("Value", labelpad=10, fontfamily='Times New Roman')
            
            plt.tight_layout()
            plt.subplots_adjust(bottom=0.25)
            
            file_path = self._save_chart(vis_type)
            if not file_path:
                return {"error": f"Failed to save chart for {vis_type}"}
            
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "categories": categories,
                    "values": values,
                    "data_field": field_used
                }
            }
        except Exception as e:
            self.logger.error(f"Error creating bar chart: {str(e)}", exc_info=True)
            plt.close()
            return {"error": f"Failed to create bar chart: {str(e)}"}
    
    def _extract_competitor_data(self, competitors_data: Any) -> Tuple[List[str], Dict[str, List[float]]]:
        competitor_names = []
        metrics = {}
        
        try:
            if isinstance(competitors_data, list):
                if all(isinstance(comp, dict) and "name" in comp for comp in competitors_data):
                    competitor_names = [comp.get("name", f"Competitor {i+1}") for i, comp in enumerate(competitors_data)]
                    all_keys = set()
                    for comp in competitors_data:
                        all_keys.update(comp.keys())
                    non_metric_keys = {"name", "description", "url", "logo", "id"}
                    metric_keys = [k for k in all_keys if k not in non_metric_keys]
                    for metric in metric_keys:
                        metrics[metric] = [float(comp.get(metric, 0)) for comp in competitors_data]
                elif all(isinstance(comp, (list, tuple)) for comp in competitors_data):
                    competitor_names = [comp[0] if len(comp) > 0 else f"Competitor {i+1}" 
                                       for i, comp in enumerate(competitors_data)]
                    if all(len(comp) > 1 for comp in competitors_data):
                        for i in range(1, len(competitors_data[0])):
                            metric_name = f"Metric {i}"
                            metrics[metric_name] = [float(comp[i]) if len(comp) > i else 0 
                                                  for comp in competitors_data]
            elif isinstance(competitors_data, dict):
                competitor_names = list(competitors_data.keys())
                first_comp = list(competitors_data.values())[0] if competitors_data else {}
                if isinstance(first_comp, dict):
                    for metric in first_comp.keys():
                        metrics[metric] = [comp.get(metric, 0) if isinstance(comp, dict) else 0 
                                           for comp in competitors_data.values()]
        
        except Exception as e:
            self.logger.error(f"Error extracting competitor data: {str(e)}", exc_info=True)
            return [], {}
        
        if self.project_name and self.project_name not in competitor_names:
            competitor_names.insert(0, self.project_name)
            for metric in metrics:
                if metrics[metric]:
                    metrics[metric].insert(0, sum(metrics[metric]) / len(metrics[metric]))
                else:
                    metrics[metric].insert(0, 0)
        
        return competitor_names, metrics
    
    def _get_chart_data(self, vis_type: str, data_field: str, data: Dict[str, Any]) -> Tuple[List[str], List[float], str]:
        categories = []
        values = []
        field_used = data_field
        
        if data_field in data and data[data_field]:
            field_data = data[data_field]
            field_used = data_field
            
            if isinstance(field_data, dict):
                categories = list(field_data.keys())
                values = list(field_data.values())
            elif isinstance(field_data, list):
                if all(isinstance(item, dict) for item in field_data):
                    if all("name" in item and "value" in item for item in field_data):
                        categories = [item["name"] for item in field_data]
                        values = [item["value"] for item in field_data]
                    elif all("label" in item and "value" in item for item in field_data):
                        categories = [item["label"] for item in field_data]
                        values = [item["value"] for item in field_data]
                elif all(isinstance(item, (list, tuple)) and len(item) == 2 for item in field_data):
                    categories = [item[0] for item in field_data]
                    values = [item[1] for item in field_data]
        
        if not categories or not values:
            potential_fields = [
                "rankings",
                "comparison",
                "metrics_comparison",
                "market_position"
            ]
            
            for field in potential_fields:
                if field in data and data[field]:
                    field_data = data[field]
                    field_used = field
                    
                    if isinstance(field_data, dict):
                        categories = list(field_data.keys())
                        values = list(field_data.values())
                    elif isinstance(field_data, list):
                        if all(isinstance(item, dict) for item in field_data):
                            if all("name" in item and "value" in item for item in field_data):
                                categories = [item["name"] for item in field_data]
                                values = [item["value"] for item in field_data]
                            elif all("label" in item and "value" in item for item in field_data):
                                categories = [item["label"] for item in field_data]
                                values = [item["value"] for item in field_data]
                        elif all(isinstance(item, (list, tuple)) and len(item) == 2 for item in field_data):
                            categories = [item[0] for item in field_data]
                            values = [item[1] for item in field_data]
                    
                    if categories and values:
                        self.logger.info(f"Using alternative field '{field}' for bar chart")
                        break
        
        if categories and values:
            try:
                values = [float(val) if isinstance(val, (int, float, str)) else 0 for val in values]
            except (ValueError, TypeError):
                self.logger.warning(f"Non-numeric values found in bar chart data")
                values = [0] * len(categories)
        
        return categories, values, field_used
    
    def _save_chart(self, vis_type: str) -> str:
        filename = self.get_safe_filename(vis_type)
        file_path = os.path.join(self.output_dir, filename)
        
        self.logger.info(f"Saving bar chart to: {file_path}")
        
        try:
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            if self.verify_file_saved(file_path):
                return file_path
            return ""
        except Exception as e:
            self.logger.error(f"Error saving chart: {str(e)}")
            plt.close()
            return ""