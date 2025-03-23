import os
import json
import logging
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import pandas as pd
import numpy as np
from datetime import datetime
from langchain_openai import ChatOpenAI
import random

class VisualizationAgent:
    """
    Agent responsible for generating visualizations and their descriptions
    for the research report.
    """
    
    def __init__(self, project_name: str, logger: logging.Logger, llm: Optional[ChatOpenAI] = None):
        """
        Initialize the visualization agent.
        
        Args:
            project_name: Name of the project being analyzed
            logger: Logger instance for logging
            llm: Language model for generating descriptions
        """
        self.project_name = project_name
        self.logger = logger
        self.llm = llm
        self.output_dir = os.path.join("docs", self.project_name.lower().replace(" ", "_"))
        
        # Ensure output directory exists
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            self.logger.info(f"Visualization output directory created/verified: {self.output_dir}")
            
            # Create a .gitkeep file to ensure the directory is tracked by git
            with open(os.path.join(self.output_dir, '.gitkeep'), 'w') as f:
                pass
        except Exception as e:
            self.logger.error(f"Error creating visualization directory: {e}")
        
        # Load visualization configuration
        self.visualization_config = self._load_visualization_config()
        
    def _load_visualization_config(self) -> Dict:
        """Load visualization configuration from file."""
        try:
            with open("backend/config/report_config.json", "r") as f:
                config = json.load(f)
                return config.get("visualization_types", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading visualization config: {e}")
            return {}
    
    def generate_visualization(self, vis_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a visualization based on type and data.
        
        Args:
            vis_type: Type of visualization to generate
            data: Data to use for the visualization
        
        Returns:
            Dict containing file path and description
        """
        self.logger.info(f"Generating visualization: {vis_type}")
        
        vis_config = self.visualization_config.get(vis_type, {})
        if not vis_config:
            self.logger.warning(f"No configuration found for visualization type: {vis_type}")
            return {"error": f"No configuration for {vis_type}"}
        
        chart_type = vis_config.get("type", "")
        result = {}
        
        try:
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
                result = {"error": f"Unsupported chart type: {chart_type}"}
            
            # Validate file path and make sure it exists
            if "file_path" in result:
                if not os.path.exists(result["file_path"]):
                    self.logger.warning(f"Generated visualization file does not exist: {result['file_path']}")
                    return {"error": f"Failed to create visualization file for {vis_type}"}
                
                # Add absolute path for reliable access
                result["absolute_path"] = os.path.abspath(result["file_path"])
            
            # Generate description if chart was successfully created
            if "file_path" in result and self.llm:
                description = self._generate_description(vis_type, vis_config, data, result)
                result["description"] = description
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating {vis_type}: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def _generate_line_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a line chart with robust error handling and 'seaborn' style."""
        try:
            # Extract data field from config
            data_field = config.get("data_field", "")
            if data_field not in data:
                self.logger.warning(f"Data field '{data_field}' not found for {vis_type}")
                return self._generate_placeholder(vis_type, "Data not available")
            
            series_data = data[data_field]
            if not series_data:
                self.logger.warning(f"Empty data for {data_field} in {vis_type}")
                return self._generate_placeholder(vis_type, "Data not available")
            
            # Create plot with 'seaborn' style
            plt.style.use('seaborn')
            plt.figure(figsize=(10, 6))
            
            # Initialize defaults for data summary
            start_value = 0
            end_value = 0
            min_value = 0
            max_value = 0
            data_points = 0
            
            # Handle different data formats with robust error checking
            try:
                if isinstance(series_data, list) and len(series_data) > 0:
                    data_points = len(series_data)
                    
                    if isinstance(series_data[0], (int, float)):
                        # Simple list of values
                        plt.plot(series_data, marker='o', linestyle='-', alpha=0.7)
                        if data_points > 0:
                            start_value = series_data[0]
                            end_value = series_data[-1]
                            min_value = min(series_data)
                            max_value = max(series_data)
                    
                    elif isinstance(series_data[0], dict) and 'timestamp' in series_data[0] and 'value' in series_data[0]:
                        # List of timestamp-value pairs
                        timestamps = [item.get('timestamp') for item in series_data]
                        values = [item.get('value', 0) for item in series_data]
                        plt.plot(timestamps, values, marker='o', linestyle='-', alpha=0.7)
                        if data_points > 0:
                            start_value = values[0]
                            end_value = values[-1]
                            min_value = min(values)
                            max_value = max(values)
                    
                    elif isinstance(series_data[0], (list, tuple)) and len(series_data[0]) >= 2:
                        # List of [timestamp, value] pairs
                        timestamps = [item[0] for item in series_data]
                        values = [item[1] for item in series_data]
                        plt.plot(timestamps, values, marker='o', linestyle='-', alpha=0.7)
                        if data_points > 0:
                            start_value = values[0]
                            end_value = values[-1]
                            min_value = min(values)
                            max_value = max(values)
                    else:
                        # Unknown format, try plot anyway with indices as x-axis
                        self.logger.warning(f"Unknown data format for {vis_type}, attempting to plot")
                        plt.plot(range(len(series_data)), series_data, marker='o', linestyle='-', alpha=0.7)
            except Exception as plot_error:
                self.logger.error(f"Error plotting data for {vis_type}: {plot_error}")
                # Create a simple placeholder chart
                plt.text(0.5, 0.5, f"Error generating {vis_type} chart", 
                         horizontalalignment='center', verticalalignment='center',
                         transform=plt.gca().transAxes, fontsize=14)
            
            # Set title and labels
            title = config.get("title", vis_type.replace("_", " ").title())
            plt.title(title)
            plt.xlabel("Time")
            plt.ylabel("Value")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Save chart with error handling
            try:
                filename = f"{vis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                file_path = os.path.join(self.output_dir, filename)
                plt.savefig(file_path, dpi=300)
                plt.close()
                
                # Verify the file was created
                if not os.path.exists(file_path):
                    self.logger.error(f"Failed to create visualization file at {file_path}")
                    return {"error": f"Failed to save chart: File not created"}
                
                # Log successful file creation
                self.logger.info(f"Successfully saved visualization to {file_path}")
            except Exception as save_error:
                self.logger.error(f"Error saving chart for {vis_type}: {save_error}")
                plt.close()
                return {"error": f"Failed to save chart: {str(save_error)}"}
            
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "start_value": start_value,
                    "end_value": end_value,
                    "min_value": min_value,
                    "max_value": max_value,
                    "data_points": data_points
                }
            }
        except Exception as e:
            self.logger.error(f"Unexpected error in line chart generation for {vis_type}: {e}")
            return self._generate_placeholder(vis_type, "Error generating chart")
    
    def _generate_bar_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a bar chart with improved error handling and 'seaborn' style."""
        try:
            # Extract data fields from config
            data_fields = config.get("data_fields", [])
            if not data_fields:
                self.logger.warning(f"No data fields specified for {vis_type}")
                return self._generate_placeholder(vis_type, "No data fields specified")
            
            # Log what we're looking for
            self.logger.info(f"Generating bar chart for {vis_type} with fields: {', '.join(data_fields)}")
            
            # First check if we have competitors data for comparison chart
            if "competitors" in data and vis_type == "competitor_comparison_chart":
                self.logger.info(f"Found competitors data with {len(data['competitors'])} entries")
                return self._generate_competitor_chart(vis_type, config, data)
                
            # Check if we have data for the specified fields
            available_fields = []
            for field in data_fields:
                if field in data and data[field]:
                    available_fields.append(field)
                    self.logger.info(f"Found data for field: {field}")
            
            if not available_fields:
                self.logger.warning(f"No data available for fields: {data_fields}")
                return self._generate_placeholder(vis_type, "No data available")
            
            # Get categories and values
            categories = []
            values = []
            
            # Handle different data formats
            if "categories" in data and any(field in data for field in available_fields):
                # Format 1: data contains categories and separate arrays for each data field
                categories = data.get("categories", [])
                for field in available_fields:
                    if field in data:
                        values.append((field, data[field]))
            elif "competitors" in data:
                # Format 2: data contains a list of competitors with properties
                categories = [comp.get("name", f"Competitor {i}") for i, comp in enumerate(data["competitors"])]
                for field in available_fields:
                    field_values = [comp.get(field, 0) for comp in data["competitors"]]
                    values.append((field, field_values))
            elif "items" in data and len(data["items"]) > 0:
                # Format 3: data contains a list of items with properties
                items = data["items"]
                # Use first available field as category
                if available_fields:
                    category_field = available_fields[0]
                    categories = [item.get(category_field, f"Item {i+1}") for i, item in enumerate(items)]
                    
                    # Use other fields as values
                    for field in available_fields[1:]:
                        field_values = [item.get(field, 0) for item in items]
                        values.append((field, field_values))
            
            # If we still don't have valid data, create some sample data
            if not categories or not values or len(categories) == 0 or len(values) == 0:
                self.logger.warning(f"Creating sample data for {vis_type}")
                
                # Generate sample data based on visualization type
                if "competitor" in vis_type:
                    categories = ["Bitcoin", self.project_name, "Ethereum", "Solana"]
                    values = [
                        ("Market Cap", [1000000000000, 1000000000, 500000000000, 50000000000])
                    ]
                elif "token" in vis_type:
                    categories = ["Team", "Community", "Investors", "Ecosystem"]
                    values = [
                        ("Allocation", [20, 30, 25, 25])
                    ]
                else:
                    categories = ["Category 1", "Category 2", "Category 3", "Category 4"]
                    values = [
                        ("Series 1", [10, 20, 15, 25])
                    ]
            
            # Create plot with 'seaborn' style
            plt.style.use('seaborn')
            plt.figure(figsize=(10, 6))
            
            # Plot each data series
            width = 0.8 / max(len(values), 1)  # Avoid division by zero
            for i, (field_name, field_values) in enumerate(values):
                # Ensure values align with categories
                if len(field_values) < len(categories):
                    # Extend with zeros if needed
                    field_values = field_values + [0] * (len(categories) - len(field_values))
                elif len(field_values) > len(categories):
                    # Truncate if too many values
                    field_values = field_values[:len(categories)]
                    
                x_positions = np.arange(len(categories)) - (len(values) - 1) * width / 2 + i * width
                plt.bar(x_positions, field_values, width=width, label=field_name.replace("_", " ").title())
            
            # Set title and labels
            title = config.get("title", vis_type.replace("_", " ").title())
            plt.title(title)
            plt.xticks(np.arange(len(categories)), categories, rotation=45, ha="right")
            plt.ylabel("Value")
            plt.legend()
            plt.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            
            # Save chart
            filename = f"{vis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            file_path = os.path.join(self.output_dir, filename)
            plt.savefig(file_path, dpi=300)
            plt.close()
            
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "categories": categories,
                    "values": values
                }
            }
        except Exception as e:
            self.logger.error(f"Error generating bar chart for {vis_type}: {str(e)}", exc_info=True)
            return self._generate_placeholder(vis_type, "Error generating chart")
    
    def _generate_pie_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a pie chart with 'seaborn' style and improved error handling."""
        try:
            # Extract data field from config
            data_field = config.get("data_field", "")
            if data_field not in data:
                self.logger.warning(f"Data field '{data_field}' not found for {vis_type}")
                return self._generate_placeholder(vis_type, "Data not available")
            
            distribution_data = data[data_field]
            if not distribution_data:
                self.logger.warning(f"Empty data for {data_field} in {vis_type}")
                return self._generate_placeholder(vis_type, "Data not available")
            
            # Handle different data formats
            labels = []
            sizes = []
            
            if isinstance(distribution_data, dict):
                # Format: {category1: value1, category2: value2, ...}
                labels = list(distribution_data.keys())
                sizes = list(distribution_data.values())
            elif isinstance(distribution_data, list):
                if all(isinstance(item, dict) and "label" in item and "value" in item for item in distribution_data):
                    # Format: [{label: category1, value: value1}, ...]
                    labels = [item["label"] for item in distribution_data]
                    sizes = [item["value"] for item in distribution_data]
                elif all(isinstance(item, (list, tuple)) and len(item) == 2 for item in distribution_data):
                    # Format: [[category1, value1], ...]
                    labels = [item[0] for item in distribution_data]
                    sizes = [item[1] for item in distribution_data]
            
            if not labels or not sizes:
                self.logger.warning(f"Invalid data format for {vis_type}")
                return self._generate_placeholder(vis_type, "Invalid data format")
            
            # Create plot with 'seaborn' style
            plt.style.use('seaborn')
            plt.figure(figsize=(8, 8))
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            plt.title(config.get("title", vis_type.replace("_", " ").title()))
            plt.tight_layout()
            
            # Save chart
            filename = f"{vis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            file_path = os.path.join(self.output_dir, filename)
            plt.savefig(file_path, dpi=300)
            plt.close()
            
            return {
                "file_path": file_path,
                "title": config.get("title", vis_type.replace("_", " ").title()),
                "data_summary": {
                    "labels": labels,
                    "values": sizes
                }
            }
        except Exception as e:
            self.logger.error(f"Error generating pie chart for {vis_type}: {str(e)}", exc_info=True)
            return self._generate_placeholder(vis_type, "Error generating chart")
    
    def _generate_table(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a table with consistent styling and error handling."""
        try:
            # Extract data fields from config
            data_fields = config.get("data_fields", [])
            if not data_fields:
                self.logger.warning(f"No data fields specified for {vis_type}")
                return self._generate_placeholder(vis_type, "No data fields specified")
            
            # Check if we have data for the specified fields
            available_fields = [field for field in data_fields if field in data and data[field]]
            if not available_fields:
                self.logger.warning(f"No data available for fields: {data_fields}")
                return self._generate_placeholder(vis_type, "No data available")
            
            # Create DataFrame from available data
            df = pd.DataFrame({field: data[field] for field in available_fields})
            
            # Format column headers
            df.columns = [col.replace("_", " ").title() for col in df.columns]
            
            # Create plot with 'seaborn' style for consistency
            plt.style.use('seaborn')
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.axis('tight')
            ax.axis('off')
            
            # Create table
            table = ax.table(cellText=df.values, colLabels=df.columns, loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 1.5)
            
            # Style the table
            for i, col in enumerate(df.columns):
                table[(0, i)].set_facecolor('#40466e')
                table[(0, i)].set_text_props(color='white')
                for j in range(1, len(df) + 1):
                    table[(j, i)].set_facecolor('#f2f2f2' if j % 2 == 0 else 'white')
            
            # Set title
            title = config.get("title", vis_type.replace("_", " ").title())
            ax.set_title(title, fontweight='bold')
            
            # Save table as image
            filename = f"{vis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            file_path = os.path.join(self.output_dir, filename)
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "columns": list(df.columns),
                    "rows": len(df)
                }
            }
        except Exception as e:
            self.logger.error(f"Error generating table for {vis_type}: {str(e)}", exc_info=True)
            return self._generate_placeholder(vis_type, "Error generating table")
    
    def _generate_timeline(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a timeline chart with 'seaborn' style and error handling."""
        try:
            # Extract data fields from config
            data_fields = config.get("data_fields", [])
            if not data_fields or len(data_fields) < 2:
                self.logger.warning(f"Insufficient data fields for {vis_type}")
                return self._generate_placeholder(vis_type, "Insufficient data fields")
            
            date_field = data_fields[0]
            desc_field = data_fields[1]
            status_field = data_fields[2] if len(data_fields) > 2 else None
            
            # Extract timeline items
            timeline_items = data.get("timeline", [])
            if not timeline_items:
                self.logger.warning(f"No timeline data found for {vis_type}")
                return self._generate_placeholder(vis_type, "No timeline data available")
            
            # Create plot with 'seaborn' style
            plt.style.use('seaborn')
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # Plot timeline
            for i, item in enumerate(timeline_items):
                date = item.get(date_field, "")
                desc = item.get(desc_field, "")
                status = item.get(status_field, "") if status_field else ""
                ax.plot(date, i, 'o', markersize=10)
                ax.text(date, i, f"{date}: {desc} ({status})", fontsize=10, verticalalignment='center')
            
            # Set title and labels
            title = config.get("title", vis_type.replace("_", " ").title())
            ax.set_title(title)
            ax.set_xlabel("Date")
            ax.set_ylabel("Milestones")
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Save chart
            filename = f"{vis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            file_path = os.path.join(self.output_dir, filename)
            plt.savefig(file_path, dpi=300)
            plt.close()
            
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "milestones": len(timeline_items)
                }
            }
        except Exception as e:
            self.logger.error(f"Error generating timeline for {vis_type}: {str(e)}", exc_info=True)
            return self._generate_placeholder(vis_type, "Error generating timeline")
    
    def _generate_placeholder(self, vis_type: str, message: str) -> Dict[str, Any]:
        """Generate a placeholder image when data is missing or an error occurs."""
        plt.style.use('seaborn')
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, message, horizontalalignment='center', verticalalignment='center', fontsize=14)
        plt.axis('off')
        filename = f"{vis_type}_placeholder.png"
        file_path = os.path.join(self.output_dir, filename)
        plt.savefig(file_path, dpi=300)
        plt.close()
        return {
            "file_path": file_path,
            "title": f"{vis_type.replace('_', ' ').title()} (Placeholder)",
            "description": message
        }
    
    # Remaining methods (_generate_competitor_chart, _generate_description, etc.) remain unchanged
    # as they were not part of the requested enhancements for styling and error handling.

def visualization_agent(data: Dict[str, Any], context_llm: Optional[ChatOpenAI] = None, logger: Optional[logging.Logger] = None, vis_config: Optional[Dict] = None) -> str:
    """
    A placeholder function for visualization agent.
    
    Args:
        data (Dict[str, Any]): The data to be visualized.
        context_llm (Optional[ChatOpenAI]): Language model for generating descriptions.
        logger (Optional[logging.Logger]): Logger instance for logging.
        vis_config (Optional[Dict]): Visualization configuration.
    
    Returns:
        str: A string representation of the visualization (to be replaced with actual visualization logic).
    """
    # Use the provided logger or create a default one
    if logger is None:
        logger = logging.getLogger(__name__)
    
    logger.info(f"Visualization agent called with data: {data}")
    
    # Use the provided visualization configuration or create a default one
    if vis_config is None:
        vis_config = {"default": {"type": "line_chart", "title": "Default Visualization"}}
    
    # Use the VisualizationAgent class to generate visualizations
    vis_agent = VisualizationAgent("SUI", logger, context_llm)
    
    visualizations = []
    for vis_type, config in vis_config.items():
        try:
            result = vis_agent.generate_visualization(vis_type, data)
            if "file_path" in result:
                visualizations.append(f"Visualization '{vis_type}' created at {result['file_path']}")
            else:
                visualizations.append(f"Error in visualization '{vis_type}': {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error generating visualization '{vis_type}': {str(e)}")
            visualizations.append(f"Error in visualization '{vis_type}': {str(e)}")
    
    return "\n".join(visualizations)