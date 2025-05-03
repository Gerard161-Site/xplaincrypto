from typing import List, Dict, Any, Optional
from ..rag.vector_store import VectorStore
from ..rag.retriever import RAGRetriever
from .client_manager import MCPClientManager
from langchain_core.tools import BaseTool
import asyncio
import logging
import uuid
import time
import os
import json
import hashlib

logger = logging.getLogger(__name__)

class MCPRouter:
    """
    Router for MCP endpoints that uses RAG to determine which endpoints to call.
    This class orchestrates the interaction between the RAG retriever and MCP clients.
    """
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.rag_retriever = RAGRetriever(vector_store)
        self.client_manager = MCPClientManager()
        
    async def initialize_endpoints(self) -> None:
        """Initialize the vector store with metadata about all available MCP endpoints."""
        # Get all available servers
        try:
            server_names = []
            for server_file in self.client_manager.server_dir.glob("*_server.py"):
                server_name = server_file.stem.replace("_server", "")
                server_names.append(server_name)
                
            logger.info(f"Found server files for: {server_names}")
                
            # Start each server and get its endpoints
            for server_name in server_names:
                logger.info(f"Starting server: {server_name}")
                await self.client_manager.start_server(server_name)
                
                # Add server description to vector store
                if server_name == "coingecko":
                    self.vector_store.upsert_endpoint(
                        f"{server_name}",
                        "CoinGecko API for cryptocurrency data including prices, market data, and metadata"
                    )
                elif server_name == "coinmarketcap":
                    self.vector_store.upsert_endpoint(
                        f"{server_name}",
                        "CoinMarketCap API for cryptocurrency market data, prices, and trading volume"
                    )
                elif server_name == "defillama":
                    self.vector_store.upsert_endpoint(
                        f"{server_name}",
                        "DeFiLlama API for DeFi protocol data including TVL (Total Value Locked) and yields"
                    )
                elif server_name == "tavily":
                    self.vector_store.upsert_endpoint(
                        f"{server_name}",
                        "Tavily API for web search and research on cryptocurrency and blockchain topics"
                    )
                elif server_name == "huggingface":
                    self.vector_store.upsert_endpoint(
                        f"{server_name}",
                        "HuggingFace API for AI models and datasets related to cryptocurrency and blockchain"
                    )
                    
            # Stop all servers after initialization
            await self.client_manager.stop_all_servers()
            logger.info("Endpoint initialization complete")
            
        except Exception as e:
            logger.error(f"Error initializing endpoints: {str(e)}")
            # Try to clean up
            try:
                await self.client_manager.stop_all_servers()
            except:
                pass
        
    async def route_query(self, query: str) -> List[BaseTool]:
        """
        Route a query to the appropriate MCP endpoints and return the tools with enhanced fallback mechanisms.
        
        Args:
            query: The query to route
            
        Returns:
            A list of LangChain tools from the appropriate MCP endpoints
        """
        try:
            # Use RAG to determine which endpoints to call
            try:
                endpoint_ids = await self.rag_retriever.process_query(query)
                logger.info(f"RAG selected endpoints: {endpoint_ids}")
            except Exception as rag_error:
                logger.error(f"Error in RAG retriever: {str(rag_error)}")
                endpoint_ids = []  # Continue with fallbacks
            
            # Ensure we have at least one endpoint (fallback to defaults if needed)
            if not endpoint_ids:
                logger.warning("No endpoints selected by RAG, using fallbacks")
                
                # Try to intelligently select endpoints based on query keywords
                endpoints_to_add = []
                
                # For price, market data queries
                if any(term in query.lower() for term in ["price", "market", "cap", "volume", "supply", "tokenomics"]):
                    endpoints_to_add.append("coinmarketcap")
                    endpoints_to_add.append("coingecko")
                
                # For DeFi-related queries
                if any(term in query.lower() for term in ["defi", "tvl", "yield", "liquidity", "protocol"]):
                    endpoints_to_add.append("defillama")
                
                # For news, research, sentiment queries
                if any(term in query.lower() for term in ["news", "information", "sentiment", "article", "research", "report"]):
                    endpoints_to_add.append("tavily")
                
                # Always add huggingface as a fallback for general content
                endpoints_to_add.append("huggingface")
                
                # Deduplicate and set as endpoints
                endpoint_ids = list(set(endpoints_to_add))
                
                logger.info(f"Using keyword-matched fallback endpoints: {endpoint_ids}")
            
            # For debugging: process endpoints in order of preference
            all_tools = []
            
            # Define the order of importance (try the most reliable first)
            preferred_order = ["coinmarketcap", "coingecko", "defillama", "tavily", "huggingface"]
            
            # Sort endpoints according to preferred order
            sorted_endpoints = sorted(endpoint_ids, key=lambda x: 
                                      preferred_order.index(x) if x in preferred_order else len(preferred_order))
            
            # Process endpoints one at a time for better error isolation
            for endpoint_id in sorted_endpoints:
                logger.info(f"Getting tools from endpoint: {endpoint_id}")
                try:
                    endpoint_tools = await self.client_manager.get_tools([endpoint_id])
                    if endpoint_tools:
                        logger.info(f"Found {len(endpoint_tools)} tools from {endpoint_id}")
                        all_tools.extend(endpoint_tools)
                    else:
                        logger.warning(f"No tools returned from {endpoint_id}")
                except Exception as endpoint_error:
                    logger.error(f"Error getting tools from {endpoint_id}: {str(endpoint_error)}")
            
            # If no tools from any endpoint, fall back to HuggingFace
            if not all_tools and "huggingface" not in endpoint_ids:
                logger.warning(f"No tools returned from any endpoint, falling back to HuggingFace")
                try:
                    hf_tools = await self.client_manager.get_tools(["huggingface"])
                    all_tools.extend(hf_tools)
                except Exception as hf_error:
                    logger.error(f"Error getting HuggingFace tools: {str(hf_error)}")
                    
            # If still no tools, create emergency fallback tools (this is last resort)
            if not all_tools:
                logger.error("All tool retrieval attempts failed. Using emergency fallback.")
                try:
                    # Try all servers one last time
                    all_server_names = [
                        f.stem.replace("_server", "") 
                        for f in self.client_manager.server_dir.glob("*_server.py")
                    ]
                    for server_name in all_server_names:
                        try:
                            # Try restarting the server
                            await self.client_manager.stop_server(server_name)
                            await asyncio.sleep(1)
                            await self.client_manager.start_server(server_name)
                            
                            # Try getting tools with fresh connection
                            server_tools = await self.client_manager.get_tools([server_name])
                            if server_tools:
                                logger.info(f"Emergency restart: Found {len(server_tools)} tools from {server_name}")
                                all_tools.extend(server_tools)
                                break  # Stop once we get some tools
                        except Exception:
                            continue  # Try next server
                except Exception as emergency_error:
                    logger.error(f"Emergency fallback failed: {str(emergency_error)}")
            
            logger.info(f"Returning {len(all_tools)} tools")
            return all_tools
            
        except Exception as e:
            logger.error(f"Error routing query: {str(e)}")
            # Try to get HuggingFace tools as a last resort
            try:
                logger.info("Attempting to get HuggingFace tools as fallback after routing error")
                return await self.client_manager.get_tools(["huggingface"])
            except Exception as fallback_error:
                logger.error(f"Fallback to HuggingFace failed: {str(fallback_error)}")
                # Return an empty list of tools if all attempts fail
                return []
        
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Execute a specific MCP tool.
        
        Args:
            tool_name: The name of the tool to execute
            **kwargs: Arguments to pass to the tool
            
        Returns:
            The result of the tool execution
        """
        try:
            # Determine which server the tool belongs to
            server_name = None
            for name in ["coingecko", "coinmarketcap", "defillama", "tavily", "huggingface"]:
                if name in tool_name.lower():
                    server_name = name
                    break
                    
            if not server_name:
                raise ValueError(f"Could not determine server for tool: {tool_name}")
                
            # Get the tool and execute it
            async with self.client_manager.create_client([server_name]) as client:
                # Get tools from the client
                tools = await client.get_tools()
                
                # Find the requested tool
                matched_tool = None
                for tool in tools:
                    if tool.name == tool_name:
                        matched_tool = tool
                        break
                        
                if not matched_tool:
                    raise ValueError(f"Tool not found: {tool_name}")
                    
                # Execute the tool
                logger.info(f"Executing tool: {tool_name} with args: {kwargs}")
                result = await matched_tool.ainvoke(**kwargs)
                logger.info(f"Tool execution complete")
                
                return result
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            raise

    def _cache_response(self, endpoint: str, params: Dict[str, Any], response: Any) -> None:
        """Cache the response for future use."""
        try:
            # Ensure we have a project name, defaulting if needed
            project_name = params.get("project_name", "default")
            
            # Create project-specific cache directory
            cache_dir = os.path.join("docs", project_name, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # Create a unique cache key
            cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
            cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
            cache_path = os.path.join(cache_dir, f"{cache_key_hash}.json")
            
            # Cache the response
            with open(cache_path, "w") as f:
                json.dump({
                    "endpoint": endpoint,
                    "params": params,
                    "response": response,
                    "timestamp": time.time()
                }, f, indent=2)
                
            self.logger.info(f"Cached response for endpoint {endpoint} at {cache_path}")
        except Exception as e:
            self.logger.error(f"Error caching response: {str(e)}")
    
    def _get_cached_response(self, endpoint: str, params: Dict[str, Any], max_age_seconds: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get a cached response if available and not expired."""
        try:
            # Ensure we have a project name, defaulting if needed
            project_name = params.get("project_name", "default")
            
            # Create a unique cache key
            cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
            cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
            cache_path = os.path.join("docs", project_name, "cache", f"{cache_key_hash}.json")
            
            # Check if the cache file exists
            if not os.path.exists(cache_path):
                return None
                
            # Check if the cache is expired
            if max_age_seconds is not None:
                cache_age = time.time() - os.path.getmtime(cache_path)
                if cache_age > max_age_seconds:
                    self.logger.info(f"Cache expired for endpoint {endpoint} ({cache_age:.1f}s old)")
                    return None
            
            # Read the cache file
            with open(cache_path, "r") as f:
                cached_data = json.load(f)
                
            self.logger.info(f"Using cached response for endpoint {endpoint} from {cache_path}")
            return cached_data["response"]
        except Exception as e:
            self.logger.error(f"Error retrieving cached response: {str(e)}")
            return None

class AgentPoolManager:
    def __init__(self, max_concurrent=5):
        self.max_concurrent = max_concurrent
        self.active_agents = {}  # agent_id -> task
        self.queue = asyncio.Queue()
        self.results = {}  # agent_id -> result
        self.task = None
        
    async def start(self):
        """Start the agent pool worker."""
        self.task = asyncio.create_task(self._worker())
        
    async def stop(self):
        """Stop the agent pool worker."""
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
                
    async def _worker(self):
        """Process agent tasks from the queue."""
        while True:
            # Get next task from queue
            agent_id, agent_func, args, kwargs = await self.queue.get()
            
            # Wait if at capacity
            while len(self.active_agents) >= self.max_concurrent:
                # Clean up completed tasks
                done_ids = []
                for aid, task in self.active_agents.items():
                    if task.done():
                        try:
                            self.results[aid] = task.result()
                        except Exception as e:
                            self.results[aid] = {"error": str(e)}
                        done_ids.append(aid)
                
                for aid in done_ids:
                    del self.active_agents[aid]
                    
                if len(self.active_agents) >= self.max_concurrent:
                    await asyncio.sleep(0.1)
            
            # Start new task
            task = asyncio.create_task(agent_func(*args, **kwargs))
            self.active_agents[agent_id] = task
            self.queue.task_done()
            
    async def submit_agent_task(self, agent_func, *args, **kwargs) -> str:
        """Submit a new agent task to the pool."""
        agent_id = str(uuid.uuid4())
        await self.queue.put((agent_id, agent_func, args, kwargs))
        return agent_id
        
    async def get_result(self, agent_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get the result of a task by ID."""
        start_time = time.time()
        while True:
            # Check if result is available
            if agent_id in self.results:
                result = self.results[agent_id]
                del self.results[agent_id]
                return result
                
            # Check if task is still active
            if agent_id not in self.active_agents:
                return {"error": "Task not found"}
                
            # Check timeout
            if timeout and time.time() - start_time > timeout:
                return {"error": "Timeout waiting for result"}
                
            await asyncio.sleep(0.5)
            
    async def get_status(self) -> Dict[str, Any]:
        """Get pool status."""
        return {
            "active_agents": len(self.active_agents),
            "queued_tasks": self.queue.qsize(),
            "completed_results": len(self.results)
        }
