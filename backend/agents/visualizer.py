import os
import logging
import json
import time
import asyncio
import math
from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
from datetime import datetime
import sys

try:
    from backend.visualizations.api import VisualizationAPI
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import VisualizationAPI: {str(e)}")
    raise

try:
    from backend.utils.cache_utils import CacheManager
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import CacheManager: {str(e)}")
    raise

try:
    from backend.utils.style_utils import StyleManager
except ImportError as e:
    logging.getLogger(__name__).error(f"Failed to import StyleManager: {str(e)}")
    raise

# Configure logger to flush immediately
logger = logging.getLogger(__name__)
for handler in logger.handlers:
    handler.flush = sys.stdout.flush
logger.info("Visualizer logger configured with immediate flush")

class Visualizer:
    """
    Visualizer that generates visualizations using the Plotly-based visualization system.
    """
    
    def __init__(self, project_name: str, logger: Optional[logging.Logger] = None, llm=None, config=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Visualizer constructor started")
        if isinstance(project_name, dict) and 'project_name' in project_name:
            project_name = project_name['project_name']
            
        self.project_name = project_name
        self.output_dir = os.path.join("docs", project_name.lower().replace(" ", "_"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.cache_dir = os.path.join(self.output_dir, "cache")
        self.visualizations = {}
        self.visualization_list = []
        self.errors = {}
        self.data_sources_used = {}
        self.theme = 'light'
        self.pdf_optimized = True
        self.config = config or {}
        self.report_config = {}
        
        self.cache_manager = CacheManager(project_name=project_name, logger=self.logger)
        self.style_manager = StyleManager(logger=self.logger)
        self.viz_api = VisualizationAPI(
            project_name=project_name,
            cache_manager=self.cache_manager,
            style_manager=self.style_manager,
            theme=self.theme
        )
        self.logger.info(f"Initialized Visualizer for project: {project_name}")
        self.logger.info("Visualizer constructor completed")
    
    def _safe_get_dict(self, data: Any, key: str = None, default: Any = None) -> Dict[str, Any]:
        if data is None:
            return {} if default is None else default
        if isinstance(data, dict):
            if key is not None:
                return data.get(key, default if default is None else {})
            return data
        if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
            try:
                result = data.to_dict()
                if isinstance(result, dict):
                    if key is not None:
                        return result.get(key, default if default is None else {})
                    return result
            except Exception as e:
                self.logger.warning(f"Error converting object to dict via to_dict(): {str(e)}")
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    if key is not None:
                        return parsed.get(key, default if default is None else {})
                    return parsed
            except Exception as e:
                self.logger.warning(f"Error parsing JSON string: {str(e)}")
            return {"content": data, "error": "Data was string, not dict"}
        if hasattr(data, "__dict__"):
            try:
                data_dict = data.__dict__
                if key is not None:
                    return data_dict.get(key, default if default is None else {})
                return data_dict
            except Exception as e:
                self.logger.warning(f"Error accessing __dict__: {str(e)}")
        self.logger.warning(f"Unexpected data type: {type(data).__name__}, cannot convert to dict")
        return {} if default is None else default
    
    def _get_data_from_state(self, state: Dict[str, Any], data_source: str, data_field: str) -> Dict[str, Any]:
        result = {}
        if state is None:
            self.logger.warning("State is None in _get_data_from_state")
            return result
        try:
            state_dict = self._safe_get_dict(state)
            if "data" in state_dict:
                state_data = self._safe_get_dict(state_dict["data"])
                if data_source in state_data:
                    source_data = self._safe_get_dict(state_data[data_source])
                    if data_field in source_data:
                        self.logger.info(f"Found data in state.data[{data_source}][{data_field}]")
                        result[data_source] = source_data
                        return result
                    self.logger.info(f"Returning all data for state.data[{data_source}]")
                    result[data_source] = source_data
                    return result
            if "visualization_data" in state_dict:
                viz_data = self._safe_get_dict(state_dict["visualization_data"])
                if data_source in viz_data:
                    source_data = self._safe_get_dict(viz_data[data_source])
                    if data_field in source_data:
                        self.logger.info(f"Found data in state.visualization_data[{data_source}][{data_field}]")
                        result[data_source] = source_data
                        return result
                    self.logger.info(f"Returning all data for state.visualization_data[{data_source}]")
                    result[data_source] = source_data
                    return result
            if hasattr(state, "data"):
                state_data = self._safe_get_dict(state.data)
                if data_source in state_data:
                    source_data = self._safe_get_dict(state_data[data_source])
                    if data_field in source_data:
                        self.logger.info(f"Found data in state.data.{data_source}.{data_field}")
                        result[data_source] = source_data
                        return result
                    self.logger.info(f"Returning all data for state.data.{data_source}")
                    result[data_source] = source_data
                    return result
            if hasattr(state, "visualization_data"):
                viz_data = self._safe_get_dict(state.visualization_data)
                if data_source in viz_data:
                    source_data = self._safe_get_dict(viz_data[data_source])
                    if data_field in source_data:
                        self.logger.info(f"Found data in state.visualization_data.{data_source}.{data_field}")
                        result[data_source] = source_data
                        return result
                    self.logger.info(f"Returning all data for state.visualization_data.{data_source}")
                    result[data_source] = source_data
                    return result
        except Exception as e:
            self.logger.error(f"Error accessing state data for {data_source}/{data_field}: {str(e)}")
        try:
            state_dict = self._safe_get_dict(state)
            if "errors" in state_dict:
                errors = self._safe_get_dict(state_dict["errors"])
                for error_key, error_value in errors.items():
                    if data_source in error_key and (data_field in error_key or not data_field):
                        self.logger.warning(f"Found error for {data_source}/{data_field} in state.errors: {error_value}")
            if "problem_sections" in state_dict:
                problems = self._safe_get_dict(state_dict["problem_sections"])
                for problem_key, problem_value in problems.items():
                    if data_source in problem_key and (data_field in problem_key or not data_field):
                        self.logger.warning(f"Found problem for {data_source}/{data_field} in state.problem_sections: {problem_value}")
        except Exception as e:
            self.logger.error(f"Error checking for errors/problems: {str(e)}")
        self.logger.info(f"No data found in state for {data_source}/{data_field}")
        return result

    def _load_data_from_cache(self, data_source: str, data_field: str) -> Dict[str, Any]:
        if data_source == "multi":
            combined_data = {}
            sources = ["coinmarketcap", "defillama", "tokenomics", "coingecko"]
            for source in sources:
                source_data = self._load_data_from_cache(source, data_field)
                if source_data and source in source_data:
                    combined_data[source] = source_data[source]
            return combined_data if combined_data else {"data_unavailable": True, "message": "No data available in cache for multi-source"}
        
        cache_keys = [
            f"{data_source}_data_{self.project_name.lower()}",
            f"{data_source}_{data_field}_{self.project_name.lower()}",
            f"{data_source}_{data_field}",
            f"data_{data_field}_{self.project_name.lower()}"
        ]
        
        for cache_key in cache_keys:
            try:
                cache_data = self.cache_manager.load(data_source, cache_key, self.project_name.lower())
                if cache_data:
                    self.logger.info(f"Loaded data from cache: {data_source}/{cache_key}")
                    return {data_source: cache_data}
            except Exception as e:
                self.logger.debug(f"Error loading {data_source}/{cache_key} from cache: {str(e)}")
        
        self.logger.info(f"No cache found for {data_source}/{data_field}")
        return {"data_unavailable": True, "message": f"No data available in cache for {data_source}/{data_field}"}
    
    def _load_data_from_huggingface(self, data_source: str, data_field: str) -> Dict[str, Any]:
        self.logger.warning(f"HuggingFace fallback is disabled for {data_source}/{data_field}")
        return {"data_unavailable": True, "source": "huggingface", "message": "HuggingFace fallback is disabled to maintain data integrity"}

    def _add_error(self, viz_id: str, error: str):
        self.errors[viz_id] = error
        self.logger.error(f"Error creating visualization {viz_id}: {error}")
    
    def _safe_handle_response(self, response: Any, viz_id: str) -> Tuple[bool, str, str]:
        if isinstance(response, tuple) and len(response) == 3:
            success, path, message = response
            if isinstance(success, bool) and isinstance(path, str) and isinstance(message, str):
                return success, path, message
            self.logger.warning(f"Unexpected response types for {viz_id}: {type(success)}, {type(path)}, {type(message)}")
            try:
                return bool(success), str(path), str(message)
            except Exception as e:
                self.logger.error(f"Error converting response types: {str(e)}")
        self.logger.error(f"Unexpected response format for {viz_id}: {type(response)}")
        if isinstance(response, dict):
            success = response.get("success", False)
            path = response.get("path", "")
            message = response.get("message", "Invalid response format")
            return bool(success), str(path), str(message)
        return False, "", f"Invalid response: {str(response)[:100]}"

    def _get_data_for_visualization(self, viz_id: str, viz_config: Dict[str, Any], state: Dict[str, Any], section_title: str = "Unknown") -> Dict[str, Any]:
        data_source = viz_config.get("data_source", "")
        data_field = viz_config.get("data_field", "")
        
        # First check if we have standardized data for this visualization
        normalized_section = section_title.lower().replace(" ", "_")
        
        # Try to get standardized data from state.visualization_data
        if state:
            if isinstance(state, dict):
                if "visualization_data" in state and normalized_section in state["visualization_data"]:
                    section_viz_data = state["visualization_data"][normalized_section]
                    if viz_id in section_viz_data:
                        self.logger.info(f"Found standardized data for visualization {viz_id} in section {section_title}")
                        self.data_sources_used[f"{section_title}_{viz_id}"] = "standardized"
                        return section_viz_data[viz_id]
            elif hasattr(state, "visualization_data"):
                viz_data = state.visualization_data
                if hasattr(viz_data, normalized_section):
                    section_viz_data = getattr(viz_data, normalized_section)
                    if isinstance(section_viz_data, dict) and viz_id in section_viz_data:
                        self.logger.info(f"Found standardized data for visualization {viz_id} in section {section_title}")
                        self.data_sources_used[f"{section_title}_{viz_id}"] = "standardized"
                        return section_viz_data[viz_id]
        
        # If no standardized data found, fall back to original data extraction logic
        if not data_source:
            self.logger.error(f"No data_source specified for visualization {viz_id}")
            return {"data_unavailable": True, "message": "No data source specified"}
        data = {}
        data_source_used = "none"
        if state:
            if isinstance(state, dict):
                state_data_path = ["data", data_source]
                current_node = state
                for path_segment in state_data_path:
                    if path_segment in current_node and current_node[path_segment]:
                        current_node = current_node[path_segment]
                    else:
                        current_node = None
                        break
                if current_node:
                    self.logger.info(f"Found data directly in state.data.{data_source}")
                    data[data_source] = current_node
                    data_source_used = "state"
            if not data:
                if isinstance(state, dict) and "visualization_data" in state and state["visualization_data"]:
                    viz_data = state["visualization_data"]
                    for expected_source in self._get_expected_sources(data_source):
                        if expected_source in viz_data:
                            self.logger.info(f"Found data in state.visualization_data[{expected_source}]")
                            data[expected_source] = viz_data[expected_source]
                            data_source_used = "state"
                            break
                if not data and isinstance(state, dict) and "data" in state and state["data"]:
                    state_data = state["data"]
                    for expected_source in self._get_expected_sources(data_source):
                        if expected_source in state_data:
                            self.logger.info(f"Found data in state.data[{expected_source}]")
                            data[expected_source] = state_data[expected_source]
                            data_source_used = "state"
                            break
                if not data and hasattr(state, "visualization_data") and state.visualization_data:
                    viz_data = state.visualization_data
                    for expected_source in self._get_expected_sources(data_source):
                        if expected_source in viz_data:
                            self.logger.info(f"Found data in state.visualization_data.{expected_source}")
                            data[expected_source] = viz_data[expected_source]
                            data_source_used = "state"
                            break
        if not data and data_source:
            cache_data = self._load_data_from_cache(data_source, data_field)
            if cache_data and not cache_data.get("data_unavailable", False):
                data = cache_data
                data_source_used = "cache"
                self.logger.info(f"Using data from cache for {viz_id}")
            else:
                data = cache_data
        viz_key = f"{section_title}_{viz_id}"
        self.data_sources_used[viz_key] = data_source_used
        return data

    def _check_data_usability(self, data: Dict[str, Any]) -> bool:
        if not data or data.get("data_unavailable", False):
            return False
        if isinstance(data, dict):
            keys = set(data.keys())
            if keys.issubset({'error', 'errors', 'available_tools', 'message', 'data_unavailable'}):
                return False
            for source, source_data in data.items():
                if source_data is None or source_data == {}:
                    continue
                if source == 'defillama' and isinstance(source_data, dict):
                    if any(key in source_data for key in ['tvl', 'chains', 'tvl_history']):
                        if ('tvl' in source_data and source_data['tvl']) or \
                           ('chains' in source_data and source_data['chains']) or \
                           ('tvl_history' in source_data and source_data['tvl_history']):
                            return True
                elif source == 'coinmarketcap' and isinstance(source_data, dict):
                    if any(key in source_data for key in ['current_price', 'market_cap', 
                                                         'circulating_supply', 'volume_24h']):
                        return True
                elif source == 'coingecko' and isinstance(source_data, dict):
                    if 'results' in source_data and isinstance(source_data['results'], list):
                        if len(source_data['results']) > 0:
                            return True
                elif source == 'tokenomics' and isinstance(source_data, dict):
                    if 'data' in source_data and isinstance(source_data['data'], dict):
                        data_obj = source_data['data']
                        if 'token_distribution' in data_obj and data_obj['token_distribution']:
                            return True
        if isinstance(data, dict):
            for _, value in data.items():
                if isinstance(value, dict) and value:
                    return True
                elif isinstance(value, list) and value:
                    return True
        return bool(data)

    def _create_visualization(self, section_title: str, viz_id: str, viz_config: Dict[str, Any], state: Dict[str, Any]) -> bool:
        try:
            self.logger.info(f"Creating visualization {viz_id} for section {section_title}")
            viz_data = self._get_data_for_visualization(viz_id, viz_config, state, section_title)
            section_summary = self._safe_get_dict(state, f"{section_title}_summary", "")
            description = viz_config.get("description", "") or section_summary
            if not description and "description_template" in viz_config:
                try:
                    template = viz_config["description_template"]
                    format_values = {
                        "project_name": self.project_name,
                        "section_title": section_title,
                        "liquidity_description": f"liquidity analysis for {self.project_name}",
                        "price_description": f"price trends for {self.project_name}",
                        "volume_description": f"trading volume for {self.project_name}",
                        "tvl_description": f"total value locked (TVL) for {self.project_name}",
                        "growth_description": f"growth metrics for {self.project_name}",
                        "comparison_description": f"comparison with similar projects",
                        "chain_description": f"chain distribution for {self.project_name}",
                        "tokenomics_description": f"token allocation for {self.project_name}",
                        "date": datetime.now().strftime("%B %Y"),
                        "token_symbol": self.project_name.upper(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d"),
                        "time_period": "30 days",
                    }
                    try:
                        if "market_analysis" in state:
                            market_data = state.get("market_analysis", {})
                            format_values["price_description"] = market_data.get("price_summary", format_values["price_description"])
                            format_values["volume_description"] = market_data.get("volume_summary", format_values["volume_description"])
                        if "liquidity" in state:
                            format_values["liquidity_description"] = state.get("liquidity", {}).get("summary", format_values["liquidity_description"])
                        if "tvl" in state:
                            format_values["tvl_description"] = state.get("tvl", {}).get("summary", format_values["tvl_description"])
                        if "tokenomics" in state:
                            format_values["tokenomics_description"] = state.get("tokenomics", {}).get("summary", format_values["tokenomics_description"])
                        if "token_data" in state:
                            token_data = state.get("token_data", {})
                            if "symbol" in token_data:
                                format_values["token_symbol"] = token_data["symbol"]
                        if "comparison" in state:
                            format_values["comparison_description"] = state.get("comparison", {}).get("summary", format_values["comparison_description"])
                        if "blockchain_data" in state:
                            format_values["chain_description"] = state.get("blockchain_data", {}).get("summary", format_values["chain_description"])
                    except Exception as template_data_error:
                        self.logger.warning(f"Error extracting template data from state: {template_data_error}")
                    try:
                        description = template.format(**format_values)
                    except KeyError as missing_key:
                        missing_key_str = str(missing_key).strip("'")
                        format_values[missing_key_str] = f"information about {missing_key_str.replace('_', ' ')}"
                        try:
                            description = template.format(**format_values)
                        except Exception:
                            description = f"Visualization for {self.project_name} {section_title}: {viz_id}"
                except Exception as template_error:
                    self.logger.warning(f"Error formatting description template: {template_error}")
                    description = f"Visualization for {section_title}: {viz_id}"
            
            vis_type = viz_config.get("type", "")
            config = {
                "title": viz_config.get("title", f"{self.project_name} {viz_id.replace('_', ' ').title()}"),
                "description": description,
                "output_filename": f"{section_title}_{viz_id}",
                "data_source": viz_config.get("data_source", ""),
                "data_field": viz_config.get("data_field", ""),
                "source": viz_config.get("source", "Various Sources")
            }
            result, file_path, error_msg = self.viz_api.create_visualization(vis_type, config)
            if result and file_path:
                self.logger.info(f"Visualization created successfully: {file_path}")
                viz_item = {
                    "id": viz_id,
                    "section": section_title,
                    "path": file_path,
                    "type": viz_config.get("type", "unknown"),
                    "title": viz_config.get("title", viz_id.replace("_", " ").title())
                }
                if isinstance(self.visualizations, dict):
                    viz_key = f"{section_title}_{viz_id}"
                    self.visualizations[viz_key] = file_path
                elif isinstance(self.visualizations, list):
                    self.visualizations.append(viz_item)
                else:
                    self.visualizations = [viz_item]
                if not hasattr(self, 'visualization_outputs'):
                    self.visualization_outputs = {}
                viz_key = f"{section_title}_{viz_id}"
                self.visualization_outputs[viz_key] = file_path
                self.visualization_list.append(viz_item)
                return True
            else:
                viz_key = f"{section_title}_{viz_id}"
                self._add_error(viz_key, error_msg or "Unknown visualization error")
                self.logger.error(f"Visualization failed: {error_msg}")
                return False
        except Exception as e:
            viz_key = f"{section_title}_{viz_id}"
            self._add_error(viz_key, str(e))
            self.logger.error(f"Error creating visualization {viz_id}: {str(e)}")
            return False

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(state, dict) and hasattr(state, 'to_dict'):
            state_dict = state.to_dict()
            return asyncio.run(self.run_with_state_async(state, state_dict))
        else:
            return asyncio.run(self.run_with_state_async(state, state))
    
    def run_with_state(self, original_state: Any, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self.run_with_state_async(original_state, state_dict))

    def _handle_visualization(self, section_name: str, viz_id: str, viz_config: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        project_name = state.get("project_name", "unknown_project")
        if not project_name and "context" in state and isinstance(state["context"], dict):
            project_name = state["context"].get("project_name", "unknown_project")
        visualizer = Visualizer(project_name=project_name)
        success = visualizer._create_visualization(section_name, viz_id, viz_config, state)
        path = ""
        if success and visualizer.visualization_list:
            path = visualizer.visualization_list[0].get("path", "")
        return {
            "type": viz_id,
            "section": section_name,
            "path": path,
            "success": success,
            "data_source": visualizer.data_sources_used.get(f"{section_name}_{viz_id}", "unknown"),
            "error": visualizer.errors.get(f"{section_name}_{viz_id}", "") if not success else ""
        }

    async def _create_visualization_async(self, section_title: str, viz_id: str, viz_config: Dict[str, Any], state: Dict[str, Any]) -> Tuple[str, bool]:
        max_attempts = 3
        retry_wait = 2
        viz_data = self._get_data_for_visualization(viz_id, viz_config, state, section_title)
        for attempt in range(1, max_attempts + 1):
            try:
                section_summary = self._safe_get_dict(state, f"{section_title}_summary", "")
                description = viz_config.get("description", "") or section_summary
                if not description and "description_template" in viz_config:
                    try:
                        template = viz_config["description_template"]
                        format_values = {
                            "project_name": self.project_name,
                            "section_title": section_title,
                            "liquidity_description": f"liquidity analysis for {self.project_name}",
                            "price_description": f"price trends for {self.project_name}",
                            "volume_description": f"trading volume for {self.project_name}",
                            "tvl_description": f"total value locked (TVL) for {self.project_name}",
                            "growth_description": f"growth metrics for {self.project_name}",
                            "comparison_description": f"comparison with similar projects",
                            "chain_description": f"chain distribution for {self.project_name}",
                            "tokenomics_description": f"token allocation for {self.project_name}",
                            "date": datetime.now().strftime("%B %Y"),
                            "token_symbol": self.project_name.upper(),
                            "timestamp": datetime.now().strftime("%Y-%m-%d"),
                            "time_period": "30 days",
                        }
                        try:
                            if "market_analysis" in state:
                                market_data = state.get("market_analysis", {})
                                format_values["price_description"] = market_data.get("price_summary", format_values["price_description"])
                                format_values["volume_description"] = market_data.get("volume_summary", format_values["volume_description"])
                            if "liquidity" in state:
                                format_values["liquidity_description"] = state.get("liquidity", {}).get("summary", format_values["liquidity_description"])
                            if "tvl" in state:
                                format_values["tvl_description"] = state.get("tvl", {}).get("summary", format_values["tvl_description"])
                            if "tokenomics" in state:
                                format_values["tokenomics_description"] = state.get("tokenomics", {}).get("summary", format_values["tokenomics_description"])
                            if "token_data" in state:
                                token_data = state.get("token_data", {})
                                if "symbol" in token_data:
                                    format_values["token_symbol"] = token_data["symbol"]
                            if "comparison" in state:
                                format_values["comparison_description"] = state.get("comparison", {}).get("summary", format_values["comparison_description"])
                            if "blockchain_data" in state:
                                format_values["chain_description"] = state.get("blockchain_data", {}).get("summary", format_values["chain_description"])
                        except Exception as template_data_error:
                            self.logger.warning(f"Error extracting template data from state: {template_data_error}")
                        try:
                            description = template.format(**format_values)
                        except KeyError as missing_key:
                            missing_key_str = str(missing_key).strip("'")
                            format_values[missing_key_str] = f"information about {missing_key_str.replace('_', ' ')}"
                            try:
                                description = template.format(**format_values)
                            except Exception:
                                description = f"Visualization for {self.project_name} {section_title}: {viz_id}"
                    except Exception as template_error:
                        self.logger.warning(f"Error formatting description template: {template_error}")
                        description = f"Visualization for {section_title}: {viz_id}"
                
                vis_type = viz_config.get("type", "")
                config = {
                    "title": viz_config.get("title", f"{self.project_name} {viz_id.replace('_', ' ').title()}"),
                    "description": description,
                    "output_filename": f"{section_title}_{viz_id}",
                    "data_source": viz_config.get("data_source", ""),
                    "data_field": viz_config.get("data_field", ""),
                    "source": viz_config.get("source", "Various Sources")
                }
                result, file_path, error_msg = self.viz_api.create_visualization(vis_type, config)
                self.logger.info(f"Successfully created visualization {viz_id} for section {section_title} on attempt {attempt}")
                viz_path = file_path if file_path else ""
                return viz_path, result
            except Exception as e:
                err_msg = f"Error creating visualization {viz_id} on attempt {attempt}: {str(e)}"
                self.logger.error(err_msg)
                if attempt < max_attempts:
                    self.logger.info(f"Retrying in {retry_wait} seconds...")
                    await asyncio.sleep(retry_wait)
        viz_key = f"{section_title}_{viz_id}"
        self._add_error(viz_key, f"Failed to create visualization after {max_attempts} attempts")
        return "", False

    async def run_with_state_async(self, original_state: Any, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info(f"Starting parallel visualization generation for {self.project_name}")
        start_time = time.time()
        
        self.visualizations = {}
        self.visualization_list = []
        self.errors = {}
        self.data_sources_used = {}
        
        state_dict_safe = self._safe_get_dict(state_dict)
        report_config = self._safe_get_dict(state_dict_safe.get("report_config", {}))
        if not report_config:
            self.logger.error("No report_config found in state")
            return original_state
        
        self.report_config = report_config
        sections = report_config.get("sections", [])
        if not sections:
            self.logger.error("No sections found in report_config")
            return original_state
        
        visualization_types = self._safe_get_dict(report_config.get("visualization_types", {}))
        if not visualization_types:
            self.logger.error("No visualization_types found in report_config")
            return original_state
        
        viz_tasks = []
        for section in sections:
            section_dict = self._safe_get_dict(section)
            section_title = section_dict.get("title", "")
            if not section_title:
                continue
            visualizations = section_dict.get("visualizations", [])
            if not visualizations:
                continue
            self.logger.info(f"Processing visualizations for section: {section_title}")
            for viz_id in visualizations:
                if viz_id not in visualization_types:
                    self.logger.warning(f"Visualization {viz_id} not found in visualization_types")
                    continue
                viz_config = self._safe_get_dict(visualization_types.get(viz_id, {}))
                if not viz_config:
                    self.logger.warning(f"Empty config for visualization {viz_id}")
                    continue
                viz_tasks.append((section_title, viz_id, viz_config))
        
        batch_size = 3
        total_tasks = len(viz_tasks)
        num_batches = math.ceil(total_tasks / batch_size)
        self.logger.info(f"Processing {total_tasks} visualizations in {num_batches} batches of {batch_size}")
        
        for batch_idx in range(num_batches):
            batch_start = batch_idx * batch_size
            batch_end = min((batch_idx + 1) * batch_size, total_tasks)
            batch_tasks = viz_tasks[batch_start:batch_end]
            self.logger.info(f"Processing batch {batch_idx+1}/{num_batches} with {len(batch_tasks)} visualizations")
            tasks = [self._create_visualization_async(section_title, viz_id, viz_config, state_dict) 
                    for section_title, viz_id, viz_config in batch_tasks]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Error in visualization batch: {str(result)}")
                    continue
                viz_path, success = result
                if not success:
                    self.logger.warning(f"Visualization {viz_path} failed")
        
        if self.errors:
            limitations = ["## Visualization Data Limitations\n\nThe following visualizations had issues:\n"]
            for viz_id, error in self.errors.items():
                limitations.append(f"- **{viz_id}**: {error}")
            visualization_errors_summary = "\n".join(limitations)
            if isinstance(original_state, dict):
                original_state["visualization_errors_summary"] = visualization_errors_summary
            elif hasattr(original_state, "visualization_errors_summary"):
                original_state.visualization_errors_summary = visualization_errors_summary
        
        if isinstance(original_state, dict):
            original_state["visualizations"] = self.visualizations
            original_state["visualization_list"] = self.visualization_list
            original_state["visualization_data_sources"] = self.data_sources_used
            if self.errors:
                original_state["errors"] = original_state.get("errors", {})
                original_state["errors"]["visualization_errors"] = self.errors
        else:
            if hasattr(original_state, "visualizations"):
                original_state.visualizations = self.visualizations
            if hasattr(original_state, "visualization_list"):
                original_state.visualization_list = self.visualization_list
            if hasattr(original_state, "visualization_data_sources"):
                original_state.visualization_data_sources = self.data_sources_used
            if self.errors and hasattr(original_state, "errors"):
                original_state.errors = original_state.errors or {}
                original_state.errors["visualization_errors"] = self.errors
        
        elapsed_time = time.time() - start_time
        self.logger.info(f"Completed parallel visualization generation in {elapsed_time:.2f} seconds. Created {len(self.visualization_list)} visualizations with {len(self.errors)} errors")
        return original_state

    def _get_expected_sources(self, data_source: str) -> List[str]:
        direct_mapping = {
            "coinmarketcap": ["coinmarketcap"],
            "coingecko": ["coingecko"],
            "defillama": ["defillama"],
            "tokenomics": ["tokenomics"],
            "tavily": ["tavily"]
        }
        if data_source in direct_mapping:
            return direct_mapping[data_source]
        if "price" in data_source:
            return ["coinmarketcap", "coingecko"]
        if "tvl" in data_source:
            return ["defillama"]
        if "distribution" in data_source or "tokenomics" in data_source:
            return ["tokenomics"]
        if "research" in data_source or "web" in data_source:
            return ["tavily"]
        return ["coinmarketcap", "coingecko", "defillama", "tokenomics", "tavily"]

# Alias for backwards compatibility
visualizer = Visualizer 

async def visualizer_async(state: Dict[str, Any], llm=None, logger: Optional[logging.Logger] = None, config=None) -> Dict[str, Any]:
    logger = logger or logging.getLogger(__name__)
    logger.info("Starting visualizer_async")
    visualizer = Visualizer(project_name=_get_project_name(state), logger=logger, llm=llm, config=config)
    if hasattr(state, 'to_dict'):
        state_dict = state.to_dict()
    else:
        state_dict = state
    logger.info("Completed visualizer_async")
    return await visualizer.run_with_state_async(state, state_dict)

def visualizer_sync(state: Dict[str, Any], llm=None, logger: Optional[logging.Logger] = None, config=None) -> Dict[str, Any]:
    logger = logger or logging.getLogger(__name__)
    logger.info("Starting visualizer_sync")
    visualizer = Visualizer(project_name=_get_project_name(state), logger=logger, llm=llm, config=config)
    if hasattr(state, 'to_dict'):
        state_dict = state.to_dict()
    else:
        state_dict = state
    
    try:
        # Use asyncio.run for sync context (fallback)
        result = asyncio.run(visualizer.run_with_state_async(state, state_dict))
        logger.info("Sync execution completed")
        return result
    except Exception as e:
        logger.error(f"Error in visualizer_sync: {str(e)}", exc_info=True)
        return state

def _get_project_name(state: Any) -> str:
    if state is None:
        return "unknown_project"
    if hasattr(state, "project_name") and state.project_name:
        return state.project_name
    if isinstance(state, dict):
        if "project_name" in state and state["project_name"]:
            return state["project_name"]
        if "context" in state and isinstance(state["context"], dict):
            context = state["context"]
            if "project_name" in context and context["project_name"]:
                return context["project_name"]
    return "unknown_project"