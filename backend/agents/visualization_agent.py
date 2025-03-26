import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime
from langchain_openai import ChatOpenAI
import random
from matplotlib.patches import Rectangle
import matplotlib.patheffects as path_effects
from matplotlib.table import Table
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import copy
from PIL import Image as PILImage
from pathlib import Path
import re

# Import visualizer classes
from backend.utils.style_utils import StyleManager
from backend.visualizations import (
    LineChartVisualizer,
    BarChartVisualizer,
    PieChartVisualizer,
    TableVisualizer,
    TimelineVisualizer
)

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
        
        # Initialize visualizers
        self._init_visualizers()
    
    def _init_visualizers(self):
        """Initialize all visualizer instances."""
        self.line_chart_visualizer = LineChartVisualizer(self.project_name, self.logger)
        self.bar_chart_visualizer = BarChartVisualizer(self.project_name, self.logger)
        self.pie_chart_visualizer = PieChartVisualizer(self.project_name, self.logger)
        self.table_visualizer = TableVisualizer(self.project_name, self.logger)
        self.timeline_visualizer = TimelineVisualizer(self.project_name, self.logger)
    
    def _load_visualization_config(self) -> Dict:
        try:
            with open("backend/config/report_config.json", "r") as f:
                config = json.load(f)
                return config.get("visualization_types", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading visualization config: {e}")
            return {}
    
    def _get_multi_source_data(self, data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """
        Get data from multiple sources and combine them based on required fields.
        Prioritizes data sources in order: structured_data, web_research, coingecko, coinmarketcap, defillama
        """
        self.logger.info(f"Getting multi-source data for fields: {required_fields}")
        self.logger.debug(f"Available data sources: {list(data.keys())}")
        
        # Initialize result
        result = {}
        
        # Define data source priority
        sources = ["structured_data", "web_research", "coingecko", "coinmarketcap", "defillama"]
        
        # Log available fields in each source
        for source in sources:
            if source in data and isinstance(data[source], dict):
                self.logger.debug(f"Fields in {source}: {list(data[source].keys())}")
            else:
                self.logger.debug(f"No data available for source: {source}")
        
        # Try to get each required field from sources in priority order
        for field in required_fields:
            self.logger.debug(f"Looking for field: {field}")
            field_found = False
            field_value = None
            source_found = None
            
            for source in sources:
                if source in data and isinstance(data[source], dict):
                    source_data = data[source]
                    
                    # Try exact match first
                    if field in source_data:
                        field_value = source_data[field]
                        source_found = source
                        field_found = True
                        self.logger.info(f"Found {field} in {source} with value: {field_value}")
                        break
                    
                    # Try case-insensitive match
                    for key in source_data:
                        if key.lower() == field.lower():
                            field_value = source_data[key]
                            source_found = source
                            field_found = True
                            self.logger.info(f"Found {field} (as {key}) in {source} with value: {field_value}")
                            break
                    
                    # Try to find field in nested structures
                    if not field_found and isinstance(source_data, dict):
                        for key, value in source_data.items():
                            if isinstance(value, dict) and field in value:
                                field_value = value[field]
                                source_found = f"{source}.{key}"
                                field_found = True
                                self.logger.info(f"Found {field} in nested data {source}.{key} with value: {field_value}")
                                break
                    
                    if field_found:
                        break
            
            if field_found and field_value is not None:
                # Validate and format the value
                if isinstance(field_value, (int, float, str, list, dict)):
                    result[field] = field_value
                    self.logger.info(f"Added {field} from {source_found} to result")
                else:
                    self.logger.warning(f"Invalid value type for {field} from {source_found}: {type(field_value)}")
            else:
                self.logger.warning(f"Field {field} not found in any data source")
                # Add a placeholder value
                result[field] = None
        
        # Log the final combined data
        self.logger.info(f"Combined data fields: {list(result.keys())}")
        self.logger.debug(f"Final combined data: {result}")
        
        return result

    def generate_visualization(self, vis_type: str, data: Dict[str, Any], skip_expensive_descriptions: bool = False, use_real_data_only: bool = False, report_config: Dict = None, section: str = "General") -> Dict[str, Any]:
        """Generate a visualization based on the provided configuration."""
        self.logger.info(f"Generating visualization: {vis_type}")
        self.logger.debug(f"Input data sources: {list(data.keys())}")
        
        # Use provided report_config or load from class
        if report_config:
            vis_config = report_config.get("visualization_types", {}).get(vis_type, {})
        else:
            vis_config = self.visualization_config.get(vis_type, {})
        
        if not vis_config:
            self.logger.warning(f"No configuration found for visualization type: {vis_type}")
            return {"error": f"No configuration for {vis_type}"}
        
        # Extract visualization parameters
        chart_type = vis_config.get("type", "")
        data_source = vis_config.get("data_source", "")
        required_fields = vis_config.get("data_fields", [])
        
        self.logger.info(f"Visualization parameters:")
        self.logger.info(f"- Type: {chart_type}")
        self.logger.info(f"- Data source: {data_source}")
        self.logger.info(f"- Required fields: {required_fields}")
        
        # Handle data source correctly
        source_data = {}
        
        try:
            # If using multi-source data
            if data_source == "multi":
                source_data = self._get_multi_source_data(data, required_fields)
                if not source_data:
                    self.logger.error("No data available from any source")
                    return {"error": "No data available from any source"}
                
                # Log what data was found
                self.logger.info("Multi-source data retrieved:")
                for field, value in source_data.items():
                    if value is not None:
                        self.logger.info(f"- {field}: {value}")
                    else:
                        self.logger.warning(f"- {field}: Missing")
                    
            # If using a specific data source
            elif data_source in data:
                source_data = data[data_source]
                self.logger.info(f"Using data from {data_source}")
                self.logger.debug(f"Available fields: {list(source_data.keys())}")
            else:
                self.logger.error(f"Required data source {data_source} not found")
                return {"error": f"Required data source {data_source} not available"}
            
            # Verify required data fields are present
            if required_fields:
                missing_fields = [f for f in required_fields if f not in source_data or source_data[f] is None]
                if missing_fields:
                    self.logger.error(f"Missing required fields: {missing_fields}")
                    return {"error": f"Missing required data fields: {', '.join(missing_fields)}"}
                
                # Log the data that will be used
                self.logger.info("Data for visualization:")
                for field in required_fields:
                    self.logger.info(f"- {field}: {source_data[field]}")
            
            try:
                self.logger.debug(f"Processing visualization with data: {source_data}")
                
                # Use the appropriate visualizer based on chart type
                if chart_type == "line_chart":
                    result = self.line_chart_visualizer.create(vis_type, vis_config, source_data)
                elif chart_type == "bar_chart":
                    result = self.bar_chart_visualizer.create(vis_type, vis_config, source_data)
                elif chart_type == "pie_chart":
                    result = self.pie_chart_visualizer.create(vis_type, vis_config, source_data)
                elif chart_type == "table":
                    result = self.table_visualizer.create(vis_type, vis_config, source_data)
                elif chart_type == "timeline":
                    result = self.timeline_visualizer.create(vis_type, vis_config, source_data)
                else:
                    self.logger.warning(f"Unsupported chart type: {chart_type}")
                    return {"error": f"Unsupported chart type: {chart_type}"}
                
                if result and isinstance(result, dict):
                    if "error" in result:
                        self.logger.warning(f"Error generating {vis_type}: {result['error']}")
                        return result
                    elif "file_path" in result and os.path.exists(result["file_path"]):
                        result["absolute_path"] = os.path.abspath(result["file_path"])
                        if self.llm and not skip_expensive_descriptions:
                            description = self._generate_description(vis_type, vis_config, source_data, result)
                            result["description"] = description
                        self.logger.info(f"Successfully generated {vis_type} at {result['file_path']}")
                        
                        # Verify the file was created and has content
                        file_size = os.path.getsize(result["file_path"])
                        self.logger.info(f"Generated file size: {file_size} bytes")
                        if file_size == 0:
                            self.logger.error("Generated file is empty")
                            return {"error": "Generated visualization file is empty"}
                            
                        return result
                    else:
                        error_msg = f"Generated visualization file does not exist: {result.get('file_path', 'No path')}"
                        self.logger.warning(error_msg)
                        return {"error": error_msg}
                else:
                    error_msg = f"Invalid result format for {vis_type}"
                    self.logger.warning(error_msg)
                    return {"error": error_msg}
                
            except Exception as e:
                self.logger.error(f"Error generating {vis_type}: {str(e)}", exc_info=True)
                return {"error": str(e)}
            
        except Exception as e:
            self.logger.error(f"Error in generate_visualization: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def _generate_description(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Generate a description for the visualization."""

        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            template = """
            You are a professional cryptocurrency analyst writing concise descriptions for data visualizations in an investment research report.
            
            Visualization Type: {chart_type}
            Title: {title}
            Data Summary: {data_summary}
            
            Write a brief but impactful analysis (2 lines maximum) that:
            1. States the most significant trend/change with exact numbers, focusing on the primary metric.
            2. Provides one key investment implication or market insight relevant to crypto investors and analysts.
            
            Guidelines:
            - Be extremely concise—maximum 2 lines.
            - Lead with the most important metric or change, using exact numbers and percentages.
            - End with a clear, actionable investment implication or market insight.
            - Avoid generic phrases or unnecessary context.
            - Use a professional, analytical tone suitable for investment-grade analysis.
            
            Example good format:
            "Price declined 32.71% over 60 days, falling from $1.35 to $0.91 with volatility between $1.56 and $0.79. This downward trend suggests heightened selling pressure and potential near-term uncertainty."
            
            "Token distribution shows 45% concentration in early investors, with 6-month vesting starting Q3 2024. This indicates potential supply pressure during unlock periods, impacting price stability."
            """
            
            prompt = ChatPromptTemplate.from_template(template)
            chain = prompt | self.llm | StrOutputParser()
            
            description = chain.invoke({
                "chart_type": config.get("type", "").replace("_", " "),
                "title": result.get("title", vis_type.replace("_", " ").title()), 
                "data_summary": json.dumps(result.get("data_summary", {}))
            })
            
            self.logger.info(f"Generated description for {vis_type}")
            return description
            
        except Exception as e:
            self.logger.error(f"Error generating description for {vis_type}: {str(e)}")
            return f"Analysis of {vis_type.replace('_', ' ')}."
    
    # Keep these helper methods that might still be used by the visualizers
    def _prepare_table_data(self, data, fields, source_field_prefix="", default_values=None):
        """Prepare data for a table visualization."""
        # For backward compatibility if any code still calls this
        return self.table_visualizer._extract_table_data(None, fields, data)
    
    def _create_html_table(self, headers, data, title):
        """Create an HTML table representation."""
        html = "<table style='width:100%; border-collapse: collapse;'>\n"
        html += f"<caption style='font-weight: bold; margin-bottom: 10px;'>{title}</caption>\n"
        html += "<tr style='background-color: #4472C4; color: white;'>\n"
        
        for header in headers:
            html += f"<th style='padding: 8px; text-align: left; border: 1px solid #ddd;'>{header}</th>\n"
        
        html += "</tr>\n"
        
        for i, row in enumerate(data):
            bg_color = "#f2f2f2" if i % 2 == 0 else "white"
            html += f"<tr style='background-color: {bg_color};'>\n"
            
            for cell in row:
                html += f"<td style='padding: 8px; text-align: left; border: 1px solid #ddd;'>{cell}</td>\n"
                
            html += "</tr>\n"
            
        html += "</table>"
        return html
    
    def _create_table_image(self, headers, data_rows, title, output_path):
        """Create a table image using matplotlib."""
        try:
            # Get font size from style manager
            body_text_size = 10  # Match report body text size
            
            # Calculate figure size with increased row height
            row_height = 0.8  # Increased from 0.7 for better readability
            fig_height = len(data_rows) * row_height + 2.0  # Increased padding
            
            # Create figure and axis
            fig = plt.figure(figsize=(10, fig_height))
            ax = fig.add_subplot(111)
            ax.axis('tight')
            ax.axis('off')
            
            # Convert all values to strings and format numbers in bold
            string_data = []
            for row in data_rows:
                formatted_row = []
                for cell in row:
                    cell_str = str(cell)
                    # Make numbers bold (including those with $ and %)
                    if any(c.isdigit() for c in cell_str):
                        cell_str = f"$\\mathbf{{{cell_str}}}$"
                    formatted_row.append(cell_str)
                string_data.append(formatted_row)
            
            # Create the table
            table = ax.table(
                cellText=string_data,
                colLabels=headers,
                loc='center',
                cellLoc='left'  # Left-align text
            )
            
            # Adjust table style
            table.auto_set_font_size(False)
            table.set_fontsize(body_text_size)  # Use report body text size
            
            # Increase row heights and scale
            table.scale(1.2, 2.0)  # Increased vertical scale for better spacing
            
            # Style header row
            for i, key in enumerate(headers):
                header_cell = table[(0, i)]
                header_cell.set_facecolor('#4472C4')
                header_cell.set_text_props(color='white', weight='bold', size=body_text_size)
                header_cell.set_height(0.2)  # Increased header height
            
            # Style data rows with more padding
            row_colors = ['#f5f5f5', 'white']
            for i, row in enumerate(range(1, len(data_rows) + 1)):
                for j, col in enumerate(range(len(headers))):
                    cell = table[(row, col)]
                    cell.set_facecolor(row_colors[i % 2])
                    cell.set_text_props(size=body_text_size)
                    cell.set_height(0.15)  # Increased row height
                    # Add padding
                    if j == 0:
                        cell._text.set_x(0.05)  # Left padding for first column
                    else:
                        cell._text.set_x(0.95)  # Right padding for second column
                        cell.set_text_props(ha='right')  # Right-align values
            
            # Add title with slightly larger size
            plt.title(title, pad=20, fontsize=body_text_size + 2, weight='bold')
            
            # Adjust layout to prevent text cutoff
            plt.tight_layout()
            
            # Save the figure with high DPI
            plt.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.2)
            plt.close()
            
            return True
        except Exception as e:
            self.logger.error(f"Error creating table image: {str(e)}")
            plt.close()
            return False

# The visualization_agent function that's called from workflows
def visualization_agent(state, llm, logger, config=None) -> Dict:
    """
    Generate visualizations for the report based on the provided configuration.
    """
    try:
        logger.info("Running visualization agent")
        
        # Create visualization agent instance
        agent = VisualizationAgent(
            project_name=state.get("project_name", "Unknown Project") if isinstance(state, dict) else getattr(state, "project_name", "Unknown Project"),
            logger=logger,
            llm=llm
        )
        
        # Get report configuration
        report_config = state.get("report_config", {}) if isinstance(state, dict) else getattr(state, "report_config", {})
        
        if not isinstance(report_config, dict) or "visualization_types" not in report_config:
            logger.error("Invalid or missing report configuration")
            return state
            
        # Process each visualization type
        vis_types = report_config.get("visualization_types", {})
        logger.info(f"Found {len(vis_types)} visualization types in report config")
        
        # Get all data from state
        data = {}
        
        # First, try to get data from the state's data attribute
        if isinstance(state, dict):
            data = state.get("data", {})
        else:
            data = getattr(state, "data", {})
            
        # Log available data sources and their content
        logger.info("Available data sources:")
        for source, source_data in data.items():
            if isinstance(source_data, dict):
                logger.info(f"- {source}: {len(source_data)} fields")
                logger.debug(f"  Fields: {list(source_data.keys())}")
            else:
                logger.warning(f"- {source}: Invalid data format - {type(source_data)}")
        
        # Add structured_data to data sources if available
        structured_data = {}
        if isinstance(state, dict):
            structured_data = state.get("structured_data", {})
        else:
            structured_data = getattr(state, "structured_data", {})
            
        if structured_data:
            data["structured_data"] = structured_data
            logger.info(f"Added structured_data with {len(structured_data)} fields")
            logger.debug(f"Structured data fields: {list(structured_data.keys())}")
        
        # Add research_data to web_research source if available
        research_data = {}
        if isinstance(state, dict):
            research_data = state.get("research_data", {})
        else:
            research_data = getattr(state, "research_data", {})
            
        if research_data:
            data["web_research"] = research_data
            logger.info(f"Added research_data as web_research with {len(research_data)} fields")
            logger.debug(f"Research data fields: {list(research_data.keys())}")
        
        # Initialize visualizations dictionary if it doesn't exist
        if isinstance(state, dict):
            if "visualizations" not in state:
                state["visualizations"] = {}
        else:
            if not hasattr(state, "visualizations"):
                state.visualizations = {}
        
        # Track missing data fields
        missing_fields = set()
        
        for vis_id, vis_config in vis_types.items():
            if not isinstance(vis_config, dict):
                continue
                
            # Skip configuration options
            if vis_id in ["report_config", "fast_mode", "skip_expensive_descriptions", "limit_charts"]:
                continue
                
            # Get data source and required fields
            data_source = vis_config.get("data_source", "")
            required_fields = vis_config.get("data_fields", [])
            
            if not data_source:
                logger.warning(f"No data source specified for visualization {vis_id}")
                continue
                
            logger.info(f"Processing visualization {vis_id}")
            logger.info(f"- Data source: {data_source}")
            logger.info(f"- Required fields: {required_fields}")
            
            # Check if required data is available
            if data_source == "multi":
                # For multi-source, check each required field
                for field in required_fields:
                    field_found = False
                    for source in ["structured_data", "web_research", "coingecko", "coinmarketcap", "defillama"]:
                        if source in data and field in data[source]:
                            field_found = True
                            logger.info(f"Found field '{field}' in {source}")
                            break
                    if not field_found:
                        logger.warning(f"Missing required field '{field}' for {vis_id}")
                        missing_fields.add(field)
            else:
                # For single source, check if source exists and has required fields
                if data_source not in data:
                    logger.warning(f"Data source '{data_source}' not found for {vis_id}")
                    continue
                
                source_data = data[data_source]
                for field in required_fields:
                    if field not in source_data:
                        logger.warning(f"Missing field '{field}' in {data_source} for {vis_id}")
                        missing_fields.add(field)
            
            # Generate visualization
            try:
                result = agent.generate_visualization(
                    vis_type=vis_id,
                    data=data,
                    skip_expensive_descriptions=False,
                    report_config=report_config
                )
                
                if result and isinstance(result, dict):
                    if "error" in result:
                        logger.warning(f"Error generating visualization {vis_id}: {result['error']}")
                    elif "file_path" in result:
                        # Store visualization in state
                        if isinstance(state, dict):
                            state["visualizations"][vis_id] = result
                        else:
                            state.visualizations[vis_id] = result
                            
                        logger.info(f"Successfully generated visualization {vis_id}")
                        logger.info(f"- Output file: {result['file_path']}")
                        if "description" in result:
                            logger.info(f"- Description: {result['description'][:100]}...")
                    else:
                        logger.warning(f"Invalid result format for {vis_id}")
                else:
                    logger.warning(f"Invalid result for {vis_id}: {result}")
                    
            except Exception as e:
                logger.error(f"Error generating visualization {vis_id}: {str(e)}", exc_info=True)
        
        # Log summary of missing fields
        if missing_fields:
            logger.warning(f"Missing {len(missing_fields)} required fields: {sorted(missing_fields)}")
            # Store missing fields in state for reference
            if isinstance(state, dict):
                state["missing_data_fields"] = sorted(missing_fields)
            else:
                state.missing_data_fields = sorted(missing_fields)
        
        # Log summary of generated visualizations
        vis_count = len(state["visualizations"] if isinstance(state, dict) else state.visualizations)
        logger.info(f"Generated {vis_count} visualizations")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in visualization agent: {str(e)}", exc_info=True)
        return state