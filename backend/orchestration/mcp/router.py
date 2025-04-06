from typing import List, Dict, Any, Optional
from ..rag.vector_store import VectorStore
from ..rag.retriever import RAGRetriever
from .client_manager import MCPClientManager
from langchain_core.tools import BaseTool
import asyncio
import logging

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
        server_names = []
        for server_file in self.client_manager.server_dir.glob("*_server.py"):
            server_name = server_file.stem.replace("_server", "")
            server_names.append(server_name)
            
        # Start each server and get its endpoints
        for server_name in server_names:
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
        
    async def route_query(self, query: str) -> List[BaseTool]:
        """
        Route a query to the appropriate MCP endpoints and return the tools.
        
        Args:
            query: The query to route
            
        Returns:
            A list of LangChain tools from the appropriate MCP endpoints
        """
        try:
            # Use RAG to determine which endpoints to call
            endpoint_ids = await self.rag_retriever.process_query(query)
            
            # Get tools from the selected endpoints
            return await self.client_manager.get_tools(endpoint_ids)
        except Exception as e:
            logger.error(f"Error routing query: {str(e)}")
            # Return an empty list of tools if there's an error
            # This allows the workflow to continue with degraded functionality
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
            tools = client.get_tools()
            for tool in tools:
                if tool.name == tool_name:
                    return await tool.ainvoke(**kwargs)
                    
        raise ValueError(f"Tool not found: {tool_name}")
