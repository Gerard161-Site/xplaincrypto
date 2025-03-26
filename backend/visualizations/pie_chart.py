"""
Pie chart visualization module.

This module provides the PieChartVisualizer class for creating pie chart visualizations,
particularly useful for token distribution visualizations.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np

from backend.visualizations.base import BaseVisualizer

class PieChartVisualizer(BaseVisualizer):
    """
    Specialized visualizer for pie charts.
    
    Handles creation of pie chart visualizations for token distribution
    and other data that is best represented as proportional segments.
    """
    
    def create(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a pie chart visualization based on the provided configuration and data.
        
        Args:
            vis_type: Type of visualization (e.g., token_distribution_pie)
            config: Configuration for the visualization
            data: Data to visualize
            
        Returns:
            Dictionary containing visualization result information
        """
        self.logger.info(f"Creating pie chart: {vis_type}")
        
        # Validate output directory
        if not self.validate_output_dir():
            return {"error": "Invalid output directory"}
        
        # Get the data field from config
        data_field = config.get("data_field", "")
        
        # Get the data based on chart type
        labels, sizes, data_field = self._get_chart_data(vis_type, data_field, data)
        if not labels or not sizes:
            return {"error": f"No data available for {vis_type}"}
        
        # Create the chart
        try:
            # Set up figure with appropriate dimensions
            plt.figure(figsize=(6.5, 5))
            
            # Plot the pie chart
            explode = self._get_explode_values(sizes)
            plt.pie(
                sizes, 
                explode=explode, 
                labels=None, 
                autopct='%1.1f%%', 
                startangle=90, 
                shadow=False,
                colors=plt.cm.tab10(np.linspace(0, 1, len(labels))),
                wedgeprops={'edgecolor': 'white', 'linewidth': 1}
            )
            
            plt.axis('equal')  # Equal aspect ratio ensures pie is drawn as a circle
            
            # Add legend
            total = sum(sizes)
            legend_labels = [f"{label}: {size/total*100:.1f}%" for label, size in zip(labels, sizes)]
            plt.legend(legend_labels, loc='center left', bbox_to_anchor=(1, 0.5))
            
            # Set title
            if "token_distribution" in vis_type.lower():
                title = f"{self.project_name} Token Distribution"
            else:
                title = config.get("title", vis_type.replace("_", " ").title())
                
            plt.title(title, pad=10, fontsize=12)
            
            # Save the chart
            file_path = self._save_chart(vis_type)
            if not file_path:
                return {"error": f"Failed to save chart for {vis_type}"}
            
            # Return the result
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "labels": labels,
                    "values": sizes,
                    "total": total,
                    "data_field": data_field
                }
            }
        except Exception as e:
            self.logger.error(f"Error creating pie chart: {str(e)}", exc_info=True)
            plt.close()
            return {"error": f"Failed to create pie chart: {str(e)}"}
    
    def _get_chart_data(self, vis_type: str, data_field: str, data: Dict[str, Any]) -> Tuple[List, List, str]:
        """
        Get the appropriate data for the chart based on visualization type.
        
        Args:
            vis_type: Type of visualization
            data_field: Field name from config
            data: Data dictionary
            
        Returns:
            Tuple of (labels, sizes, field name used)
        """
        labels = []
        sizes = []
        field_used = data_field
        
        # Special handling for token distribution charts
        if "token_distribution" in vis_type.lower():
            # Try various field names that might contain token distribution data
            possible_token_fields = [
                "token_distribution", 
                "token_allocation",
                "tokenomics_distribution", 
                "supply_allocation",
                "token_supply_distribution"
            ]
            
            # Add the configured field if not already in the list
            if data_field and data_field not in possible_token_fields:
                possible_token_fields.insert(0, data_field)
            
            # Try each field
            for field in possible_token_fields:
                if field in data and data[field]:
                    field_used = field
                    distribution_data = data[field]
                    
                    # Extract labels and sizes based on data format
                    if isinstance(distribution_data, dict):
                        # Format: {"Team": 20, "Community": 30, ...}
                        labels = list(distribution_data.keys())
                        sizes = list(distribution_data.values())
                        self.logger.info(f"Using token distribution data from '{field}' (dict format)")
                        break
                    elif isinstance(distribution_data, list):
                        if all(isinstance(item, dict) for item in distribution_data):
                            # Format: [{"category": "Team", "percentage": 20}, ...]
                            if all("category" in item and "percentage" in item for item in distribution_data):
                                labels = [item["category"] for item in distribution_data]
                                sizes = [item["percentage"] for item in distribution_data]
                                self.logger.info(f"Using token distribution data from '{field}' (category/percentage format)")
                                break
                            # Format: [{"label": "Team", "value": 20}, ...]
                            elif all("label" in item and "value" in item for item in distribution_data):
                                labels = [item["label"] for item in distribution_data]
                                sizes = [item["value"] for item in distribution_data]
                                self.logger.info(f"Using token distribution data from '{field}' (label/value format)")
                                break
                            # Format: [{"name": "Team", "value": 20}, ...]
                            elif all("name" in item and "value" in item for item in distribution_data):
                                labels = [item["name"] for item in distribution_data]
                                sizes = [item["value"] for item in distribution_data]
                                self.logger.info(f"Using token distribution data from '{field}' (name/value format)")
                                break
                        elif all(isinstance(item, (list, tuple)) and len(item) == 2 for item in distribution_data):
                            # Format: [["Team", 20], ["Community", 30], ...]
                            labels = [item[0] for item in distribution_data]
                            sizes = [item[1] for item in distribution_data]
                            self.logger.info(f"Using token distribution data from '{field}' (list of pairs format)")
                            break
        
        # For other pie chart types, try the specified field directly
        else:
            if data_field in data and data[data_field]:
                distribution_data = data[data_field]
                
                # Extract labels and sizes based on data format
                if isinstance(distribution_data, dict):
                    labels = list(distribution_data.keys())
                    sizes = list(distribution_data.values())
                elif isinstance(distribution_data, list):
                    if all(isinstance(item, dict) for item in distribution_data):
                        if all("category" in item and "percentage" in item for item in distribution_data):
                            labels = [item["category"] for item in distribution_data]
                            sizes = [item["percentage"] for item in distribution_data]
                        elif all("label" in item and "value" in item for item in distribution_data):
                            labels = [item["label"] for item in distribution_data]
                            sizes = [item["value"] for item in distribution_data]
                        elif all("name" in item and "value" in item for item in distribution_data):
                            labels = [item["name"] for item in distribution_data]
                            sizes = [item["value"] for item in distribution_data]
                    elif all(isinstance(item, (list, tuple)) and len(item) == 2 for item in distribution_data):
                        labels = [item[0] for item in distribution_data]
                        sizes = [item[1] for item in distribution_data]
        
        # No data found, return empty lists
        if not labels or not sizes:
            self.logger.warning(f"No valid data found for pie chart {vis_type}")
            if "token_distribution" in vis_type.lower():
                self.logger.info(f"Tried fields: {possible_token_fields}")
            else:
                self.logger.info(f"Tried field: {data_field}")
                
            return [], [], ""
        
        # Ensure data quality
        if len(labels) != len(sizes):
            self.logger.warning(f"Mismatch in data length: {len(labels)} labels vs {len(sizes)} values")
            min_len = min(len(labels), len(sizes))
            labels = labels[:min_len]
            sizes = sizes[:min_len]
            
        return labels, sizes, field_used
    
    def _get_explode_values(self, sizes: List[float]) -> List[float]:
        """
        Generate explode values to highlight the largest segment.
        
        Args:
            sizes: List of segment sizes
            
        Returns:
            List of explode values
        """
        if not sizes:
            return []
            
        # Highlight the largest segment
        max_index = sizes.index(max(sizes))
        return [0.1 if i == max_index else 0 for i in range(len(sizes))]
    
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
        
        self.logger.info(f"Saving pie chart to: {file_path}")
        
        try:
            # Save the figure
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # Verify the file was saved correctly
            if self.verify_file_saved(file_path):
                return file_path
            return ""
        except Exception as e:
            self.logger.error(f"Error saving chart: {str(e)}")
            plt.close()
            return "" 