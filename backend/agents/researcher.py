# researcher.py
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
    from backend.utils.data_standardizer import DataStandardizer
    from backend.utils.state_manager import StateManager
except ModuleNotFoundError:
    from state import ResearchState
    from orchestration.mcp.client_manager import MCPClientManager
    from utils.cache_utils import CacheManager
    from orchestration.rag.retriever import RAGRetriever
    from orchestration.rag.vector_store import get_vector_store
    from utils.data_standardizer import DataStandardizer
    from utils.state_manager import StateManager

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
        
        # Initialize StateManager for consistent state access
        self.state_manager = StateManager(logger=self.logger)
        
        self.logger.info("Researcher constructor started")

        # Define core data queries for RAG-driven fetching of project-wide data
        self.CORE_DATA_QUERIES = [
            {
                "concept": "overview",
                "query_template": "{project_name} market overview, including current price, market cap, 24h volume, circulating supply, total supply, max supply, and a brief description.",
                "target_sources": ["coinmarketcap", "coingecko"], # Primary sources for general overview
                "description_for_report": "Fetches general market overview, current price, market cap, 24h volume, etc."
            },
            {
                "concept": "price_history", 
                "query_template": "{project_name} cryptocurrency 30-day price history OHLCV", 
                "target_sources": ["coinmarketcap", "coingecko"],
                "description": "Fetches 30-day historical price data (Open, High, Low, Close, Volume)."
            },
            {
                "concept": "volume_history", 
                "query_template": "{project_name} cryptocurrency 30-day trading volume history", 
                "target_sources": ["coinmarketcap", "coingecko"],
                "description": "Fetches 30-day historical trading volume."
            },
            {
                "concept": "protocol_data_tvl", 
                "query_template": "{project_name} DeFi protocol data including Total Value Locked (TVL) and historical TVL", 
                "target_sources": ["defillama"],
                "description": "Fetches comprehensive DeFi protocol data, including current and historical TVL."
            },
            {
                "concept": "token_distribution", 
                "query_template": "{project_name} cryptocurrency tokenomics, supply, and distribution details", 
                "target_sources": ["tokenomics", "huggingface"], # Added huggingface as a fallback for tokenomics
                "description": "Fetches details about token supply, allocation, and distribution."
            }
            # Add more core data concepts as needed
        ]
        self.logger.info("Researcher constructor completed")
    
    async def initialize(self):
        """Initialize RAG and MCP components."""
        self.logger.info("Starting Researcher.initialize")
        try:
            self.logger.info('Initializing RAG components')
            try:
                self.logger.info("Getting vector store synchronously")
                self.vector_store = get_vector_store()
                self.logger.info("Vector store object created")
                if not self.vector_store or not self.vector_store.is_healthy():
                    self.logger.error("Vector store initialization failed or store is not healthy.")
                    self.vector_store = None
                else:
                    self.logger.info("Vector store appears healthy")
            except Exception as e:
                self.logger.error(f"Error getting vector store instance: {str(e)}", exc_info=True)
                self.vector_store = None
            
            if self.vector_store:
                self.logger.info("Initializing RAGRetriever")
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
            
            # Servers are started by MCPClientManager during WorkflowManager initialization
            self.logger.info('MCP servers should already be running via WorkflowManager')
            
            self.logger.info('RAG and MCP components initialized successfully')
        except Exception as e:
            self.logger.error(f'Error initializing RAG and MCP components: {str(e)}', exc_info=True)
            raise
        self.logger.info("Completed Researcher.initialize")

    async def run(self, state: Union[ResearchState, Dict]) -> Union[ResearchState, Dict]:
        """Run the researcher to collect data for the given project."""
        self.logger.info("Entering Researcher.run")
        
        try:
            self.project_name = self.state_manager.get_project_name(state)
            self.logger.info(f"Running researcher for {self.project_name}")
            
            self.cache_dir = os.path.join("reports", self.project_name.lower(), "cache")
            os.makedirs(self.cache_dir, exist_ok=True)
            self.logger.info(f"Cache directory set to: {self.cache_dir}")
            
            self.logger.info("Calling initialize")
            await asyncio.wait_for(self.initialize(), timeout=30.0)
            self.logger.info("Initialize completed")
            
            self.logger.info("Calling execute_workflow")
            result = await asyncio.wait_for(self.execute_workflow(query_or_state=state), timeout=300.0)
            self.logger.info("Completed Researcher.run")
            return result
            
        except asyncio.TimeoutError:
            self.logger.error("Researcher.run timed out after 300 seconds")
            error_msg = "Researcher timed out"
            return self.state_manager.add_error(state, "researcher", error_msg)
        except Exception as e:
            self.logger.error(f"Error in researcher run: {str(e)}", exc_info=True)
            error_msg = f"Researcher error: {str(e)}"
            return self.state_manager.add_error(state, "researcher", error_msg)
    
    async def execute_workflow(self, query_or_state: Any, context: Dict[str, Any] = None) -> Any:
        """Execute the research workflow using RAG to select MCP endpoints."""
        self.logger.info("Entering execute_workflow")
        context = context or {}
        
        state = query_or_state
        project_name = self.state_manager.get_project_name(state)
        report_config = self.state_manager.get_report_config(state)
        
        if not report_config:
            self.logger.warning("No report_config found in state")
            report_config = {}
            
        self.project_name = project_name.lower()
        self.logger.info(f"Project name: {self.project_name}")
        
        state = self.state_manager.ensure_state_structure(state)
        
        try:
            self.processed_endpoints = set()
            await self._fetch_core_project_data_via_rag(project_name)
            
            if "batch_data" in self.data and "tavily" in self.data["batch_data"]:
                section_research_results = self.data["batch_data"]["tavily"]
                for section_key, section_data in section_research_results.items():
                    section_title = None
                    for section in report_config.get("sections", []):
                        if section.get("title", "").lower().replace(" ", "_") == section_key:
                            section_title = section.get("title")
                            break
                    
                    if section_title:
                        current_section_data = self.state_manager.get_section_data(state, section_title) or {}
                        current_section_data["tavily"] = section_data
                        state = self.state_manager.update_section_data(state, section_title, current_section_data)
            
            for section in report_config.get("sections", []):
                section_title = section.get("title")
                if not section_title:
                    continue
                    
                # Normalize data_sources: ensure it's a list, handle "web_research" consistently
                # All sources, including 'web_research', will go through the RAG process.
                data_sources = section.get("data_sources", [])
                if isinstance(data_sources, str):
                    data_sources = [data_sources]
                
                # Map "web_research" to "tavily" for RAG consistency if needed,
                # though RAGRetriever also has logic for this.
                # For clarity here, we ensure 'tavily' is used if 'web_research' is specified.
                required_sources_for_section = []
                for src in data_sources:
                    if src.lower() == "web_research":
                        if "tavily" not in required_sources_for_section: # Avoid duplicates
                            required_sources_for_section.append("tavily")
                    elif src.lower() not in required_sources_for_section: # Avoid duplicates
                        required_sources_for_section.append(src.lower())

                self.logger.info(f"Processing section: '{section_title}' | Required sources: {required_sources_for_section}")
                
                # Attempt to use pre-fetched core data if concepts are listed for the section
                section_data_found_in_core = False
                if section.get("data_concepts_needed"):
                    for concept in section.get("data_concepts_needed"):
                        if concept in self.data["batch_data"] and self.data["batch_data"][concept] and not self.data["batch_data"][concept].get("error"):
                            section_data_found_in_core = True
                            self.logger.info(f"All data for section '{section_title}' found in pre-fetched core data. Skipping RAG/tool invocation.")
                            continue

                # If not all data was found in core, or no core concepts needed, proceed with RAG for the section
                if not section_data_found_in_core:
                    section_query_template = section.get("query_template")
                    if section_query_template:
                        query = section_query_template.format(project_name=self.project_name)
                        self.logger.info(f"Section '{section_title}': Running RAG with query: '{query}' and sources: {required_sources_for_section}")
                        
                        try:
                            # Pass the required_sources_for_section to RAG
                            endpoints = await self.rag_retriever.get_endpoints_for_project(
                                query,
                                required_sources=required_sources_for_section if required_sources_for_section else None,
                                top_k=5 # Fetch a few relevant endpoints for sections
                            )
                            self.logger.info(f"RAG retrieved {len(endpoints)} endpoints for section query: {endpoints}")

                            if endpoints:
                                for endpoint in endpoints:
                                    if endpoint in self.processed_endpoints:
                                        self.logger.info(f"Endpoint {endpoint} already processed. Skipping.")
                                        continue
                                    
                                    try:
                                        self.logger.info(f"Section '{section_title}': Invoking tool for endpoint: {endpoint}")
                                        result = await self._invoke_tool_for_endpoint(endpoint, project_name, query=query, cache_key=section_title)
                                        self.processed_endpoints.add(endpoint)
                                        
                                        if result:
                                            source = endpoint.split("://")[1].split("/")[0] if "://" in endpoint else "unknown"
                                            current_section_data = self.state_manager.get_section_data(state, section_title) or {}
                                            current_section_data[source] = result
                                            state = self.state_manager.update_section_data(state, section_title, current_section_data)
                                    except Exception as e:
                                        self.logger.error(f"Error processing endpoint {endpoint} for section '{section_title}': {str(e)}")
                                        problem_sections = self.state_manager.get_problem_sections(state) or []
                                        if not any(ps.get("title") == section_title for ps in problem_sections):
                                            problem_sections.append({"title": section_title, "missing_fields": [source]})
                                            state = self.state_manager.update_problem_sections(state, problem_sections)
                            else:
                                self.logger.warning(f"RAGRetriever returned no suitable endpoints for section '{section_title}'. Skipping RAG.")
                        except Exception as e:
                            self.logger.error(f"Error during RAG processing for section '{section_title}': {e}", exc_info=True)
                    elif required_sources_for_section:
                        # This case might indicate a config error: sources specified but no query template.
                        # Or, it might rely purely on source-based core data already fetched.
                        # For now, we log if it seems like RAG should have run but didn't due to no query.
                        self.logger.warning(f"Section '{section_title}' has required sources {required_sources_for_section} but no query_template. RAG was not performed. Ensure this is intended or core data covers needs.")
                    else:
                        self.logger.info(f"Section '{section_title}' has no query_template and no specific required_sources for RAG. Skipping RAG.")
            
            # Consolidate all fetched data into state
            self.logger.info("Consolidating additional fetched data into state...")
            for key, value in self.data.items():
                if key != "batch_data":
                    for field_key, field_data in value.items():
                        state = self.state_manager.update_data_field(state, key, field_key, field_data)
            
            # Report problem sections
            problem_sections = self.state_manager.get_problem_sections(state) or []
            self.logger.info(f"Problem sections reported: {len(problem_sections)}")
            
            # Standardize data for visualizations
            self.logger.info("Standardizing data for visualizations")
            try:
                data_standardizer = DataStandardizer(logger=self.logger, state_manager=self.state_manager)
                state = data_standardizer.standardize_state_data(state, report_config)
                self.logger.info("Data standardization complete")
            except Exception as e:
                self.logger.error(f"Error standardizing data: {str(e)}", exc_info=True)
                state = self.state_manager.add_error(state, "data_standardizer", f"Error standardizing data: {str(e)}")
            
            self.logger.info("Completed execute_workflow")
            return state
            
        except Exception as e:
            self.logger.error(f"Error in execute_workflow: {str(e)}", exc_info=True)
            return self.state_manager.add_error(state, "researcher", f"Error in execute_workflow: {str(e)}")

    async def _fetch_core_project_data_via_rag(self, project_name: str) -> None:
        """
        Fetches core, project-wide data points using RAG to determine the best endpoint for each predefined concept.
        Results are stored in self.data['batch_data'][<concept_name>].
        """
        self.logger.info(f"Starting RAG-driven fetching of core project data for: {project_name}")

        if not self.rag_retriever:
            self.logger.error("RAG retriever is not initialized. Cannot fetch core project data.")
            return

        if "batch_data" not in self.data: # Ensure batch_data dict exists
            self.data["batch_data"] = {}

        # Ensure a set to track successfully processed core concepts to avoid redundant calls if a concept maps to multiple RAG queries later
        # This is distinct from self.already_processed_endpoints which is for section-level generic endpoint tracking
        successfully_fetched_core_concepts = set()

        for item in self.CORE_DATA_QUERIES:
            concept = item["concept"]
            query = item["query_template"].format(project_name=project_name)
            target_sources = item["target_sources"]
            description = item.get("description", "core data point")

            self.logger.info(f"Processing core concept: '{concept}' ({item.get('description_for_report', query)})")
            
            # Check if data for this concept already exists from a previous step (e.g. resume from interruption)
            if concept in self.data["batch_data"] and self.data["batch_data"][concept] and not self.data["batch_data"][concept].get("error"):
                self.logger.info(f"Core concept '{concept}' already present in self.data['batch_data']. Skipping RAG fetch.")
                continue

            try:
                endpoints = await self.rag_retriever.get_endpoints_for_project(
                    query,
                    required_sources=target_sources,
                    top_k=1 # We want the single best endpoint for each core concept
                )

                if endpoints and isinstance(endpoints, list) and len(endpoints) > 0:
                    endpoint_to_call = endpoints[0] # Take the top_k=1 result
                    self.logger.info(f"RAG selected endpoint '{endpoint_to_call}' for core concept '{concept}' with query '{query}'")
                    
                    # Use a more specific cache key for core data to avoid collision with section-specific calls to same endpoint
                    core_data_cache_key_suffix = f"core_concept_{concept}"

                    # Invoke the tool for the selected endpoint
                    # Pass the original concept query for potential use in _invoke_tool_for_endpoint if needed for specific tools
                    fetched_data = await self._invoke_tool_for_endpoint(
                        endpoint_pattern=endpoint_to_call, 
                        project_name=project_name, 
                        query_for_formatting=query, # Pass the concept-specific query
                        section_key_for_cache=core_data_cache_key_suffix # Use concept for specific caching
                    )
                    
                    if fetched_data is not None:
                        # Store data under the concept key, and also identify the source if possible from the endpoint
                        source_name = endpoint_to_call.split('://')[1].split('/')[0] if '://' in endpoint_to_call else 'unknown_source'
                        self.data['batch_data'][concept] = {
                            "source_endpoint": endpoint_to_call,
                            "source_name": source_name,
                            "data": fetched_data
                        }
                        successfully_fetched_core_concepts.add(concept)
                        self.logger.info(f"Successfully fetched and stored data for core concept '{concept}' from '{endpoint_to_call}'")
                    else:
                        self.logger.warning(f"No data returned from endpoint '{endpoint_to_call}' for core concept '{concept}'. Storing as None.")
                        self.data['batch_data'][concept] = None # Explicitly store None if fetch fails

                else:
                    self.logger.warning(f"RAGRetriever returned no suitable endpoints for core concept '{concept}' with query: {query}. Storing as None.")
                    self.data['batch_data'][concept] = None # Explicitly store None if no endpoint found

            except Exception as e:
                self.logger.error(f"Exception during RAG-driven fetch for core concept '{concept}': {e}", exc_info=True)
                self.data['batch_data'][concept] = None # Store None on exception
        
        self.logger.info(f"Completed RAG-driven fetching of core project data. self.data['batch_data'] keys: {list(self.data['batch_data'].keys())}")
        self.logger.info(f"Successfully fetched core concepts: {successfully_fetched_core_concepts}")

    async def _invoke_tool_for_endpoint(self, endpoint_pattern: str, project_name: str, query: Optional[str] = None, cache_key: Optional[str] = None) -> Dict[str, Any]:
        """Formats endpoint pattern INCLUDING identifiers in the path and calls fetch_data."""
        self.logger.info(f"Invoking tool for endpoint pattern: '{endpoint_pattern}' for project '{project_name}' with query '{query}'")
        
        source = "unknown"
        tool_name_for_cache = "unknown"
        query_param_for_cache = project_name.lower()
        formatted_endpoint_for_call = endpoint_pattern
        call_params = {}
        safe_name = project_name.lower().strip()

        try:
            if "://" in endpoint_pattern:
                parts = endpoint_pattern.split("://")
                path = parts[1]
                source = path.strip("/").split("/")[0]
            else:
                self.logger.warning(f"Received endpoint pattern '{endpoint_pattern}' is not a valid URI.")
                source = endpoint_pattern
                formatted_endpoint_for_call = endpoint_pattern

            if '{coin}' in formatted_endpoint_for_call: formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{coin}', safe_name)
            if '{protocol}' in formatted_endpoint_for_call: formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{protocol}', safe_name)
            if '{project}' in formatted_endpoint_for_call: formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{project}', safe_name)
            
            if '{query}' in formatted_endpoint_for_call:
                if query:
                    formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{query}', query)
                    tool_name_for_cache = "research"
                    query_param_for_cache = query
                    self.logger.info(f"Using full query string '{query}' for research endpoint")
                else:
                    formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{query}', safe_name)
                    tool_name_for_cache = "research"
                    query_param_for_cache = safe_name
                    self.logger.warning(f"No query string for pattern '{endpoint_pattern}', using project name for {{query}}.")
                  
            if '{project_name}' in formatted_endpoint_for_call:
                formatted_endpoint_for_call = formatted_endpoint_for_call.replace('{project_name}', safe_name)

            call_params['project_name'] = project_name
            
            try:
                path_parts_cache = endpoint_pattern.split("://")[1].strip("/").split("/")
                if tool_name_for_cache == "unknown":
                    if len(path_parts_cache) > 1:
                        tool_name_for_cache = path_parts_cache[1]
                    else:
                        tool_name_for_cache = source
            except Exception:
                tool_name_for_cache = endpoint_pattern
                 
            self.logger.info(f"Prepared call: Endpoint='{formatted_endpoint_for_call}', Params={call_params}, CacheKey=({source}, {tool_name_for_cache}, {query_param_for_cache})")

        except Exception as format_err:
            self.logger.error(f"Error preparing call for endpoint pattern '{endpoint_pattern}': {str(format_err)}", exc_info=True)
            return {
                "error": f"Endpoint preparation error: {str(format_err)}",
                "endpoint_pattern": endpoint_pattern,
                "data_unavailable": True,
                "source": "error"
            }

        try:
            cache_mgr = CacheManager(project_name=project_name)
            
            if cache_key:
                formatted_cache_key = cache_key.lower().replace(' ', '_')
                cache_path = cache_mgr.get_cache_path(source, tool_name_for_cache, formatted_cache_key)
                self.logger.info(f"Using section-specific cache path with key '{formatted_cache_key}': {cache_path}")
                cached_data = cache_mgr.load(source, tool_name_for_cache, formatted_cache_key)
            else:
                cache_path = cache_mgr.get_cache_path(source, tool_name_for_cache, query_param_for_cache)
                self.logger.info(f"Using standardized cache path: {cache_path}")
                cached_data = cache_mgr.load(source, tool_name_for_cache, query_param_for_cache)
                
            if cached_data:
                self.logger.info(f"Using cached data for {endpoint_pattern} (key: {source}_{tool_name_for_cache}_{cache_key or query_param_for_cache})")
                if isinstance(cached_data, dict):
                    cached_data.setdefault("source", source)
                    return cached_data
                elif isinstance(cached_data, str):
                    try:
                        parsed_data = json.loads(cached_data)
                        if isinstance(parsed_data, dict):
                            parsed_data.setdefault("source", source)
                            return parsed_data
                        else:
                            self.logger.warning(f"Cached data is a string but parses to {type(parsed_data)}, not a dict")
                            return {"data": parsed_data, "source": source, "from_cache": True}
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to parse cached data as JSON for {endpoint_pattern}")
                        return {"error": "Invalid cached data format", "source": source, "from_cache": True}
                else:
                    return {"data": cached_data, "source": source, "from_cache": True}

            self.logger.info(f"No cache hit for {endpoint_pattern}. Calling fetch_data with Endpoint='{formatted_endpoint_for_call}', Params={call_params}")
            
            try:
                self.logger.info(f"Setting 15-second timeout for fetch_data call to {formatted_endpoint_for_call}")
                async with asyncio.timeout(15.0):
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
            
            processed_result = self._safe_handle_response(fetched_data, formatted_endpoint_for_call, query_param_for_cache)
            processed_result["source"] = source

            if "error" not in processed_result:
                if cache_key:
                    formatted_cache_key = cache_key.lower().replace(' ', '_')
                    cache_mgr.save(processed_result, source, tool_name_for_cache, formatted_cache_key)
                    self.logger.info(f"Saved fetched data to cache for {endpoint_pattern} (key: {source}_{tool_name_for_cache}_{formatted_cache_key})")
                else:
                    cache_mgr.save(processed_result, source, tool_name_for_cache, query_param_for_cache)
                    self.logger.info(f"Saved fetched data to cache for {endpoint_pattern} (key: {source}_{tool_name_for_cache}_{query_param_for_cache})")
            else:
                self.logger.warning(f"Result for {endpoint_pattern} contained an error, not caching. Error: {processed_result.get('error')}")
            
            return processed_result
            
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
        self.logger.debug(f"Handling response for endpoint: {endpoint}, type: {type(result)}")
        if isinstance(result, dict):
            return result
        elif isinstance(result, str):
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    self.logger.debug(f"Successfully parsed string response to dict for {endpoint}")
                    return parsed
                return {
                    "data": parsed,
                    "endpoint": endpoint,
                    "query": project_param,
                    "warning": f"Response was parsed JSON but not a dictionary, type: {type(parsed)}"
                }
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse string response as JSON for {endpoint}: {result[:200]}...")
                return {
                    "text": result,
                    "endpoint": endpoint,
                    "query": project_param,
                    "warning": "Unexpected string response, failed to parse as JSON"
                }
        elif isinstance(result, list):
            return {
                "results": result,
                "endpoint": endpoint,
                "query": project_param,
                "count": len(result),
                "source": endpoint.split("://")[1].split("/")[0] if "://" in endpoint else "unknown_list_source" # Added source
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
        
        fallback_endpoints = [
            f"data://huggingface/tokenomics/{project_name.lower()}",
            f"data://tokenomics/distribution/{project_name.lower()}",
            f"research://tavily/tokenomics {project_name}"
        ]
        
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
                
                try:
                    cache_manager = CacheManager(project_name=project_name)
                    cached_data = cache_manager.load("tavily", "research", section_title)
                    
                    if cached_data:
                        self.logger.info(f"Using cached Tavily data for section '{section_title}'")
                        section_data[section_title] = cached_data
                    else:
                        self.logger.info(f"Fetching fresh Tavily data for section '{section_title}'")
                        result = await self.mcp_client.call_tool("tavily", "research", query=query, project_name=project_name, cache_key=section_title)
                        section_data[section_title] = result
                        self.logger.info(f"Successfully retrieved Tavily data for section '{section_title}'")
                except Exception as inner_e:
                    self.logger.error(f"Error in Tavily search for section '{section_title}': {str(inner_e)}")
                    section_data[section_title] = {"error": str(inner_e), "results": []}
            except Exception as e:
                self.logger.error(f"Error processing section '{section_title}': {str(e)}")
                section_data[section_title] = {"error": str(e), "results": []}
        
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
        
        cache_manager = CacheManager(project_name=project_name)
        cached_data = cache_manager.load("tokenomics", "distribution", project_name.lower())
        
        if cached_data:
            self.logger.info(f"Using cached token distribution data for {project_name}")
            if isinstance(cached_data, str):
                try:
                    cached_data = json.loads(cached_data)
                    self.logger.debug(f"Parsed cached tokenomics data keys: {list(cached_data.keys())}")
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse cached tokenomics data as JSON for {project_name}")
                    cached_data = {"error": "Invalid cached data format"}
            if isinstance(cached_data, dict) and "error" not in cached_data:
                return cached_data
            else:
                self.logger.warning(f"Cached tokenomics data is invalid, fetching fresh data")
            
        self.logger.info(f"Fetching fresh token distribution data for {project_name}")
        
        try:
            tokenomics_data = await self.mcp_client.call_tool("tokenomics", "get_distribution", project=project_name, project_name=project_name)
            
            if isinstance(tokenomics_data, str):
                try:
                    tokenomics_data = json.loads(tokenomics_data)
                    self.logger.debug(f"Parsed tokenomics response keys: {list(tokenomics_data.keys())}")
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse tokenomics response as JSON for {project_name}")
                    return {"error": "Invalid tokenomics response format"}
            
            if tokenomics_data and isinstance(tokenomics_data, dict) and "error" not in tokenomics_data:
                self.logger.info(f"Successfully retrieved token distribution for {project_name}, keys: {list(tokenomics_data.keys())}")
                cache_manager.save(tokenomics_data, "tokenomics", "distribution", project_name.lower())
                return tokenomics_data
            else:
                self.logger.warning(f"Failed to retrieve token distribution for {project_name}")
                error_msg = tokenomics_data.get('error', 'Unknown error') if isinstance(tokenomics_data, dict) else "Failed to retrieve token distribution data"
                return {"error": error_msg}
        except Exception as e:
            self.logger.error(f"Error extracting token distribution for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def _batch_process_project_data(self, report_config: Dict, project_name: str) -> None:
        """
        Batch process all API calls for a project using RAG for source selection.
        
        Args:
            report_config: Report configuration containing required data sources
            project_name: The name of the project to process
        """
        self.logger.info(f"Starting batch processing of all API data for project: {project_name}")
        
        if not hasattr(self, 'data'):
            self.data = {}
        if "batch_data" not in self.data:
            self.data["batch_data"] = {}
            
        all_required_sources = set()
        sections_by_source = {}
        
        if "sections" in report_config:
            for section in report_config.get("sections", []):
                section_title = section.get("title")
                if not section_title:
                    continue
                
                section_key = section_title.lower().replace(" ", "_")
                sources = section.get("data_sources", [])
                if not sources:
                    continue
                
                all_required_sources.update(sources)
                
                for source in sources:
                    if source not in sections_by_source:
                        sections_by_source[source] = []
                    sections_by_source[source].append(section_key)
        
        self.logger.info(f"Found {len(all_required_sources)} unique required sources: {all_required_sources}")
        
        if "web_research" in all_required_sources:
            tasks = [self._batch_process_tavily(project_name, report_config)]
            self.logger.info(f"Including research processing for web_research")
        else:
            tasks = []
        
        for source in all_required_sources:
            if source != "web_research":
                self.logger.info(f"Processing source {source} for project {project_name}")
                if source == "coingecko":
                    tasks.append(self._batch_process_coingecko(project_name))
                elif source == "coinmarketcap":
                    tasks.append(self._batch_process_coinmarketcap(project_name))
                elif source == "defillama":
                    tasks.append(self._batch_process_defillama(project_name))
                elif source == "tokenomics":
                    tasks.append(self._batch_process_tokenomics(project_name))
                else:
                    self.logger.warning(f"No specific handler for source {source}, will rely on RAG")
        
        if tasks:
            self.logger.info(f"Executing {len(tasks)} batch processing tasks in parallel")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error in batch processing task {i}: {str(result)}")
        
        self.logger.info(f"Completed batch processing for project: {project_name}")
    
    async def _batch_process_coingecko(self, project_name: str) -> Dict[str, Any]:
        """Batch process all CoinGecko API calls for a project."""
        self.logger.info(f"Batch processing CoinGecko data for {project_name}")
        
        try:
            cache_manager = CacheManager(project_name=project_name)
            cached_data = cache_manager.load("coingecko", "data", project_name.lower())
            
            if cached_data:
                self.logger.info(f"Using cached CoinGecko data for {project_name}")
                if isinstance(cached_data, str):
                    try:
                        cached_data = json.loads(cached_data)
                        self.logger.debug(f"Parsed cached coingecko data keys: {list(cached_data.keys())}")
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to parse cached coingecko data as JSON for {project_name}")
                        cached_data = {"error": "Invalid cached data format"}
                if isinstance(cached_data, dict) and "error" not in cached_data:
                    self.data["batch_data"]["coingecko"] = cached_data
                    self.logger.debug(f"Cached CoinGecko data keys: {list(cached_data.keys())}")
                    return cached_data
                else:
                    self.logger.warning(f"Cached CoinGecko data is invalid, fetching fresh data")
            
            self.logger.info(f"Calling CoinGecko tool directly for {project_name}")
            coingecko_data = await self.mcp_client.call_tool("coingecko", "get_batch_data", coin=project_name, project_name=project_name)
            
            if isinstance(coingecko_data, str):
                try:
                    coingecko_data = json.loads(coingecko_data)
                    self.logger.debug(f"Parsed coingecko response keys: {list(coingecko_data.keys())}")
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse coingecko response as JSON for {project_name}")
                    return {"error": "Invalid coingecko response format"}
            
            if coingecko_data and isinstance(coingecko_data, dict) and "error" not in coingecko_data:
                self.logger.info(f"Successfully retrieved CoinGecko data for {project_name}, keys: {list(coingecko_data.keys())}")
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
        """Batch process CoinMarketCap API calls for a project by invoking standard endpoints for overview, price history, and volume history."""
        self.logger.info(f"Batch processing CoinMarketCap data for {project_name} by invoking standard endpoints via _invoke_tool_for_endpoint.")
        
        cmc_consolidated_data = {
            "overview": None,
            "price_history": None, 
            "volume_history": None,
            "error_in_batch": False # Flag to indicate if any part of the batch failed
        }

        endpoint_patterns_to_fetch = {
            "overview": "data://coinmarketcap/overview/{coin}",
            "price_history": "data://coinmarketcap/price_history/{coin}", # Expects 30-day OHLCV or similar
            "volume_history": "data://coinmarketcap/volume_history/{coin}"  # Expects 30-day volume
        }

        for data_key, pattern in endpoint_patterns_to_fetch.items():
            self.logger.info(f"Attempting to fetch '{data_key}' for CMC batch using pattern: {pattern}")
            try:
                # Using project_name as query, and a specific cache_key for batch context
                # _invoke_tool_for_endpoint handles its own caching logic.
                # Parameters like 'days=30' should be part of the MCP server's tool definition or passed if _invoke_tool_for_endpoint is enhanced.
                # For now, assuming the server tools default to 30 days or the patterns are specific enough.
                # If specific params like 'days' are needed and not part of the pattern, this approach needs refinement or _invoke_tool_for_endpoint needs enhancement.
                # For this iteration, we'll assume the endpoint pattern or server-side tool handles 'days=30' implicitly.
                
                # Let's construct a more unique cache key for batch items to avoid collision with section-specific calls
                # for the same endpoint, if the underlying data isn't identical (though for project-wide data it should be).
                batch_cache_key = f"batch_cmc_{data_key}"

                result = await self._invoke_tool_for_endpoint(
                    endpoint_pattern=pattern, 
                    project_name=project_name, 
                    query=project_name, # Generic query for project-level data
                    cache_key=batch_cache_key
                )
                
                if result and not result.get("error") and not result.get("data_unavailable"):
                    cmc_consolidated_data[data_key] = result
                    self.logger.info(f"Successfully fetched and stored '{data_key}' for CMC batch.")
                else:
                    error_detail = result.get("error", "Data unavailable") if isinstance(result, dict) else "Unknown error"
                    self.logger.warning(f"Failed to fetch '{data_key}' for CMC batch. Error: {error_detail}")
                    cmc_consolidated_data[data_key] = {"error": f"Failed to fetch {data_key}: {error_detail}", "data_unavailable": True}
                    cmc_consolidated_data["error_in_batch"] = True
            except Exception as e:
                self.logger.error(f"Exception fetching '{data_key}' for CMC batch: {e!s}", exc_info=True)
                cmc_consolidated_data[data_key] = {"error": f"Exception fetching {data_key}: {e!s}", "data_unavailable": True}
                cmc_consolidated_data["error_in_batch"] = True
        
        if not self.data.get("batch_data"):
            self.data["batch_data"] = {}
        self.data["batch_data"]["coinmarketcap"] = cmc_consolidated_data
        
        if cmc_consolidated_data["error_in_batch"]:
            self.logger.error(f"CoinMarketCap batch processing for {project_name} encountered errors in one or more components.")
        else:
            self.logger.info(f"Successfully completed CoinMarketCap batch processing for {project_name}.")
            
        return cmc_consolidated_data
    
    async def _batch_process_defillama(self, project_name: str) -> Dict[str, Any]:
        """Batch process all DeFiLlama API calls for a project."""
        self.logger.info(f"Batch processing DeFiLlama data for {project_name}")
        defillama_final_data = None
        
        try:
            cache_manager = CacheManager(project_name=project_name)
            cached_data = cache_manager.load("defillama", "batch_consolidated_data", project_name.lower())
            
            if cached_data and isinstance(cached_data, dict) and not cached_data.get("error_in_batch"):
                self.logger.info(f"Using cached consolidated DeFiLlama data for {project_name}")
                self.data["batch_data"]["defillama"] = cached_data
                return cached_data
            
            self.logger.info(f"No valid consolidated cache for DeFiLlama data for {project_name}, fetching fresh.")
            self.logger.info(f"Calling DeFiLlama tool 'get_protocol_data' for {project_name}")
            defillama_response_raw = await self.mcp_client.call_tool("defillama", "get_protocol_data", protocol=project_name, project_name=project_name)
            
            defillama_data_processed = self._safe_handle_response(defillama_response_raw, "defillama.get_protocol_data", project_name)

            if "error" in defillama_data_processed:
                self.logger.warning(f"Failed to retrieve or parse base DeFiLlama data for {project_name}: {defillama_data_processed.get('error')}")
                defillama_final_data = {**defillama_data_processed, "error_in_batch": True, "data_unavailable": True}
            else:
                self.logger.info(f"Successfully retrieved and parsed base DeFiLlama data for {project_name}, keys: {list(defillama_data_processed.keys())}")
                
                # Ensure 'tvl_history' is present and is a list, even if empty
                tvl_history = defillama_data_processed.get("tvl_history")
                if tvl_history is None: # Key might be missing
                    self.logger.warning(f"DeFiLlama 'tvl_history' key missing for {project_name}. Setting to empty list.")
                    defillama_data_processed["tvl_history"] = []
                elif not isinstance(tvl_history, list):
                    self.logger.warning(f"DeFiLlama 'tvl_history' is not a list for {project_name} (type: {type(tvl_history)}). Setting to empty list.")
                    defillama_data_processed["tvl_history"] = []
                elif not tvl_history: # Empty list
                    self.logger.info(f"DeFiLlama 'tvl_history' is an empty list for {project_name}.")
                else: # Non-empty list
                    self.logger.info(f"DeFiLlama 'tvl_history' for {project_name} has {len(tvl_history)} entries.")
                    # Optional: Add validation for items within tvl_history if needed
                
                defillama_final_data = defillama_data_processed

            if not defillama_final_data.get("error_in_batch"):
                self.logger.info(f"Successfully processed DeFiLlama data for {project_name}. Saving to cache. Keys: {list(defillama_final_data.keys())}")
                cache_manager.save(defillama_final_data, "defillama", "batch_consolidated_data", project_name.lower())
            else:
                 self.logger.warning(f"Not caching DeFiLlama batch data for {project_name} due to 'error_in_batch' flag.")

            self.data["batch_data"]["defillama"] = defillama_final_data
            return defillama_final_data
                
        except Exception as e:
            self.logger.error(f"Error in batch processing DeFiLlama data for {project_name}: {str(e)}", exc_info=True)
            error_payload = {"error": str(e), "error_in_batch": True, "data_unavailable": True}
            self.data["batch_data"]["defillama"] = error_payload
            return error_payload
    
    async def _batch_process_tokenomics(self, project_name: str) -> Dict[str, Any]:
        """Batch process all Tokenomics API calls for a project."""
        self.logger.info(f"Batch processing Tokenomics data for {project_name}")
        
        try:
            cache_manager = CacheManager(project_name=project_name)
            cached_data = cache_manager.load("tokenomics", "distribution", project_name.lower())
            
            if cached_data:
                self.logger.info(f"Using cached Tokenomics data for {project_name}")
                if isinstance(cached_data, str):
                    try:
                        cached_data = json.loads(cached_data)
                        self.logger.debug(f"Parsed cached Tokenomics data keys: {list(cached_data.keys())}")
                    except json.JSONDecodeError:
                        self.logger.error(f"Failed to parse cached Tokenomics data as JSON for {project_name}")
                        cached_data = {"error": "Invalid cached data format"}
                if isinstance(cached_data, dict) and "error" not in cached_data:
                    self.data["batch_data"]["tokenomics"] = cached_data
                    self.logger.debug(f"Cached Tokenomics data keys: {list(cached_data.keys())}")
                    return cached_data
                else:
                    self.logger.warning(f"Cached Tokenomics data is invalid, fetching fresh data")
            
            self.logger.info(f"Calling Tokenomics tool directly for {project_name}")
            tokenomics_data = await self.mcp_client.call_tool("tokenomics", "get_distribution", project=project_name, project_name=project_name)
            
            if isinstance(tokenomics_data, str):
                try:
                    tokenomics_data = json.loads(tokenomics_data)
                    self.logger.debug(f"Parsed Tokenomics response keys: {list(tokenomics_data.keys())}")
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to parse Tokenomics response as JSON for {project_name}")
                    return {"error": "Invalid Tokenomics response format"}
            
            if tokenomics_data and isinstance(tokenomics_data, dict) and "error" not in tokenomics_data:
                self.logger.info(f"Successfully retrieved Tokenomics data for {project_name}, keys: {list(tokenomics_data.keys())}")
                cache_manager.save(tokenomics_data, "tokenomics", "distribution", project_name.lower())
                self.data["batch_data"]["tokenomics"] = tokenomics_data
                return tokenomics_data
            else:
                self.logger.warning(f"Failed to retrieve Tokenomics data for {project_name}")
                error_msg = tokenomics_data.get('error', 'Failed to retrieve Tokenomics data') if isinstance(tokenomics_data, dict) else "Failed to retrieve Tokenomics data"
                return {"error": error_msg}
        except Exception as e:
            self.logger.error(f"Error in batch processing Tokenomics data for {project_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def _batch_process_tavily(self, project_name: str, report_config: Dict = None) -> Dict[str, Any]:
        """Use RAG to process research needs for each section rather than direct Tavily calls."""
        self.logger.info(f"Processing Tavily research for {project_name} using section query_templates")
        
        try:
            if not hasattr(self, 'data'):
                self.data = {}
            if "batch_data" not in self.data:
                self.data["batch_data"] = {}
            if "tavily" not in self.data["batch_data"]:
                self.data["batch_data"]["tavily"] = {}
            
            if not self.rag_retriever:
                self.logger.warning("RAG retriever not available for Tavily research processing")
                return self.data["batch_data"]["tavily"]
            
            standard_sections_fallback = [
                "market_analysis", "tokenomics", "team_overview",
                "technology", "competition", "risks", "future_developments"
            ]
            
            config_section_keys = []
            section_details_map = {} 
            section_data_sources_map = {}

            if report_config and isinstance(report_config, dict) and "sections" in report_config:
                for section_config_item in report_config["sections"]:
                    if "title" in section_config_item:
                        section_title = section_config_item["title"]
                        section_key = section_title.lower().replace(' ', '_')
                        config_section_keys.append(section_key)
                        
                        default_query_template = f"{{project_name}} cryptocurrency {section_title}"
                        query_template_to_use = section_config_item.get("query_template", default_query_template)
                        
                        section_details_map[section_key] = {
                            "title": section_title,
                            "query_template": query_template_to_use
                        }
                        section_data_sources_map[section_key] = section_config_item.get("data_sources", [])
                self.logger.info(f"Extracted {len(config_section_keys)} sections from report_config for Tavily: {list(section_details_map.keys())}")
            
            sections_to_process = config_section_keys if config_section_keys else standard_sections_fallback
            self.logger.info(f"Tavily will process {len(sections_to_process)} sections: {sections_to_process}")
            
            section_tavily_queries = {}
            for s_key in sections_to_process:
                if s_key in section_details_map:
                    details = section_details_map[s_key]
                    template = details["query_template"]
                    try:
                        query_for_tavily = template.format(project_name=project_name)
                    except KeyError as e:
                        self.logger.warning(f"Query template for section '{details['title']}' (key: {s_key}) has a missing key: {e}. Using default query format.")
                        query_for_tavily = f"{project_name} cryptocurrency {details['title']}"
                    section_tavily_queries[s_key] = query_for_tavily
                else:
                    formatted_name = s_key.replace('_', ' ')
                    section_tavily_queries[s_key] = f"{project_name} cryptocurrency {formatted_name}"
            
            all_section_results = {}
            
            for current_section_key, tavily_search_query_content in section_tavily_queries.items():
                try:
                    self.logger.info(f"Tavily processing section_key '{current_section_key}' with search query: '{tavily_search_query_content}'")
                    
                    cache_manager = CacheManager(project_name=project_name, logger=self.logger)
                    cached_data = cache_manager.load("tavily", "research", current_section_key) 
                    
                    if cached_data:
                        self.logger.info(f"Using cached Tavily data for section_key '{current_section_key}' (file: research_{current_section_key}.json)")
                        if not isinstance(cached_data, dict):
                            self.logger.warning(f"Cached data for section_key '{current_section_key}' not a dict. Wrapping.")
                            all_section_results[current_section_key] = {"results": [{"content": str(cached_data)}]}
                        else:
                            all_section_results[current_section_key] = cached_data
                    else:
                        self.logger.info(f"No Tavily cache for section_key '{current_section_key}'. Fetching. Target server cache key: {current_section_key}")
                        
                        research_data_found = None
                        try:
                            self.logger.info(f"Calling MCP client.call_tool for tavily.research: query='{tavily_search_query_content}', cache_key='{current_section_key}'")
                            fetched_result = await self.mcp_client.call_tool(
                                server_name="tavily",
                                tool_name="research",
                                query=tavily_search_query_content, 
                                project_name=project_name,
                                cache_key=current_section_key 
                            )

                            self.logger.info(f"MCP call_tool raw fetched_result for section '{current_section_key}': TYPE={type(fetched_result)}, CONTENT='{str(fetched_result)[:500]}...'")

                            if isinstance(fetched_result, str):
                                self.logger.warning(f"MCP call_tool returned a STRING for section '{current_section_key}'. Attempting to parse as JSON.")
                                try:
                                    parsed_json = json.loads(fetched_result)
                                    if isinstance(parsed_json, dict):
                                        fetched_result = parsed_json
                                        self.logger.info(f"Successfully parsed string response into dict for section '{current_section_key}'.")
                                    else:
                                        error_detail = f"Parsed JSON for '{current_section_key}' is not a dict, type: {type(parsed_json)}. Original: '{fetched_result[:200]}...'"
                                        self.logger.error(error_detail)
                                        fetched_result = {"error": error_detail, "data_unavailable": True, "original_response_type": str(type(parsed_json))}
                                except json.JSONDecodeError as jde:
                                    error_detail = f"JSONDecodeError for '{current_section_key}': {str(jde)}. Original: '{fetched_result[:200]}...'"
                                    self.logger.error(error_detail)
                                    fetched_result = {"error": error_detail, "data_unavailable": True, "original_response_snippet": f"{fetched_result[:200]}"}
                                except Exception as e_parse:
                                    error_detail = f"Unexpected error parsing str response for '{current_section_key}': {str(e_parse)}. Original: '{fetched_result[:200]}...'"
                                    self.logger.error(error_detail)
                                    fetched_result = {"error": error_detail, "data_unavailable": True, "original_response_snippet": f"{fetched_result[:200]}"}
                            
                            if fetched_result and isinstance(fetched_result, dict) and not fetched_result.get("error") and (fetched_result.get("results") or fetched_result.get("data")):
                                if "data" in fetched_result and "results" not in fetched_result:
                                    if isinstance(fetched_result["data"], list):
                                        fetched_result["results"] = fetched_result["data"]
                                    elif fetched_result["data"] is not None:
                                        fetched_result["results"] = [fetched_result["data"]]
                                    else:
                                        fetched_result["results"] = []
                                elif "results" in fetched_result and "data" not in fetched_result and fetched_result["results"] is not None:
                                    pass
                                elif "results" not in fetched_result and "data" not in fetched_result:
                                    self.logger.warning(f"Fetched result for '{current_section_key}' has neither 'data' nor 'results' key. Setting empty results.")
                                    fetched_result["results"] = []

                                research_data_found = fetched_result
                                self.logger.info(f"Successfully processed data via mcp.call_tool for Tavily section_key '{current_section_key}'.")
                            else:
                                if isinstance(fetched_result, dict):
                                    err_msg = fetched_result.get('error', 'No usable data fields (results/data) in dict')
                                else:
                                    err_msg = f'Non-dict result of type {type(fetched_result)} after processing'
                                self.logger.warning(f"mcp.call_tool for tavily.research on section '{current_section_key}' yielded no usable data or an error: {err_msg}")
                                if not (isinstance(fetched_result, dict) and fetched_result.get("error")):
                                    fetched_result = {"error": err_msg, "data_unavailable": True, "original_result": str(fetched_result)[:200]}

                        except Exception as e_call_tool:
                            self.logger.error(f"Exception during mcp_client.call_tool for tavily.research on section '{current_section_key}': {str(e_call_tool)}", exc_info=True)
                            research_data_found = None

                        if research_data_found:
                            all_section_results[current_section_key] = research_data_found
                        else:
                            msg = f"No valid Tavily data obtained for section_key '{current_section_key}' via mcp.call_tool."
                            self.logger.warning(msg)
                            all_section_results[current_section_key] = {"error": msg, "results": [], "data_unavailable": True}
                except Exception as e:
                    self.logger.error(f"Error processing Tavily for section_key '{current_section_key}': {str(e)}", exc_info=True)
                    all_section_results[current_section_key] = {"error": str(e), "results": [], "data_unavailable": True}
            
            self.data["batch_data"]["tavily"] = all_section_results
            
            for key_check in sections_to_process:
                cache_file_path = os.path.join("reports", project_name.lower(), "cache", "tavily", f"research_{key_check}.json")
                if os.path.exists(cache_file_path):
                    self.logger.info(f"✅ Verified Tavily cache for '{key_check}' exists: {cache_file_path}")
                else:
                    self.logger.warning(f"❌ Tavily cache file missing for '{key_check}': {cache_file_path}.")
            
            return all_section_results
                
        except Exception as e:
            self.logger.error(f"General error in _batch_process_tavily for {project_name}: {str(e)}", exc_info=True)
            error_payload = {"error": str(e), "data_unavailable": True, "source": "tavily_exception"}
            if hasattr(self, 'data') and "batch_data" in self.data:
                if "tavily_section_research" not in self.data["batch_data"]:
                    self.data["batch_data"]["tavily_section_research"] = {}
                self.data["batch_data"]["tavily_section_research"]["_overall_error"] = error_payload 
            return error_payload

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