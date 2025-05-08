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
            if "web_research" not in state["data"]: state["data"]["web_research"] = {}
        else: # Assuming ResearchState object
            if not hasattr(state, "problem_sections"): state.problem_sections = []
            if not hasattr(state, "data"): state.data = {}
            if not hasattr(state, "visualization_data"): state.visualization_data = {}
            # Use getattr for safe check before accessing nested attribute
            data_attr = getattr(state, "data", None)
            if isinstance(data_attr, dict) and "web_research" not in data_attr:
                data_attr["web_research"] = {}
            elif not isinstance(data_attr, dict):
                 self.logger.error(f"State object 'data' attribute is not a dict: {type(data_attr)}. Cannot initialize web_research.")
                 state.data = {"web_research": {}} # Reset data if it's not a dict

        
        self.logger.info(f'Executing research for {project_name}')

        cache_mgr = CacheManager(project_name=project_name)
        data_fields_needed_for_viz = set()
        sections = report_config.get('sections', [])
        
        if not sections:
             self.logger.warning("No sections found in report_config. Research may be incomplete.")
             # Decide how to handle this - maybe return state early or try a default query?
             # For now, let it continue, but it will likely fetch nothing.

        # First pass: Collect all data fields needed for visualizations across all sections
        if report_config and 'visualization_types' in report_config:
            for section in sections:
                for viz_type in section.get('visualizations', []):
                    if viz_type in report_config['visualization_types']:
                        viz_config = report_config['visualization_types'][viz_type]
                        if 'data_field' in viz_config and viz_config['data_field']:
                            data_fields_needed_for_viz.add(viz_config['data_field'])
                        if 'data_fields' in viz_config:
                            data_fields_needed_for_viz.update(viz_config['data_fields'])
            self.logger.info(f'Data fields needed for visualizations: {list(data_fields_needed_for_viz)}')
        else:
             self.logger.warning("No 'visualization_types' found in report_config. Cannot determine data fields needed for visualizations.")


        results = {} # Stores raw results keyed by endpoint
        successful_sources = set()
        problem_sections_list = []
        
        # --- Main Loop: Iterate through sections to fetch data ---
        for section in sections:
            section_title = section.get('title', 'Unknown Section')
            section_data_sources = section.get('data_sources', [])
            section_query_template = section.get('query_template')
            section_missing_sources = []
            self.logger.info(f"Processing section: '{section_title}' | Required sources: {section_data_sources}")

            # --- 1. Use RAG for Section-Level Data Needs ---
            if section_query_template:
                formatted_section_query = section_query_template.format(project_name=project_name)
                self.logger.info(f"Section '{section_title}': Running RAG with query: '{formatted_section_query}'")
                section_endpoints = []
                try:
                    if self.rag_retriever:
                        section_endpoints = await asyncio.wait_for(
                            self.rag_retriever.get_endpoints_for_project(formatted_section_query, project_name=project_name),
                            timeout=30.0
                        )
                        # Filter problematic endpoints
                        section_endpoints = [
                            endpoint for endpoint in section_endpoints
                            if "://project/" not in endpoint
                            and "://multi/" not in endpoint
                            and not endpoint in ["project", "multi", "tokenomics", "defillama", "coingecko", "coinmarketcap"]
                        ]
                        self.logger.info(f"RAG retrieved {len(section_endpoints)} endpoints for section query: {section_endpoints}")
                    else:
                        self.logger.warning("RAGRetriever unavailable; Cannot dynamically fetch section-level data.")

                    # Invoke tools for endpoints found by RAG for the section query
                    for endpoint in section_endpoints:
                        # Use a unique key for results dict based on section and endpoint
                        result_key = f"section_{section_title}_{endpoint}" 
                        # Avoid re-fetching if already fetched (e.g., by another section's RAG query)
                        if result_key in results:
                             self.logger.info(f"Endpoint {endpoint} already processed for section '{section_title}'. Skipping.")
                             continue
                             
                        self.logger.info(f"Section '{section_title}': Invoking tool for RAG-selected endpoint: {endpoint}")
                        
                        # Pass the full formatted_section_query to _invoke_tool_for_endpoint for tavily/research endpoints
                        endpoint_result = await asyncio.wait_for(
                            self._invoke_tool_for_endpoint(
                                endpoint, 
                                project_name,
                                # Important: Pass the formatted section query to use in research calls
                                query=formatted_section_query if "/research/" in endpoint else None
                            ), 
                            timeout=45.0 # Increase timeout for potential web searches
                        )
                        
                        results[result_key] = endpoint_result # Store raw result

                        # Store result in state (needs careful consolidation later)
                        # For now, just track successful sources based on RAG results
                        try:
                            source = endpoint.split("://")[1].split("/")[0]
                            if "error" not in self._safe_get_dict(endpoint_result):
                                successful_sources.add(source)
                            else:
                                section_missing_sources.append(f"{endpoint} (error: {endpoint_result.get('error', 'Unknown')})")
                        except IndexError:
                            self.logger.warning(f"Could not determine source from section endpoint: {endpoint}")
                            if "error" in self._safe_get_dict(endpoint_result):
                                section_missing_sources.append(f"{endpoint} (error)")
                                
                except asyncio.TimeoutError:
                    self.logger.error(f"Timeout retrieving/processing RAG endpoints for section '{section_title}' query: '{formatted_section_query}'")
                    section_missing_sources.append(f"Section RAG Query Timeout")
                except Exception as e:
                    self.logger.error(f"Error retrieving/processing RAG endpoints for section '{section_title}' query '{formatted_section_query}': {str(e)}", exc_info=True)
                    section_missing_sources.append(f"Section RAG Query Error: {str(e)}")
            else:
                self.logger.warning(f"Section '{section_title}' has no 'query_template'. Skipping RAG-based data fetching for this section.")

            # --- 2. Handle Visualization-Specific Data Sources (RAG + Fallback) ---
            section_missing_viz_fields = []
            for viz_type in section.get('visualizations', []):
                if 'visualization_types' not in report_config or viz_type not in report_config['visualization_types']:
                    self.logger.warning(f"Visualization type '{viz_type}' for section '{section_title}' not found in report_config['visualization_types']. Skipping.")
                    continue
                
                viz_config = report_config['visualization_types'][viz_type]
                data_source = viz_config.get('data_source', '').lower()
                viz_data_fields = viz_config.get('data_fields', [])
                if not isinstance(viz_data_fields, list):
                    self.logger.warning(f"'data_fields' for viz '{viz_type}' is not a list ({type(viz_data_fields)}). Initializing as empty list.")
                    viz_data_fields = []
                if 'data_field' in viz_config and viz_config['data_field']:
                    viz_data_fields.append(viz_config['data_field'])
                
                if not data_source or not viz_data_fields:
                    self.logger.warning(f"Skipping visualization {viz_type} in section '{section_title}': missing data_source ('{data_source}') or data_fields ('{viz_data_fields}')")
                    continue
                
                for data_field in set(viz_data_fields): 
                     data_field = data_field.lower()
                     
                     # Check if already fetched (more robust check might be needed)
                     # Key difference: Check specific viz endpoints in results, not section keys
                     potential_viz_endpoint = f"data://{data_source}/{data_field}/{project_name.lower()}" # Example format
                     # A better check might involve iterating results keys and parsing
                     already_fetched = False
                     for key in results.keys():
                          # Simplistic check, assumes endpoint structure might match
                          if f"/{data_field}/" in key and source in key:
                               if "error" not in self._safe_get_dict(results[key]):
                                    self.logger.info(f"Data for '{data_field}' from source '{data_source}' possibly fetched by section RAG or other viz. Skipping viz-specific fetch.")
                                    already_fetched = True
                                    successful_sources.add(data_source) # Assume success
                                    break
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
                                 self.rag_retriever.get_endpoints_for_project(viz_rag_query, project_name=project_name),
                                 timeout=30.0
                             )
                             # Filter problematic endpoints
                             endpoints_for_viz = [
                                 endpoint for endpoint in endpoints_for_viz
                                 if "://project/" not in endpoint
                                 and "://multi/" not in endpoint
                                 and not endpoint in ["project", "multi", "tokenomics", "defillama", "coingecko", "coinmarketcap"]
                             ]
                             self.logger.info(f"RAG retrieved {len(endpoints_for_viz)} endpoints for viz query '{viz_rag_query}': {endpoints_for_viz}")
                         else:
                             self.logger.warning("RAGRetriever unavailable; using fallback endpoints for visualization data")
                         
                         if not endpoints_for_viz:
                             # --- !!! IMPORTANT: Correct Fallback Endpoint Construction !!! ---
                             # Construct fallback based on source and expected resource path
                             # These need to match the @mcp.resource definitions in server files
                             if data_source == "defillama":
                                 # DefiLlama server likely uses protocol name/slug (project_name) or specific field
                                 # Example: data://defillama/tvl/{protocol} -> use project_name?
                                 # Example: data://defillama/chains/{protocol} -> use project_name?
                                 # Let's try using the data_field as the resource subpath for now
                                 fallback_endpoint = f"data://defillama/{data_field}/{project_name.lower()}" 
                             elif data_source == "coinmarketcap":
                                 # CMC likely needs coin symbol/name
                                 # Example: data://coinmarketcap/quotes/{symbol} -> use project_name
                                 # Example: data://coinmarketcap/ohlcv/{symbol} -> use project_name
                                 # Let's try data_field as subpath
                                 fallback_endpoint = f"data://coinmarketcap/{data_field}/{project_name.lower()}"
                             elif data_source == "coingecko":
                                 # CoinGecko likely needs coin id (project_name)
                                 # Example: data://coingecko/market_chart/{id}
                                 fallback_endpoint = f"data://coingecko/{data_field}/{project_name.lower()}"
                             elif data_source == "tokenomics":
                                 # Tokenomics server might need project name
                                 # Example: data://tokenomics/distribution/{project}
                                 fallback_endpoint = f"data://tokenomics/{data_field}/{project_name.lower()}"
                             elif data_source == "multi": # This source seems problematic / undefined
                                  # Remove fallback to 'multi' source - it doesn't exist
                                  self.logger.error(f"Source 'multi' does not exist. Skipping data field '{data_field}'")
                                  section_missing_viz_fields.append(f"{data_field} (source 'multi' does not exist)")
                                  continue # Skip this field completely
                             elif data_source == "project": # This source is problematic / undefined
                                  # Remove fallback to 'project' source - it doesn't exist
                                  self.logger.error(f"Source 'project' does not exist. Skipping data field '{data_field}'")
                                  section_missing_viz_fields.append(f"{data_field} (source 'project' does not exist)")
                                  continue # Skip this field completely
                             else:
                                 # Default fallback (might often be wrong)
                                 fallback_endpoint = f"data://{data_source}/{data_field}/{project_name.lower()}"
                                 self.logger.warning(f"Using generic fallback endpoint format for source '{data_source}': {fallback_endpoint}")

                             self.logger.warning(f"No endpoints retrieved via RAG for viz query '{viz_rag_query}'. Using fallback: {fallback_endpoint}")
                             endpoints_for_viz = [fallback_endpoint]
                             
                     except asyncio.TimeoutError:
                         self.logger.error(f"Timeout retrieving endpoints via RAG for viz query: '{viz_rag_query}'")
                         results[f"viz_rag_error_{data_source}_{data_field}"] = {"error": "RAG timeout for viz data", "data_unavailable": True}
                         section_missing_viz_fields.append(f"{data_field} (RAG timeout)")
                         continue 
                     except Exception as e:
                         self.logger.error(f"Error retrieving endpoints via RAG for viz query '{viz_rag_query}': {str(e)}")
                         results[f"viz_rag_error_{data_source}_{data_field}"] = {"error": f"RAG error for viz data: {str(e)}", "data_unavailable": True}
                         section_missing_viz_fields.append(f"{data_field} (RAG error: {str(e)})")
                         continue 

                     # --- Invoke Tools for Visualization Endpoints ---
                     for endpoint in endpoints_for_viz:
                          # Avoid re-fetching if the exact endpoint was already processed
                          if endpoint in results:
                               self.logger.info(f"Viz endpoint {endpoint} already processed. Skipping.")
                               continue
                          # --- Start Try Block for Viz Endpoint Invocation ---
                          try: 
                             # Project placeholder replacement likely not needed for fallbacks, but keep for RAG results
                             endpoint = endpoint.replace('{project}', project_name.lower()) 
                             
                             self.logger.info(f"Viz '{viz_type}': Invoking tool for endpoint: {endpoint}")
                             result = await asyncio.wait_for(
                                 self._invoke_tool_for_endpoint(
                                     endpoint, 
                                     project_name,
                                     # Pass full viz query to research endpoints
                                     query=viz_rag_query if "/research/" in endpoint else None
                                 ),
                                 timeout=45.0
                             )
                             results[endpoint] = result 

                             # Determine source from endpoint for tracking success
                             try:
                                  source = endpoint.split("://")[1].split("/")[0]
                                  if "error" not in self._safe_get_dict(result):
                                       successful_sources.add(source)
                                  else:
                                       section_missing_viz_fields.append(f"{data_field} from {source} (error: {result.get('error', 'Unknown')})")
                             except IndexError:
                                  self.logger.warning(f"Could not determine source from viz endpoint: {endpoint}")
                                  if "error" in self._safe_get_dict(result):
                                       section_missing_viz_fields.append(f"{data_field} from unknown source (error: {result.get('error', 'Unknown')})")
                          
                          # --- Correctly Indented Except Blocks --- 
                          except asyncio.TimeoutError:
                             self.logger.error(f"Timeout fetching data for viz endpoint {endpoint}")
                             results[endpoint] = {"error": "Timeout fetching viz data", "data_unavailable": True}
                             section_missing_viz_fields.append(f"{data_field} (fetch timeout)")
                          except Exception as e:
                             self.logger.error(f"Error processing viz endpoint {endpoint}: {str(e)}", exc_info=True)
                             results[endpoint] = {"error": f"Viz data error: {str(e)}", "data_unavailable": True}
                             section_missing_viz_fields.append(f"{data_field} (fetch error: {str(e)})")
            
            # Combine missing sources/fields for the section report
            section_problems = section_missing_sources + section_missing_viz_fields
            if section_problems:
                problem_sections_list.append({'title': section_title, 'missing_items': list(set(section_problems))}) # Use set to deduplicate
        
        # --- Consolidate Data for State (NEEDS REFINEMENT) ---
        # This part needs careful review to handle data from both section RAG and viz RAG/fallback
        self.logger.info("Consolidating fetched data into state... (Refinement likely needed)")
        viz_data_consolidated = {} # Data structured primarily for visualizations {source: {field: value}}
        all_data_consolidated = {} # Broader structure {source: {data...}} potentially including section data

        # Process all results
        for key, data in results.items():
            if key.startswith("viz_rag_error_"):
                continue # Skip RAG error placeholders
            
            if "error" in self._safe_get_dict(data):
                self.logger.warning(f"Skipping consolidation for key '{key}' due to error: {data.get('error')}")
                continue

            # Try to determine source and potentially field/section info from key
            source = "unknown"
            field = "unknown"
            is_section_data = key.startswith("section_")
            endpoint = "" # Initialize endpoint

            if is_section_data:
                # Find the start of the endpoint URI after section_TITLE_
                try:
                    # Find the first part that looks like a protocol scheme
                    uri_start_index = key.find("://")
                    # Search backwards from there to find the preceding underscore
                    separator_index = key.rfind("_", len("section_"), uri_start_index)
                    if separator_index != -1 and uri_start_index != -1:
                         endpoint = key[separator_index + 1:]
                    else:
                         # Fallback if format is unexpected
                         self.logger.warning(f"Could not reliably parse endpoint from section key: {key}. Using fallback split.")
                         endpoint = key.split("_")[-1] 
                except Exception:
                     self.logger.error(f"Error parsing section key '{key}' for endpoint.", exc_info=True)
                     endpoint = key.split("_")[-1] # Fallback
            else:
                 endpoint = key # If not section data, key is the endpoint

            # --- Start Try Block --- 
            try: 
                # Parse endpoint info
                if "://" in endpoint:
                     source = endpoint.split("://")[1].split("/")[0]
                     parts = endpoint.split("/")
                     field = parts[3] if len(parts) > 3 else parts[-1] 
                else:
                     self.logger.warning(f"Cannot determine source/field from parsed endpoint '{endpoint}' (Original key: '{key}')")
                     continue # Skip if source cannot be determined
                 
                processed_data = self._safe_get_dict(data)
                 
                # Initialize source dicts if needed
                if source not in all_data_consolidated: all_data_consolidated[source] = {}
                if source not in viz_data_consolidated: viz_data_consolidated[source] = {}

                # --- Consolidation Strategy --- 
                if is_section_data:
                    section_title_from_key = key.split("_")[1]
                    if section_title_from_key not in all_data_consolidated[source]:
                         all_data_consolidated[source][section_title_from_key] = processed_data
                    else:
                         self.logger.info(f"Section data for '{section_title_from_key}' from {source} already exists. Not overwriting.")
                else: # Visualization data
                    if field in processed_data:
                         current_value = processed_data[field]
                    elif 'data' in processed_data and isinstance(processed_data['data'], dict) and field in processed_data['data']:
                         current_value = processed_data['data'][field]
                    else:
                         current_value = processed_data
                         self.logger.warning(f"Could not extract specific field '{field}' from viz result for {endpoint}. Storing entire result.")
                    
                    # Assign values with correct indentation
                    viz_data_consolidated[source][field] = current_value
                    all_data_consolidated[source][field] = current_value 
            
            # --- Catch Errors during parsing/consolidation ---    
            except Exception as e: 
                self.logger.error(f"Error during consolidation for key {key}: {str(e)}", exc_info=True)
            # --- End Try-Except Block --- 

        # Add error indicator if all sources failed
        if not successful_sources and len(results) > 0:
             self.logger.error('All data sources seem to have failed or returned errors.')
             error_value = "No valid data found for any source"
             if is_state_dict:
                 # Ensure dicts exist before adding error key
                 if not isinstance(state.get("visualization_data"), dict): state["visualization_data"] = {}
                 if not isinstance(state.get("data"), dict): state["data"] = {}
                 state["visualization_data"]['error'] = error_value
                 state["data"]['error'] = error_value
             else: # Assuming object
                  if not hasattr(state, "visualization_data") or not isinstance(state.visualization_data, dict):
                       state.visualization_data = {}
                  if not hasattr(state, "data") or not isinstance(state.data, dict):
                       state.data = {}
                  state.visualization_data['error'] = error_value
                  state.data['error'] = error_value

        # --- Update State --- 
        if is_state_dict:
             state["visualization_data"] = viz_data_consolidated
             state["problem_sections"] = problem_sections_list
             state["data"] = all_data_consolidated # Assign the main consolidated data
             # Remove multi-source rebuilding logic
             # multi_source_data = {}
             # ... (loop removed) ...
             # state["data"]["multi"] = multi_source_data

        else: # Assume state object
             state.visualization_data = viz_data_consolidated
             state.problem_sections = problem_sections_list
             state.data = all_data_consolidated # Assign the main consolidated data
             # Remove multi-source rebuilding logic
             # multi_source_data = {}
             # ... (loop removed) ...
             # if not isinstance(state.data, dict):
             #      state.data = {}
             # state.data["multi"] = multi_source_data

        # Log final state structure
        final_viz_keys = list(state["visualization_data"].keys()) if is_state_dict else list(getattr(state, "visualization_data", {}).keys())
        final_data_keys = list(state["data"].keys()) if is_state_dict else list(getattr(state, "data", {}).keys())
        final_problems = state["problem_sections"] if is_state_dict else getattr(state, "problem_sections", [])
        
        self.logger.info(f"Consolidated visualization_data sources: {final_viz_keys}")
        self.logger.info(f"Consolidated state.data sources: {final_data_keys}")
        self.logger.info(f"Problem sections reported: {len(final_problems)}")
        self.logger.info("Completed execute_workflow")
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

    async def _run_parallel_tavily_searches(self, report_config: Dict, project_name: str) -> None:
        """
        Run Tavily searches for multiple report sections in parallel.
        
        Args:
            report_config: The report configuration containing sections
            project_name: Name of the project being researched
            
        Returns:
            None - results are stored in self.data["tavily_sections"]
        """
        self.logger.info(f"Setting up parallel Tavily searches for {project_name}")
        
        # Initialize storage for tavily results if not present
        if "tavily_sections" not in self.data:
            self.data["tavily_sections"] = {}
        
        # Extract section titles and prepare queries
        section_titles = []
        section_queries = {}
        
        for section in report_config.get("sections", []):
            title = section.get("title")
            query_template = section.get("query_template")
            if title and query_template:
                formatted_query = query_template.format(project_name=project_name)
                section_titles.append(title)
                section_queries[title] = formatted_query
        
        # Set up batch processing
        batch_size = 3  # Process 3 sections at a time to limit concurrent API calls
        num_batches = (len(section_titles) + batch_size - 1) // batch_size
        
        self.logger.info(f"Processing {len(section_titles)} sections in {num_batches} batches")
        
        # Process each batch
        for batch_idx in range(num_batches):
            batch_start = batch_idx * batch_size
            batch_end = min((batch_idx + 1) * batch_size, len(section_titles))
            batch_section_titles = section_titles[batch_start:batch_end]
            
            self.logger.info(f"Processing batch {batch_idx+1}/{num_batches} with {len(batch_section_titles)} sections")
            
            # Define search function for a single section
            async def search_section(section_title):
                try:
                    query = section_queries[section_title]
                    self.logger.info(f"Executing Tavily search for section: {section_title}")
                    
                    # Use the _invoke_tool_for_endpoint method to leverage existing caching
                    endpoint = f"research://tavily/{query}"
                    section_data = await self._invoke_tool_for_endpoint(endpoint, project_name, query=query)
                    
                    return section_title, section_data
                except Exception as e:
                    self.logger.error(f"Error in Tavily search for section {section_title}: {str(e)}", exc_info=True)
                    return section_title, {"error": str(e), "data_unavailable": True}
            
            # Execute searches for this batch in parallel
            try:
                results = await asyncio.gather(
                    *(search_section(title) for title in batch_section_titles),
                    return_exceptions=True
                )
                
                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        self.logger.error(f"Exception in batch search: {str(result)}")
                        continue
                        
                    section_title, section_data = result
                    
                    # Store results in data
                    section_key = section_title.lower().replace(" ", "_")
                    self.data["tavily_sections"][section_key] = section_data
                    self.logger.info(f"Stored Tavily results for section: {section_title}")
                    
            except Exception as batch_error:
                self.logger.error(f"Error processing batch {batch_idx+1}: {str(batch_error)}", exc_info=True)
            
            # Short delay between batches to avoid rate limiting
            if batch_idx < num_batches - 1:
                await asyncio.sleep(2)
        
        self.logger.info(f"Completed parallel Tavily searches - processed {len(self.data['tavily_sections'])} sections")
        return None

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
        cached_data, from_cache = cache_manager.load_from_cache("tokenomics", "distribution", project_name.lower())
        
        # Log cache expiration
        if from_cache and not cached_data:
            self.logger.info(f"Cached token distribution for {project_name} is expired")
            
        # If we have valid cached data, return it
        if cached_data:
            self.logger.info(f"Using cached token distribution data for {project_name}")
            return cached_data
            
        # Otherwise, fetch new data
        self.logger.info(f"Fetching fresh token distribution data for {project_name}")
        try:
            # Attempt to fetch from tokenomics endpoint
            endpoint = f"data://tokenomics/distribution/{project_name.lower()}"
            distribution_data = await self._invoke_tool_for_endpoint(endpoint, project_name)
            
            if distribution_data and "error" not in self._safe_get_dict(distribution_data):
                self.logger.info(f"Successfully retrieved token distribution for {project_name}")
                return distribution_data
                
            # Try fallback if primary source fails
            self.logger.warning(f"Primary source failed for token distribution of {project_name}, trying fallbacks")
            return await self._get_fallback_data(project_name)
            
        except Exception as e:
            self.logger.error(f"Error extracting token distribution for {project_name}: {str(e)}", exc_info=True)
            return await self._get_fallback_data(project_name)

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