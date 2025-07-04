# Creating a new client_manager.py with the suggested fixes
# This code will focus on:
# 1. Forcing SelectSelector instead of KqueueSelector on macOS
# 2. Increasing buffer size from 8192 to 65536 bytes
# 3. Implementing robust multi-line JSON parsing
# 4. Adding proper timeout handling for server initialization
# 5. Addressing pydantic compatibility issues where possible

import sys
import os
import platform
import json
import logging
import asyncio
import selectors
from typing import Dict, List, Optional, Any
from pathlib import Path
from langchain_core.tools import BaseTool



import os
import sys
import json
import logging
import asyncio
import selectors
import platform
import traceback
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from langchain_core.tools import BaseTool

# Force SelectSelector on macOS to fix KqueueSelector hang issue (CPython issue #95600)
def _force_select_selector():
    """
    Force the use of SelectSelector instead of KqueueSelector on macOS systems
    to avoid hanging issues with named pipes and large message buffers.
    This is a critical fix for Python 3.10.9 on macOS.
    """
    if platform.system() == 'Darwin':  # Check if running on macOS
        # Set the selector policy before any asyncio operations
        if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
            # Use the Windows policy which uses SelectSelector by default
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        else:
            # Direct approach for older Python versions
            selector = selectors.SelectSelector()
            loop = asyncio.SelectorEventLoop(selector)
            asyncio.set_event_loop(loop)
        logging.getLogger(__name__).info("Forced SelectSelector for macOS compatibility")

# Apply the fix immediately on module import
_force_select_selector()

class MCPClientManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.servers = self._load_servers()
        self.processes: Dict[str, asyncio.subprocess.Process] = {}
        self.project_root = Path(__file__).parent.parent.parent.parent
        # Increased buffer size for message handling
        self.buffer_size = 65536  # Increased from 8192 to 65536 bytes

    def _load_servers(self) -> Dict[str, Dict]:
        """
        Load MCP server configurations from mcp_servers.json.
        
        Returns:
            Dictionary mapping server names to their configurations.
        """
        servers_path = Path("backend/config/mcp_servers.json")
        if not servers_path.exists():
            self.logger.warning("mcp_servers.json not found, no servers configured")
            return {}
        
        try:
            with open(servers_path, "r") as f:
                servers_list = json.load(f)
                self.logger.info(f"Found {len(servers_list)} servers in mcp_servers.json: {[s['server_name'] for s in servers_list]}")
                servers_dict = {server["server_name"]: server for server in servers_list}
                return servers_dict
        except Exception as e:
            self.logger.error(f"Error loading mcp_servers.json: {str(e)}")
            raise

    async def initialize(self):
        """
        Initialize the MCPClientManager by starting all configured servers.
        """
        self.logger.info("Initializing MCPClientManager")
        
        for server_name in self.servers:
            if server_name not in self.processes:
                self.logger.info(f"Server {server_name} not started yet, starting it now")
                
                # More robust retry mechanism with longer delays between attempts
                for attempt in range(3):
                    try:
                        await self.start_server(server_name)
                        # More timeout for initial server startup
                        await asyncio.wait_for(self._start_minimal_client(server_name), timeout=30)
                        self.logger.info(f"Server {server_name} initialized successfully")
                        break
                    except asyncio.TimeoutError:
                        self.logger.error(f"Attempt {attempt + 1} timed out starting server {server_name}")
                        if attempt < 2:
                            await asyncio.sleep(5)  # Longer delay between retries
                        else:
                            raise
                    except Exception as e:
                        self.logger.error(f"Attempt {attempt + 1} failed to start server {server_name}: {str(e)}")
                        if attempt < 2:
                            await asyncio.sleep(5)  # Longer delay between retries
                        else:
                            raise
        
        self.logger.info(f"MCPClientManager initialization complete. Servers started: {set(self.processes.keys())}")

    async def start_server(self, server_name: str):
        """
        Start an MCP server as a background process and monitor its initial output.
        
        Args:
            server_name: The name of the server to start.
            
        Raises:
            ValueError: If the server is not found in the configuration.
            RuntimeError: If the server fails to start.
        """
        if server_name not in self.servers:
            raise ValueError(f"Server {server_name} not found in configuration")
        
        cmd = self.servers[server_name]["command"]
        script_path = cmd.split(" ", 1)[1] if cmd.startswith("python ") else cmd
        resolved_script_path = (self.project_root / script_path).resolve()
        
        if not resolved_script_path.exists():
            self.logger.error(f"Script not found at {resolved_script_path}")
            raise FileNotFoundError(f"Script not found: {resolved_script_path}")
        
        python_path = os.pathsep.join([os.getcwd(), os.path.dirname(os.path.abspath(__file__))])
        # Add PYTHONUNBUFFERED to env to ensure unbuffered output from subprocesses
        env = {
            **os.environ, 
            "PYTHONPATH": python_path, 
            "PYTHONUNBUFFERED": "1"  # Force unbuffered I/O in the subprocess
        }
        
        cmd = f"python {resolved_script_path}"
        self.logger.info(f"Starting MCP server for {server_name} with command={cmd}, PYTHONPATH={python_path}")
        
        # Increased pipe buffer size to avoid large message issues
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            limit=self.buffer_size  # Increased buffer limit
        )
        
        self.processes[server_name] = process
        
        try:
            # Allow more time for server startup with multiple progress checks
            startup_timeout = 30
            check_interval = 2
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < startup_timeout:
                if process.returncode is not None:
                    stdout, stderr = await process.communicate()
                    self.logger.error(f"Server {server_name} failed to start: exit code {process.returncode}")
                    self.logger.error(f"STDOUT: {stdout.decode() if stdout else 'No output'}")
                    self.logger.error(f"STDERR: {stderr.decode() if stderr else 'No output'}")
                    del self.processes[server_name]
                    raise RuntimeError(f"Failed to start MCP server for {server_name}")
                
                # Capture any initial output without blocking too long
                try:
                    stdout_data, stderr_data = await asyncio.gather(
                        asyncio.wait_for(self._read_stream(process.stdout), timeout=check_interval/2),
                        asyncio.wait_for(self._read_stream(process.stderr), timeout=check_interval/2)
                    )
                    
                    if stdout_data:
                        self.logger.info(f"Initial STDOUT from {server_name}: {stdout_data.decode()}")
                    if stderr_data:
                        self.logger.warning(f"Initial STDERR from {server_name}: {stderr_data.decode()}")
                    
                    # If we got some output and process is still running, consider it started
                    if (stdout_data or stderr_data) and process.returncode is None:
                        self.logger.info(f"Server {server_name} started successfully and is running in the background")
                        return
                
                except asyncio.TimeoutError:
                    # Just continue checking
                    pass
                
                await asyncio.sleep(check_interval)
            
            # If we reached here without returning, the server is likely hanging
            self.logger.warning(f"Server {server_name} startup may be hanging, proceeding with initialization anyway")
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Server {server_name} startup timed out, may be hanging")
            raise RuntimeError(f"Server {server_name} startup timed out")

    async def _read_stream(self, stream):
        """
        Helper method to read from a stream without blocking too long.
        Returns empty bytes if nothing is available.
        """
        if stream.at_eof():
            return b""
        try:
            return await stream.read(self.buffer_size)
        except Exception:
            return b""

    async def _start_minimal_client(self, server_name: str):
        """
        Start a minimal stdio client to prevent server hang by sending an initialize request and reading response.
        
        Enhanced with better JSON handling and response accumulation.
        """
        try:
            process = self.processes.get(server_name)
            if not process or process.stdin is None:
                self.logger.error(f"No valid process or stdin for {server_name}")
                return
            
            # Send JSON-RPC initialize request
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": 1
            }).encode() + b"\\n"
            
            process.stdin.write(request)
            await process.stdin.drain()
            
            # Improved response reading with multi-line JSON handling
            for attempt in range(3):
                try:
                    response_data = await self._read_json_response(process.stdout, timeout=20)
                    
                    if response_data:
                        self.logger.info(f"Client for {server_name} received response: {response_data}")
                        return
                    
                    self.logger.warning(f"Attempt {attempt + 1}: Empty response from {server_name}")
                    
                except asyncio.TimeoutError:
                    self.logger.warning(f"Attempt {attempt + 1}: Timeout reading from {server_name}")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Attempt {attempt + 1}: Invalid JSON from {server_name}, error: {str(e)}")
                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1}: Error reading from {server_name}: {str(e)}")
                
                if attempt < 2:
                    await asyncio.sleep(5)  # Longer delay between retries
            
            self.logger.error(f"Failed to get valid response from {server_name} after retries")
            
        except Exception as e:
            self.logger.error(f"Error in minimal client for {server_name}: {str(e)}")
            self.logger.debug(traceback.format_exc())

    async def _read_json_response(self, stream, timeout=15):
        """
        Read and parse a JSON response from an asyncio stream.
        
        This method handles multi-line JSON responses and accumulates data until a valid JSON object is found.
        If the timeout is reached before a valid JSON is found, a TimeoutError is raised.
        
        Args:
            stream: The asyncio stream to read from
            timeout: Maximum time to wait for a complete JSON response
            
        Returns:
            Parsed JSON object or None if no valid JSON could be parsed
            
        Raises:
            asyncio.TimeoutError: If timeout is reached before a complete response
            json.JSONDecodeError: If the response contains invalid JSON
        """
        response_data = b""
        start_time = asyncio.get_event_loop().time()
        json_obj = None
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            # Check if we already have a complete JSON object
            if response_data:
                try:
                    json_obj = json.loads(response_data.decode())
                    return json_obj
                except json.JSONDecodeError:
                    # Not a complete JSON yet, continue reading
                    pass
            
            # Read more data with a short timeout to prevent blocking
            try:
                chunk = await asyncio.wait_for(stream.readline(), timeout=1)
                if not chunk:  # EOF
                    break
                
                response_data += chunk
                
                # Try parsing accumulated data after each chunk
                try:
                    # Try parsing as a single object first
                    json_obj = json.loads(response_data.decode())
                    return json_obj
                except json.JSONDecodeError:
                    # Try finding complete JSON objects line by line
                    for line in response_data.splitlines():
                        if line.strip():
                            try:
                                json_obj = json.loads(line.decode() if isinstance(line, bytes) else line)
                                return json_obj
                            except json.JSONDecodeError:
                                continue
            
            except asyncio.TimeoutError:
                # Short timeout on readline expired, but we still have time in our overall timeout
                continue
        
        # If we've accumulated data but couldn't parse it as JSON, raise the error
        if response_data:
            try:
                return json.loads(response_data.decode())
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON from accumulated data: {response_data.decode()}")
                raise e
        
        # If we got here without returning, we timed out
        raise asyncio.TimeoutError("Timed out waiting for complete JSON response")

    async def shutdown(self):
        """
        Shut down all running MCP servers.
        """
        self.logger.info("Shutting down MCPClientManager")
        
        for server_name, process in list(self.processes.items()):
            if process.returncode is None:
                self.logger.info(f"Stopping server {server_name}")
                
                # Try to gracefully terminate the process
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                    self.logger.info(f"Server {server_name} stopped")
                except asyncio.TimeoutError:
                    self.logger.warning(f"Timeout stopping server {server_name}, forcing kill")
                    process.kill()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        self.logger.error(f"Failed to kill server {server_name}")
            else:
                self.logger.info(f"Server {server_name} already stopped (code {process.returncode})")
        
        self.processes.clear()
        self.logger.info("MCPClientManager shutdown complete")

    async def get_tools(self, server_names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Get available tools from the specified MCP servers via stdio.
        
        Args:
            server_names: List of server names to query. If None, queries all servers.
            
        Returns:
            List of available tools.
        """
        tools = []
        server_names = server_names or list(self.servers.keys())
        
        for server_name in server_names:
            if server_name not in self.servers:
                self.logger.warning(f"Server {server_name} not found, skipping")
                continue
            
            try:
                process = self.processes.get(server_name)
                if not process or process.stdin is None:
                    self.logger.error(f"No valid process or stdin for {server_name}")
                    continue
                
                # Send JSON-RPC list_tools request
                request = json.dumps({
                    "jsonrpc": "2.0",
                    "method": "list_tools",
                    "params": {},
                    "id": 2
                }).encode() + b"\\n"
                
                process.stdin.write(request)
                await process.stdin.drain()
                
                # Improved response reading with better error handling
                try:
                    response = await self._read_json_response(process.stdout, timeout=20)
                    
                    if response and "result" in response:
                        for tool_data in response["result"]:
                            tools.append(BaseTool(
                                name=tool_data.get("name", f"{server_name}_tool"),
                                description=tool_data.get("description", f"Tool from {server_name}"),
                                func=lambda x, name=tool_data["name"], srv=server_name: self._execute_tool(srv, name, x)
                            ))
                        self.logger.info(f"Fetched {len(response['result'])} tools from {server_name}")
                    else:
                        self.logger.warning(f"Error in list_tools response from {server_name}: {response}")
                
                except asyncio.TimeoutError:
                    self.logger.warning(f"Timeout fetching tools from {server_name}")
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Invalid JSON response from {server_name}: {str(e)}")
                except Exception as e:
                    self.logger.error(f"Error getting tools from {server_name}: {str(e)}")
            
            except Exception as e:
                self.logger.error(f"Error getting tools from {server_name}: {str(e)}")
        
        return tools

    async def execute_tool(self, server_name: str, tool_name: str, params: Dict[str, any]) -> Dict[str, any]:
        """
        Execute a specific tool on an MCP server via stdio.
        
        Args:
            server_name: The name of the server to execute the tool on.
            tool_name: The name of the tool to execute.
            params: Parameters to pass to the tool.
            
        Returns:
            Result of the tool execution.
        """
        if server_name not in self.servers:
            raise ValueError(f"Server {server_name} not found")
        
        if server_name not in self.processes:
            raise ValueError(f"Server {server_name} is not running")
        
        try:
            process = self.processes[server_name]
            if not process or process.stdin is None:
                self.logger.error(f"No valid process or stdin for {server_name}")
                raise RuntimeError(f"No valid process for {server_name}")
            
            # Send JSON-RPC call_tool request
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {"name": tool_name, "arguments": params},
                "id": 3
            }).encode() + b"\\n"
            
            process.stdin.write(request)
            await process.stdin.drain()
            
            # Read response with improved handling
            try:
                response = await self._read_json_response(process.stdout, timeout=30)
                
                if response and "result" in response:
                    self.logger.info(f"Executed tool {tool_name} on {server_name}")
                    return response["result"]
                else:
                    error_msg = response.get("error", {"message": "Unknown error"}) if response else "No response"
                    self.logger.error(f"Error in call_tool response from {server_name}: {error_msg}")
                    raise RuntimeError(f"Tool execution failed: {error_msg}")
            
            except asyncio.TimeoutError:
                self.logger.error(f"Timeout executing tool {tool_name} on {server_name}")
                raise RuntimeError(f"Timeout executing tool {tool_name}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON response from {server_name}: {str(e)}")
                raise RuntimeError("Invalid JSON response")
            
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name} on {server_name}: {str(e)}")
            raise

    async def _execute_tool(self, server_name: str, tool_name: str, params: Dict[str, any]) -> str:
        """
        Helper method to execute a tool and return result as string for BaseTool.func.
        """
        result = await self.execute_tool(server_name, tool_name, params)
        return str(result)
