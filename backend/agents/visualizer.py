import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from backend.visualizations.line_chart import LineChartVisualizer
from backend.visualizations.bar_chart import BarChartVisualizer
from backend.visualizations.pie_chart import PieChartVisualizer
from backend.visualizations.table import TableVisualizer
from backend.visualizations.timeline import TimelineVisualizer
from backend.visualizations.base import BaseVisualizer
from backend.utils.logging_utils import log_safe

from backend.state import ResearchState
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

async def visualizer(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    # Get project name
    project_name = state.get("project_name", "Unknown Project")
    
    # Handle progress update
    if hasattr(state, 'update_progress'):
        state.update_progress(f"Creating visualizations for {project_name}...")
    else:
        state["progress"] = f"Creating visualizations for {project_name}..."
    
    # Diagnostic information
    logger.info("----------- VISUALIZATION DIAGNOSTIC INFO -----------")
    logger.info(f"Current working directory: {os.getcwd()}")
    try:
        docs_dir = os.path.join(os.getcwd(), "docs")
        project_dir = os.path.join(docs_dir, project_name.lower().replace(" ", "_"))
        
        # Check docs directory
        if os.path.exists(docs_dir):
            logger.info(f"Docs directory exists: {docs_dir}")
            logger.info(f"Docs directory contents: {os.listdir(docs_dir)}")
        else:
            logger.warning(f"Docs directory does not exist: {docs_dir}")
            os.makedirs(docs_dir, exist_ok=True)
            logger.info(f"Created docs directory: {docs_dir}")
        
        # Check project directory
        if os.path.exists(project_dir):
            logger.info(f"Project directory exists: {project_dir}")
            logger.info(f"Project directory contents: {os.listdir(project_dir)}")
        else:
            logger.warning(f"Project directory does not exist: {project_dir}")
    except Exception as e:
        logger.error(f"Error during directory diagnostics: {str(e)}")
    logger.info("-----------------------------------------------------")
    
    # Get data for visualization
    hf_fallback = state.get("hf_fallback")
    
    # Get data sources from state
    if "data" in state and isinstance(state["data"], dict):
        web_research_data = state["data"].get("web_research", {})
    else:
        web_research_data = {}
        
    # Create visualization agent
    agent = Visualizer(
        logger=logger, 
        hf_fallback=hf_fallback, 
        web_data=web_research_data, 
        project_name=project_name
    )
    agent.llm = llm
    
    try:
        # Create a temporary ResearchState for backward compatibility
        temp_state = ResearchState(project_name=project_name)
        for key, value in state.items():
            if hasattr(temp_state, key):
                setattr(temp_state, key, value)
        
        # Run the visualization agent
        updated_state = agent.run(temp_state)
        
        # Copy visualizations back to the dictionary state
        if hasattr(updated_state, "visualizations"):
            state["visualizations"] = updated_state.visualizations
            
            # Log visualization results for debugging
            vis_count = len(state["visualizations"])
            logger.info(f"Generated {vis_count} visualizations")
            for viz_type, viz_data in state["visualizations"].items():
                path = viz_data.get("path", "")
                if path and os.path.exists(path):
                    file_size = os.path.getsize(path) / 1024
                    logger.info(f"  - {viz_type}: {path} ({file_size:.1f} KB)")
                else:
                    logger.warning(f"  - {viz_type}: File not found or invalid path")
        else:
            logger.error("No visualizations returned from agent")
            
        # Copy visualization errors if any
        if hasattr(updated_state, "visualization_errors"):
            state["visualization_errors"] = updated_state.visualization_errors
            logger.warning(f"Visualization errors: {updated_state.visualization_errors}")
        
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Visualizations created for {project_name}")
        else:
            state["progress"] = f"Visualizations created for {project_name}"
            
    except Exception as e:
        logger.error(f"Error in visualizer: {str(e)}", exc_info=True)
        
        # Initialize visualizations dict if needed
        state["visualizations"] = state.get("visualizations", {})
        state["visualization_errors"] = {"global_error": str(e)}
        
        # Update progress with error
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Error creating visualizations: {str(e)}")
        else:
            state["progress"] = f"Error creating visualizations: {str(e)}"
            
    return state

class Visualizer:
    def __init__(self, hf_fallback=None, web_data=None, logger=None, project_name=None):
        self.hf_fallback = hf_fallback
        self.web_data = web_data or {}
        self.logger = logger or logging.getLogger(__name__)
        self.project_name = project_name
        self.visualizer_map = {
            "line_chart": LineChartVisualizer,
            "bar_chart": BarChartVisualizer,
            "pie_chart": PieChartVisualizer,
            "table": TableVisualizer,
            "timeline": TimelineVisualizer,
        }

    def _get_multi_source_data(self, data, required_fields):
        result = {}

        if "coinmarketcap" in data and isinstance(data["coinmarketcap"], dict):
            if "price_history" in data["coinmarketcap"]:
                result["price_history"] = data["coinmarketcap"]["price_history"]
            if "volume_history" in data["coinmarketcap"]:
                result["volume_history"] = data["coinmarketcap"]["volume_history"]

        aliases = {
            "price_history": ["price_history", "prices", "price_data"],
            "volume_history": ["volume_history", "volumes", "total_volumes"],
            "tvl_history": ["tvl_history", "tvl_data"],
            "competitors": ["competitors", "competitor_data"],
            "token_allocation": ["token_allocation", "token_distribution", "distribution"],
            "exchange_count": ["exchange_count", "exchange_number"],
            "active_addresses": ["active_addresses", "user_addresses"],
        }

        sources = ["structured_data", "web_research", "coingecko", "coinmarketcap", "defillama", None]

        for field in required_fields:
            alias_group = list(dict.fromkeys(aliases.get(field, [field])))
            for alias in alias_group:
                for source in sources:
                    if source is None:
                        if alias in data:
                            result[field] = data[alias]
                            break
                    elif source in data and isinstance(data[source], dict) and alias in data[source]:
                        result[field] = data[source][alias]
                        break
                if field in result:
                    break
            if field not in result:
                result[field] = None

        self.logger.debug(f"Resolved data fields: {list(result.keys())}")
        for field, value in result.items():
            if value is not None:
                self.logger.debug(f"Field '{field}' value: {log_safe(value, max_length=100)}")
        return result

    def _generate_description(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any], result: Dict[str, Any]) -> str:
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            import json

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

    def run(self, state):
        visuals_config = state.report_config.get("visualization_types", {})
        sections = state.report_config.get("sections", [])
        generated_visuals = {}
        already_generated = set()
        visualization_errors = {}

        # First, ensure output directory exists
        try:
            project_dir = os.path.join("docs", state.project_name.lower().replace(" ", "_"))
            os.makedirs(project_dir, exist_ok=True)
            self.logger.info(f"Verified visualization output directory: {project_dir}")
            
            # Create a test file to verify write permissions
            test_file = os.path.join(project_dir, ".test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            self.logger.info("Successfully verified file system write access")
        except Exception as e:
            self.logger.error(f"Failed to create or verify output directory: {str(e)}")
            state.visualizations = {"error": f"Visualization directory error: {str(e)}"}
            return state

        for section in sections:
            visual_types = section.get("visualizations", [])
            for viz_type in visual_types:
                if viz_type in already_generated:
                    continue
                already_generated.add(viz_type)

                viz_config = visuals_config.get(viz_type)
                if not viz_config:
                    self.logger.warning(f"No config found for visualization type: {viz_type}")
                    visualization_errors[viz_type] = "Missing configuration"
                    continue

                chart_type = viz_config.get("type")
                VisualizerCls = self.visualizer_map.get(chart_type)
                if not VisualizerCls:
                    self.logger.error(f"No visualizer found for type: {chart_type}")
                    visualization_errors[viz_type] = f"Unknown chart type: {chart_type}"
                    continue

                data_source = viz_config.get("data_source", "multi")
                required_fields = viz_config.get("data_fields", [])

                if data_source == "multi":
                    data = self._get_multi_source_data(state.data, required_fields)
                else:
                    data = state.data.get(data_source, {})

                missing_fields = [f for f in required_fields if f not in data or data[f] is None]

                if missing_fields:
                    for field in missing_fields:
                        if field in self.web_data:
                            data[field] = self.web_data[field]
                    missing_fields = [f for f in required_fields if f not in data or data[f] is None]

                if missing_fields and self.hf_fallback:
                    try:
                        filled = self.hf_fallback.infer_missing_data(data, missing_fields)
                        data.update(filled)
                        missing_fields = [f for f in required_fields if f not in data or data[f] is None]
                    except Exception as e:
                        self.logger.error(f"Hugging Face fallback failed for {viz_type}: {e}")

                if missing_fields:
                    missing_str = ", ".join(missing_fields)
                    self.logger.warning(f"Skipping {viz_type}, missing fields: {missing_str}")
                    visualization_errors[viz_type] = f"Missing required data: {missing_str}"
                    continue

                try:
                    visualizer = VisualizerCls(project_name=self.project_name or state.project_name, logger=self.logger)
                    result = visualizer.create(viz_type, viz_config, data)
                    if not result or "file_path" not in result:
                        raise ValueError(f"No file created for {viz_type}")
                        
                    # Verify the file exists and is valid
                    file_path = result["file_path"]
                    if not os.path.exists(file_path):
                        raise FileNotFoundError(f"Generated file not found: {file_path}")
                    
                    if os.path.getsize(file_path) == 0:
                        raise ValueError(f"Generated file is empty: {file_path}")
                        
                    self.logger.info(f"Successfully generated visualization: {viz_type} ({os.path.getsize(file_path)/1024:.1f} KB)")

                    if hasattr(self, "llm"):
                        result["description"] = self._generate_description(viz_type, viz_config, data, result)

                    # Add relative path for frontend use
                    if os.path.isabs(file_path):
                        docs_dir = os.path.join(os.getcwd(), "docs")
                        if file_path.startswith(docs_dir):
                            result["relative_path"] = os.path.relpath(file_path, os.getcwd())
                    
                    generated_visuals[viz_type] = {
                        "path": file_path,
                        "relative_path": result.get("relative_path", file_path),
                        "meta": result,
                        "timestamp": datetime.utcnow().isoformat()
                    }

                except Exception as e:
                    self.logger.error(f"Failed to generate {viz_type}: {str(e)}", exc_info=True)
                    visualization_errors[viz_type] = f"Generation error: {str(e)}"

        if visualization_errors:
            self.logger.warning(f"Encountered {len(visualization_errors)} visualization errors")
            state.visualization_errors = visualization_errors
            
        state.visualizations = generated_visuals
        return state 