"""
Table visualization module.

This module provides the TableVisualizer class for creating table visualizations
for key metrics, supply metrics, and other tabular data.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.table import Table
from datetime import datetime

from backend.visualizations.base import BaseVisualizer
from backend.utils.number_formatter import NumberFormatter

class TableVisualizer(BaseVisualizer):
    """
    Specialized visualizer for tables.
    
    Handles creation of table visualizations for key metrics, supply metrics,
    and other tabular data that needs to be presented in a structured format.
    """
    
    def __init__(self, project_name: str, logger: logging.Logger):
        super().__init__(project_name, logger)
        self.output_dir = os.path.join("docs", project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
        self.number_formatter = NumberFormatter()
    
    def create(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a table visualization based on the provided configuration and data.
        
        Args:
            vis_type: Type of visualization (e.g., key_metrics_table)
            config: Configuration for the visualization
            data: Data to visualize
            
        Returns:
            Dictionary containing visualization result information
        """
        self.logger.info(f"Creating table visualization: {vis_type}")
        self.logger.debug(f"Configuration: {config}")
        self.logger.debug(f"Input data: {data}")
        
        # Validate output directory
        if not self.validate_output_dir():
            self.logger.error(f"Invalid output directory: {self.output_dir}")
            return {"error": "Invalid output directory"}
        
        # Get the data fields from config
        data_fields = config.get("data_fields", [])
        if not data_fields:
            self.logger.warning(f"No data fields specified for {vis_type}")
            return {"error": "No data fields specified"}
            
        self.logger.debug(f"Data fields for {vis_type}: {data_fields}")
        
        # Extract table data based on fields
        table_data = self._extract_table_data(vis_type, data_fields, data)
        self.logger.debug(f"Extracted table data: {table_data}")
        
        if "error" in table_data:
            return table_data
        
        # Format data into two columns: Metric and Value
        headers = ["Metric", "Value"]
        rows = []
        
        # For metrics tables, format as key-value pairs
        if vis_type in ["key_metrics_table", "basic_metrics_table", "supply_metrics_table"]:
            for field in data_fields:
                if field in table_data:
                    # Format the metric name
                    metric_name = field.replace("_", " ").title()
                    # Format the value based on its type
                    value = self._format_value(table_data[field], field)
                    rows.append([metric_name, value])
        else:
            # For other tables, use the data as is
            for field in data_fields:
                if field in table_data:
                    rows.append([field, str(table_data[field])])
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.output_dir, f"{vis_type}_{timestamp}.png")
        
        # Create the table image
        success = self._create_table_image(headers, rows, vis_type, output_file)
        
        if success:
            self.logger.info(f"Created table visualization: {output_file}")
            return {
                "file_path": output_file,
                "title": vis_type.replace("_", " ").title(),
                "data_summary": {"headers": headers, "row_count": len(rows)}
            }
        else:
            return {"error": "Failed to create table image"}
    
    def _extract_table_data(self, vis_type: str, data_fields: List[str], data: Dict[str, Any]) -> Dict[str, List]:
        """
        Extract table data based on the requested fields.
        """
        table_data = {}
        missing_fields = []
        
        # Try to get each field from the data
        for field in data_fields:
            if field in data:
                table_data[field] = data[field]
                self.logger.info(f"Found {field} with value: {data[field]}")
            else:
                missing_fields.append(field)
                self.logger.warning(f"Field {field} not found in data")
        
        # Log missing fields
        if missing_fields:
            self.logger.error(f"Missing required fields for {vis_type}: {missing_fields}")
            return {"error": f"Missing required fields for {vis_type}: {missing_fields}"}
        
        # Validate data
        if not table_data:
            self.logger.error(f"No valid data found for {vis_type}")
            return {"error": f"No valid data found for {vis_type}"}
        
        # Ensure all values are lists
        for key, value in table_data.items():
            if not isinstance(value, list):
                table_data[key] = [value]
        
        # Ensure all columns have the same length
        max_length = max([len(values) for values in table_data.values()], default=0)
        
        for key, value in table_data.items():
            if len(value) < max_length:
                table_data[key] = value * max_length
                
        self.logger.debug(f"Extracted table data: {len(table_data)} columns, {max_length} rows")
        return table_data
    
    def _format_value(self, value: Any, field: str) -> str:
        """Format value based on field type."""
        try:
            if value is None or value == "N/A":
                return "N/A"
                
            if isinstance(value, (int, float)):
                if "price" in field.lower():
                    # For prices, use more precision for small values
                    if abs(value) < 1:
                        return f"${value:.6f}"
                    else:
                        return self.number_formatter.format_currency(value)
                elif any(term in field.lower() for term in ["market_cap", "tvl", "volume"]):
                    return self.number_formatter.format_currency(value)
                elif "supply" in field.lower():
                    return self.number_formatter.format_number(value)
                else:
                    return self.number_formatter.format_number(value)
            
            return str(value)
            
        except Exception as e:
            self.logger.warning(f"Error formatting value {value} for field {field}: {str(e)}")
            return str(value)
    
    def _create_table_image(self, headers: List[str], data_rows: List[List[str]], title: str, output_path: str) -> bool:
        """Create a table image using matplotlib."""
        try:
            # Fixed width for all tables (reduced by 5%)
            FIXED_WIDTH = 11.4  # Reduced from 12 to 11.4 (5% reduction)
            MIN_HEIGHT = 3    # Minimum height
            ROW_HEIGHT = 0.5  # Height per row
            
            # Calculate height based on content
            content_height = len(data_rows) * ROW_HEIGHT
            title_and_padding = 1.5  # Space for title and padding
            height = max(MIN_HEIGHT, content_height + title_and_padding)
            
            # Create figure and axis
            fig = plt.figure(figsize=(FIXED_WIDTH, height))
            ax = fig.add_subplot(111)
            ax.axis('tight')
            ax.axis('off')
            
            # Clean up data rows - remove brackets and format numbers
            cleaned_rows = []
            for row in data_rows:
                cleaned_row = []
                for i, cell in enumerate(row):
                    # Clean up the cell value
                    value = str(cell)
                    # Remove brackets
                    value = value.strip('[]')
                    # If this is the value column (index 1), try to format numbers
                    if i == 1:
                        try:
                            # Check if it's a number with a suffix
                            if any(suffix in value for suffix in ['K', 'M', 'B', 'T']):
                                # Already formatted, just clean up spaces
                                value = value.replace(' ', '')
                            elif value.replace('.', '').replace('-', '').isdigit():
                                # It's a plain number, format it
                                num = float(value)
                                if abs(num) >= 1e12:
                                    value = f"{num/1e12:.1f}T"
                                elif abs(num) >= 1e9:
                                    value = f"{num/1e9:.1f}B"
                                elif abs(num) >= 1e6:
                                    value = f"{num/1e6:.1f}M"
                                elif abs(num) >= 1e3:
                                    value = f"{num/1e3:.1f}K"
                                else:
                                    value = f"{num:,.0f}" if num.is_integer() else f"{num:,.2f}"
                        except (ValueError, TypeError):
                            pass
                    cleaned_row.append(value)
                cleaned_rows.append(cleaned_row)
            
            # Create the table with fixed proportions
            table = ax.table(
                cellText=cleaned_rows,
                colLabels=headers,
                loc='center',
                cellLoc='left',
                colWidths=[0.6, 0.4]  # Fixed proportions: 60% for metric, 40% for value
            )
            
            # Adjust table style
            table.auto_set_font_size(False)
            table.set_fontsize(11)  # Slightly reduced font size for better fit
            
            # Calculate scale based on content
            num_rows = len(cleaned_rows) + 1  # +1 for header
            vertical_scale = min(2.0, 8.0 / num_rows)  # Adjust scale based on number of rows
            table.scale(1.2, vertical_scale)
            
            # Style header row
            for i, key in enumerate(headers):
                header_cell = table[(0, i)]
                header_cell.set_facecolor('#4472C4')
                header_cell.set_text_props(color='white', weight='bold')
                header_cell.set_text_props(ha='center')
                header_cell.set_height(0.15)  # Fixed header height
            
            # Style data rows
            row_colors = ['#f5f5f5', 'white']
            for i, row in enumerate(range(1, len(cleaned_rows) + 1)):
                row_height = 0.1  # Fixed row height
                for j, col in enumerate(range(len(headers))):
                    cell = table[(row, col)]
                    cell.set_facecolor(row_colors[i % 2])
                    cell.set_height(row_height)
                    
                    # Left-align first column (metrics), right-align second column (values)
                    if j == 0:
                        cell.set_text_props(ha='left', va='center')
                        cell._text.set_x(0.05)  # 5% padding from left
                    else:
                        cell.set_text_props(ha='right', va='center')
                        cell._text.set_x(0.95)  # 5% padding from right
                    
                    # Add subtle borders
                    cell.set_edgecolor('#dddddd')
                    cell.set_linewidth(0.5)
            
            # Add title with consistent padding
            plt.title(title.replace("_", " ").title(), pad=20, fontsize=13, weight='bold')
            
            # Adjust layout to ensure consistent spacing
            plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
            
            # Save the figure with high quality
            plt.savefig(
                output_path,
                dpi=300,
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none',
                pad_inches=0.2  # Consistent padding around the figure
            )
            plt.close()
            
            return True
        except Exception as e:
            self.logger.error(f"Error creating table image: {str(e)}")
            plt.close()
            return False
    
    def _calculate_circulating_ratio(self, circulating: Optional[float], total: Optional[float]) -> str:
        """
        Calculate the circulating ratio from supply metrics.
        
        Args:
            circulating: Circulating supply
            total: Total supply
            
        Returns:
            Formatted circulating ratio string
        """
        if circulating is not None and total is not None and total > 0:
            ratio = circulating / total * 100
            return f"{ratio:.1f}%"
        return "N/A"

    def create_visualization(self, data: Dict[str, Any], title: str) -> str:
        """
        Create a table visualization based on the provided data.
        
        Args:
            data: Data to visualize
            title: Title for the visualization
            
        Returns:
            File path if successful, empty string otherwise
        """
        self.logger.info(f"Creating table visualization: {title}")
        
        # Validate output directory
        if not self.validate_output_dir():
            self.logger.error("Output directory validation failed")
            return ""
        
        # Check for basic metrics
        table_data = []
        
        # First try to extract basic metrics
        basic_metrics = {
            "current_price": ("Current Price", "${}"),
            "market_cap": ("Market Cap", "${:,.2f} billion"),
            "24h_volume": ("24h Trading Volume", "${:,.2f} million"),
            "total_supply": ("Total Supply", "{:,.0f} tokens"),
            "circulating_supply": ("Circulating Supply", "{:,.0f} tokens"),
            "tvl": ("Total Value Locked", "${:,.2f} million")
        }
        
        for key, (label, format_str) in basic_metrics.items():
            if key in data:
                value = data[key]
                # Apply appropriate scaling for better readability
                if key == "market_cap" and value > 1000000:
                    value = value / 1000000000  # Convert to billions
                elif key in ["24h_volume", "tvl"] and value > 1000:
                    value = value / 1000000  # Convert to millions
                
                # Format the value
                formatted_value = format_str.format(value)
                table_data.append([label, formatted_value])
        
        # If no basic metrics, try to use key-value pairs from the data
        if not table_data:
            for key, value in data.items():
                if isinstance(value, (int, float, str, bool)):
                    # Format numbers nicely
                    if isinstance(value, (int, float)):
                        if value > 1000000:
                            value = f"{value/1000000:.2f}M"
                        elif value > 1000:
                            value = f"{value/1000:.2f}K"
                    
                    table_data.append([key.replace("_", " ").title(), str(value)])
        
        # If still no data, return empty string
        if not table_data:
            self.logger.error("No suitable data found for table visualization")
            return ""
        
        try:
            # Set up figure
            fig, ax = plt.subplots(figsize=(6, len(table_data) * 0.5 + 1))
            
            # Hide axes
            ax.axis('off')
            ax.axis('tight')
            
            # Create table
            table = ax.table(
                cellText=table_data,
                colLabels=["Metric", "Value"],
                cellLoc='center',
                loc='center',
                colColours=['#f2f2f2', '#f2f2f2']
            )
            
            # Style the table
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 1.5)
            
            # Add title
            plt.title(title, fontsize=12, pad=20)
            plt.tight_layout()
            
            # Save the table
            filename = self.get_safe_filename(title)
            file_path = os.path.join(self.output_dir, filename)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save figure
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # Verify the file was saved correctly
            if self.verify_file_saved(file_path):
                return file_path
                
            self.logger.error(f"Failed to verify file was saved: {file_path}")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error creating table visualization: {str(e)}", exc_info=True)
            plt.close()
            return ""

    def create_test_visualization(self) -> str:
        """Create a test visualization to verify the system is working."""
        headers = ["Column 1", "Column 2", "Column 3"]
        data_rows = [
            ["Test 1", "Value 1", "Result 1"],
            ["Test 2", "Value 2", "Result 2"],
            ["Test 3", "Value 3", "Result 3"]
        ]
        title = "Test Visualization"
        
        return self._create_table_image(headers, data_rows, title, "test_table") 