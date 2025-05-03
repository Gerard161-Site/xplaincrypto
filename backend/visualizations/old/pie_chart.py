import os
import logging
import json
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Optional, Tuple, Union
import re
import pandas as pd
from .base import BaseVisualizer
import traceback

class PieChartVisualizer(BaseVisualizer):
    """
    Creates professional pie chart visualizations for tokenomics distribution and other data.
    """
    
    def __init__(self, theme='light', pdf_optimized=True, project_name=None, logger=None):
        """Initialize the pie chart visualizer with theme and project settings."""
        super().__init__(theme, pdf_optimized)
        self.project_name = project_name or "unknown"
        self.logger = logger or logging.getLogger(__name__)
        
        # Set up output directory
        self.output_dir = os.path.join("docs", self.project_name)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a professional pie chart visualization.
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating {viz_type} for {self.project_name}")
            
            # Get theme colors
            colors = self.theme_colors
            
            # Extract pie data from the input
            pie_data = self._extract_pie_data(data, viz_type)
            
            # Process data into labels and values
            labels, values = self._process_pie_data(pie_data)
            
            # If still no data, use placeholder
            if not labels or not values:
                self.logger.warning(f"No valid data for {viz_type}, using placeholder data")
                labels = ["Team", "Foundation", "Ecosystem", "Community", "Investors"]
                values = [20, 20, 30, 20, 10]
            
            # Validate data - ensure all values are numeric
            validated_labels = []
            validated_values = []
            for i, (label, value) in enumerate(zip(labels, values)):
                if isinstance(value, (int, float)) and not isinstance(value, dict) and not isinstance(value, bool):
                    validated_labels.append(label)
                    validated_values.append(value)
                else:
                    self.logger.warning(f"Skipping non-numeric value for {label}: {value}")
            
            if not validated_labels or not validated_values:
                self.logger.warning(f"No valid numeric data for {viz_type}, using placeholder data")
                validated_labels = ["Team", "Foundation", "Ecosystem", "Community", "Investors"]
                validated_values = [20, 20, 30, 20, 10]
            
            # Create the pie chart
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Create explode list for slight separation (optional)
            explode = [0.01] * len(validated_labels)
            
            # Get color map based on theme
            if 'accent_palette' in colors and len(validated_labels) <= len(colors['accent_palette']):
                pie_colors = colors['accent_palette'][:len(validated_labels)]
            else:
                # Fallback to matplotlib colormap if accent_palette is missing or too small
                cmap = plt.cm.get_cmap('tab20')
                pie_colors = [cmap(i) for i in np.linspace(0, 1, len(validated_labels))]
            
            # Create the pie chart
            wedges, texts, autotexts = ax.pie(
                validated_values, 
                explode=explode,
                labels=None,  # We'll add a legend instead
                autopct='%1.1f%%',
                shadow=False,
                startangle=90,
                colors=pie_colors,
                wedgeprops={'edgecolor': colors['background'], 'linewidth': 1}
            )
            
            # Style the percentage text
            for autotext in autotexts:
                autotext.set_color(colors['text'])
                autotext.set_fontsize(10)
                autotext.set_fontweight('bold')
            
            # Add title
            title = config.get('title', f"{viz_type.replace('_', ' ').title()}")
            plt.title(title, fontsize=16, color=colors['text'], pad=20)
            
            # Add legend
            ax.legend(
                wedges, 
                validated_labels,
                title="Distribution",
                loc="center left",
                bbox_to_anchor=(1, 0, 0.5, 1),
                frameon=False,
                fontsize=10
            )
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            ax.set_aspect('equal')
            
            # Set background color
            fig.patch.set_facecolor(colors['background'])
            ax.set_facecolor(colors['background'])
            
            # Save the chart
            output_filename = config.get('output_filename', f"{viz_type.replace(' ', '_')}.png")
            output_path = os.path.join(self.output_dir, output_filename)
            
            # Ensure the output directory exists
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                
            plt.tight_layout()
            plt.savefig(output_path, bbox_inches='tight', dpi=300, facecolor=colors['background'])
            plt.close(fig)
            
            self.logger.info(f"Pie chart saved to {output_path}")
            return {
                "success": True,
                "visualization_path": output_path,
                "type": viz_type
            }
            
        except Exception as e:
            self.logger.error(f"Error creating pie chart for {viz_type}: {e}", exc_info=True)
            return {"error": str(e), "success": False}

    def _extract_pie_data(self, data: Dict[str, Any], viz_type: str) -> Any:
        """Extract pie chart data based on visualization type."""
        self.logger.info(f"Extracting pie data for {viz_type}")
        
        # For tokenomics chart
        if 'tokenomics' in viz_type.lower() or 'distribution' in viz_type.lower():
            # Try finding in tokenomics section
            if 'tokenomics' in data:
                token_data = data['tokenomics']
                # Check if it's nested in 'data'
                if isinstance(token_data, dict) and 'data' in token_data:
                    return token_data['data']
                return token_data
                
            # Try distribution section
            if 'distribution' in data:
                dist_data = data['distribution']
                # Check if it's nested in 'data'
                if isinstance(dist_data, dict) and 'data' in dist_data:
                    return dist_data['data']
                return dist_data
        
        # Try direct access through data field
        if viz_type in data:
            # Check if it's nested in 'data'
            if isinstance(data[viz_type], dict) and 'data' in data[viz_type]:
                return data[viz_type]['data']
            return data[viz_type]
        
        # Check if 'data' is a top-level key
        if 'data' in data:
            # Try to find the viz_type in the data field
            if viz_type in data['data']:
                return data['data'][viz_type]
            
            # Try with normalized viz_type (remove underscores)
            normalized_viz_type = viz_type.replace('_', '').lower()
            for key in data['data']:
                if key.replace('_', '').lower() == normalized_viz_type:
                    return data['data'][key]
        
        # Try to guess the data field
        if 'pie_data' in data:
            return data['pie_data']
        
        # Last resort - deep search for any allocation or distribution data
        for key, value in data.items():
            if isinstance(value, dict):
                # Check for allocation or distribution fields
                for field in ['allocation', 'distribution', 'token_distribution', 'token_allocation']:
                    if field in value:
                        return value[field]
                
                # Check nested 'data' field
                if 'data' in value and isinstance(value['data'], dict):
                    for field in ['allocation', 'distribution', 'token_distribution', 'token_allocation']:
                        if field in value['data']:
                            return value['data'][field]
        
        self.logger.warning(f"Could not find relevant data for viz_type: {viz_type}")
        return None
    
    def _process_pie_data(self, pie_data: Any) -> tuple:
        """Process the pie data into labels and values lists."""
        self.logger.info(f"Processing pie data type: {type(pie_data)}")
        
        labels = []
        values = []
        
        # Handle different data formats
        if isinstance(pie_data, dict):
            # Simple key-value pairs for labels and values
            # Example: {"Team": 20, "Investors": 30, "Community": 50}
            for label, value in pie_data.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    labels.append(label)
                    values.append(value)
        
        elif isinstance(pie_data, list):
            # List of dictionaries with label/value pairs
            # Example: [{"category": "Team", "allocation": 20}, ...]
            if pie_data and isinstance(pie_data[0], dict):
                # Try to find label and value fields
                label_keys = ['category', 'label', 'name', 'allocation_type', 'segment']
                value_keys = ['value', 'allocation', 'percentage', 'amount', 'size']
                
                # Determine which keys to use based on first item
                label_key = next((k for k in label_keys if k in pie_data[0]), None)
                value_key = next((k for k in value_keys if k in pie_data[0]), None)
                
                if label_key and value_key:
                    for item in pie_data:
                        if label_key in item and value_key in item:
                            label = item[label_key]
                            value = item[value_key]
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                labels.append(label)
                                values.append(value)
                else:
                    # If we can't determine fields, try to use the dict directly
                    for item in pie_data:
                        for key, value in item.items():
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                labels.append(key)
                                values.append(value)
            
            # Handle list of tuples/lists
            # Example: [("Team", 20), ("Investors", 30), ...]
            elif pie_data and isinstance(pie_data[0], (list, tuple)) and len(pie_data[0]) >= 2:
                for item in pie_data:
                    if len(item) >= 2 and isinstance(item[1], (int, float)) and not isinstance(item[1], bool):
                        labels.append(item[0])
                        values.append(item[1])
        
        elif isinstance(pie_data, pd.DataFrame):
            # Handle DataFrame
            if len(pie_data.columns) >= 2:
                # Assume first column is labels, second is values
                labels = pie_data.iloc[:, 0].tolist()
                values = pie_data.iloc[:, 1].tolist()
        
        self.logger.info(f"Processed pie data into {len(labels)} labels and {len(values)} values")
        return labels, values