import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import sys

try:
    from backend.state import ResearchState
    from backend.orchestration.mcp.client_manager import MCPClientManager
    from backend.utils.cache_utils import CacheManager
    from backend.orchestration.rag.retriever import RAGRetriever
    from backend.orchestration.rag.vector_store import get_vector_store
except ModuleNotFoundError:
    from state import ResearchState
    from orchestration.mcp.client_manager import MCPClientManager
    from utils.cache_utils import CacheManager
    from orchestration.rag.retriever import RAGRetriever
    from orchestration.rag.vector_store import get_vector_store

# Configure logger to flush immediately
logger = logging.getLogger(__name__)
for handler in logger.handlers:
    handler.flush = sys.stdout.flush
logger.info("Logger configured with immediate flush")

class Researcher:
    """
    Agent that performs research on cryptocurrency projects using RAG and MCP.
    Collects data from various sources and prepares it for visualization and report generation.
    """
    
    def __init__(self, llm_model: str = 'gpt-4o-mini', logger: logging.Logger = None):
        self.llm_model = llm_model
        self.logger = logger or logging.getLogger(__name__)
        self.vector_store = None
        self.rag_retriever = None
        self.mcp_client = None
        self.cache_dir = None
        self.data = {}
        self.project_name = None
        self.state = {}
        self.logger.info("Researcher constructor started")
        self.logger.info("Researcher constructor completed")
    
    async def initialize(self):
        """Initialize RAG and MCP components."""
        self.logger.info("Starting Researcher.initialize")
        try:
            self.logger.info('Initializing RAG components')
            try:
                self.logger.info("Getting vector store synchronously")
                # Call get_vector_store directly as it's synchronous
                self.vector_store = get_vector_store()
                self.logger.info("Vector store object created")
                # Check if the store initialized correctly internally
                if not self.vector_store or not self.vector_store.is_healthy():
                     self.logger.error("Vector store initialization failed or store is not healthy.")
                     self.vector_store = None # Set to None if unhealthy
                else:
                     self.logger.info("Vector store appears healthy")
            except Exception as e:
                self.logger.error(f"Error getting vector store instance: {str(e)}", exc_info=True)
                self.vector_store = None
            
            if self.vector_store:
                self.logger.info("Initializing RAGRetriever")
                # Assuming RAGRetriever constructor is synchronous
                self.rag_retriever = RAGRetriever(self.vector_store, llm_model=self.llm_model)
                self.logger.info("RAGRetriever initialized")
            else:
                self.logger.warning("RAGRetriever not initialized due to vector store failure")
            
            self.logger.info('Initializing MCP client')
            try:
                from backend.main import mcp_client_manager
                if mcp_client_manager:
                    self.logger.info('Using existing MCP client manager')
                    self.mcp_client = mcp_client_manager
                else:
                    self.logger.info('Creating new MCP client manager')
                    self.mcp_client = MCPClientManager()
            except (ImportError, AttributeError):
                self.logger.info('No global client manager found, creating a new one')
                self.mcp_client = MCPClientManager()
            
            if not hasattr(self.mcp_client, 'servers_started') or not self.mcp_client.servers_started:
                self.logger.info('Starting MCP servers')
                server_names = ['coingecko', 'coinmarketcap', 'defillama', 'tavily', 'tokenomics']
                for server_name in server_names:
                    self.logger.info(f'Starting MCP server: {server_name}')
                    try:
                        await asyncio.wait_for(self.mcp_client.start_server(server_name), timeout=10.0)
                        self.logger.info(f'Server {server_name} started')
                    except asyncio.TimeoutError:
                        self.logger.error(f"Timeout starting MCP server: {server_name}")
                    except Exception as e:
                        self.logger.error(f"Error starting MCP server {server_name}: {str(e)}")
                self.mcp_client.servers_started = True
            else:
                self.logger.info('All MCP servers already running')
            
            self.logger.info('RAG and MCP components initialized successfully')
        except Exception as e:
            self.logger.error(f'Error initializing RAG and MCP components: {str(e)}', exc_info=True) # Added exc_info
            # Optionally re-raise or handle differently depending on desired behavior
            raise
        self.logger.info("Completed Researcher.initialize")
    
    async def run(self, state: Union[ResearchState, Dict]) -> Union[ResearchState, Dict]:
        """Run the researcher to collect data for the given project."""
        self.logger.info("Entering Researcher.run")
        is_state_dict = isinstance(state, dict)
        
        try:
            self.logger.info("Processing state")
            if is_state_dict:
                project_name = state.get("project_name", "Unknown Project")
                self.logger.info(f"Running researcher for {project_name}")
                self.project_name = project_name
            else: # Assuming ResearchState object
                self.logger.info(f"Running researcher for {state.project_name}")
                self.project_name = state.project_name
            
            self.logger.info("Setting up cache directory")
            self.cache_dir = os.path.join("docs", self.project_name.lower(), "cache")
            os.makedirs(self.cache_dir, exist_ok=True)
            self.logger.info(f"Cache directory set to: {self.cache_dir}")
            
            self.logger.info("Calling initialize")
            await asyncio.wait_for(self.initialize(), timeout=30.0)
            self.logger.info("Initialize completed")
            
            self.logger.info("Calling execute_workflow")
            # Pass the original state (dict or object) to execute_workflow
            result = await asyncio.wait_for(self.execute_workflow(query_or_state=state), timeout=300.0)
            self.logger.info("Completed Researcher.run")
            return result # execute_workflow should return the modified state (dict or object)
            
        except asyncio.TimeoutError:
            self.logger.error("Researcher.run timed out after 300 seconds")
            error_msg = "Researcher timed out"
            if is_state_dict:
                if "errors" not in state or not isinstance(state["errors"], list):
                    state["errors"] = [] # Ensure errors is a list
                state["errors"].append(error_msg)
            else: # Assuming ResearchState object
                if not hasattr(state, 'errors') or not isinstance(state.errors, list):
                    state.errors = [] # Ensure errors is a list
                state.errors.append(error_msg)
            return state
        except Exception as e:
            self.logger.error(f"Error in researcher run: {str(e)}", exc_info=True)
            error_msg = f"Researcher error: {str(e)}"
            if is_state_dict:
                if "errors" not in state or not isinstance(state["errors"], list):
                    state["errors"] = [] # Ensure errors is a list
                state["errors"].append(error_msg)
            else: # Assuming ResearchState object
                if not hasattr(state, 'errors') or not isinstance(state.errors, list):
                    state.errors = [] # Ensure errors is a list
                state.errors.append(error_msg)
            return state
    
    async def execute_workflow(self, query_or_state: Any, context: Dict[str, Any] = None) -> Any: # Return type matches input
        """Execute the research workflow using RAG to select MCP endpoints."""
        self.logger.info("Entering execute_workflow")
        context = context or {}
        
        # Determine if input is dict or object and keep it consistent
        is_state_dict = isinstance(query_or_state, dict)
        state = query_or_state # Use the original reference
        
        # Load report_config from state if not in context
        # Needs consistent access based on state type
        if 'report_config' not in context:
             if is_state_dict:
                  report_config = state.get('report_config', {})
                  if report_config: self.logger.info("Loaded report_config from state dict")
             else:
                  report_config = getattr(state, 'report_config', {})
                  if report_config: self.logger.info("Loaded report_config from state object")
        elif 'report_config' in context:
            report_config = context['report_config']
            self.logger.info("Loaded report_config from context")
        else:
            report_config = {}
            self.logger.warning("report_config not found in state or context")
            
        project_name = state.get('project_name', 'Unknown Project') if is_state_dict else getattr(state, 'project_name', 'Unknown Project')
        
        self.state_ref = state # Keep a reference for internal use if needed, but modify state directly
        self.project_name = project_name.lower()
        self.logger.info(f"Project name: {self.project_name}")
        
        # Ensure state has necessary keys/attributes
        if is_state_dict:
            if "problem_sections" not in state: state["problem_sections"] = []
            if "data" not in state: state["data"] = {}
            if "visualization_data" not in state: state["visualization_data"] = {}
        else:
            if not hasattr(state, 'problem_sections'): state.problem_sections = []
            if not hasattr(state, 'data'): state.data = {}
            if not hasattr(state, 'visualization_data'): state.visualization_data = {}
        
        try:
            # Track processed endpoints to avoid duplicate API calls
            self.processed_endpoints = set()
            
            # First, batch process all API calls to minimize redundant requests
            await self._batch_process_project_data(report_config, project_name)
            
            # Then run Tavily searches in batches for all sections
            # Process Tavily requests in batches using our optimized method
            tavily_results = await self._batch_process_tavily(project_name, report_config)
            
            # Store Tavily results in batch data if not already there
            if "batch_data" not in self.data:
                self.data["batch_data"] = {}
            self.data["batch_data"]["tavily"] = tavily_results
            
            # Process each section from report_config
            for section in report_config.get("sections", []):
                section_title = section.get("title")
                if not section_title:
                    continue
                    
                required_sources = section.get("data_sources", [])
                self.logger.info(f"Processing section: '{section_title}' | Required sources: {required_sources}")
                
                # Use RAG to select endpoints for this section
                query_template = section.get("query_template", "{project_name}")
                section_query = query_template.format(project_name=project_name)
                self.logger.info(f"Section '{section_title}': Running RAG with query: '{section_query}'")
                
                endpoints_for_section = []
                try:
                    if self.rag_retriever:
                        endpoints_for_section = await asyncio.wait_for(
                            self.rag_retriever.get_endpoints_for_project(section_query), 
                            timeout=5.0
                        )
                        # Filter out HuggingFace endpoints - we'll use them only as fallbacks
                        endpoints_for_section = [
                            endpoint for endpoint in endpoints_for_section
                            if "huggingface" not in endpoint
                        ]
                        self.logger.info(f"RAG retrieved {len(endpoints_for_section)} endpoints for section query: {endpoints_for_section}")
                    else:
                        self.logger.warning("RAG retriever not available, using fallback endpoints")
                        # Use tool calls directly instead of hardcoded endpoints
                        endpoints_for_section = []
                except Exception as e:
                    self.logger.error(f"Error in RAG retrieval for section '{section_title}': {str(e)}")
                    endpoints_for_section = []
                
                # If RAG failed or returned no endpoints, try to use required sources directly
                if not endpoints_for_section and required_sources:
                    self.logger.info(f"No endpoints from RAG for section '{section_title}', trying direct tool calls for required sources: {required_sources}")
                    
                    for source in required_sources:
                        if source.lower() == "web_research" or source.lower() == "tavily":
                            # For web research, use Tavily directly
                            try:
                                self.logger.info(f"Calling Tavily directly for section '{section_title}'")
                                cache_manager = CacheManager(project_name=project_name)
                                cached_data = cache_manager.load("tavily", "research", section_title)
                                
                                if cached_data:
                                    self.logger.info(f"Using cached Tavily data for section '{section_title}'")
                                    section_data = cached_data
                                else:
                                    self.logger.info(f"Fetching fresh Tavily data for section '{section_title}'")
                                    # Use named parameters for the call_tool method
                                    section_data = await self.mcp_client.call_tool("tavily", "research", query=section_query, project_name=project_name, cache_key=section_title)
                                    
                                    # Caching is now handled by the mcp client
                                
                                # Store result in state
                                if is_state_dict:
                                    section_key = section_title.lower().replace(" ", "_")
                                    if section_key not in state["data"]:
                                        state["data"][section_key] = {}
                                    state["data"][section_key]["tavily"] = section_data
                                else:
                                    section_key = section_title.lower().replace(" ", "_")
                                    if not hasattr(state.data, section_key):
                                        setattr(state.data, section_key, {})
                                    section_data_obj = getattr(state.data, section_key)
                                    section_data_obj["tavily"] = section_data
                                    
                                self.logger.info(f"Stored direct Tavily results for section: {section_title}")
                                
                            except Exception as e:
                                self.logger.error(f"Error in direct Tavily call for section '{section_title}': {str(e)}")
                                if is_state_dict and section_title not in state["problem_sections"]:
                                    state["problem_sections"].append(section_title)
                                elif not is_state_dict and section_title not in state.problem_sections:
                                    state.problem_sections.append(section_title)
                
                # Process each endpoint from RAG for this section
                for endpoint in endpoints_for_section:
                    # Skip if this endpoint has already been processed
                    if endpoint in self.processed_endpoints:
                        self.logger.info(f"Endpoint {endpoint} already processed. Skipping.")
                        continue
                        
                    try:
                        # Invoke the tool for this endpoint
                        self.logger.info(f"Section '{section_title}': Invoking tool for endpoint: {endpoint}")
                        result = await self._invoke_tool_for_endpoint(endpoint, project_name)
                        
                        # Mark as processed to avoid duplicate calls
                        self.processed_endpoints.add(endpoint)
                        
                        # Store result in state
                        if is_state_dict:
                            section_key = section_title.lower().replace(" ", "_")
                            if section_key not in state["data"]:
                                state["data"][section_key] = {}
                            
                            # Extract source from endpoint
                            source = endpoint.split("://")[1].split("/")[0] if "://" in endpoint else "unknown"
                            if source not in state["data"][section_key]:
                                state["data"][section_key][source] = result
                        else:
                            # Similar logic for object-style state
                            section_key = section_title.lower().replace(" ", "_")
                            if not hasattr(state.data, section_key):
                                setattr(state.data, section_key, {})
                            
                            # Extract source from endpoint
                            source = endpoint.split("://")[1].split("/")[0] if "://" in endpoint else "unknown"
                            section_data = getattr(state.data, section_key)
                            if source not in section_data:
                                section_data[source] = result
                    except Exception as e:
                        self.logger.error(f"Error processing endpoint {endpoint} for section '{section_title}': {str(e)}")
                        # Add to problem sections if there's an error
                        if is_state_dict and section_title not in state["problem_sections"]:
                            state["problem_sections"].append(section_title)
                        elif not is_state_dict and section_title not in state.problem_sections:
                            state.problem_sections.append(section_title)
            
            # Process visualizations from report_config
            if "visualization_types" in report_config:
                for viz_type, viz_config in report_config["visualization_types"].items():
                    # Skip visualizations without proper configuration
                    if not viz_config.get("data_source") or not viz_config.get("data_field"):
                        self.logger.warning(f"Skipping visualization {viz_type}: missing data_source or data_field")
                        continue
                        
                    # Get the section this visualization belongs to
                    section_title = viz_config.get("section", "General")
                    data_source = viz_config.get("data_source")
                    data_field = viz_config.get("data_field")
                    
                    # Check if we already have this data from batch processing
                    already_fetched = False
                    if data_source in self.data and data_field in self.data[data_source]:
                        self.logger.info(f"Section '{section_title}', Viz '{viz_type}': Already have data for '{data_field}' from batch processing")
                        already_fetched = True
                    
                    if already_fetched:
                        continue
                    
                    # --- RAG Query for Visualization Data ---
                    viz_rag_query = f"{project_name} {data_field} {data_source}" 
                    self.logger.info(f"Section '{section_title}', Viz '{viz_type}': Processing field '{data_field}' from source '{data_source}' using RAG query: '{viz_rag_query}'")
                    
                    endpoints_for_viz = []
                    try:
                        if self.rag_retriever:
                            self.logger.info(f"Attempting RAG endpoint retrieval for viz query: '{viz_rag_query}'")
                            endpoints_for_viz = await asyncio.wait_for(
                                self.rag_retriever.get_endpoints_for_project(viz_rag_query), 
                                timeout=5.0
                            )
                            # Filter out HuggingFace endpoints - we'll use them only as fallbacks
                            endpoints_for_viz = [
                                endpoint for endpoint in endpoints_for_viz
                                if "huggingface" not in endpoint
                            ]
                            self.logger.info(f"RAG retrieved {len(endpoints_for_viz)} endpoints for viz query '{viz_rag_query}': {endpoints_for_viz}")
                        else:
                            self.logger.warning("RAG retriever not available for visualization, using fallback endpoints")
                            # Use tool calls directly instead of hardcoded endpoints
                            endpoints_for_viz = []
                    except Exception as e:
                        self.logger.error(f"Error in RAG retrieval for viz '{viz_type}': {str(e)}")
                        endpoints_for_viz = []
                    
                    # Process each endpoint for this visualization
                    primary_source_success = False
                    for endpoint in endpoints_for_viz:
                        # Skip if this endpoint has already been processed
                        if endpoint in self.processed_endpoints:
                            self.logger.info(f"Viz endpoint {endpoint} already processed. Skipping.")
                            continue
                            
                        try:
                            # Invoke the tool for this endpoint
                            self.logger.info(f"Viz '{viz_type}': Invoking tool for endpoint: {endpoint}")
                            result = await self._invoke_tool_for_endpoint(endpoint, project_name)
                            
                            # Mark as processed to avoid duplicate calls
                            self.processed_endpoints.add(endpoint)
                            
                            # Check if we got valid data
                            if result and "error" not in self._safe_get_dict(result) and "data_unavailable" not in self._safe_get_dict(result):
                                primary_source_success = True
                                
                                # Store result in visualization_data
                                if is_state_dict:
                                    viz_key = f"{section_title.lower().replace(' ', '_')}.{viz_type}"
                                    if viz_key not in state["visualization_data"]:
                                        state["visualization_data"][viz_key] = {}
                                    
                                    # Extract source and field from endpoint
                                    source = endpoint.split("://")[1].split("/")[0] if "://" in endpoint else "unknown"
                                    state["visualization_data"][viz_key][f"{source}.{data_field}"] = result
                                else:
                                    # Similar logic for object-style state
                                    viz_key = f"{section_title.lower().replace(' ', '_')}.{viz_type}"
                                    if not hasattr(state.visualization_data, viz_key):
                                        setattr(state.visualization_data, viz_key, {})
                                    
                                    # Extract source and field from endpoint
                                    source = endpoint.split("://")[1].split("/")[0] if "://" in endpoint else "unknown"
                                    viz_data = getattr(state.visualization_data, viz_key)
                                    viz_data[f"{source}.{data_field}"] = result
                        except Exception as e:
                            self.logger.error(f"Error processing endpoint {endpoint} for viz '{viz_type}': {str(e)}")
                    
                    # If all primary sources failed, try HuggingFace as fallback
                    if not primary_source_success:
                        self.logger.warning(f"All primary sources failed for data field '{data_field}'. Trying HuggingFace as fallback.")
                        
                        # Create HuggingFace fallback endpoint
                        hf_endpoint = f"data://huggingface/research/{project_name} {data_field} {data_source}"
                        
                        # Skip if this HuggingFace endpoint has already been processed
                        if hf_endpoint in self.processed_endpoints:
                            self.logger.info(f"HuggingFace fallback endpoint {hf_endpoint} already processed. Skipping.")
                            continue
                            
                        try:
                            self.logger.info(f"Using HuggingFace as fallback for data field '{data_field}'")
                            result = await self._invoke_tool_for_endpoint(hf_endpoint, project_name)
                            
                            # Mark as processed to avoid duplicate calls
                            self.processed_endpoints.add(hf_endpoint)
                            
                            # Check if we got valid data
                            if result and "error" not in self._safe_get_dict(result) and "data_unavailable" not in self._safe_get_dict(result):
                                # Store result in visualization_data
                                if is_state_dict:
                                    viz_key = f"{section_title.lower().replace(' ', '_')}.{viz_type}"
                                    if viz_key not in state["visualization_data"]:
                                        state["visualization_data"][viz_key] = {}
                                    
                                    state["visualization_data"][viz_key][f"huggingface.{data_field}"] = result
                                else:
                                    # Similar logic for object-style state
                                    viz_key = f"{section_title.lower().replace(' ', '_')}.{viz_type}"
                                    if not hasattr(state.visualization_data, viz_key):
                                        setattr(state.visualization_data, viz_key, {})
                                    
                                    viz_data = getattr(state.visualization_data, viz_key)
                                    viz_data[f"huggingface.{data_field}"] = result
                            else:
                                self.logger.warning(f"HuggingFace fallback failed for data field '{data_field}': {result.get('error', 'Unknown error')}")
                        except Exception as e:
                            self.logger.error(f"Error using HuggingFace fallback for data field '{data_field}': {str(e)}")
            
            # Consolidate all fetched data into state
            self.logger.info("Consolidating fetched data into state... (Refinement likely needed)")
            
            # Process each key in self.data
            for key, value in self.data.items():
                if key == "tavily_sections":
                    # Handle tavily section data specially
                    for section_key, section_data in value.items():
                        # Convert section_key back to title format for matching
                        section_title = section_key.replace("_", " ").title()
                        
                        # Find matching section in report_config
                        for section in report_config.get("sections", []):
                            if section.get("title", "").lower().replace(" ", "_") == section_key:
                                # Found matching section, store data
                                if is_state_dict:
                                    if section_key in state["data"]:
                                        self.logger.info(f"Section data for '{section_title}' from tavily already exists. Not overwriting.")
                                    else:
                                        state["data"][section_key] = {"tavily": section_data}
                                else:
                                    if hasattr(state.data, section_key):
                                        self.logger.info(f"Section data for '{section_title}' from tavily already exists. Not overwriting.")
                                    else:
                                        setattr(state.data, section_key, {"tavily": section_data})
                                break
                else:
                    # Handle other data sources
                    for field_key, field_data in value.items():
                        # Store in state.data for general access
                        if is_state_dict:
                            if key not in state["data"]:
                                state["data"][key] = {}
                            state["data"][key][field_key] = field_data
                        else:
                            if not hasattr(state.data, key):
                                setattr(state.data, key, {})
                            source_data = getattr(state.data, key)
                            source_data[field_key] = field_data
            
            # Report problem sections
            problem_count = len(state["problem_sections"] if is_state_dict else state.problem_sections)
            self.logger.info(f"Problem sections reported: {problem_count}")
            
            self.logger.info("Completed execute_workflow")
            return state
            
        except Exception as e:
            self.logger.error(f"Error in execute_workflow: {str(e)}", exc_info=True)
            if is_state_dict:
                if "errors" not in state:
                    state["errors"] = []
                state["errors"].append(str(e))
            else:
                if not hasattr(state, 'errors'):
                    state.errors = []
                state.errors.append(str(e))
            return state

    async def _invoke_tool_for_endpoint(self, endpoint_pattern: str, project_name: str, query: Optional[str] = None) -> Dict[str, Any]:
        """Formats endpoint pattern INCLUDING identifiers in the path and calls fetch_data."""
        logger.info(f"Invoking tool for endpoint pattern: '{endpoint_pattern}' for project '{project_name}' with query '{query}'")
        
        source = "unknown"
        tool_name_for_cache = "unknown"
        query_param_for_cache = project_name.lower() # Default for cache key
        formatted_endpoint_for_call = endpoint_pattern # Start with pattern
        call_params = {} # Parameters to pass to fetch_data
        safe_name = project_name.lower().strip()

        try:
            # --- 1. Format Endpoint Path with Identifiers --- 
            if "://" in endpoint_pattern:
                 parts = endpoint_pattern.split("://")
                 path = parts[1]
                 source = path.strip("/").split("/")[0]
            else:
                 logger.warning(f"Received endpoint pattern '{endpoint_pattern}' is not a valid URI.")
                 # Attempt to proceed? Or return error? Let's try proceeding cautiously.
                 source = endpoint_pattern # Best guess for source
                 formatted_endpoint_for_call = endpoint_pattern # Use as is

            # Replace placeholders WITHIN the endpoint string
            if '{coin}' in formatted_endpoint_for_call: formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{coin}', safe_name)
            if '{protocol}' in formatted_endpoint_for_call: formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{protocol}', safe_name)
            if '{project}' in formatted_endpoint_for_call: formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{project}', safe_name)
            
            # Handle {query} placeholder - key area for tavily fix
            if '{query}' in formatted_endpoint_for_call:
                if query:
                    # Use the full, formatted query from the section template
                    formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{query}', query)
                    tool_name_for_cache = "research"  # Use a consistent tool name 
                    query_param_for_cache = query     # Use the FULL query for caching
                    logger.info(f"Using full query string '{query}' for research endpoint")
                else:
                    # If no query provided, use project name as a fallback
                    formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{query}', safe_name)
                    tool_name_for_cache = "research"
                    query_param_for_cache = safe_name
                    logger.warning(f"No query string for pattern '{endpoint_pattern}', using project name for {{query}}.")
                  
            # Handle {project_name} placeholder - replace it if present
            if '{project_name}' in formatted_endpoint_for_call:
                 formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{project_name}', safe_name)

            # --- 2. Prepare Minimal Params for fetch_data --- 
            # The original fetch_data extracts main id from path, so only pass project_name if needed.
            # Crucially, DO NOT pass coin/protocol/query here if they are already in the path.
            call_params['project_name'] = project_name
            
            # Determine tool name for cache based on the *original pattern* before param substitution
            try:
                 path_parts_cache = endpoint_pattern.split("://")[1].strip("/").split("/")
                 if tool_name_for_cache == "unknown": # If not set by {query}
                     if len(path_parts_cache) > 1:
                          tool_name_for_cache = path_parts_cache[1] # Use resource part (e.g., 'market', 'tvl')
                     else:
                          tool_name_for_cache = source # Fallback to source
            except Exception:
                 tool_name_for_cache = endpoint_pattern # Fallback
                 
            logger.info(f"Prepared call: Endpoint='{formatted_endpoint_for_call}', Params={call_params}, CacheKey=({source}, {tool_name_for_cache}, {query_param_for_cache})")

        except Exception as format_err:
             logger.error(f"Error preparing call for endpoint pattern '{endpoint_pattern}': {str(format_err)}", exc_info=True)
             return {
                 "error": f"Endpoint preparation error: {str(format_err)}",
                 "endpoint_pattern": endpoint_pattern,
                 "data_unavailable": True,
                 "source": "error"
             }

        # --- 3. Check Cache --- 
        try:
            cache_mgr = CacheManager(project_name=project_name)
            
            # Use standardized cache path generation
            cache_path = cache_mgr.get_cache_path(source, tool_name_for_cache, query_param_for_cache)
            self.logger.info(f"Using standardized cache path: {cache_path}")
            
            cached_data = cache_mgr.load(source, tool_name_for_cache, query_param_for_cache)
            if cached_data:
                self.logger.info(f"Using cached data for {endpoint_pattern} (key: {source}_{tool_name_for_cache}_{query_param_for_cache})")
                if isinstance(cached_data, dict):
                     cached_data.setdefault("source", source)
                     return cached_data
                else:
                     return {"data": cached_data, "source": source, "from_cache": True}

            # --- 4. Fetch from MCP (using formatted endpoint and minimal params) --- 
            self.logger.info(f"No cache hit for {endpoint_pattern}. Calling fetch_data with Endpoint='{formatted_endpoint_for_call}', Params={call_params}")
            
            # Call fetch_data with the formatted endpoint string and minimal params with a timeout
            try:
                self.logger.info(f"Setting 15-second timeout for fetch_data call to {formatted_endpoint_for_call}")
                async with asyncio.timeout(15.0):  # 15-second timeout to prevent hanging
                    fetched_data = await self.mcp_client.fetch_data(formatted_endpoint_for_call, params=call_params)
                    self.logger.info(f"fetch_data completed successfully for {formatted_endpoint_for_call}")
            except asyncio.TimeoutError:
                self.logger.error(f"TIMEOUT during fetch_data call to {formatted_endpoint_for_call}")
                return {
                    "error": f"Timeout fetching data from {formatted_endpoint_for_call}",
                    "endpoint_pattern": endpoint_pattern,
                    "data_unavailable": True,
                    "source": "timeout"
                }
            
            # Process the response
            processed_result = self._safe_handle_response(fetched_data, formatted_endpoint_for_call, query_param_for_cache)
            processed_result["source"] = source

            # Save the processed result to cache
            if "error" not in processed_result: # Only cache successful results
                 cache_mgr.save(processed_result, source, tool_name_for_cache, query_param_for_cache)
                 self.logger.info(f"Saved fetched data to cache for {endpoint_pattern} (key: {source}_{tool_name_for_cache}_{query_param_for_cache})")
            else:
                 self.logger.warning(f"Result for {endpoint_pattern} contained an error, not caching. Error: {processed_result.get('error')}")
            
            return processed_result
            
        # --- 5. Handle Exceptions during Cache/Fetch --- 
        except Exception as e:
            self.logger.error(f"Error executing tool for endpoint pattern '{endpoint_pattern}' (Formatted Endpoint: {formatted_endpoint_for_call}, Params: {call_params}): {str(e)}", exc_info=True)
            return {
                "error": f"Tool execution error: {str(e)}",
                "endpoint_pattern": endpoint_pattern,
                "formatted_endpoint_called": formatted_endpoint_for_call,
                "call_params": call_params,
                "query": query,
                "data_unavailable": True,
                "source": "error"
            }

    def _safe_handle_response(self, result, endpoint, project_param):
        """Process API responses to ensure they're properly formatted as dictionaries."""
        self.logger.debug(f"Handling response for endpoint: {endpoint}")
        if isinstance(result, dict):
            return result
        elif isinstance(result, str):
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    return parsed
                return {
                    "data": parsed,
                    "endpoint": endpoint,
                    "query": project_param,
                    "warning": "Response was parsed JSON but not a dictionary"
                }
            except:
                return {
                    "text": result,
                    "endpoint": endpoint,
                    "query": project_param,
                    "warning": "Unexpected string response"
                }
        elif isinstance(result, list):
            return {
                "results": result,
                "endpoint": endpoint,
                "query": project_param,
                "count": len(result)
            }
        else:
            return {
                "error": f"Unexpected response type: {type(result).__name__}",
                "endpoint": endpoint,
                "query": project_param
            }

    def _safe_get_dict(self, data):
        """Safely get dictionary data, handling string or other non-dict types."""
        if isinstance(data, dict):
            return data
        elif isinstance(data, str):
            if data.strip().startswith('{') and data.strip().endswith('}'):
                try:
                    parsed = json.loads(data)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception as e:
                    self.logger.warning(f"Error parsing JSON string: {str(e)}")
            return {"content": data, "error": "Data was a string, not a proper response object"}
        else:
            return {"error": f"Unexpected data type: {type(data).__name__}"}

    def _safe_update_dict(self, target_dict, source_data):
        """Safely update a dictionary with source data, handling non-dict source types."""
        source_dict = self._safe_get_dict(source_data)
        
        for key, value in source_dict.items():
            if value is not None and isinstance(value, (dict, list, str, int, float, bool)):
                if key in target_dict and target_dict[key] != value:
                    if isinstance(target_dict[key], dict) and "conflict" in target_dict[key]:
                        previous_sources = [item.get("source", "unknown") for item in target_dict[key]["values"]]
                        source_name = source_dict.get("source", "unknown")
                        if source_name not in previous_sources:
                            target_dict[key]["values"].append({
                                "source": source_name,
                                "value": value
                            })
                            self.logger.info(f"Added additional conflict value for {key} from source {source_name}")
                    else:
                        previous_value = target_dict[key]
                        previous_source = target_dict.get("source", "previous_source")
                        current_source = source_dict.get("source", "current_source")
                        target_dict[key] = {
                            "values": [
                                {"source": previous_source, "value": previous_value},
                                {"source": current_source, "value": value}
                            ],
                            "conflict": True
                        }
                        self.logger.warning(f"Detected conflict for {key} between {previous_source} and {current_source}")
                else:
                    target_dict[key] = value
            else:
                self.logger.warning(f"Skipping invalid data for key {key}: {value}")
                
        return target_dict

    async def _get_fallback_data(self, project_name: str) -> Dict[str, Any]:
        """
        Attempt to retrieve fallback data from alternative sources when primary sources fail.
        
        Args:
            project_name: Name of the project to retrieve data for
            
        Returns:
            Dictionary containing available data or data_unavailable flag
        """
        self.logger.info(f"Attempting fallback data retrieval for {project_name}")
        
        # Generate fallback endpoints to try
        fallback_endpoints = [
            f"data://huggingface/tokenomics/{project_name.lower()}",
            f"data://tokenomics/distribution/{project_name.lower()}",
            f"research://tavily/tokenomics {project_name}"
        ]
        
        # Try each fallback endpoint
        for endpoint in fallback_endpoints:
            try:
                self.logger.info(f"Trying fallback endpoint: {endpoint}")
                data = await self._invoke_tool_for_endpoint(endpoint, project_name)
                if data and "error" not in self._safe_get_dict(data):
                    self.logger.info(f"Fallback data retrieved from {endpoint}")
                    return data
                self.logger.warning(f"Fallback endpoint {endpoint} returned no valid data")
            except Exception as e:
                self.logger.warning(f"Fallback endpoint {endpoint} failed: {str(e)}")
        
        # Return unavailable data response if all fallbacks fail
        self.logger.info(f"No fallback data available for {project_name}")
        return {
            "data_unavailable": True,
            "source": "unavailable",
            "message": f"Data for {project_name} is not available from any verifiable sources."
        }

    async def _run_parallel_tavily_searches(self, section_queries: Dict[str, str], project_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Run multiple Tavily searches in parallel.
        
        Args:
            section_queries: Dictionary of section titles to search queries
            project_name: The cryptocurrency project name
            
        Returns:
            Dictionary of section titles to search results
        """
        self.logger.info(f"Running parallel Tavily searches for sections: {list(section_queries.keys())}")
        
        section_data = {}
        
        async def search_section(section_title):
            try:
                query = section_queries[section_title]
                self.logger.info(f"Executing Tavily search for section: {section_title}")
                
                # Use direct tool call to tavily research
                try:
                    # Create a cache key for this specific search - use section_title as the key
                    cache_manager = CacheManager(project_name=project_name)
                    # The section_title serves as the cache key
                    cached_data = cache_manager.load("tavily", "research", section_title)
                    
                    if cached_data:
                        self.logger.info(f"Using cached Tavily data for section '{section_title}'")
                        section_data[section_title] = cached_data
                    else:
                        self.logger.info(f"Fetching fresh Tavily data for section '{section_title}'")
                        # FIXED: Specify "tavily" as the server name
                        result = await self.mcp_client.call_tool("tavily", "research", query=query, project_name=project_name, cache_key=section_title)
                        section_data[section_title] = result
                        self.logger.info(f"Successfully retrieved Tavily data for section '{section_title}'")
                except Exception as inner_e:
                    self.logger.error(f"Error in Tavily search for section '{section_title}': {str(inner_e)}")
                    section_data[section_title] = {"error": str(inner_e), "results": []}
            except Exception as e:
                self.logger.error(f"Error processing section '{section_title}': {str(e)}")
                section_data[section_title] = {"error": str(e), "results": []}
        
        # Run all searches in parallel
        await asyncio.gather(*[search_section(title) for title in section_queries])
        
        return section_data

    async def extract_token_distribution(self, project_name: str) -> Dict[str, Any]:
        """
        Extract token distribution data for a project with proper cache handling.
        
        Args:
            project_name: Name of the project to extract token distribution for
            
        Returns:
            Dict containing token distribution data or data_unavailable flag
        """
        self.logger.info(f"Extracting token distribution data for {project_name}")
        
        # Use the CacheManager to check for cached data first
        cache_manager = CacheManager(project_name=project_name)
        cached_data = cache_manager.load("tokenomics", "distribution", project_name.lower())
        
        # If we have valid cached data, return it
        if cached_data:
            self.logger.info(f"Using cached token distribution data for {project_name}")
            return cached_data
            
        # Otherwise, fetch fresh data using the tokenomics tool
        self.logger.info(f"Fetching fresh token distribution data for {project_name}")
        
        try:
            # Use named parameters for call_tool method
            tokenomics_data = await self.mcp_client.call_tool("tokenomics", "get_distribution", project=project_name, project_name=project_name)
            
            # Cache the results if we got valid data
            if tokenomics_data and "error" not in tokenomics_data:
                self.logger.info(f"Successfully retrieved token distribution for {project_name}")
                cache_manager.save(tokenomics_data, "tokenomics", "distribution", project_name.lower())
                return tokenomics_data
            else:
                self.logger.warning(f"Failed to retrieve token distribution for {project_name}")
                error_msg = tokenomics_data.get('error', 'Unknown error') if tokenomics_data else "Failed to retrieve token distribution data"
                return {"error": error_msg}
        except Exception as e:
            self.logger.error(f"Error extracting token distribution for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def _batch_process_project_data(self, report_config: Dict, project_name: str) -> None:
        """
        Batch process all API calls for a project to minimize redundant API requests.
        This method analyzes the report_config, identifies all required data sources and fields,
        and makes consolidated API calls to each source once per project.
        
        Args:
            report_config: The report configuration containing sections and visualization types
            project_name: Name of the project being researched
        """
        self.logger.info(f"Starting batch processing of all API data for project: {project_name}")
        
        # Initialize storage for batch results if not present
        if "batch_data" not in self.data:
            self.data["batch_data"] = {}
        
        # 1. Collect all required data sources and fields from report_config
        required_sources = {
            "coingecko": set(),
            "coinmarketcap": set(),
            "defillama": set(),
            "tokenomics": set(),
            "tavily": set()  # Always include Tavily
        }
        
        # Extract from visualization types
        if 'visualization_types' in report_config:
            for viz_type, viz_config in report_config['visualization_types'].items():
                data_source = viz_config.get('data_source', '').lower()
                if data_source in required_sources:
                    # Add data_field if present
                    if 'data_field' in viz_config and viz_config['data_field']:
                        required_sources[data_source].add(viz_config['data_field'])
                    
                    # Add data_fields if present
                    if 'data_fields' in viz_config and isinstance(viz_config['data_fields'], list):
                        required_sources[data_source].update(viz_config['data_fields'])
        
        # Extract from section data_sources
        for section in report_config.get('sections', []):
            for source in section.get('data_sources', []):
                if source.lower() in required_sources:
                    # Just note that this source is needed (specific fields will be determined by API)
                    required_sources[source.lower()].add('*')
            
            # Always include tavily for each section
            required_sources["tavily"].add(section.get('title', '').lower().replace(' ', '_'))
        
        # Ensure tavily is always processed regardless of explicit requirement
        required_sources["tavily"].add('*')
        
        # Log what we found
        for source, fields in required_sources.items():
            if fields:
                self.logger.info(f"Batch processing will fetch from {source}: {list(fields)}")
        
        # 2. Process each data source in parallel
        tasks = []
        
        # CoinGecko batch processing
        if required_sources["coingecko"]:
            tasks.append(self._batch_process_coingecko(project_name))
        
        # CoinMarketCap batch processing
        if required_sources["coinmarketcap"]:
            tasks.append(self._batch_process_coinmarketcap(project_name))
        
        # DeFiLlama batch processing
        if required_sources["defillama"]:
            tasks.append(self._batch_process_defillama(project_name))
        
        # Tokenomics batch processing
        if required_sources["tokenomics"]:
            tasks.append(self._batch_process_tokenomics(project_name))
        
        # Tavily batch processing - ALWAYS include this
        tasks.append(self._batch_process_tavily(project_name))
        
        # Execute all batch processing tasks in parallel
        if tasks:
            self.logger.info(f"Executing {len(tasks)} batch processing tasks in parallel")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error in batch processing task {i}: {str(result)}")
        
        self.logger.info(f"Completed batch processing for project: {project_name}")
    
    async def _batch_process_coingecko(self, project_name: str) -> Dict[str, Any]:
        """Batch process all CoinGecko API calls for a project."""
        self.logger.info(f"Batch processing CoinGecko data for {project_name}")
        
        try:
            # Use direct tool call instead of hardcoded endpoint
            cache_manager = CacheManager(project_name=project_name)
            cached_data = cache_manager.load("coingecko", "data", project_name.lower())
            
            if cached_data:
                self.logger.info(f"Using cached CoinGecko data for {project_name}")
                self.data["batch_data"]["coingecko"] = cached_data
                return cached_data
            
            self.logger.info(f"Calling CoinGecko tool directly for {project_name}")
            # Use named parameters for call_tool method
            coingecko_data = await self.mcp_client.call_tool("coingecko", "get_batch_data", coin=project_name, project_name=project_name)
            
            if coingecko_data:
                self.logger.info(f"Successfully retrieved CoinGecko data for {project_name}")
                cache_manager.save(coingecko_data, "coingecko", "data", project_name.lower())
                self.data["batch_data"]["coingecko"] = coingecko_data
                return coingecko_data
            else:
                self.logger.warning(f"Failed to retrieve CoinGecko data for {project_name}")
                return {"error": "Failed to retrieve CoinGecko data"}
                
        except Exception as e:
            self.logger.error(f"Error in batch processing CoinGecko data for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    async def _batch_process_coinmarketcap(self, project_name: str) -> Dict[str, Any]:
        """Batch process all CoinMarketCap API calls for a project."""
        self.logger.info(f"Batch processing CoinMarketCap data for {project_name}")
        
        try:
            # Use direct tool call instead of hardcoded endpoint
            cache_manager = CacheManager(project_name=project_name)
            cached_data = cache_manager.load("coinmarketcap", "data", project_name.lower())
            
            if cached_data:
                self.logger.info(f"Using cached CoinMarketCap data for {project_name}")
                self.data["batch_data"]["coinmarketcap"] = cached_data
                return cached_data
            
            self.logger.info(f"Calling CoinMarketCap tool directly for {project_name}")
            # Use named parameters for call_tool method
            cmc_data = await self.mcp_client.call_tool("coinmarketcap", "get_batch_data", coin=project_name, project_name=project_name)
            
            if cmc_data:
                self.logger.info(f"Successfully retrieved CoinMarketCap data for {project_name}")
                cache_manager.save(cmc_data, "coinmarketcap", "data", project_name.lower())
                self.data["batch_data"]["coinmarketcap"] = cmc_data
                return cmc_data
            else:
                self.logger.warning(f"Failed to retrieve CoinMarketCap data for {project_name}")
                return {"error": "Failed to retrieve CoinMarketCap data"}
        except Exception as e:
            self.logger.error(f"Error in batch processing CoinMarketCap data for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    async def _batch_process_defillama(self, project_name: str) -> Dict[str, Any]:
        """Batch process all DeFiLlama API calls for a project."""
        self.logger.info(f"Batch processing DeFiLlama data for {project_name}")
        
        try:
            # Use direct tool call instead of hardcoded endpoint
            cache_manager = CacheManager(project_name=project_name)
            cached_data = cache_manager.load("defillama", "tvl", project_name.lower())
            
            if cached_data:
                self.logger.info(f"Using cached DeFiLlama data for {project_name}")
                self.data["batch_data"]["defillama"] = cached_data
                return cached_data
            
            self.logger.info(f"Calling DeFiLlama tool directly for {project_name}")
            # Use named parameters for call_tool method
            defillama_data = await self.mcp_client.call_tool("defillama", "get_protocol_data", protocol=project_name, project_name=project_name)
            
            if defillama_data:
                self.logger.info(f"Successfully retrieved DeFiLlama data for {project_name}")
                cache_manager.save(defillama_data, "defillama", "tvl", project_name.lower())
                self.data["batch_data"]["defillama"] = defillama_data
                return defillama_data
            else:
                self.logger.warning(f"Failed to retrieve DeFiLlama data for {project_name}")
                return {"error": "Failed to retrieve DeFiLlama data"}
                
        except Exception as e:
            self.logger.error(f"Error in batch processing DeFiLlama data for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    async def _batch_process_tokenomics(self, project_name: str) -> Dict[str, Any]:
        """Batch process all Tokenomics API calls for a project."""
        self.logger.info(f"Batch processing Tokenomics data for {project_name}")
        
        try:
            # Use direct tool call instead of hardcoded endpoint
            cache_manager = CacheManager(project_name=project_name)
            cached_data = cache_manager.load("tokenomics", "distribution", project_name.lower())
            
            if cached_data:
                self.logger.info(f"Using cached Tokenomics data for {project_name}")
                self.data["batch_data"]["tokenomics"] = cached_data
                return cached_data
            
            self.logger.info(f"Calling Tokenomics tool directly for {project_name}")
            # Use named parameters for call_tool method
            tokenomics_data = await self.mcp_client.call_tool("tokenomics", "get_distribution", project=project_name, project_name=project_name)
            
            if tokenomics_data:
                self.logger.info(f"Successfully retrieved Tokenomics data for {project_name}")
                cache_manager.save(tokenomics_data, "tokenomics", "distribution", project_name.lower())
                self.data["batch_data"]["tokenomics"] = tokenomics_data
                return tokenomics_data
            else:
                self.logger.warning(f"Failed to retrieve Tokenomics data for {project_name}")
                return {"error": "Failed to retrieve Tokenomics data"}
                
        except Exception as e:
            self.logger.error(f"Error in batch processing Tokenomics data for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def _batch_process_tavily(self, project_name: str, report_config: Dict = None) -> Dict[str, Any]:
        """Batch process all Tavily API calls for a project.
        This creates a separate cache file for each section, enabling section-specific research.
        
        Args:
            project_name: Name of the project to research
            report_config: Optional report configuration with sections
            
        Returns:
            Dict containing Tavily search results organized by section
        """
        self.logger.info(f"Batch processing Tavily data for {project_name}")
        
        try:
            # Initialize batch_data if it doesn't exist
            if not hasattr(self, 'data'):
                self.data = {}
            if "batch_data" not in self.data:
                self.data["batch_data"] = {}
            
            # Define section-specific queries based on report_config
            # Standard required sections as fallback
            standard_sections = [
                "market_analysis", 
                "tokenomics", 
                "team_overview",
                "technology",
                "competition",
                "risks",
                "future_developments"
            ]
            
            # Extract sections from report_config if available
            config_sections = []
            if report_config and isinstance(report_config, dict) and "sections" in report_config:
                for section in report_config["sections"]:
                    if "title" in section:
                        section_key = section["title"].lower().replace(' ', '_')
                        config_sections.append(section_key)
                self.logger.info(f"Extracted {len(config_sections)} sections from report_config")
            
            # Use sections from report_config if available, otherwise use standard sections
            sections = config_sections if config_sections else standard_sections
            self.logger.info(f"Processing {len(sections)} sections: {sections}")
            
            section_queries = {}
            for section in sections:
                # Create section-specific query using section name
                formatted_section = section.replace('_', ' ')
                section_queries[section] = f"{project_name} cryptocurrency {formatted_section}"
            
            # Run section-specific searches
            self.logger.info(f"Processing {len(section_queries)} sections with Tavily")
            
            # Maintain results for all sections
            all_section_results = {}
            
            # Process each section with a specific cache key
            for section, query in section_queries.items():
                try:
                    self.logger.info(f"Processing section '{section}' with query: '{query}'")
                    
                    # First check if we have cached data for this section
                    cache_manager = CacheManager(project_name=project_name)
                    cached_data = cache_manager.load("tavily", "research", section)
                    
                    if cached_data:
                        self.logger.info(f"Using cached Tavily data for section '{section}'")
                        all_section_results[section] = cached_data
                    else:
                        self.logger.info(f"Fetching fresh Tavily data for section '{section}'")
                        # Use section as the cache key to create section-specific cache files
                        result = await self.mcp_client.call_tool("tavily", "research", query=query, project_name=project_name, cache_key=section)
                        
                        if result and "error" not in result:
                            all_section_results[section] = result
                            self.logger.info(f"Successfully retrieved and cached Tavily data for section '{section}'")
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else f"Failed to retrieve Tavily data for section {section}"
                            self.logger.warning(f"Error in section '{section}': {error_msg}")
                            all_section_results[section] = {"error": error_msg, "results": []}
                except Exception as e:
                    self.logger.error(f"Error processing section '{section}': {str(e)}")
                    all_section_results[section] = {"error": str(e), "results": []}
            
            # Store the section results in the batch data
            self.data["batch_data"]["tavily"] = all_section_results
            
            # Check if cache files were created properly
            for section in sections:
                cache_path = os.path.join("docs", project_name.lower(), "cache", "tavily", f"research_{section}.json")
                if os.path.exists(cache_path):
                    self.logger.info(f"✅ Verified cache for '{section}' exists at: {cache_path}")
                else:
                    self.logger.warning(f"❌ Cache file missing for '{section}': {cache_path}")
            
            return all_section_results
                
        except Exception as e:
            self.logger.error(f"Error in batch processing Tavily data for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}

async def researcher(state, llm=None, logger=None, config=None):
    """Async function interface for researcher."""
    logger = logger or logging.getLogger(__name__)
    logger.info("Using async researcher function")
    
    logger.info("Creating Researcher instance for async function")
    researcher_instance = Researcher(logger=logger)
    logger.info("Calling initialize for async function")
    await researcher_instance.initialize()
    logger.info("Calling run for async function")
    return await researcher_instance.run(state)

def researcher_sync(state: Dict, llm: Optional[Any] = None, logger: Optional[logging.Logger] = None, config: Optional[Dict[str, Any]] = None) -> Dict:
    """Synchronous wrapper for the Researcher class (fallback)."""
    logger = logger or logging.getLogger(__name__)
    project_name = state.get("project_name", "Unknown Project")
    logger.info(f"Starting researcher_sync for project: {project_name}")
    
    try:
        logger.info("Creating Researcher instance")
        researcher_instance = Researcher(logger=logger)
        logger.info("Researcher instance created")
        logger.info("Running synchronous execution")
        # Use asyncio.run for sync context (fallback)
        result = asyncio.run(researcher_instance.run(state))
        logger.info("Sync execution completed")
        return result
    except Exception as e:
        logger.error(f"Error in researcher_sync: {str(e)}", exc_info=True)
        updated_state = state.copy() if isinstance(state, dict) else state
        if isinstance(updated_state, dict):
            if "errors" not in updated_state:
                updated_state["errors"] = {}
            updated_state["errors"]["researcher"] = str(e)
        return updated_state