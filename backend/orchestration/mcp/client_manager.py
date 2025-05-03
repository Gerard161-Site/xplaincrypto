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
import json

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
        self.servers_initialized = {}
        self.servers_started = set()  # Track which servers have been started
        self.external_servers = set()  # Track servers started externally
        self.skip_unavailable = False  # New flag to skip unavailable endpoints
        self.base_dir = Path(__file__).parent.resolve()
        self.server_dir = self.base_dir / "retriever_servers"
        self.use_detached_processes = True  # Use detached processes by default
        
        # Set up pythonpath for server processes
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self.pythonpath = project_root
        if "PYTHONPATH" in os.environ:
            self.pythonpath = f"{project_root}:{os.environ['PYTHONPATH']}"
        logging.info(f"Using PYTHONPATH: {self.pythonpath}")
        
    def set_skip_unavailable(self, skip: bool):
        """Set whether to skip unavailable endpoints rather than trying fallbacks."""
        self.skip_unavailable = skip
        
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

        # Fix: Find server file using case-insensitive matching
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
        # This fixes issues with CoinMarketCap API key not being available in subprocess
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

    async def restart_server(self, server_name: str) -> None:
        """Stop and restart a specific MCP server to refresh tool registration."""
        if server_name not in self.server_processes:
            logging.error(f"No server config found for {server_name}")
            return
        
        # Stop the server if it's running
        if server_name in self.servers_started:
            await self.stop_server(server_name)
        
        # Remove it from the started_servers set just in case
        if server_name in self.servers_started:
            self.servers_started.remove(server_name)
        
        # Start the server again
        await self.start_server(server_name)
        
        # Let's make sure it's fully initialized
        await asyncio.sleep(2.0)
        
        logging.info(f"Server {server_name} has been restarted")
        
        # Verify tools are available
        async with self.create_client([server_name]) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]
            logging.info(f"Available tools after restart: {tool_names}")
        
        return tool_names

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
                          timeout: float = 30.0, 
                          restart_on_error: bool = True) -> AsyncIterator[MultiServerMCPClient]:
        """
        Create an MCP client connected to the specified servers with improved robustness.
        
        Args:
            server_names: List of server names to connect to. If None, connects to all available servers.
            timeout: Maximum time in seconds to wait for server operations
            restart_on_error: Whether to attempt to restart servers on connection errors
            
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
            
            # Create a wrapper to handle reconnection on errors
            class RobustClient:
                def __init__(self, base_client, manager, server_names):
                    self.client = base_client
                    self.manager = manager
                    self.server_names = server_names
                    self.restart_on_error = restart_on_error
                    
                async def get_tools(self, *args, **kwargs):
                    try:
                        # Don't pass args to self.client.get_tools() as it doesn't accept any arguments
                        # Add a very short timeout to prevent hanging on ListToolsRequest
                        try:
                            async with asyncio.timeout(3.0):  # Ultra short timeout for list_tools/get_tools
                                tools_or_future = self.client.get_tools()
                                
                                # Check if it's awaitable
                                if hasattr(tools_or_future, "__await__"):
                                    tools = await tools_or_future
                                    return tools
                                else:
                                    # If it's not awaitable (already a list of tools), return it directly
                                    return tools_or_future
                        except asyncio.TimeoutError:
                            logger.error("TIMEOUT while fetching tools list - detected 'Processing request of type ListToolsRequest' hang")
                            return []  # Return empty list to allow graceful degradation
                            
                    except anyio.ClosedResourceError:
                        if self.restart_on_error:
                            print("Connection closed, attempting to restart servers and reconnect...")
                            await self._reconnect()
                            # Try again after reconnection with timeout
                            try:
                                async with asyncio.timeout(5.0):  # Short timeout for retry
                                    tools_or_future = self.client.get_tools()
                                    
                                    # Check if it's awaitable
                                    if hasattr(tools_or_future, "__await__"):
                                        tools = await tools_or_future
                                        return tools
                                    else:
                                        # If it's not awaitable, return it directly
                                        return tools_or_future
                            except asyncio.TimeoutError:
                                logger.error("Timeout during retry of tools fetch - aborting")
                                return []  # Return empty list on timeout
                        raise
                    except Exception as e:
                        logger.error(f"Error fetching tools list: {str(e)}")
                        return []  # Return empty list to allow continuation
                
                async def list_tools(self, *args, **kwargs):
                    """Alias for get_tools to support both method names."""
                    return await self.get_tools(*args, **kwargs)
                
                async def invoke_tool(self, *args, **kwargs):
                    try:
                        # If there are positional args, handle them correctly
                        if len(args) > 0 and isinstance(args[0], str):
                            tool_name = args[0]
                            # Remove the first arg (tool name) and use the rest as normal args
                            args = args[1:]
                            
                            # For each server, try to find and invoke the tool
                            for server_name in self.server_names:
                                try:
                                    # Get tools from this server - don't pass server_name to get_tools()
                                    tools = await self.get_tools()
                                    
                                    # Find the tool by name
                                    for tool in tools:
                                        if tool.name == tool_name:
                                            # Found the tool, invoke it with kwargs or args[0]
                                            if len(args) > 0:
                                                # Use the first argument as input
                                                if hasattr(tool, "ainvoke"):
                                                    return await tool.ainvoke(input=args[0])
                                                else:
                                                    return await tool.invoke(input=args[0])
                                            else:
                                                # Use kwargs for tool invocation
                                                if hasattr(tool, "ainvoke"):
                                                    try:
                                                        return await tool.ainvoke(**kwargs)
                                                    except Exception:
                                                        # Try with input wrapper
                                                        return await tool.ainvoke(input=kwargs)
                                                else:
                                                    try:
                                                        return await tool.invoke(**kwargs)
                                                    except Exception:
                                                        # Try with input wrapper
                                                        return await tool.invoke(input=kwargs)
                                except Exception as e:
                                    print(f"Error getting tools from {server_name}: {str(e)}")
                            
                            # If we got here, no matching tool was found
                            raise ValueError(f"No matching tool found: {tool_name}")
                        else:
                            # Just pass through to the client's invoke_tool - may not exist
                            if hasattr(self.client, 'invoke_tool'):
                                return await self.client.invoke_tool(*args, **kwargs)
                            else:
                                # Try to extract the tool name from kwargs
                                tool_name = kwargs.pop('tool_name', None)
                                if tool_name:
                                    for server_name in self.server_names:
                                        tools = await self.get_tools()
                                        for tool in tools:
                                            if tool.name == tool_name:
                                                if hasattr(tool, "ainvoke"):
                                                    return await tool.ainvoke(**kwargs)
                                                else:
                                                    return await tool.invoke(input=kwargs)
                                raise AttributeError("MultiServerMCPClient has no attribute 'invoke_tool' and no tool_name provided in kwargs")
                    except anyio.ClosedResourceError:
                        if self.restart_on_error:
                            print("Connection closed during tool invocation, attempting to restart and retry...")
                            await self._reconnect()
                            # Try again after reconnection
                            if hasattr(self.client, 'invoke_tool'):
                                return await self.client.invoke_tool(*args, **kwargs)
                            raise
                        raise
                
                async def invoke_resource(self, endpoint: str, params: dict = None):
                    """Delegate resource invocation to the underlying client, with robust error handling.
                    
                    Args:
                        endpoint: The resource endpoint to invoke
                        params: Parameters to pass to the resource
                        
                    Returns:
                        The result of the resource invocation or an error dict
                    """
                    logger.info(f"RobustClient.invoke_resource called with endpoint={endpoint}, params={params}")
                    
                    # Default parameters to empty dict if None
                    if params is None:
                        params = {}
                    
                    try:
                        # Try to invoke the resource using the underlying client
                        if hasattr(self.client, 'invoke_resource'):
                            logger.info(f"Invoking resource via client.invoke_resource: {endpoint}")
                            result = await self.client.invoke_resource(endpoint, params)
                            return result
                        else:
                            # Fallback to fetch_data on the manager
                            logger.info(f"Client lacks invoke_resource method, falling back to manager.fetch_data: {endpoint}")
                            result = await self.manager.fetch_data(endpoint, params)
                            return result
                    except Exception as e:
                        logger.error(f"Error in invoke_resource for {endpoint}: {str(e)}")
                        
                        # Try to reconnect if we're having connection issues
                        if "connection" in str(e).lower() or "timeout" in str(e).lower():
                            try:
                                logger.info(f"Connection error in invoke_resource, attempting to reconnect...")
                                await self._reconnect()
                                
                                # Retry after reconnection
                                if hasattr(self.client, 'invoke_resource'):
                                    logger.info(f"Retrying invoke_resource after reconnect: {endpoint}")
                                    result = await self.client.invoke_resource(endpoint, params)
                                    return result
                                else:
                                    logger.info(f"Client still lacks invoke_resource after reconnect, falling back to manager.fetch_data: {endpoint}")
                                    result = await self.manager.fetch_data(endpoint, params)
                                    return result
                            except Exception as reconnect_error:
                                logger.error(f"Reconnect and retry failed: {str(reconnect_error)}")
                                return {"error": f"Resource invocation failed after reconnect: {str(reconnect_error)}"}
                        
                        # Return a descriptive error
                        return {"error": f"Resource invocation failed: {str(e)}", "endpoint": endpoint}
                
                async def _reconnect(self):
                    """Restart servers and reconnect the client."""
                    # Clean up current connections
                    await self.client.__aexit__(None, None, None)
                    
                    # Restart servers
                    for name in self.server_names:
                        try:
                            await self.manager.stop_server(name)
                            await asyncio.sleep(1)
                            await self.manager.start_server(name)
                        except Exception as e:
                            print(f"Error restarting server {name}: {str(e)}")
                    
                    # Recreate connections
                    connections = {}
                    for server_name in self.server_names:
                        if server_name in self.manager.server_processes:
                            connections[server_name] = {
                                "command": "python",
                                "args": [str(self.manager.server_dir / f"{server_name}_server.py")],
                                "transport": "stdio",
                                "timeout": timeout
                            }
                    
                    # Recreate client
                    self.client = MultiServerMCPClient(connections)
                    await self.client.__aenter__()
            
            # Yield the wrapped client
            yield RobustClient(client, self, server_names)
            
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
                        tools_result = await client.get_tools()
                        
                        if tools_result:
                            logger.info(f"Retrieved {len(tools_result)} tools from server: {server_name}")
                            all_tools.extend(tools_result)
                        else:
                            logger.warning(f"No tools returned from server: {server_name}")
                except anyio.ClosedResourceError:
                    logger.error(f"Connection closed while getting tools from {server_name}")
                    # Try restarting the server and connecting again
                    try:
                        await self.stop_server(server_name)
                        await asyncio.sleep(1)
                        await self.start_server(server_name)
                        
                        # Try again with a fresh connection
                        async with self.create_client([server_name], timeout=10.0) as client:
                            retry_tools = await client.get_tools()
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
                        fallback_tools = await client.get_tools()
                        if fallback_tools:
                            logger.info(f"Retrieved {len(fallback_tools)} tools from huggingface fallback")
                            all_tools.extend(fallback_tools)
                except Exception as fallback_error:
                    logger.error(f"Huggingface fallback failed: {str(fallback_error)}")
        
        logger.info(f"Returning {len(all_tools)} tools in total")
        return all_tools

    async def fetch_data(self, endpoint, params=None, max_depth=5):
        """
        Fetch data from the specified endpoint using available tools or direct API access.
        
        Args:
            endpoint (str): The data endpoint in the format data://{service}/{resource}
            params (dict, optional): Parameters for the request
            max_depth (int): Maximum recursion depth for fallbacks
            
        Returns:
            Any: The data from the endpoint or an error dict
        """
        if max_depth <= 0:
            return {"error": "Max recursion depth exceeded", "endpoint": endpoint}
            
        if params is None:
            params = {}
            
        # Skip problematic endpoints that often cause infinite loops
        if ("coinmarketcap/volume/" in endpoint or 
            "huggingface/" in endpoint and "research" not in endpoint or
            "huggingface/research/" in endpoint and len(endpoint.split("/")) > 3 or  
            "tavily/research/" in endpoint and any(term in endpoint.lower() for term in ["whitepaper", "security", "audit", "technical"])):
            logger.warning(f"Skipping known problematic endpoint: {endpoint}")
            return {"error": f"Endpoint {endpoint} is known to cause issues and has been disabled"}
            
        try:
            # Extract service and resource path from the endpoint
            parts = endpoint.split("://")
            if len(parts) != 2:
                logger.error(f"Invalid endpoint format: {endpoint}")
                return {"error": f"Invalid endpoint format: {endpoint}"}
                
            protocol, resource_path = parts
            
            # Extract service from the first part of the path
            service = resource_path.split("/")[0]
            
            # Set a strict timeout for the data fetching to prevent hangs
            try:
                # Use asyncio.timeout instead of wait_for for cleaner error handling
                async with asyncio.timeout(10.0):  # 10-second timeout for all operations
                    # Get the target service
                    target_service = service
                    
                    if not target_service:
                        return {"error": f"Could not determine service from endpoint: {endpoint}"}
                    
                    # Skip problematic services
                    if target_service == "project" or target_service == "multi":
                        logger.warning(f"Skipping problematic service: {target_service}")
                        return {"error": f"Service '{target_service}' is not supported"}
                    
                    # Try to get a client for the target service
                    client = await self._get_client_for_service(target_service)
                    if not client:
                        logger.error(f"Could not get client for service: {target_service}")
                        if not self.skip_unavailable:
                            # Try fallbacks only if we're not skipping unavailable endpoints
                            return await self._try_rag_fallback(
                                endpoint,
                                params=params,
                                max_depth=max_depth-1,
                                skip_unavailable=False
                            )
                        else:
                            return {"error": f"No client available for service: {target_service}"}
                    
                    # Replace template parameters in the target_resource
                    # For example, replace {coin} with actual coin name from params
                    target_resource = endpoint
                    
                    # Handle special cases for problematic endpoints
                    if "tavily/research/" in target_resource and " " in target_resource:
                        # Complex tavily query that might hang - try to simplify
                        project_name = params.get("project_name", "")
                        if project_name:
                            # Extract only the project part to simplify the query
                            simple_parts = target_resource.split("/")
                            if len(simple_parts) >= 3:
                                # Replace the complex query with just the project name
                                simple_resource = f"{simple_parts[0]}//{simple_parts[1]}/research/{project_name}"
                                logger.warning(f"Simplifying complex tavily query: {target_resource} -> {simple_resource}")
                                target_resource = simple_resource
                    
                    for key, value in params.items():
                        # Replace direct key matches
                        placeholder = "{" + key + "}"
                        if placeholder in target_resource:
                            target_resource = target_resource.replace(placeholder, str(value))
                    
                    # Handle special cases for common placeholders
                    if "{coin}" in target_resource and "project_name" in params:
                        target_resource = target_resource.replace("{coin}", params["project_name"].lower())
                    if "{protocol}" in target_resource and "project_name" in params:
                        target_resource = target_resource.replace("{protocol}", params["project_name"].lower())
                    if "{project}" in target_resource and "project_name" in params:
                        target_resource = target_resource.replace("{project}", params["project_name"].lower())
                    if "{query}" in target_resource and "project_name" in params:
                        target_resource = target_resource.replace("{query}", params["project_name"].lower())
                        logger.warning(f"No query string for pattern '{endpoint}', using project name for {{query}}.")
                    
                    # Log the final resource being requested
                    logger.info(f"No cache hit for {endpoint}. Calling fetch_data with Endpoint='{target_resource}', Params={params}")
                    
                    try:
                        # We need a separate timeout for the actual resource invocation
                        async with asyncio.timeout(5.0):  # Inner timeout for the actual fetch - reduced from longer value
                            if hasattr(client, 'invoke_resource'):
                                result = await client.invoke_resource(target_resource, params)
                                return result
                            else:
                                logger.error(f"Client has no invoke_resource method: {type(client)}")
                                return {"error": f"Client type {type(client)} has no invoke_resource method"}
                    except asyncio.TimeoutError:
                        logger.error(f"Inner timeout fetching resource for {target_resource}")
                        # Return error without trying fallbacks to prevent loops
                        return {"error": f"Timeout fetching resource: {target_resource}"}
                    except Exception as e:
                        logger.error(f"Resource invocation failed for {target_resource}: {str(e)}")
                        
                        # Check skip_unavailable flag (it's a boolean, not iterable)
                        if self.skip_unavailable:
                            return {"error": f"Service {target_service} unavailable and fallbacks disabled"}
                        
                        # If we get here, try fallback if we're not at max depth
                        if max_depth > 1:
                            return await self._try_rag_fallback(
                                endpoint,
                                params=params,
                                max_depth=max_depth-1,
                                skip_unavailable=True  # Prevent further fallbacks to avoid loops
                            )
                        else:
                            return {"error": f"Resource invocation failed: {str(e)}"}
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching data for endpoint {endpoint}")
                return {"error": f"Timeout fetching data for endpoint {endpoint}"}
            except Exception as e:
                logger.error(f"Error in fetch_data for {endpoint}: {str(e)}")
                return {"error": f"Error in fetch_data: {str(e)}"}
                
        except Exception as e:
            logger.error(f"Unexpected error in fetch_data: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}
            
        # If we get here, all attempts failed
        return {"error": f"All fetch attempts failed for endpoint: {endpoint}"}

    async def _try_rag_fallback(self, endpoint, params=None, max_depth=3, skip_unavailable=False):
        """
        Log the failure and return a clear error. RAG should be responsible for endpoint selection.
        
        Args:
            endpoint: The original endpoint that failed
            params: The parameters to pass to the endpoint
            max_depth: Maximum recursion depth to prevent infinite loops
            skip_unavailable: Boolean flag to skip unavailable endpoints rather than trying fallbacks
            
        Returns:
            Error response with details about the failure
        """
        if max_depth <= 0:
            logger.error(f"Maximum fallback depth reached for endpoint {endpoint}. Stopping recursion.")
            return {
                "error": "Maximum fallback depth reached", 
                "endpoint": endpoint
            }
            
        # Check if we should skip fallbacks - skip_unavailable is a boolean flag,
        # so we just check its value directly
        if skip_unavailable:
            logger.info(f"Skipping RAG fallback for endpoint {endpoint} because skip_unavailable is True")
            return {
                "error": f"Endpoint {endpoint} not available", 
                "endpoint": endpoint,
                "skip_unavailable": True
            }
            
        # Otherwise, log the failure and return an error
        logger.error(f"No matching tools found for endpoint: {endpoint}")
        return {
            "error": f"No matching tools found for endpoint: {endpoint}",
            "endpoint": endpoint,
            "params": params
        }

    async def execute_tool(self, server_name: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific tool on a specific server with proper caching and error handling.
        
        Args:
            server_name: The name of the server to execute the tool on
            tool_name: The name of the tool to execute
            params: Dictionary of parameters to pass to the tool
            
        Returns:
            The result of the tool execution
        """
        # First try to get from cache
        cache_key = f"{server_name}_{tool_name}_{str(sorted(params.items()))}"
        
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
                # Try using direct tool invocation first - simplest approach
                try:
                    logging.info(f"Trying direct tool invocation for {tool_name}")
                    result = await client.invoke_tool(tool_name, **params)
                    logging.info(f"Direct tool invocation for {tool_name} succeeded")
                    return result
                except Exception as e:
                    logging.warning(f"Direct tool invocation failed: {str(e)}")
                
                # If that failed, get tools and try to invoke the specific tool
                try:
                    # Get all tools from the server
                    logging.info(f"Getting tools from {server_name} server to find {tool_name}")
                    tools = await client.list_tools()
                    
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
                        if hasattr(result, "__await__"):
                            result = await result
                        logging.info(f"Tool {tool_name} execution successful with invoke")
                        return result
                    else:
                        raise ValueError(f"Tool {tool_name} doesn't support ainvoke or invoke methods")
                
                except Exception as tool_error:
                    logging.error(f"Error executing tool {tool_name}: {str(tool_error)}")
                    return {
                        "error": f"Error executing tool {tool_name}: {str(tool_error)}",
                        "available_tools": tool_names
                    }
        except Exception as e:
            logging.error(f"Error connecting to server {server_name}: {str(e)}")
            # Try to restart the server and try again if not already retried
            if not getattr(self, '_retry_attempted', False):
                try:
                    self._retry_attempted = True
                    logging.info(f"Attempting to restart server {server_name} and retry")
                    await self.restart_server(server_name)
                    # Recursive call with one retry
                    result = await self.execute_tool(server_name, tool_name, params)
                    self._retry_attempted = False
                    return result
                except Exception as retry_e:
                    logging.error(f"Retry after restart also failed: {str(retry_e)}")
                    self._retry_attempted = False
            
            # Return error details as a structured response instead of raising
            return {
                "error": f"Error executing tool {tool_name}: {str(e)}",
                "tool": tool_name,
                "server": server_name,
                "params": params
            }

    async def _get_client_for_service(self, service_name: str) -> Any:
        """
        Get or create a client for a specific service.
        
        Args:
            service_name: The name of the service to get a client for
            
        Returns:
            A client object for the service, or None if not available
        """
        class ClientWrapper:
            """Wrapper to keep context manager alive while using it."""
            def __init__(self, client_manager, service_name):
                self.client_manager = client_manager
                self.service_name = service_name
                self.client = None
                self.context = None
                
            async def __aenter__(self):
                try:
                    if self.service_name in self.client_manager.servers_started or self.service_name in self.client_manager.external_servers:
                        logger.info(f"Creating client for service: {self.service_name}")
                        self.context = self.client_manager.create_client([self.service_name], timeout=10.0)
                        self.client = await self.context.__aenter__()
                        return self.client
                    else:
                        # Try to start the server first
                        try:
                            await self.client_manager.start_server(self.service_name)
                            logger.info(f"Started server for service: {self.service_name}")
                            self.context = self.client_manager.create_client([self.service_name], timeout=10.0)
                            self.client = await self.context.__aenter__()
                            return self.client
                        except Exception as e:
                            logger.error(f"Could not start server for {self.service_name}: {str(e)}")
                            return None
                except Exception as e:
                    logger.error(f"Error getting client for service {self.service_name}: {str(e)}")
                    return None
                    
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.context:
                    await self.context.__aexit__(exc_type, exc_val, exc_tb)
        
        return await ClientWrapper(self, service_name).__aenter__()
