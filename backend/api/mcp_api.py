from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from backend.orchestration.workflow_manager import WorkflowManager
from backend.orchestration.mcp.initialize_endpoints import initialize_pinecone_endpoints
import logging
import os

# Set up logging
logger = logging.getLogger(__name__)

# Set MCP environment variable
os.environ["USE_MCP"] = "true"

# Initialize the FastAPI app
app = FastAPI(title="XplainCrypto API with MCP Integration")

# Initialize the workflow manager
workflow_manager = WorkflowManager(logger=logger)

# Initialize the workflow manager and Pinecone endpoints on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting application initialization")
    
    # First initialize Pinecone with MCP endpoint metadata
    logger.info("Initializing Pinecone with MCP endpoint metadata")
    endpoints_initialized = await initialize_pinecone_endpoints()
    if not endpoints_initialized:
        logger.warning("Failed to initialize Pinecone with MCP endpoint metadata")
    
    # Then initialize the workflow manager
    logger.info("Initializing workflow manager")
    await workflow_manager.initialize()
    logger.info("Application initialization complete")

class ResearchRequest(BaseModel):
    """Request model for research queries."""
    query: str
    context: Optional[Dict[str, Any]] = None

class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    arguments: Dict[str, Any]

class ApiResponse(BaseModel):
    """Generic API response model."""
    success: bool
    data: Any
    error: Optional[str] = None

@app.post("/api/research", response_model=ApiResponse)
async def execute_research(request: ResearchRequest):
    """
    Execute the research workflow for a given query.
    
    Args:
        request: The research request containing the query and optional context
        
    Returns:
        The result of the research workflow
    """
    try:
        result = await workflow_manager.execute_research_workflow(request.query, request.context)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, data=None, error=str(e))

@app.get("/api/tools", response_model=ApiResponse)
async def get_tools(server_names: Optional[List[str]] = None):
    """
    Get all available tools from the specified MCP servers.
    
    Args:
        server_names: List of server names to get tools from. If None, gets tools from all available servers.
        
    Returns:
        A list of available tools
    """
    try:
        tools = workflow_manager.get_available_tools(server_names)
        # Convert tools to a serializable format
        tool_data = [{"name": tool.name, "description": tool.description} for tool in tools]
        return ApiResponse(success=True, data=tool_data)
    except Exception as e:
        return ApiResponse(success=False, data=None, error=str(e))

@app.post("/api/execute-tool", response_model=ApiResponse)
async def execute_tool(request: ToolExecutionRequest):
    """
    Execute a specific MCP tool.
    
    Args:
        request: The tool execution request containing the tool name and arguments
        
    Returns:
        The result of the tool execution
    """
    try:
        result = await workflow_manager.execute_tool(request.tool_name, **request.arguments)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        return ApiResponse(success=False, data=None, error=str(e))

@app.get("/api/initialize-endpoints", response_model=ApiResponse)
async def reinitialize_endpoints():
    """
    Manually reinitialize Pinecone with MCP endpoint metadata.
    This can be used if the automatic initialization failed or if endpoints were updated.
    
    Returns:
        Success status of the initialization
    """
    try:
        success = await initialize_pinecone_endpoints()
        return ApiResponse(success=success, data={"message": "Endpoints initialized successfully"})
    except Exception as e:
        return ApiResponse(success=False, data=None, error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
