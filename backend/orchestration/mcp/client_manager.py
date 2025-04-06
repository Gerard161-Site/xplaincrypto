from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
import os
import subprocess
import asyncio
from pathlib import Path

class MCPClientManager:
    """
    Manager for MCP clients that connects to multiple retriever servers.
    This class handles the lifecycle of MCP server processes and client connections.
    """
    
    def __init__(self):
        self.server_processes = {}
        self.base_dir = Path(__file__).parent.resolve()
        self.server_dir = self.base_dir / "retriever_servers"
        
    async def start_server(self, server_name: str) -> None:
        """Start an MCP server process."""
        server_path = self.server_dir / f"{server_name}_server.py"
        if not server_path.exists():
            raise FileNotFoundError(f"Server file not found: {server_path}")
            
        # Set the Python path to include the project root directory
        project_root = self.base_dir.parent.parent.resolve()  # Go up two levels from base_dir
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        if python_path:
            env["PYTHONPATH"] = f"{project_root}:{python_path}"
        else:
            env["PYTHONPATH"] = str(project_root)
            
        print(f"Starting MCP server for {server_name} with PYTHONPATH={env['PYTHONPATH']}")
            
        # Start the server process with the updated environment
        process = subprocess.Popen(
            ["python", str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )
        self.server_processes[server_name] = process
        
        # Give the server a moment to start and check for immediate errors
        await asyncio.sleep(1)
        
        # Check if process is still running
        if process.poll() is not None:
            # Process has already exited, read error output
            stderr = process.stderr.read()
            raise RuntimeError(f"Server process for {server_name} failed to start: {stderr}")
        
    async def stop_server(self, server_name: str) -> None:
        """Stop an MCP server process."""
        if server_name in self.server_processes:
            process = self.server_processes[server_name]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            del self.server_processes[server_name]
            
    async def stop_all_servers(self) -> None:
        """Stop all MCP server processes."""
        for server_name in list(self.server_processes.keys()):
            await self.stop_server(server_name)
            
    @asynccontextmanager
    async def create_client(self, server_names: Optional[List[str]] = None) -> AsyncIterator[MultiServerMCPClient]:
        """
        Create an MCP client connected to the specified servers.
        
        Args:
            server_names: List of server names to connect to. If None, connects to all available servers.
            
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
        for server_name in server_names:
            await self.start_server(server_name)
            
        # Create the connection configurations
        connections = {}
        for server_name in server_names:
            connections[server_name] = {
                "command": "python",
                "args": [str(self.server_dir / f"{server_name}_server.py")],
                "transport": "stdio"
            }
            
        # Create and yield the client
        async with MultiServerMCPClient(connections) as client:
            try:
                yield client
            finally:
                # Stop all servers when the client is closed
                await self.stop_all_servers()
                
    async def get_tools(self, server_names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        Get all tools from the specified servers.
        
        Args:
            server_names: List of server names to get tools from. If None, gets tools from all available servers.
            
        Returns:
            A list of LangChain tools from the specified servers.
        """
        async with self.create_client(server_names) as client:
            return client.get_tools()
