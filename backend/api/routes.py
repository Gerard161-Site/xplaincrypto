from fastapi import APIRouter, HTTPException
from typing import List, Optional
from backend.api.models import ResearchRequest, ChatRequest, ToolExecutionRequest, ApiResponse
from backend.orchestration.workflow_manager import WorkflowManager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

workflow_manager = WorkflowManager(logger=logger)

@router.on_event("startup")
async def startup_event():
    logger.info("Starting application initialization")
    logger.info("Initializing workflow manager")
    await workflow_manager.initialize()
    logger.info("Application initialization complete")

@router.post("/research", response_model=ApiResponse)
async def execute_research(request: ResearchRequest):
    try:
        result = await workflow_manager.execute_research_workflow(request.query, request.context)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in /api/research: {str(e)}")
        return ApiResponse(success=False, data=None, error=str(e))

@router.post("/chat", response_model=ApiResponse)
async def execute_chat(request: ChatRequest):
    try:
        result = await workflow_manager.execute_chat_workflow(request.query, request.project_name)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in /api/chat: {str(e)}")
        return ApiResponse(success=False, data=None, error=str(e))

@router.get("/tools", response_model=ApiResponse)
async def get_tools(server_names: Optional[List[str]] = None):
    """
    Get all available tools from the specified MCP servers.
    
    Args:
        server_names: List of server names to get tools from. If None, gets tools from all available servers.
        
    Returns:
        A list of available tools
    """
    try:
        tools = await workflow_manager.get_available_tools(server_names)
        tool_data = [{"name": tool.name, "description": tool.description} for tool in tools]
        return ApiResponse(success=True, data=tool_data)
    except Exception as e:
        logger.error(f"Error in /api/tools: {str(e)}")
        return ApiResponse(success=False, data=None, error=str(e))

@router.post("/execute-tool", response_model=ApiResponse)
async def execute_tool(request: ToolExecutionRequest):
    try:
        result = await workflow_manager.execute_tool(request.tool_name, **request.arguments)
        return ApiResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Error in /api/execute-tool: {str(e)}")
        return ApiResponse(success=False, data=None, error=str(e))