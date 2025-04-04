from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.staticfiles import StaticFiles
import logging
import json
import os
from typing import Dict, Any, Optional
import socketio
import asyncio

from backend.services.communication.socket_service import SocketService
from backend.orchestration.workflow_manager import WorkflowManager
from backend.state import ResearchState
from backend.utils.api_config import APIConfig

def register_routes(
    fastapi_app: FastAPI,
    socket_service: SocketService,
    workflow_manager: WorkflowManager,
    static_dir: str = "docs"
):
    """
    Register routes and handlers for the FastAPI application.
    
    Args:
        fastapi_app: The FastAPI application instance
        socket_service: The Socket.IO service
        workflow_manager: The workflow manager for handling report generation
        static_dir: Directory to serve static files from
    """
    logger = logging.getLogger("XplainCrypto")
    
    # Mount static files
    if os.path.exists(static_dir):
        fastapi_app.mount("/docs", StaticFiles(directory=static_dir), name="docs")
        logger.info(f"Mounted static files from {static_dir}")
    else:
        logger.warning(f"Static directory {static_dir} does not exist")
    
    # Register message handler
    @socket_service.sio.on("message")
    async def handle_message(sid, data):
        """Handle message event from client."""
        logger.info(f"Received message from client {sid}: {data}")
        
        try:
            # Extract data from the message - handle both string and object formats
            if isinstance(data, str):
                # If data is just a string (e.g., "ONDO"), treat it as the project name
                project_name = data.strip()
                fast_mode = False
                logger.info(f"Received project name as string: '{project_name}'")
            elif isinstance(data, dict):
                # If data is a JSON object, extract project_name field
                project_name = data.get("project_name")
                fast_mode = data.get("fast_mode", False)
                logger.info(f"Received project name from JSON: '{project_name}'")
            else:
                # Invalid message format
                error_msg = f"Invalid message format: {type(data)}"
                logger.error(error_msg)
                await socket_service.emit_error(sid, error_msg)
                return
            
            if not project_name:
                await socket_service.emit_error(sid, "Project name is required")
                return
            
            # Debug: Log the exact project name for tracing
            logger.info(f"Using project name for workflow: '{project_name}' (type: {type(project_name)})")
            
            # Update session information
            if sid in socket_service.active_sessions:
                socket_service.active_sessions[sid]["project"] = project_name
                socket_service.active_sessions[sid]["last_activity"] = asyncio.get_event_loop().time()
                logger.info(f"Updated session {sid} with project: '{project_name}'")
            
            # Send initial progress
            await socket_service.emit(
                "progress", 
                {
                    "message": f"Initiating research on {project_name}...",
                    "step": "initialization",
                    "percentage": 0
                }, 
                room=sid
            )
            
            # Execute workflow asynchronously
            # Debug: Log immediately before workflow execution
            logger.info(f"About to execute workflow with project name: '{project_name}'")
            result = await workflow_manager.execute_workflow(project_name, fast_mode)
            
            if "error" in result:
                logger.error(f"Workflow error: {result['error']}")
                await socket_service.emit_error(sid, result["error"])
                return
            
            # Send completion message
            logger.info(f"Workflow completed for project: '{project_name}'")
            await socket_service.emit(
                "complete",
                {
                    "message": f"Report for {project_name} completed in {result['duration']:.2f} seconds",
                    "report_path": result.get("report_path"),
                    "metrics": {
                        "total_time": result["duration"],
                        "steps_completed": 6,
                        "errors": len(result.get("errors", [])),
                        "report_path": result.get("report_path")
                    }
                },
                room=sid
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            await socket_service.emit_error(sid, f"Server error: {str(e)}")
    
    # Root endpoint
    @fastapi_app.get("/")
    async def root():
        return {"message": "XplainCrypto API is running"}

    # API Configuration endpoints
    @fastapi_app.get("/api/config")
    async def get_api_config():
        """Get the current API configuration."""
        config = APIConfig.get_api_config()
        return {"api_config": config}

    @fastapi_app.post("/api/config/{api_name}")
    async def set_api_config(api_name: str, enabled: bool = Body(..., embed=True)):
        """Update the configuration for a specific API."""
        os.environ[f"{api_name.upper()}_ENABLED"] = "true" if enabled else "false"
        logger.info(f"Set {api_name} API to {'enabled' if enabled else 'disabled'}")
        return {"message": f"{api_name} API {('enabled' if enabled else 'disabled')}"}

    # Add a health check endpoint
    @fastapi_app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "ok",
            "active_sessions": socket_service.get_session_count(),
            "active_workflows": len(workflow_manager.get_active_workflows())
        }
    
    # Extended health check with API status
    @fastapi_app.get("/api/health")
    async def api_health_check():
        """API-specific health check endpoint."""
        return {
            "status": "ok",
            "api_status": {
                name: config["enabled"] and config["has_key"] 
                for name, config in APIConfig.get_api_config().items()
            }
        }
    
    # Add a status endpoint
    @fastapi_app.get("/status")
    async def server_status():
        """Get detailed server status."""
        return {
            "status": "ok",
            "active_sessions": socket_service.get_active_sessions(),
            "active_workflows": workflow_manager.get_active_workflows(),
            "recent_workflows": workflow_manager.get_completed_workflows(5)
        }
    
    logger.info("Routes registered successfully") 