from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class ResearchRequest(BaseModel):
    """Request model for research queries."""
    query: str
    context: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    """Request model for chatbot queries."""
    query: str
    project_name: str = "unknown"

class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    arguments: Dict[str, Any]

class ApiResponse(BaseModel):
    """Generic API response model."""
    success: bool
    data: Any
    error: Optional[str] = None