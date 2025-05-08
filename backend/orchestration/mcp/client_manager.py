from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional, Any
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
import os
import subprocess
import asyncio
import anyio
import logging
from pathlib import Path
import sys

# Get logger
logger = logging.getLogger(__name__)

class MCPClientManager:
    """
    Manager for MCP clients that connects to multiple retriever servers.
    This class handles the lifecycle of MCP server processes and client connections.
    """
    
    def __init__(self, spawn_servers=True):
        """Initialize the MCP client manager."""
        self.spawn_servers = spawn_servers
        self.server_processes = {}
        self.servers_started = set()  # Track which servers have been started
        self.external_servers = set()  # Track servers started externally
        self.base_dir = Path(__file__).parent.resolve()
        self.server_dir = self.base_dir / "retriever_servers"
        self.logger = logging.getLogger(__name__)  # Add logger attribute
        
        # Set up pythonpath for server processes
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self.pythonpath = project_root
        if "PYTHONPATH" in os.environ:
            self.pythonpath = f"{project_root}:{os.environ['PYTHONPATH']}"
        logging.info(f"Using PYTHONPATH: {self.pythonpath}")
        
    async def start_server(self, server_name: str, max_retries: int = 3) -> None:
        """Start a specific MCP server."""
        # Skip invalid server names that don't have matching server files
        if server_name == "project" or server_name == "multi":
            logging.warning(f"Skipping invalid server name: {server_name}")
            return

        if server_name in self.server_processes:
            logging.info(f"Server process already exists for {server_name}")
            return
        
        if server_name in self.servers_started:
            logging.info(f"Server {server_name} already marked as started")
            return

        # Find server file using case-insensitive matching
        server_path = None
        requested_server_file = f"{server_name}_server.py"
        
        # Check all server files with case-insensitive matching
        for server_file in self.server_dir.glob("*_server.py"):
            if server_file.name.lower() == requested_server_file.lower():
                server_path = server_file
                logging.info(f"Found matching server file: {server_file}")
                break
                
        if not server_path:
            logging.warning(f"Server file not found for: {server_name} (looking for {requested_server_file})")
            return
            
        # Start the server as a subprocess
        logging.info(f"Starting MCP server for {server_name} with PYTHONPATH={self.pythonpath}")
        
        if sys.platform == "win32":
            startup_cmd = [
                sys.executable, 
                "-m", 
                os.path.splitext(os.path.basename(server_path))[0]
            ]
        else:
            startup_cmd = [sys.executable, str(server_path)]
        
        env = os.environ.copy()
        env["PYTHONPATH"] = self.pythonpath
        
        # Explicitly ensure API keys are copied to subprocess environment
        for key in ["COINMARKETCAP_API_KEY", "COINGECKO_API_KEY", "TAVILY_API_KEY", 
                    "HUGGINGFACE_API_KEY", "DUNE_API_KEY", "OPENAI_API_KEY"]:
            if key in os.environ:
                logging.info(f"Passing {key} to {server_name} server process")
                env[key] = os.environ[key]
        
        process = subprocess.Popen(
            startup_cmd,
            cwd=os.path.dirname(server_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1
        )
        
        # Store the process
        self.server_processes[server_name] = process
        
        # Let's wait briefly to make sure it starts up properly
        await asyncio.sleep(1.0)
        
        if process.poll() is not None:
            # Process exited already
            stdout, stderr = process.communicate()
            logging.error(f"Server {server_name} failed to start: exit code {process.returncode}")
            logging.error(f"STDOUT: {stdout}")
            logging.error(f"STDERR: {stderr}")
            raise RuntimeError(f"Failed to start MCP server for {server_name}")
        
        self.servers_started.add(server_name)
        logging.info(f"Server {server_name} started successfully")

    async def stop_server(self, server_name: str) -> None:
        """Stop a specific MCP server."""
        if server_name not in self.servers_started:
            logging.info(f"Server {server_name} is not running")
            return

        if server_name in self.server_processes:
            process = self.server_processes[server_name]
            if process.poll() is None:  # Process is still running
                logging.info(f"Stopping MCP server for {server_name}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logging.warning(f"Server {server_name} did not terminate gracefully, killing")
                    process.kill()
                    process.wait()
            del self.server_processes[server_name]
        
        if server_name in self.servers_started:
            self.servers_started.remove(server_name)
        
        logging.info(f"Server {server_name} stopped")
        
    async def stop_all_servers(self) -> None:
        """Stop all MCP server processes."""
        for server_name in list(self.server_processes.keys()):
            await self.stop_server(server_name)
            
    @asynccontextmanager
    async def create_client(self, server_names: Optional[List[str]] = None, 
                          timeout: float = 30.0) -> AsyncIterator[MultiServerMCPClient]:
        """
        Create an MCP client connected to the specified servers with improved robustness.
        
        Args:
            server_names: List of server names to connect to. If None, connects to all available servers.
            timeout: Maximum time in seconds to wait for server operations
            
        Yields:
            An initialized MultiServerMCPClient connected to the specified servers.
        """
        if server_names is None:
            # Get all server files in the server directory
            server_names = [
                f.stem.replace("_server", "") 
                for f in self.server_dir.glob("*_server.py")
            ]
            
        # Start all the specified servers
        start_tasks = [self.start_server(name) for name in server_names]
        try:
            await asyncio.gather(*start_tasks)
        except Exception as e:
            print(f"Error starting some servers: {str(e)}")
            # Continue with the servers that did start
            
        # Create the connection configurations
        connections = {}
        for server_name in server_names:
            if server_name in self.server_processes:
                # Find the actual server file for this server
                server_file = None
                for file_path in self.server_dir.glob("*_server.py"):
                    if file_path.stem.lower() == f"{server_name.lower()}_server":
                        server_file = file_path
                        break
                
                if server_file:
                    # Use the actual case-sensitive filename
                    connections[server_name] = {
                        "command": "python",
                        "args": [str(server_file)],
                        "transport": "stdio",
                        "timeout": timeout  # Set timeout for operations
                    }
                    logging.info(f"Added connection for {server_name} using file {server_file}")
                else:
                    logging.error(f"Could not find server file for {server_name}")
            
        # Create the client with more robust error handling
        client = None
        try:
            client = MultiServerMCPClient(connections)
            await client.__aenter__()
            
            # Simply yield the client directly - no wrapper needed
            yield client
            
        except Exception as e:
            print(f"Error creating MCP client: {str(e)}")
            if client:
                try:
                    await client.__aexit__(type(e), e, None)
                except:
                    pass
            raise
        finally:
            # Ensure client is closed properly
            if client:
                try:
                    await client.__aexit__(None, None, None)
                except:
                    pass
                    
            # Stop all servers when the client is closed
            await self.stop_all_servers()

    async def get_tools(self, server_names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Get all tools from the specified servers with improved error handling.
        
        Args:
            server_names: List of server names to get tools from. If None, gets tools from all available servers.
            
        Returns:
            A list of LangChain tools from the specified servers.
        """
        if not server_names:
            logger.warning("No server names provided, using all available servers")
            server_names = [
                f.stem.replace("_server", "") 
                for f in self.server_dir.glob("*_server.py")
            ]
        
        all_tools = []
        
        # Process each server individually for better error isolation
        for server_name in server_names:
            try:
                logger.info(f"Getting tools from server: {server_name}")
                # Start server if it's not already running
                try:
                    await self.start_server(server_name)
                except Exception as server_error:
                    logger.error(f"Failed to start server {server_name}: {str(server_error)}")
                    continue  # Skip this server and try the next one
                
                # Try to get tools with timeout protection
                try:
                    async with self.create_client([server_name], timeout=10.0) as client:
                        try:
                            async with asyncio.timeout(5.0):  # Short timeout for tools fetch
                                # Handle both awaitable and non-awaitable get_tools results
                                tools_result = client.get_tools()
                                
                                # Check if tools_result is awaitable
                                if hasattr(tools_result, "__await__"):
                                    tools_result = await tools_result
                                
                                if tools_result:
                                    logger.info(f"Retrieved {len(tools_result)} tools from server: {server_name}")
                                    all_tools.extend(tools_result)
                                else:
                                    logger.warning(f"No tools returned from server: {server_name}")
                        except asyncio.TimeoutError:
                            logger.error(f"TIMEOUT getting tools from {server_name}")
                except anyio.ClosedResourceError:
                    logger.error(f"Connection closed while getting tools from {server_name}")
                    # Try restarting the server and connecting again
                    try:
                        await self.stop_server(server_name)
                        await asyncio.sleep(1)
                        await self.start_server(server_name)
                        
                        # Try again with a fresh connection
                        async with self.create_client([server_name], timeout=10.0) as client:
                            # Handle both awaitable and non-awaitable get_tools results
                            retry_tools = client.get_tools()
                            
                            # Check if retry_tools is awaitable
                            if hasattr(retry_tools, "__await__"):
                                retry_tools = await retry_tools
                                
                            if retry_tools:
                                logger.info(f"Retrieved {len(retry_tools)} tools from server {server_name} after restart")
                                all_tools.extend(retry_tools)
                    except Exception as retry_error:
                        logger.error(f"Failed to get tools after restart: {str(retry_error)}")
                except Exception as e:
                    logger.error(f"Error getting tools from {server_name}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Unexpected error processing server {server_name}: {str(e)}")
        
        # Check if we got any tools
        if not all_tools:
            logger.warning(f"No tools retrieved from any of the requested servers: {server_names}")
            
            # Try to get tools from huggingface as a last resort if not already tried
            if "huggingface" not in server_names:
                logger.info("Attempting to get tools from huggingface as fallback")
                try:
                    await self.start_server("huggingface")
                    async with self.create_client(["huggingface"], timeout=10.0) as client:
                        # Handle both awaitable and non-awaitable get_tools results
                        fallback_tools = client.get_tools()
                        
                        # Check if fallback_tools is awaitable
                        if hasattr(fallback_tools, "__await__"):
                            fallback_tools = await fallback_tools
                            
                        if fallback_tools:
                            logger.info(f"Retrieved {len(fallback_tools)} tools from huggingface fallback")
                            all_tools.extend(fallback_tools)
                except Exception as fallback_error:
                    logger.error(f"Huggingface fallback failed: {str(fallback_error)}")
        
        logger.info(f"Returning {len(all_tools)} tools in total")
        return all_tools

    async def execute_tool(self, server_name: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific tool on a specific server with proper error handling.
        
        Args:
            server_name: The name of the server to execute the tool on
            tool_name: The name of the tool to execute
            params: Dictionary of parameters to pass to the tool
            
        Returns:
            The result of the tool execution
        """
        # Make sure servers_started is a set
        if not isinstance(self.servers_started, set):
            self.servers_started = set()
        
        # Start the server if needed
        if server_name not in self.servers_started:
            try:
                await self.start_server(server_name)
            except Exception as e:
                logging.error(f"Error starting server {server_name}: {str(e)}")
                # Continue anyway, in case we can still connect to an existing server
        
        try:
            # Create client connection
            async with self.create_client([server_name]) as client:
                # Get all tools from the server
                logging.info(f"Getting tools from {server_name} server to find {tool_name}")
                
                # Handle both awaitable and non-awaitable get_tools results
                tools_result = client.get_tools()
                
                # Check if tools_result is awaitable
                if hasattr(tools_result, "__await__"):
                    tools = await tools_result
                else:
                    # If it's not awaitable (already a list of tools), use it directly
                    tools = tools_result
                
                # Find the specific tool
                found_tool = None
                tool_names = []
                for tool in tools:
                    tool_names.append(tool.name)
                    if tool.name == tool_name:
                        found_tool = tool
                        break
                
                if not found_tool:
                    logging.error(f"Tool {tool_name} not found on server {server_name}. Available tools: {tool_names}")
                    return {"error": f"Tool {tool_name} not found", "available_tools": tool_names}
                
                # Log the tool execution plan
                logging.info(f"Executing {tool_name} on {server_name} with params: {params}")
                
                # Use the langchain tool invocation pattern for structured tools
                if hasattr(found_tool, "ainvoke"):
                    result = await found_tool.ainvoke(input=params)
                    logging.info(f"Tool {tool_name} execution successful with ainvoke")
                    return result
                elif hasattr(found_tool, "invoke"):
                    # Try structured tool invocation
                    result = found_tool.invoke(input=params)
                    # Check if result is awaitable
                    if hasattr(result, "__await__"):
                        result = await result
                    logging.info(f"Tool {tool_name} execution successful with invoke")
                    return result
                else:
                    raise ValueError(f"Tool {tool_name} doesn't support ainvoke or invoke methods")
        
        except Exception as e:
            logging.error(f"Error executing tool {tool_name}: {str(e)}")
            # Return error details as a structured response instead of raising
            return {
                "error": f"Error executing tool {tool_name}: {str(e)}",
                "tool": tool_name,
                "server": server_name,
                "params": params
            }

    async def initialize(self):
        """Initialize the MCP client manager by ensuring all servers are ready."""
        logger.info("Initializing MCPClientManager")
        
        # Get list of all server files
        server_names = [
            f.stem.replace("_server", "") 
            for f in self.server_dir.glob("*_server.py")
        ]
        
        logger.info(f"Found {len(server_names)} server files: {server_names}")
        
        # Check if servers are already started
        if self.servers_started:
            logger.info(f"Servers already started: {self.servers_started}")
            return
        
        # Verify that all servers are running
        for server_name in server_names:
            if server_name not in self.servers_started:
                logger.info(f"Server {server_name} not started yet, starting it now")
                try:
                    await self.start_server(server_name)
                    logger.info(f"Successfully started server: {server_name}")
                except Exception as e:
                    logger.error(f"Failed to start server {server_name}: {str(e)}")
        
        logger.info(f"MCPClientManager initialization complete. Servers started: {self.servers_started}")
        return True

    # Simple adapter method to maintain compatibility with code that expects resource invocation
    async def fetch_data(self, endpoint, params=None, max_depth=5):
        """
        Fetch data using tools instead of resources.
        This is a compatibility method that translates resource endpoints to tool calls.
        """
        logger.info(f"fetch_data called with endpoint={endpoint}, params={params}")
        
        if params is None:
            params = {}
            
        try:
            # Extract service from the endpoint
            parts = endpoint.split("://")
            if len(parts) != 2:
                logger.error(f"Invalid endpoint format: {endpoint}")
                return {"error": f"Invalid endpoint format: {endpoint}"}
                
            service_path = parts[1].split("/")
            service = service_path[0]
            
            # Get project_name from params
            project_name = params.get("project_name", None)
            
            # Special handling for different services
            if service == "tavily":
                # Standardize on using only the 'research' endpoint for Tavily
                # to prevent redundant API calls
                logger.info(f"Processing tavily research endpoint: {endpoint}")
                
                # Extract query from path or params
                query = None
                
                # First try to get query from the endpoint path
                if len(service_path) > 1:
                    # Handle both formats: data://tavily/research/{query} and data://tavily/{query}
                    if service_path[1] == "research" and len(service_path) > 2:
                        query = "/".join(service_path[2:])
                    else:
                        query = "/".join(service_path[1:])
                
                # If not in path, try to get from params
                if not query and "query" in params:
                    query = params["query"]
                elif not query and project_name:
                    query = project_name
                    
                if not query:
                    logger.error(f"No query found for tavily endpoint: {endpoint}")
                    return {"error": "No query provided for tavily search"}
                
                # Ensure query is a string
                if isinstance(query, dict):
                    if "query" in query:
                        query = query["query"]
                    elif "project_name" in query:
                        query = query["project_name"]
                    else:
                        query = str(query)
                
                # Add project name to query for better context
                if project_name and project_name.lower() not in query.lower():
                    query = f"{project_name} {query}"
                    
                logger.info(f"Invoking tavily research with query: {query}, project_name: {project_name}")
                
                # Always use the research tool (not deep_research) to avoid redundant API calls
                return await self.execute_tool("tavily", "research", {
                    "query": query,
                    "project_name": project_name
                })
                
            elif service == "defillama":
                # Extract protocol from path
                protocol = None
                if len(service_path) > 1:
                    if service_path[1] == "tvl" and len(service_path) > 2:
                        protocol = service_path[2]
                    else:
                        protocol = service_path[1]
                
                # If not in path, try to get from params
                if not protocol and "protocol" in params:
                    protocol = params["protocol"]
                elif not protocol and project_name:
                    protocol = project_name
                    
                if not protocol:
                    logger.error(f"No protocol found for defillama endpoint: {endpoint}")
                    return {"error": "No protocol provided for defillama"}
                
                logger.info(f"Invoking defillama get_tvl with protocol: {protocol}")
                return await self.execute_tool("defillama", "get_tvl", {"protocol": protocol})
                
            elif service == "coinmarketcap":
                # Extract coin from path
                coin = None
                if len(service_path) > 1:
                    if len(service_path) > 2:
                        coin = service_path[2]
                    else:
                        coin = service_path[1]
                
                # If not in path, try to get from params
                if not coin and "coin" in params:
                    coin = params["coin"]
                elif not coin and project_name:
                    coin = project_name
                    
                if not coin:
                    logger.error(f"No coin found for coinmarketcap endpoint: {endpoint}")
                    return {"error": "No coin provided for coinmarketcap"}
                
                # Determine which CMC endpoint to use based on the path
                # Use the correct tool names that match what's available in coinmarketcap_server.py
                cmc_endpoint = "get_coin_price_data"  # Changed from get_price
                if len(service_path) > 1 and service_path[1] == "market":
                    cmc_endpoint = "get_coin_market_data"  # Changed from get_market_data
                elif len(service_path) > 1 and service_path[1] == "volume":
                    cmc_endpoint = "get_coin_price_data"  # Volume data comes from price data
                
                logger.info(f"Invoking coinmarketcap {cmc_endpoint} with coin: {coin}")
                return await self.execute_tool("coinmarketcap", cmc_endpoint, {"coin": coin, "project_name": project_name})
                
            elif service == "coingecko":
                # Extract coin from path
                coin = None
                project_name_from_path = None
                
                # Parse endpoint format data://coingecko/ENDPOINT/COIN or data://coingecko/ENDPOINT/COIN/PROJECT_NAME
                if len(service_path) > 1:
                    if len(service_path) > 2:
                        coin = service_path[2]
                    else:
                        coin = service_path[1]
                
                # If not in path, try to get from params
                if not coin and params and "coin" in params:
                    coin = params["coin"]
                elif not coin and project_name:
                    coin = project_name
                    
                if not coin:
                    logger.error(f"No coin found for coingecko endpoint: {endpoint}")
                    return {"error": "No coin provided for coingecko"}
                
                # Ensure we always have a project_name for CoinGecko to prevent default cache usage
                if not project_name:
                    project_name = coin
                    logger.info(f"No project_name provided for CoinGecko, using coin as project_name: {project_name}")
                
                # Determine which CoinGecko endpoint to use based on the path
                cg_endpoint = "get_price"
                if len(service_path) > 1:
                    if service_path[1] == "market":
                        cg_endpoint = "get_market_data"
                    elif service_path[1] == "history":
                        cg_endpoint = "get_history"
                    elif service_path[1] == "price":
                        cg_endpoint = "search_coins"  # This is the closest match for price in the available tools
                
                logger.info(f"Invoking coingecko {cg_endpoint} with coin: {coin}, project_name: {project_name}")
                
                # Include project_name in parameters if available
                tool_params = {}
                if cg_endpoint == "search_coins":
                    tool_params["query"] = coin  # search_coins uses 'query' parameter
                else:
                    tool_params["coin"] = coin  # other endpoints use 'coin' parameter
                
                # Always include project_name
                tool_params["project_name"] = project_name
                
                return await self.execute_tool("coingecko", cg_endpoint, tool_params)
                
            elif service == "tokenomics":
                # Extract project from path or use project_name
                project = None
                if len(service_path) > 1:
                    # For paths like data://tokenomics/distribution/ondo
                    # service_path[1] is "distribution", service_path[2] is "ondo"
                    if len(service_path) > 2:
                        project = service_path[2]  # Get the actual project name
                    elif service_path[1] != "distribution" and service_path[1] != "details" and service_path[1] != "whitepaper":
                        project = service_path[1]  # Only use as project if not a known endpoint name
                
                # If not in path, try to get from params
                if not project and "project" in params:
                    project = params["project"]
                elif not project and project_name:
                    project = project_name
                    
                if not project:
                    logger.error(f"No project found for tokenomics endpoint: {endpoint}")
                    return {"error": "No project provided for tokenomics"}
                
                # Ensure project_name is set for proper caching
                if not project_name:
                    project_name = project
                    logger.info(f"No project_name provided, using project as project_name: {project_name}")
                
                # Determine which tokenomics endpoint to use based on the path
                tokenomics_endpoint = "get_distribution"  # Default endpoint
                if len(service_path) > 1:
                    if service_path[1] == "distribution":
                        tokenomics_endpoint = "get_distribution"
                    elif service_path[1] == "details":
                        tokenomics_endpoint = "get_details"
                    elif service_path[1] == "whitepaper":
                        tokenomics_endpoint = "get_whitepaper"
                
                logger.info(f"Invoking tokenomics {tokenomics_endpoint} with project: {project}, project_name: {project_name}")
                return await self.execute_tool("tokenomics", tokenomics_endpoint, {"project": project, "project_name": project_name})
                
            else:
                logger.error(f"Unknown service in endpoint: {service}")
                return {"error": f"Unknown service: {service}"}
                
        except Exception as e:
            logger.error(f"Error in fetch_data: {str(e)}")
            return {"error": f"Error fetching data: {str(e)}"}

    async def call_tool(self, server_name: str, tool_name: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Call a tool on a specific server with positional and keyword arguments.
        This is a convenience wrapper around execute_tool that handles parameter formatting.
        
        Args:
            server_name: The name of the server to call the tool on
            tool_name: The name of the tool to call
            *args: Positional arguments to pass to the tool
            **kwargs: Keyword arguments to pass to the tool
            
        Returns:
            The result of the tool execution
        """
        try:
            self.logger.info(f"Calling tool {tool_name} on server {server_name} with args={args}, kwargs={kwargs}")
            
            # Make sure servers_started is a set
            if not isinstance(self.servers_started, set):
                self.servers_started = set()
            
            # If server doesn't exist, try to start it
            if server_name not in self.servers_started:
                self.logger.info(f"Server {server_name} not connected, attempting to start it")
                await self.start_server(server_name)
            
            # Create a parameters dictionary
            parameters = {}
            
            # Handle common parameter mappings for known servers and tools
            if args:
                if server_name == "tavily" and (tool_name == "research" or tool_name == "deep_research"):
                    parameters["query"] = args[0]
                elif server_name == "coingecko":
                    parameters["coin"] = args[0]
                elif server_name == "coinmarketcap":
                    parameters["coin"] = args[0]
                elif server_name == "defillama":
                    parameters["protocol"] = args[0]
                elif server_name == "tokenomics":
                    parameters["project"] = args[0]
                elif server_name == "huggingface":
                    parameters["query"] = args[0]
                else:
                    # Generic fallback - use "query" for the first arg
                    parameters["query"] = args[0]
                
                # Add any additional positional args with generic names
                for i, arg in enumerate(args[1:], start=1):
                    parameters[f"arg{i}"] = arg
            
            # Add keyword arguments, which override positional args if there's a conflict
            parameters.update(kwargs)
            
            # Special handling for Tavily
            if server_name == "tavily":
                # Ensure we're calling the right tool on the tavily server
                self.logger.info(f"Detected tavily call with tool: {tool_name}")
                # If tool_name is 'research', keep as is
                if tool_name != "research" and tool_name != "deep_research":
                    # Default to 'research' tool if another name is provided (like 'tavily')
                    self.logger.info(f"Changing tool name from {tool_name} to 'research' for tavily server")
                    tool_name = "research"
            
            self.logger.info(f"Executing {tool_name} with parameters: {parameters}")
            result = await self.execute_tool(server_name, tool_name, parameters)
            self.logger.info(f"Tool {tool_name} execution successful")
            return result
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name} on server {server_name}: {str(e)}", exc_info=True)
            return {"error": f"Tool execution failed: {str(e)}"}
