import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.api.mcp_api import app
from backend.agent.workflow_manager_mcp import WorkflowManagerWithMCP

# Create test client
client = TestClient(app)

@pytest.fixture
def mock_workflow_manager():
    """Fixture to mock the workflow manager."""
    with patch("backend.api.mcp_api.workflow_manager") as mock_manager:
        yield mock_manager

def test_execute_research_endpoint(mock_workflow_manager):
    """Test the research endpoint."""
    # Set up mock
    mock_workflow_manager.execute_research_workflow.return_value = {"agent_outcome": "Mock research result"}
    
    # Test the endpoint
    response = client.post(
        "/api/research",
        json={"query": "What is the price of Bitcoin?", "context": {}}
    )
    
    # Verify the response
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "data" in response.json()
    assert response.json()["data"]["agent_outcome"] == "Mock research result"
    
    # Verify that the workflow manager was called
    mock_workflow_manager.execute_research_workflow.assert_called_once()

def test_get_tools_endpoint(mock_workflow_manager):
    """Test the tools endpoint."""
    # Set up mock
    mock_tool = MagicMock()
    mock_tool.name = "mock_tool"
    mock_tool.description = "A mock tool for testing"
    mock_workflow_manager.get_available_tools.return_value = [mock_tool]
    
    # Test the endpoint
    response = client.get("/api/tools")
    
    # Verify the response
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "data" in response.json()
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["name"] == "mock_tool"
    assert response.json()["data"][0]["description"] == "A mock tool for testing"
    
    # Verify that the workflow manager was called
    mock_workflow_manager.get_available_tools.assert_called_once()

def test_execute_tool_endpoint(mock_workflow_manager):
    """Test the execute tool endpoint."""
    # Set up mock
    mock_workflow_manager.execute_tool.return_value = {"result": "Mock tool result"}
    
    # Test the endpoint
    response = client.post(
        "/api/execute-tool",
        json={"tool_name": "mock_tool", "arguments": {"arg1": "value1"}}
    )
    
    # Verify the response
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "data" in response.json()
    assert response.json()["data"]["result"] == "Mock tool result"
    
    # Verify that the workflow manager was called
    mock_workflow_manager.execute_tool.assert_called_once_with("mock_tool", arg1="value1")

def test_error_handling(mock_workflow_manager):
    """Test error handling in the API."""
    # Set up mock to raise an exception
    mock_workflow_manager.execute_research_workflow.side_effect = Exception("Test error")
    
    # Test the endpoint
    response = client.post(
        "/api/research",
        json={"query": "What is the price of Bitcoin?", "context": {}}
    )
    
    # Verify the response
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["error"] == "Test error"
    
    # Verify that the workflow manager was called
    mock_workflow_manager.execute_research_workflow.assert_called_once()
