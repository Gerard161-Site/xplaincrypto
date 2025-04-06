import unittest
import asyncio
import os
from unittest.mock import patch, MagicMock
from backend.orchestration.rag.vector_store import VectorStore
from backend.orchestration.rag.retriever import RAGRetriever
from backend.orchestration.mcp.router import MCPRouter
from backend.agent.enhanced_researcher_mcp import EnhancedResearcherWithMCP
from backend.agent.workflow_manager_mcp import WorkflowManagerWithMCP

class TestMCPIntegration(unittest.TestCase):
    """Test cases for the MCP integration."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        os.environ["PINECONE_API_KEY"] = "mock-pinecone-api-key"
        os.environ["OPENAI_API_KEY"] = "mock-openai-api-key"
        
        # Create mock vector store
        self.mock_vector_store = MagicMock(spec=VectorStore)
        self.mock_vector_store.query.return_value = [
            ("coingecko", "CoinGecko API for cryptocurrency data"),
            ("tavily", "Tavily API for web search")
        ]
        
    @patch("backend.orchestration.rag.vector_store.get_vector_store")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.start_server")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.get_tools")
    async def test_rag_retriever(self, mock_get_tools, mock_start_server, mock_get_vector_store):
        """Test the RAG retriever component."""
        # Set up mocks
        mock_get_vector_store.return_value = self.mock_vector_store
        mock_get_tools.return_value = []
        
        # Create RAG retriever
        retriever = RAGRetriever(self.mock_vector_store)
        
        # Test process_query
        endpoints = await retriever.process_query("What is the price of Bitcoin?")
        
        # Verify that the vector store was queried
        self.mock_vector_store.query.assert_called_once()
        
        # Verify that endpoints were returned
        self.assertIsInstance(endpoints, list)
        
    @patch("backend.orchestration.rag.vector_store.get_vector_store")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.start_server")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.get_tools")
    async def test_mcp_router(self, mock_get_tools, mock_start_server, mock_get_vector_store):
        """Test the MCP router component."""
        # Set up mocks
        mock_get_vector_store.return_value = self.mock_vector_store
        mock_get_tools.return_value = []
        
        # Create MCP router
        router = MCPRouter(self.mock_vector_store)
        
        # Test route_query
        tools = await router.route_query("What is the price of Bitcoin?")
        
        # Verify that tools were returned
        self.assertIsInstance(tools, list)
        
    @patch("backend.orchestration.rag.vector_store.get_vector_store")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.start_server")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.get_tools")
    @patch("backend.agent.enhanced_researcher_mcp.EnhancedResearcherWithMCP.create_agent")
    async def test_enhanced_researcher(self, mock_create_agent, mock_get_tools, mock_start_server, mock_get_vector_store):
        """Test the Enhanced Researcher with MCP."""
        # Set up mocks
        mock_get_vector_store.return_value = self.mock_vector_store
        mock_get_tools.return_value = []
        
        # Mock the agent executor
        mock_agent = MagicMock()
        mock_agent.return_value = {"agent_outcome": "Mock research result"}
        mock_create_agent.return_value = mock_agent
        
        # Create Enhanced Researcher
        researcher = EnhancedResearcherWithMCP()
        
        # Test execute_workflow
        result = await researcher.execute_workflow("What is the price of Bitcoin?")
        
        # Verify that the workflow was executed
        self.assertIn("agent_outcome", result)
        
    @patch("backend.orchestration.rag.vector_store.get_vector_store")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.start_server")
    @patch("backend.orchestration.mcp.client_manager.MCPClientManager.get_tools")
    @patch("backend.agent.enhanced_researcher_mcp.EnhancedResearcherWithMCP.execute_workflow")
    async def test_workflow_manager(self, mock_execute_workflow, mock_get_tools, mock_start_server, mock_get_vector_store):
        """Test the Workflow Manager with MCP."""
        # Set up mocks
        mock_get_vector_store.return_value = self.mock_vector_store
        mock_get_tools.return_value = []
        mock_execute_workflow.return_value = {"agent_outcome": "Mock research result"}
        
        # Create Workflow Manager
        manager = WorkflowManagerWithMCP()
        
        # Test execute_research_workflow
        result = await manager.execute_research_workflow("What is the price of Bitcoin?")
        
        # Verify that the workflow was executed
        self.assertIn("agent_outcome", result)

def run_async_test(test_case):
    """Run an async test case."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_case)

if __name__ == "__main__":
    unittest.main()
