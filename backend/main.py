# backend/main.py
import logging
import os
import sys
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import socketio
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import time
import traceback
import json

# Ensure we're adding project root to path first thing
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Add dotenv loading with explicit logging
from dotenv import load_dotenv
print("Loading environment variables in main.py...")
load_dotenv()  # This loads .env file variables into os.environ

# Print API key status
api_key = os.getenv("COINMARKETCAP_API_KEY", "")
print(f"COINMARKETCAP_API_KEY is {'available' if api_key else 'NOT AVAILABLE'}")
print(f"API key length: {len(api_key)}")

# Import the logging config setup
from backend.services.reporting.logging_config import setup_logging

# Define request models
class ProjectRequest(BaseModel):
    name: str
    fast_mode: bool = False

class ResearchRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None

class VisualizeRequest(BaseModel):
    project_name: str
    visualization_type: str
    time_period: Optional[str] = "30d"
    data_source: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None

# Set up proper logging with file handler
logger = setup_logging(
    log_file="logs/xplaincrypto.log",
    log_level="INFO"
)

# Set tokenizers parallelism to false to avoid deadlocks
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Initialize Socket.IO with explicit CORS origins
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://xplaincrypto.com"],
    logger=logging.getLogger("socketio")
)

# Initialize FastAPI app
fastapi_app = FastAPI(
    title="XplainCrypto",
    description="Cryptocurrency Research Platform",
    version="1.0.0"
)

# Add CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://xplaincrypto.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the combined ASGI app
app = socketio.ASGIApp(sio, fastapi_app)

# Initialize the server components
from backend.orchestration.workflow_manager import WorkflowManager
from backend.services.reporting.progress_tracker import ProgressTracker
from backend.services.reporting.error_reporter import ErrorReporter

# Initialize global WorkflowManager with progress tracking
progress_tracker = ProgressTracker(logger=logger)
error_reporter = ErrorReporter(logger=logger)
workflow_manager = WorkflowManager(
    logger=logger,
    progress_tracker=progress_tracker,
    error_reporter=error_reporter
)

# Track active socket sessions
active_sessions = {}

@fastapi_app.on_event("startup")
async def startup_event():
    """Initialize app components on startup."""
    logger.info("Starting application initialization")
    
    # Initialize MCP servers first to ensure they're ready
    try:
        from backend.orchestration.mcp.client_manager import MCPClientManager
        # Create a singleton instance of the client manager
        global mcp_client_manager
        mcp_client_manager = MCPClientManager()
        
        # Start all required servers upfront - make sure to include all required servers
        server_names = ['coingecko', 'coinmarketcap', 'defillama', 'tavily', 'huggingface', 'tokenomics']
        logger.info(f"Starting {len(server_names)} MCP servers...")
        
        # Process each server one by one for better error control
        for server_name in server_names:
            try:
                logger.info(f"Starting MCP server: {server_name}")
                await mcp_client_manager.start_server(server_name)
                logger.info(f"Successfully started MCP server: {server_name}")
            except Exception as e:
                logger.error(f"Failed to start MCP server {server_name}: {str(e)}")
                # Continue with other servers even if one fails
        
        # Ensure we have started the essential servers
        try:
            await mcp_client_manager.initialize()
            logger.info("MCP client manager initialized")
        except Exception as e:
            logger.error(f"Error during MCP client manager initialization: {str(e)}")
            # Continue even if initialization fails - the servers are already started individually
    except Exception as e:
        logger.error(f"Failed to initialize MCP client manager: {str(e)}")
    
    # Now set up other components
    try:
        # Initialize socketio and other components
        logger.info("Initializing other components")
        # await initialize_socketio(socketio_app)  # This seems to be undefined
    except Exception as e:
        logger.error(f"Failed to initialize other components: {str(e)}")
    
    logger.info("Application initialization complete")

@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    logger.info(f"Client connected: {sid}")
    active_sessions[sid] = {
        "connected_at": asyncio.get_event_loop().time(),
        "project": None
    }

@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {sid}")
    if sid in active_sessions:
        del active_sessions[sid]

@sio.event
async def message(sid, data):
    """Handle message from client."""
    logger.info(f"Received message from client {sid}: {data}")
    
    try:
        # Extract project name from message
        if isinstance(data, str):
            project_name = data.strip()
            fast_mode = False
        elif isinstance(data, dict):
            project_name = data.get("project_name")
            fast_mode = data.get("fast_mode", False)
        else:
            await sio.emit("error", "Invalid message format", room=sid)
            return
            
        if not project_name:
            await sio.emit("error", "Project name is required", room=sid)
            return
            
        # Update session information
        if sid in active_sessions:
            active_sessions[sid]["project"] = project_name
            
        # Send initial progress
        await sio.emit(
            "progress", 
            {
                "message": f"Initiating research on {project_name}...",
                "step": "initialization",
                "percentage": 0
            }, 
            room=sid
        )
        
        # Execute workflow (async, requires await)
        result = await workflow_manager.execute_workflow(project_name, fast_mode)
        
        if "error" in result:
            logger.error(f"Workflow error: {result['error']}")
            await sio.emit("error", result["error"], room=sid)
            return
            
        # Send completion message
        await sio.emit(
            "complete",
            {
                "message": f"Report for {project_name} completed",
                "report_path": result.get("report_path"),
                "metrics": {
                    "total_time": result.get("duration", 0),
                    "steps_completed": 6,
                    "errors": len(result.get("errors", [])),
                    "report_path": result.get("report_path")
                }
            },
            room=sid
        )
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        await sio.emit("error", f"Server error: {str(e)}", room=sid)

@fastapi_app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "XplainCrypto API is running"}

@fastapi_app.post("/api/research")
async def generate_research(request: ResearchRequest):
    """Generate a research report based on the provided query."""
    try:
        logger.info(f"Received research request: {request.query}")
        
        # Initialize the LLM if not already done
        if not workflow_manager.llm:
            workflow_manager.initialize_llm()
            await workflow_manager.initialize()
        
        # Execute the research workflow
        result = await workflow_manager.execute_research_workflow(
            query=request.query,
            context=request.context
        )
        
        return result
    except Exception as e:
        logger.error(f"Error generating research: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@fastapi_app.post("/api/visualize")
async def generate_visualization(request: VisualizeRequest):
    """Generate a specific visualization for a project."""
    try:
        logger.info(f"Generating visualization {request.visualization_type} for {request.project_name}")
        
        # Initialize the LLM if not already done
        if not workflow_manager.llm:
            workflow_manager.initialize_llm()
            await workflow_manager.initialize()
        
        # Create visualization request with all parameters
        visualization_request = {
            "type": request.visualization_type,
            "time_period": request.time_period
        }
        
        # Add data source if provided
        if request.data_source:
            visualization_request["data_source"] = request.data_source
            
        # Add any additional parameters
        if request.additional_params:
            visualization_request.update(request.additional_params)
        
        # Run workflow in query mode
        result = await workflow_manager.execute_workflow(
            project_name=request.project_name,
            fast_mode=True,
            mode="query",
            visualization_request=visualization_request
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Filter visualizations for the requested type
        visualizations = result.get("visualization_list", [])
        target_viz = next((viz for viz in visualizations if viz["type"] == request.visualization_type), None)
        
        if not target_viz:
            raise HTTPException(status_code=404, detail=f"Visualization type {request.visualization_type} not found")
        
        # Check if client wants the file or just metadata
        return {
            "message": f"Visualization generated for {request.project_name}",
            "visualization": target_viz,
            "path": target_viz["path"]
        }
    except Exception as e:
        logger.error(f"Error generating visualization: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@fastapi_app.get("/api/status/{project_name}")
async def get_project_status(project_name: str):
    """Get the status of a project."""
    try:
        # Get active workflows
        active_workflows = workflow_manager.get_active_workflows()
        
        # Find workflow for the specified project
        workflow = next((w for w in active_workflows if w["project_name"] == project_name), None)
        
        if workflow:
            # Project is actively being processed
            progress = progress_tracker.get_progress(project_name)
            return {
                "status": "processing",
                "project_name": project_name,
                "running_time": workflow["running_time"],
                "progress": progress
            }
        
        # Check completed workflows
        completed_workflows = workflow_manager.get_completed_workflows()
        completed = next((w for w in completed_workflows if w["project_name"] == project_name), None)
        
        if completed:
            return {
                "status": "completed",
                "project_name": project_name,
                "completed_at": completed["completed_at"],
                "duration": completed["duration"]
            }
        
        # Project not found
        return {
            "status": "not_found",
            "project_name": project_name
        }
    except Exception as e:
        logger.error(f"Error getting project status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "services": {
            "workflow_manager": workflow_manager is not None,
        },
        "active_sessions": len(active_sessions)
    }

if __name__ == "__main__":
    print("Starting XplainCrypto API server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)