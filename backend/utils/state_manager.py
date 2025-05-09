import logging
import json
import os
import time
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path

try:
    from backend.state import ResearchState
except ImportError:
    from state import ResearchState

class StateManager:
    """
    Utility class to standardize state access patterns across agents.
    
    This class provides consistent methods to:
    1. Access data from both dict and object-style states
    2. Retrieve standardized visualization data
    3. Update state with new content
    4. Handle section-specific data access
    5. Manage common error patterns
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the StateManager with optional logger."""
        self.logger = logger or logging.getLogger(__name__)
    
    def get_project_name(self, state: Union[ResearchState, Dict]) -> str:
        """
        Get project name from state regardless of format.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Project name string
        """
        if isinstance(state, dict):
            return state.get("project_name", "Unknown Project")
        return getattr(state, "project_name", "Unknown Project")
    
    def get_report_config(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get report configuration from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Report configuration dictionary
        """
        if isinstance(state, dict):
            return state.get("report_config", {})
        return getattr(state, "report_config", {})
    
    def get_section_data(self, state: Union[ResearchState, Dict], section_title: str) -> Dict:
        """
        Get data for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            
        Returns:
            Dictionary of data for the section
        """
        normalized_section = self._normalize_section_name(section_title)
        
        # First try to get data from state.data
        if isinstance(state, dict):
            if "data" in state and normalized_section in state["data"]:
                return state["data"][normalized_section]
        else:
            if hasattr(state, "data"):
                state_data = state.data
                if isinstance(state_data, dict) and normalized_section in state_data:
                    return state_data[normalized_section]
        
        # If not found, return empty dict
        return {}
    
    def get_visualization_data(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get all visualization data from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of visualization data
        """
        if isinstance(state, dict):
            return state.get("visualization_data", {})
        return getattr(state, "visualization_data", {})
    
    def get_specific_visualization_data(self, state: Union[ResearchState, Dict], section_title: str, viz_id: str) -> Dict:
        """
        Get standardized visualization data for a specific visualization.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            viz_id: ID of the visualization
            
        Returns:
            Standardized visualization data
        """
        normalized_section = self._normalize_section_name(section_title)
        
        # Try to get standardized data from state.visualization_data
        if isinstance(state, dict):
            if "visualization_data" in state and normalized_section in state["visualization_data"]:
                section_viz_data = state["visualization_data"][normalized_section]
                if viz_id in section_viz_data:
                    self.logger.info(f"Found standardized data for visualization {viz_id} in section {section_title}")
                    return section_viz_data[viz_id]
        else:
            if hasattr(state, "visualization_data"):
                viz_data = state.visualization_data
                if isinstance(viz_data, dict) and normalized_section in viz_data:
                    section_viz_data = viz_data[normalized_section]
                    if isinstance(section_viz_data, dict) and viz_id in section_viz_data:
                        self.logger.info(f"Found standardized data for visualization {viz_id} in section {section_title}")
                        return section_viz_data[viz_id]
        
        # If not found, return empty dict
        self.logger.warning(f"No standardized data found for visualization {viz_id} in section {section_title}")
        return {}
    
    def get_visualization_data_for_section(self, state: Union[ResearchState, Dict], section_title: str) -> Dict:
        """
        Get all visualization data for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            
        Returns:
            Dictionary of visualization data for the section
        """
        normalized_section = self._normalize_section_name(section_title)
        
        # Get visualization data from state
        visualization_data = self.get_visualization_data(state)
        
        # Return section-specific visualization data if it exists
        if normalized_section in visualization_data:
            return visualization_data[normalized_section]
        
        # If not found, return empty dict
        return {}
    
    def get_section_content(self, state: Union[ResearchState, Dict], section_title: str) -> str:
        """
        Get content for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            
        Returns:
            Section content string
        """
        if isinstance(state, dict):
            if "sections" in state and section_title in state["sections"]:
                return state["sections"][section_title].get("content", "")
        else:
            if hasattr(state, "sections") and section_title in state.sections:
                return state.sections[section_title].get("content", "")
        
        return ""
    
    def update_section_content(self, state: Union[ResearchState, Dict], section_title: str, content: str) -> Union[ResearchState, Dict]:
        """
        Update content for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            content: New content for the section
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "sections" not in state:
                state["sections"] = {}
            if section_title not in state["sections"]:
                state["sections"][section_title] = {}
            state["sections"][section_title]["content"] = content
        else:
            if not hasattr(state, "sections"):
                state.sections = {}
            if section_title not in state.sections:
                state.sections[section_title] = {}
            state.sections[section_title]["content"] = content
        
        return state
    
    def get_problem_sections(self, state: Union[ResearchState, Dict]) -> List[Dict]:
        """
        Get problem sections from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            List of problem section dictionaries
        """
        if isinstance(state, dict):
            return state.get("problem_sections", [])
        return getattr(state, "problem_sections", [])
    
    def get_data_sources(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get all data sources from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of data sources
        """
        if isinstance(state, dict):
            return state.get("data", {})
        return getattr(state, "data", {})
    
    def get_data(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get all data from state (alias for get_data_sources for backward compatibility).
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of data
        """
        return self.get_data_sources(state)
    
    def get_visualizations(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get visualizations from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of visualizations
        """
        if isinstance(state, dict):
            return state.get("visualizations", {})
        return getattr(state, "visualizations", {})
    
    def update_visualizations(self, state: Union[ResearchState, Dict], visualizations: Dict) -> Union[ResearchState, Dict]:
        """
        Update visualizations in state.
        
        Args:
            state: Research state object or dictionary
            visualizations: Dictionary of visualizations
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            state["visualizations"] = visualizations
        else:
            state.visualizations = visualizations
        
        return state
    
    def add_error(self, state: Union[ResearchState, Dict], error_type: str, error_message: str) -> Union[ResearchState, Dict]:
        """
        Add error to state.
        
        Args:
            state: Research state object or dictionary
            error_type: Type of error
            error_message: Error message
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "errors" not in state:
                state["errors"] = {}
            state["errors"][error_type] = error_message
        else:
            if not hasattr(state, "errors") or not isinstance(state.errors, dict):
                state.errors = {}
            state.errors[error_type] = error_message
        
        return state
    
    def add_errors(self, state: Union[ResearchState, Dict], errors: Dict[str, Any]) -> Union[ResearchState, Dict]:
        """
        Add multiple errors to state.
        
        Args:
            state: Research state object or dictionary
            errors: Dictionary of errors to add
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "errors" not in state:
                state["errors"] = {}
            for error_type, error_message in errors.items():
                state["errors"][error_type] = error_message
        else:
            if not hasattr(state, "errors") or not isinstance(state.errors, dict):
                state.errors = {}
            for error_type, error_message in errors.items():
                state.errors[error_type] = error_message
        
        return state
    
    def _normalize_section_name(self, section_title: str) -> str:
        """
        Normalize section title for consistent key naming.
        
        Args:
            section_title: Original section title
            
        Returns:
            Normalized section name (lowercase with underscores)
        """
        return section_title.lower().replace(" ", "_")
        
    def get_key_metrics(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Extract key metrics from state data.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of key metrics
        """
        # Get data sources
        data_sources = self.get_data_sources(state)
        
        # Extract key metrics from available data
        key_metrics = {}
        
        # Check if we have CoinMarketCap data
        cmc_data = data_sources.get("coinmarketcap", {})
        if cmc_data:
            overview = cmc_data.get("overview", {})
            if overview:
                key_metrics["market_cap"] = overview.get("market_cap", "N/A")
                key_metrics["price"] = overview.get("price", "N/A")
                key_metrics["volume_24h"] = overview.get("volume_24h", "N/A")
                key_metrics["circulating_supply"] = overview.get("circulating_supply", "N/A")
                key_metrics["total_supply"] = overview.get("total_supply", "N/A")
                
        # Check if we have DeFiLlama data
        defillama_data = data_sources.get("defillama", {})
        if defillama_data:
            tvl = defillama_data.get("tvl", {})
            if tvl:
                key_metrics["tvl"] = tvl.get("current_tvl", "N/A")
                key_metrics["tvl_change_24h"] = tvl.get("change_24h", "N/A")
                
        # Check if we have tokenomics data
        tokenomics_data = data_sources.get("tokenomics", {})
        if tokenomics_data:
            distribution = tokenomics_data.get("distribution", {})
            if distribution:
                key_metrics["token_distribution"] = distribution
                
        return key_metrics
        
    def format_key_metrics(self, key_metrics: Dict) -> Dict:
        """
        Format key metrics for better readability.
        
        Args:
            key_metrics: Dictionary of key metrics
            
        Returns:
            Dictionary of formatted key metrics
        """
        formatted_metrics = {}
        
        for key, value in key_metrics.items():
            if value is None:
                continue
                
            if key in ["current_price", "price"]:
                if isinstance(value, (int, float)):
                    formatted_metrics[key] = f"${value:,.2f}"
            elif key in ["market_cap", "volume_24h", "tvl"]:
                if isinstance(value, (int, float)):
                    if value >= 1_000_000_000:
                        formatted_metrics[key] = f"${value/1_000_000_000:.2f}B"
                    elif value >= 1_000_000:
                        formatted_metrics[key] = f"${value/1_000_000:.2f}M"
                    else:
                        formatted_metrics[key] = f"${value:,.2f}"
            elif key in ["circulating_supply", "total_supply"]:
                if isinstance(value, (int, float)):
                    if value >= 1_000_000_000:
                        formatted_metrics[key] = f"{value/1_000_000_000:.2f}B"
                    elif value >= 1_000_000:
                        formatted_metrics[key] = f"{value/1_000_000:.2f}M"
                    else:
                        formatted_metrics[key] = f"{value:,}"
            else:
                formatted_metrics[key] = value
                
        return formatted_metrics
        
    def get_section_summary(self, state: Union[ResearchState, Dict], section_title: str) -> str:
        """
        Get summary for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            
        Returns:
            Section summary string
        """
        if isinstance(state, dict):
            if "sections" in state and section_title in state["sections"]:
                return state["sections"][section_title].get("summary", "")
        else:
            if hasattr(state, "sections") and section_title in state.sections:
                return state.sections[section_title].get("summary", "")
        
        return ""
        
    def update_section_summary(self, state: Union[ResearchState, Dict], section_title: str, summary: str) -> Union[ResearchState, Dict]:
        """
        Update summary for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            summary: New summary for the section
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "sections" not in state:
                state["sections"] = {}
            if section_title not in state["sections"]:
                state["sections"][section_title] = {}
            state["sections"][section_title]["summary"] = summary
        else:
            if not hasattr(state, "sections"):
                state.sections = {}
            if section_title not in state.sections:
                state.sections[section_title] = {}
            state.sections[section_title]["summary"] = summary
        
        return state
        
    def update_draft(self, state: Union[ResearchState, Dict], draft: str) -> Union[ResearchState, Dict]:
        """
        Update the draft content in state.
        
        Args:
            state: Research state object or dictionary
            draft: New draft content
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            state["draft"] = draft
        else:
            state.draft = draft
        
        return state
        
    def get_draft(self, state: Union[ResearchState, Dict]) -> str:
        """
        Get draft content from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Draft content string
        """
        if isinstance(state, dict):
            return state.get("draft", "")
        return getattr(state, "draft", "")
        
    def get_visualization_list(self, state: Union[ResearchState, Dict]) -> List[Dict]:
        """
        Get list of visualizations from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            List of visualization dictionaries
        """
        if isinstance(state, dict):
            return state.get("visualization_list", [])
        return getattr(state, "visualization_list", [])
        
    def update_visualization_list(self, state: Union[ResearchState, Dict], visualization_list: List[Dict]) -> Union[ResearchState, Dict]:
        """
        Update visualization list in state.
        
        Args:
            state: Research state object or dictionary
            visualization_list: List of visualization dictionaries
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            state["visualization_list"] = visualization_list
        else:
            state.visualization_list = visualization_list
        
        return state
        
    def add_visualization(self, state: Union[ResearchState, Dict], section_title: str, viz_id: str, viz_path: str, viz_type: str, viz_title: str) -> Union[ResearchState, Dict]:
        """
        Add a visualization to state.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            viz_id: ID of the visualization
            viz_path: Path to the visualization file
            viz_type: Type of visualization
            viz_title: Title of the visualization
            
        Returns:
            Updated state
        """
        # Create visualization item
        viz_item = {
            "id": viz_id,
            "section": section_title,
            "path": viz_path,
            "type": viz_type,
            "title": viz_title
        }
        
        # Add to visualization list
        if isinstance(state, dict):
            if "visualization_list" not in state:
                state["visualization_list"] = []
            state["visualization_list"].append(viz_item)
            
            # Also update visualizations dict for backward compatibility
            if "visualizations" not in state:
                state["visualizations"] = {}
            viz_key = f"{section_title}_{viz_id}"
            state["visualizations"][viz_key] = viz_path
        else:
            if not hasattr(state, "visualization_list"):
                state.visualization_list = []
            state.visualization_list.append(viz_item)
            
            # Also update visualizations dict for backward compatibility
            if not hasattr(state, "visualizations"):
                state.visualizations = {}
            viz_key = f"{section_title}_{viz_id}"
            state.visualizations[viz_key] = viz_path
        
        return state
        
    def get_visualization_errors(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get visualization errors from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of visualization errors
        """
        if isinstance(state, dict):
            errors = state.get("errors", {})
            return errors.get("visualization_errors", {})
        
        if hasattr(state, "errors") and isinstance(state.errors, dict):
            return state.errors.get("visualization_errors", {})
        
        return {}
        
    def add_visualization_error(self, state: Union[ResearchState, Dict], viz_key: str, error_message: str) -> Union[ResearchState, Dict]:
        """
        Add a visualization error to state.
        
        Args:
            state: Research state object or dictionary
            viz_key: Visualization key (section_title_viz_id)
            error_message: Error message
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "errors" not in state:
                state["errors"] = {}
            if "visualization_errors" not in state["errors"]:
                state["errors"]["visualization_errors"] = {}
            state["errors"]["visualization_errors"][viz_key] = error_message
        else:
            if not hasattr(state, "errors"):
                state.errors = {}
            if "visualization_errors" not in state.errors:
                state.errors["visualization_errors"] = {}
            state.errors["visualization_errors"][viz_key] = error_message
        
        return state
        
    def get_visualization_data_sources(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get visualization data sources from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of visualization data sources
        """
        if isinstance(state, dict):
            return state.get("visualization_data_sources", {})
        return getattr(state, "visualization_data_sources", {})
        
    def update_visualization_data_sources(self, state: Union[ResearchState, Dict], viz_key: str, data_source: str) -> Union[ResearchState, Dict]:
        """
        Update visualization data sources in state.
        
        Args:
            state: Research state object or dictionary
            viz_key: Visualization key (section_title_viz_id)
            data_source: Data source used for visualization
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "visualization_data_sources" not in state:
                state["visualization_data_sources"] = {}
            state["visualization_data_sources"][viz_key] = data_source
        else:
            if not hasattr(state, "visualization_data_sources"):
                state.visualization_data_sources = {}
            state.visualization_data_sources[viz_key] = data_source
        
        return state
        
    def update_edited_draft(self, state: Union[ResearchState, Dict], edited_draft: str) -> Union[ResearchState, Dict]:
        """
        Update the edited draft content in state.
        
        Args:
            state: Research state object or dictionary
            edited_draft: New edited draft content
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            state["edited_draft"] = edited_draft
        else:
            state.edited_draft = edited_draft
        
        return state
        
    def update_final_report(self, state: Union[ResearchState, Dict], final_report: str) -> Union[ResearchState, Dict]:
        """
        Update the final report content in state.
        
        Args:
            state: Research state object or dictionary
            final_report: New final report content
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            state["final_report"] = final_report
        else:
            state.final_report = final_report
        
        return state
        
    def update_visualization_errors_summary(self, state: Union[ResearchState, Dict], summary: str) -> Union[ResearchState, Dict]:
        """
        Update the visualization errors summary in state.
        
        Args:
            state: Research state object or dictionary
            summary: Summary of visualization errors
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "errors" not in state:
                state["errors"] = {}
            state["errors"]["visualization_errors_summary"] = summary
        else:
            if not hasattr(state, "errors") or not isinstance(state.errors, dict):
                state.errors = {}
            state.errors["visualization_errors_summary"] = summary
        
        return state
        
    def update_field(self, state: Union[ResearchState, Dict], field_name: str, field_value: Any) -> Union[ResearchState, Dict]:
        """
        Update any field in state.
        
        Args:
            state: Research state object or dictionary
            field_name: Name of the field to update
            field_value: New value for the field
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            state[field_name] = field_value
        else:
            setattr(state, field_name, field_value)
        
        return state
        
    def get_references(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get references from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of references
        """
        if isinstance(state, dict):
            return state.get("references", {})
        return getattr(state, "references", {}) or {}
    
    def get_section_titles(self, state: Union[ResearchState, Dict]) -> List[str]:
        """
        Get all section titles from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            List of section titles
        """
        report_config = self.get_report_config(state)
        if report_config and "sections" in report_config:
            return [section.get("title") for section in report_config["sections"] if section.get("title")]
        
        # Fallback to looking at sections directly
        if isinstance(state, dict):
            if "sections" in state:
                return list(state["sections"].keys())
        else:
            if hasattr(state, "sections") and state.sections:
                return list(state.sections.keys())
        
        return []
    
    def get_visualization_data_for_section(self, state: Union[ResearchState, Dict], section_title: str) -> Dict:
        """
        Get visualization data for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            
        Returns:
            Dictionary of visualization data for the section
        """
        normalized_section = self._normalize_section_name(section_title)
        
        if isinstance(state, dict):
            visualization_data = state.get("visualization_data", {})
            return visualization_data.get(normalized_section, {})
        else:
            if hasattr(state, "visualization_data"):
                visualization_data = state.visualization_data
                if isinstance(visualization_data, dict):
                    return visualization_data.get(normalized_section, {})
        
        return {}
        
    def update_progress(self, state: Union[ResearchState, Dict], message: str) -> Union[ResearchState, Dict]:
        """
        Update progress message in state.
        
        Args:
            state: Research state object or dictionary
            message: Progress message
            
        Returns:
            Updated state
        """
        if isinstance(state, dict):
            if "progress" not in state:
                state["progress"] = []
            state["progress"].append({
                "message": message,
                "timestamp": time.time()
            })
        else:
            if not hasattr(state, "progress") or not isinstance(state.progress, list):
                state.progress = []
            state.progress.append({
                "message": message,
                "timestamp": time.time()
            })
            
        # Log progress message
        if self.logger:
            self.logger.info(f"Progress: {message}")
            
        return state
        
    def get_errors(self, state: Union[ResearchState, Dict]) -> Dict:
        """
        Get all errors from state.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Dictionary of errors
        """
        if isinstance(state, dict):
            return state.get("errors", {})
        return getattr(state, "errors", {}) or {}
        
    def ensure_state_structure(self, state: Union[ResearchState, Dict]) -> Union[ResearchState, Dict]:
        """
        Ensure the state has all required structures initialized.
        
        Args:
            state: Research state object or dictionary
            
        Returns:
            Updated state with all necessary structure
        """
        # For dictionary state
        if isinstance(state, dict):
            # Initialize data sections
            if "data" not in state:
                state["data"] = {}
                
            # Initialize visualization data
            if "visualization_data" not in state:
                state["visualization_data"] = {}
                
            # Initialize sections
            if "sections" not in state:
                state["sections"] = {}
                
            # Initialize errors
            if "errors" not in state:
                state["errors"] = {}
                
            # Initialize progress
            if "progress" not in state:
                state["progress"] = []
                
            # Initialize visualizations
            if "visualizations" not in state:
                state["visualizations"] = {}
                
            # Initialize visualization list
            if "visualization_list" not in state:
                state["visualization_list"] = []
                
            # Initialize problem sections
            if "problem_sections" not in state:
                state["problem_sections"] = []
        
        # For object state
        else:
            # Initialize data sections
            if not hasattr(state, "data") or state.data is None:
                state.data = {}
                
            # Initialize visualization data
            if not hasattr(state, "visualization_data") or state.visualization_data is None:
                state.visualization_data = {}
                
            # Initialize sections
            if not hasattr(state, "sections") or state.sections is None:
                state.sections = {}
                
            # Initialize errors
            if not hasattr(state, "errors") or state.errors is None:
                state.errors = {}
                
            # Initialize progress
            if not hasattr(state, "progress") or state.progress is None:
                state.progress = []
                
            # Initialize visualizations
            if not hasattr(state, "visualizations") or state.visualizations is None:
                state.visualizations = {}
                
            # Initialize visualization list
            if not hasattr(state, "visualization_list") or state.visualization_list is None:
                state.visualization_list = []
                
            # Initialize problem sections
            if not hasattr(state, "problem_sections") or state.problem_sections is None:
                state.problem_sections = []
        
        return state
        
    def update_section_data(self, state: Union[ResearchState, Dict], section_title: str, section_data: Dict) -> Union[ResearchState, Dict]:
        """
        Update data for a specific section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            section_data: New data for the section
            
        Returns:
            Updated state
        """
        normalized_section = self._normalize_section_name(section_title)
        
        if isinstance(state, dict):
            if "data" not in state:
                state["data"] = {}
            state["data"][normalized_section] = section_data
        else:
            if not hasattr(state, "data") or state.data is None:
                state.data = {}
            state.data[normalized_section] = section_data
        
        return state
        
    def update_data_field(self, state: Union[ResearchState, Dict], section_title: str, field_name: str, field_value: Any) -> Union[ResearchState, Dict]:
        """
        Update a specific data field within a section.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the section
            field_name: Name of the field to update
            field_value: New value for the field
            
        Returns:
            Updated state
        """
        normalized_section = self._normalize_section_name(section_title)
        
        # Get current section data
        if isinstance(state, dict):
            if "data" not in state:
                state["data"] = {}
            if normalized_section not in state["data"]:
                state["data"][normalized_section] = {}
            state["data"][normalized_section][field_name] = field_value
        else:
            if not hasattr(state, "data") or state.data is None:
                state.data = {}
            if normalized_section not in state.data:
                state.data[normalized_section] = {}
            state.data[normalized_section][field_name] = field_value
        
        return state
        
    def update_problem_sections(self, state: Union[ResearchState, Dict], section_title: str, reason: str) -> Union[ResearchState, Dict]:
        """
        Add a section to problem_sections.
        
        Args:
            state: Research state object or dictionary
            section_title: Title of the problematic section
            reason: Reason for the problem
            
        Returns:
            Updated state
        """
        problem_section = {
            "title": section_title,
            "reason": reason
        }
        
        if isinstance(state, dict):
            if "problem_sections" not in state:
                state["problem_sections"] = []
            state["problem_sections"].append(problem_section)
        else:
            if not hasattr(state, "problem_sections") or not isinstance(state.problem_sections, list):
                state.problem_sections = []
            state.problem_sections.append(problem_section)
        
        return state 