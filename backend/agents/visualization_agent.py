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
        os.makedirs(self.output_dir, exist_ok=True)
        
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
            
            # Generate description if chart was successfully created
            if "file_path" in result and self.llm:
                description = self._generate_description(vis_type, vis_config, data, result)
                result["description"] = description
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating {vis_type}: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def _generate_line_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a line chart."""
        # Extract data field from config
        data_field = config.get("data_field", "")
        if data_field not in data:
            return {"error": f"Data field '{data_field}' not found"}
        
        series_data = data[data_field]
        if not series_data:
            return {"error": f"No data available for {data_field}"}
        
        # Create plot
        plt.figure(figsize=(10, 6))
        
        # Handle different data formats
        if isinstance(series_data, list) and len(series_data) > 0:
            if isinstance(series_data[0], (int, float)):
                # Simple list of values
                plt.plot(series_data, marker='o', linestyle='-', alpha=0.7)
            elif isinstance(series_data[0], dict) and 'timestamp' in series_data[0] and 'value' in series_data[0]:
                # List of timestamp-value pairs
                timestamps = [item['timestamp'] for item in series_data]
                values = [item['value'] for item in series_data]
                plt.plot(timestamps, values, marker='o', linestyle='-', alpha=0.7)
            elif isinstance(series_data[0], (list, tuple)) and len(series_data[0]) == 2:
                # List of [timestamp, value] pairs
                timestamps = [item[0] for item in series_data]
                values = [item[1] for item in series_data]
                plt.plot(timestamps, values, marker='o', linestyle='-', alpha=0.7)
        
        # Set title and labels
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title)
        plt.xlabel("Time")
        plt.ylabel("Value")
        plt.grid(True, alpha=0.3)
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
                "start_value": series_data[0] if isinstance(series_data[0], (int, float)) else series_data[0]["value"] if isinstance(series_data[0], dict) else series_data[0][1],
                "end_value": series_data[-1] if isinstance(series_data[-1], (int, float)) else series_data[-1]["value"] if isinstance(series_data[-1], dict) else series_data[-1][1],
                "min_value": min(series_data) if isinstance(series_data[0], (int, float)) else min(item["value"] for item in series_data) if isinstance(series_data[0], dict) else min(item[1] for item in series_data),
                "max_value": max(series_data) if isinstance(series_data[0], (int, float)) else max(item["value"] for item in series_data) if isinstance(series_data[0], dict) else max(item[1] for item in series_data),
                "data_points": len(series_data)
            }
        }
    
    def _generate_bar_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a bar chart."""
        # Extract data fields from config
        data_fields = config.get("data_fields", [])
        if not data_fields:
            return {"error": "No data fields specified"}
        
        # Check if we have data for the specified fields
        valid_fields = [field for field in data_fields if field in data]
        if not valid_fields:
            return {"error": f"No data available for fields: {data_fields}"}
        
        # Get categories and values
        categories = []
        values = []
        
        # Handle different data formats
        if "categories" in data and any(field in data for field in data_fields):
            # Format 1: data contains categories and separate arrays for each data field
            categories = data.get("categories", [])
            for field in valid_fields:
                if field in data:
                    values.append((field, data[field]))
        elif "competitors" in data:
            # Format 2: data contains a list of competitors with properties
            categories = [comp.get("name", f"Competitor {i}") for i, comp in enumerate(data["competitors"])]
            for field in valid_fields:
                field_values = [comp.get(field, 0) for comp in data["competitors"]]
                values.append((field, field_values))
        
        if not categories or not values:
            return {"error": "Could not extract valid data for bar chart"}
        
        # Create plot
        plt.figure(figsize=(10, 6))
        
        # Plot each data series
        width = 0.8 / len(values)
        for i, (field_name, field_values) in enumerate(values):
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
    
    def _generate_pie_chart(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a pie chart."""
        # Extract data field from config
        data_field = config.get("data_field", "")
        if data_field not in data:
            return {"error": f"Data field '{data_field}' not found"}
        
        distribution_data = data[data_field]
        if not distribution_data:
            return {"error": f"No data available for {data_field}"}
        
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
            return {"error": "Could not extract valid data for pie chart"}
        
        # Create plot
        plt.figure(figsize=(10, 8))
        plt.pie(sizes, labels=None, autopct='%1.1f%%', startangle=90, shadow=False)
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
        
        # Add legend with percentages
        total = sum(sizes)
        legend_labels = [f"{label}: {size/total*100:.1f}%" for label, size in zip(labels, sizes)]
        plt.legend(legend_labels, loc="best")
        
        # Set title
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title)
        
        # Save chart
        filename = f"{vis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path = os.path.join(self.output_dir, filename)
        plt.savefig(file_path, dpi=300)
        plt.close()
        
        return {
            "file_path": file_path,
            "title": title,
            "data_summary": {
                "labels": labels,
                "values": sizes,
                "total": total
            }
        }
    
    def _generate_table(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a table (as an image and markdown)."""
        # Extract data fields from config
        data_fields = config.get("data_fields", [])
        if not data_fields:
            return {"error": "No data fields specified"}
        
        # Extract and format table data
        table_data = {}
        
        # Handle different data formats
        if all(field in data for field in data_fields):
            # Format 1: data contains each field directly
            table_data = {field: data[field] for field in data_fields if field in data}
        elif "items" in data:
            # Format 2: data contains a list of items with properties
            table_data = {}
            for field in data_fields:
                if any(field in item for item in data["items"]):
                    table_data[field] = [item.get(field, "") for item in data["items"]]
        
        if not table_data:
            return {"error": "Could not extract valid data for table"}
        
        # Create DataFrame
        df = pd.DataFrame(table_data)
        
        # Format column headers
        df.columns = [col.replace("_", " ").title() for col in df.columns]
        
        # Generate markdown table
        markdown_table = df.to_markdown(index=False)
        
        # Create a visual table (as an image)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('tight')
        ax.axis('off')
        table = ax.table(
            cellText=df.values,
            colLabels=df.columns,
            loc='center',
            cellLoc='center'
        )
        
        # Adjust table style
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.5)
        
        # Set title
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title, y=0.9)
        
        # Save table as image
        filename = f"{vis_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path = os.path.join(self.output_dir, filename)
        plt.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return {
            "file_path": file_path,
            "markdown_table": markdown_table,
            "title": title,
            "data_summary": {
                "columns": list(df.columns),
                "rows": len(df)
            }
        }
    
    def _generate_timeline(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a timeline chart."""
        # Extract data fields from config
        data_fields = config.get("data_fields", [])
        if not data_fields or len(data_fields) < 2:
            return {"error": "Insufficient data fields for timeline"}
        
        date_field = data_fields[0]
        desc_field = data_fields[1]
        status_field = data_fields[2] if len(data_fields) > 2 else None
        
        # Extract timeline items
        timeline_items = []
        
        if "roadmap" in data:
            timeline_items = data["roadmap"]
        elif "milestones" in data:
            timeline_items = data["milestones"]
        
        if not timeline_items:
            return {"error": "No timeline data found"}
        
        # Sort items by date
        if all(date_field in item for item in timeline_items):
            timeline_items.sort(key=lambda x: x[date_field])
        
        # Create a timeline visualization
        plt.figure(figsize=(12, 8))
        
        # Extract dates and descriptions
        dates = [item.get(date_field, "") for item in timeline_items]
        descriptions = [item.get(desc_field, "") for item in timeline_items]
        
        # Plot the timeline
        y_positions = range(len(dates))
        plt.plot([0] * len(dates), y_positions, 'o', markersize=12, color='blue')
        
        # Add milestone descriptions
        for i, (date, desc) in enumerate(zip(dates, descriptions)):
            plt.text(0.1, i, f"{date}: {desc}", fontsize=12, verticalalignment='center')
        
        # Add status indicators if available
        if status_field and all(status_field in item for item in timeline_items):
            statuses = [item.get(status_field, "") for item in timeline_items]
            for i, status in enumerate(statuses):
                if status.lower() in ("completed", "done", "finished"):
                    plt.plot(0, i, 'o', markersize=14, color='green', alpha=0.5)
                elif status.lower() in ("in progress", "ongoing"):
                    plt.plot(0, i, 'o', markersize=14, color='orange', alpha=0.5)
                elif status.lower() in ("planned", "future", "upcoming"):
                    plt.plot(0, i, 'o', markersize=14, color='gray', alpha=0.5)
        
        # Set title and labels
        title = config.get("title", vis_type.replace("_", " ").title())
        plt.title(title)
        plt.yticks([])
        plt.xticks([])
        plt.grid(False)
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
                "milestones": len(timeline_items),
                "earliest": dates[0] if dates else "",
                "latest": dates[-1] if dates else ""
            }
        }
    
    def _generate_description(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Generate a description for the visualization using LLM."""
        if not self.llm:
            return config.get("title", vis_type.replace("_", " ").title())
        
        try:
            # Get the description template
            template = config.get("description_template", "")
            if not template:
                return config.get("title", vis_type.replace("_", " ").title())
            
            # Prepare context for the LLM
            context = {
                "project_name": self.project_name,
                "visualization_type": vis_type,
                "title": config.get("title", vis_type.replace("_", " ").title()),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_summary": result.get("data_summary", {})
            }
            
            # Generate description based on data and visualization type
            if vis_type == "price_history_chart":
                context["trend_description"] = self._analyze_price_trend(result.get("data_summary", {}))
            elif vis_type == "volume_chart":
                context["volume_description"] = self._analyze_volume_trend(result.get("data_summary", {}))
            elif vis_type == "tvl_chart":
                context["tvl_description"] = self._analyze_tvl_trend(result.get("data_summary", {}))
            elif vis_type == "token_distribution_chart":
                context["distribution_description"] = self._analyze_distribution(result.get("data_summary", {}))
            elif "comparison" in vis_type:
                context["metrics_description"] = self._analyze_comparison(result.get("data_summary", {}))
            
            # Apply the template with available context
            description = template
            for key, value in context.items():
                placeholder = "{" + key + "}"
                if placeholder in description and isinstance(value, str):
                    description = description.replace(placeholder, value)
            
            # For any remaining placeholders, use LLM to generate content
            if "{" in description and "}" in description:
                prompt = f"""
                Based on this data about {self.project_name}:
                {json.dumps(result.get('data_summary', {}), indent=2)}
                
                Complete this description by filling in any remaining placeholders:
                "{description}"
                
                Return only the completed description.
                """
                
                llm_response = self.llm.invoke(prompt).content
                description = llm_response.strip()
            
            return description
            
        except Exception as e:
            self.logger.error(f"Error generating description: {str(e)}")
            return config.get("title", vis_type.replace("_", " ").title())
    
    def _analyze_price_trend(self, data_summary: Dict[str, Any]) -> str:
        """Analyze price trend data and return a description."""
        if not data_summary:
            return "the price trend over time"
        
        start_value = data_summary.get("start_value", 0)
        end_value = data_summary.get("end_value", 0)
        min_value = data_summary.get("min_value", 0)
        max_value = data_summary.get("max_value", 0)
        
        if end_value > start_value:
            change_pct = ((end_value - start_value) / start_value * 100) if start_value else 0
            return f"an upward trend with a {change_pct:.2f}% increase over the period"
        elif end_value < start_value:
            change_pct = ((start_value - end_value) / start_value * 100) if start_value else 0
            return f"a downward trend with a {change_pct:.2f}% decrease over the period"
        else:
            return "a relatively stable price over the period"
    
    def _analyze_volume_trend(self, data_summary: Dict[str, Any]) -> str:
        """Analyze volume trend data and return a description."""
        if not data_summary:
            return "the trading volume trend over time"
        
        # Similar logic to price trend analysis
        start_value = data_summary.get("start_value", 0)
        end_value = data_summary.get("end_value", 0)
        
        if end_value > start_value:
            change_pct = ((end_value - start_value) / start_value * 100) if start_value else 0
            return f"an increase in trading activity with volume up {change_pct:.2f}% over the period"
        elif end_value < start_value:
            change_pct = ((start_value - end_value) / start_value * 100) if start_value else 0
            return f"a decrease in trading activity with volume down {change_pct:.2f}% over the period"
        else:
            return "relatively consistent trading activity over the period"
    
    def _analyze_tvl_trend(self, data_summary: Dict[str, Any]) -> str:
        """Analyze TVL trend data and return a description."""
        if not data_summary:
            return "the Total Value Locked (TVL) trend over time"
        
        # Similar logic to price trend analysis
        start_value = data_summary.get("start_value", 0)
        end_value = data_summary.get("end_value", 0)
        
        if end_value > start_value:
            change_pct = ((end_value - start_value) / start_value * 100) if start_value else 0
            return f"an increase in capital locked in the protocol, up {change_pct:.2f}% over the period"
        elif end_value < start_value:
            change_pct = ((start_value - end_value) / start_value * 100) if start_value else 0
            return f"a decrease in capital locked in the protocol, down {change_pct:.2f}% over the period"
        else:
            return "relatively stable capital locked in the protocol over the period"
    
    def _analyze_distribution(self, data_summary: Dict[str, Any]) -> str:
        """Analyze token distribution data and return a description."""
        if not data_summary:
            return "the distribution of tokens across different categories"
        
        labels = data_summary.get("labels", [])
        values = data_summary.get("values", [])
        total = data_summary.get("total", 0)
        
        if not labels or not values or not total:
            return "the token allocation across different stakeholders"
        
        # Find the largest allocation
        max_idx = values.index(max(values))
        max_pct = (values[max_idx] / total * 100) if total else 0
        
        return f"that the largest allocation is to '{labels[max_idx]}' at {max_pct:.1f}%, with the remaining tokens distributed across other categories"
    
    def _analyze_comparison(self, data_summary: Dict[str, Any]) -> str:
        """Analyze comparison data and return a description."""
        if not data_summary:
            return "market metrics"
        
        categories = data_summary.get("categories", [])
        values = data_summary.get("values", [])
        
        if not categories or not values:
            return "key performance indicators"
        
        metric_names = [name for name, _ in values]
        return ", ".join(metric_names).replace("_", " ")

def visualization_agent(state, llm, logger, config=None) -> Dict:
    """
    Visualization agent function for integration with the research workflow.
    
    Args:
        state: Current state of the research
        llm: Language model for generating descriptions
        logger: Logger instance
        config: Optional configuration
    
    Returns:
        Updated state with visualizations
    """
    project_name = state.project_name
    logger.info(f"Visualization agent processing for {project_name}")
    
    # Initialize the visualization agent
    agent = VisualizationAgent(project_name, logger, llm)
    
    # Use report config from state if available, otherwise load from file
    try:
        report_config = {}
        
        # First check if state already has report_config
        if hasattr(state, 'report_config') and state.report_config:
            report_config = state.report_config
            logger.info("Using report configuration from state")
        else:
            # Fall back to loading from file
            try:
                with open("backend/config/report_config.json", "r") as f:
                    report_config = json.load(f)
                logger.info("Loaded report configuration from file")
            except Exception as file_error:
                logger.warning(f"Could not load report configuration from file: {str(file_error)}")
        
        # Get visualizations for each section
        visualizations = []
        for section in report_config.get("sections", []):
            section_visualizations = section.get("visualizations", [])
            visualizations.extend(section_visualizations)
        
        # Generate each visualization
        generated_visualizations = {}
        for vis_type in visualizations:
            # Check if we have relevant data for this visualization
            vis_config = agent.visualization_config.get(vis_type, {})
            data_source = vis_config.get("data_source", "")
            
            # Determine if we have the data for this visualization
            if data_source == "coingecko" and hasattr(state, "coingecko_data"):
                data = state.coingecko_data
                result = agent.generate_visualization(vis_type, data)
                generated_visualizations[vis_type] = result
            
            elif data_source == "coinmarketcap" and hasattr(state, "coinmarketcap_data"):
                data = state.coinmarketcap_data
                result = agent.generate_visualization(vis_type, data)
                generated_visualizations[vis_type] = result
            
            elif data_source == "defillama" and hasattr(state, "defillama_data"):
                data = state.defillama_data
                result = agent.generate_visualization(vis_type, data)
                generated_visualizations[vis_type] = result
            
            elif data_source == "web_research" and hasattr(state, "research_data"):
                data = state.research_data
                result = agent.generate_visualization(vis_type, data)
                generated_visualizations[vis_type] = result
            
            elif data_source == "multi":
                # Combine data from multiple sources
                combined_data = {}
                if hasattr(state, "coingecko_data"):
                    combined_data.update(state.coingecko_data)
                if hasattr(state, "coinmarketcap_data"):
                    combined_data.update(state.coinmarketcap_data)
                if hasattr(state, "defillama_data"):
                    combined_data.update(state.defillama_data)
                
                result = agent.generate_visualization(vis_type, combined_data)
                generated_visualizations[vis_type] = result
        
        # Add visualizations to state
        state.visualizations = generated_visualizations
        state.update_progress(f"Generated {len(generated_visualizations)} visualizations")
            
    except Exception as e:
        logger.error(f"Error in visualization agent: {str(e)}", exc_info=True)
        state.update_progress(f"Error generating visualizations: {str(e)}")
    
    return state 