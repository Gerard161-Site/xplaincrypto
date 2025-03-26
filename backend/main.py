from langgraph.graph import StateGraph, END
from fastapi import FastAPI
from pydantic import BaseModel
from backend.state import ResearchState
from backend.agents.enhanced_researcher import enhanced_researcher
from backend.agents.writer import writer
from backend.agents.editor import editor
from backend.agents.publisher import publisher
from backend.agents.reviewer import reviewer
from backend.agents.visualization_agent import visualization_agent
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os
import logging
from logging.handlers import RotatingFileHandler
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import socketio
import time
import json

# Create a custom log handler that forwards logs to the frontend via Socket.IO
class SocketIOLogHandler(logging.Handler):
    """Custom logging handler that sends logs to the frontend via Socket.IO."""
    
    def __init__(self, sio, sid):
        super().__init__()
        self.sio = sio
        self.sid = sid
        self.setLevel(logging.INFO)  # Only send INFO level and above
        
        # Set a formatter that includes the level and message
        self.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        
    def emit(self, record):
        """Send the log record to the frontend."""
        try:
            log_entry = self.format(record)
            asyncio.create_task(self.sio.emit('log_update', {'message': log_entry}, to=self.sid))
        except Exception:
            self.handleError(record)

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed output
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            "logs/xplaincrypto.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
    ]
)
logger = logging.getLogger("XplainCrypto")
logger.setLevel(logging.INFO)  # Default to INFO, override with DEBUG via env

# Move Socket.IO logs to a separate logger
socket_logger = logging.getLogger("socketio")
socket_logger.setLevel(logging.WARNING)  # Set to WARNING to suppress INFO logs
socket_logger.propagate = False  # Prevent propagation to root logger

# Load environment variables
load_dotenv()
if os.getenv("DEBUG_MODE") == "true":
    logger.setLevel(logging.DEBUG)

# Initialize Socket.IO
sio = socketio.AsyncServer(
    async_mode='asgi', 
    cors_allowed_origins=['http://localhost:3000'], 
    logger=socket_logger,
    ping_timeout=60,  # 60 seconds ping timeout
    ping_interval=25,  # 25 seconds ping interval
    max_http_buffer_size=5 * 1024 * 1024  # 5MB - increase for large PDF transfers
)
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create Socket.IO app
socket_app = socketio.ASGIApp(sio, app)

# Initialize LLM
api_key = os.getenv("OPENAI_API_KEY")
logger.info(f"Loaded OPENAI_API_KEY: {api_key[:10]}... (truncated for security)")
llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key)

# Create cache directory if it doesn't exist
os.makedirs("cache", exist_ok=True)
logger.info("Initialized cache directory")

# Mount the docs directory
app.mount("/docs", StaticFiles(directory="docs"), name="docs")

class ReportRequest(BaseModel):
    project_name: str

# Define workflow - Fully integrated approach with visualization agent
workflow = StateGraph(ResearchState)
workflow.add_node("enhanced_researcher", lambda state, config=None: enhanced_researcher(state, llm, logger, config))
workflow.add_node("writer", lambda state, config=None: writer(state, llm, logger, config))
workflow.add_node("visualization_agent", lambda state, config=None: visualization_agent(state, llm, logger, config))
workflow.add_node("reviewer", lambda state, config=None: reviewer(state, llm, logger, config))
workflow.add_node("editor", lambda state, config=None: editor(state, llm, logger, config))
workflow.add_node("publisher", lambda state, config=None: publisher(state, llm, logger, config))
workflow.set_entry_point("enhanced_researcher")

# Chain steps sequentially to ensure proper data flow
workflow.add_edge("enhanced_researcher", "writer")
workflow.add_edge("writer", "visualization_agent")
workflow.add_edge("visualization_agent", "reviewer")
workflow.add_edge("reviewer", "editor")
workflow.add_edge("editor", "publisher")
workflow.add_edge("publisher", END)
graph = workflow.compile()

@sio.event
async def connect(sid, environ):
    socket_logger.debug(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    socket_logger.debug(f"Client disconnected: {sid}")

@sio.event
async def message(sid, data):
    try:
        project_name = data.get('project_name')
        fast_mode = data.get('fast_mode', False)  # Default to False to ensure full research is done
        if not project_name:
            logger.error("No project name provided")
            await sio.emit('error', "Project name is required", to=sid)
            return
            
        logger.info(f"Starting report generation for {project_name} (fast_mode: {fast_mode})")
        state = ResearchState(project_name=project_name)
        
        # Add the SocketIO log handler for this session
        socket_handler = SocketIOLogHandler(sio, sid)
        logger.addHandler(socket_handler)
        
        # Store metrics for timing and API usage tracking
        metrics = {
            'start_time': time.time(),
            'steps_completed': 0,
            'api_calls': 0,
            'errors': 0,
            'report_path': None
        }
        
        # Create docs directory if it doesn't exist
        os.makedirs("docs", exist_ok=True)
        os.makedirs(os.path.join("docs", project_name.lower().replace(" ", "_")), exist_ok=True)
        
        # Create progress tracking for client
        async def update_client_progress(current_state, step=None, percentage=None):
            progress_data = {
                'message': current_state.progress,
                'step': step,
                'percentage': percentage
            }
            await sio.emit('progress', progress_data, to=sid)
            logger.info(f"Progress: {current_state.progress} | Step: {step}, {percentage}%")
        
        # Define error handler
        async def handle_error(step_name, error):
            error_msg = f"Error in {step_name}: {str(error)}"
            logger.error(error_msg, exc_info=True)
            await sio.emit('error', error_msg, to=sid)
            state.update_progress(error_msg)
            await update_client_progress(state, step_name, 100)
            metrics['errors'] += 1

        # Load report configuration and save to state - CRITICAL FIX
        try:
            with open("backend/config/report_config.json", "r") as f:
                report_config = json.load(f)
            state.report_config = report_config
            logger.info("Successfully loaded report configuration from file")
            await update_client_progress(state, "configuration", 100)
        except Exception as e:
            logger.error(f"Could not load report configuration: {str(e)}")
            await handle_error("configuration", e)
            # Provide minimal default configuration
            state.report_config = {"sections": [], "visualization_types": {}}
        
        # Set the LLM parameters based on mode
        if fast_mode:
            # Use smaller models and reduce token usage in fast mode
            model_params = {
                "temperature": 0.5,
                "max_tokens": 750,  # Increased from 500 to ensure enough context
                "model": "gpt-4o-mini",  # Use the smaller model
            }
            logger.info("Using fast mode settings with optimized token usage")
        else:
            # Standard mode uses more comprehensive settings
            model_params = {
                "temperature": 0.7,
                "max_tokens": 1500,  # Increased from 1000 to provide more context
                "model": llm.model_name,  # Use the default model
            }
            logger.info("Using standard mode settings")
        
        # Create a context-aware LLM configured with the appropriate model parameters
        context_llm = ChatOpenAI(
            model=model_params["model"],
            temperature=model_params["temperature"],
            max_tokens=model_params["max_tokens"]
        )
        
        # Run each agent in sequence with proper error handling
        try:
            # STEP 1: Enhanced Researcher
            logger.info(f"Starting enhanced research for {project_name}")
            state.update_progress(f"Researching {project_name}...")
            await update_client_progress(state, "research", 0)
            
            # Configure research with proper parameters
            research_config = {
                "fast_mode": fast_mode,
                "api_limit": 10 if fast_mode else 20,
                "cache_enabled": True,
                "cache_ttl": 21600,  # 6 hours TTL
                "report_sections": state.report_config.get("sections", [])
            }
            
            # Execute enhanced researcher
            try:
                enhanced_state = enhanced_researcher(state, context_llm, logger, research_config)
                if enhanced_state:
                    state = enhanced_state
                    metrics['steps_completed'] += 1
                    logger.info("Enhanced research completed successfully")
                else:
                    logger.warning("Enhanced researcher returned None, keeping original state")
            except Exception as e:
                logger.error(f"Error in enhanced_researcher: {str(e)}", exc_info=True)
                await handle_error("research", e)
                # Continue to next step even with error - state might have partial data
            
            await update_client_progress(state, "research", 100)
            
            # STEP 2: Writer
            logger.info(f"Starting writer for {project_name}")
            state.update_progress(f"Writing report for {project_name}...")
            await update_client_progress(state, "writing", 0)
            
            try:
                # Configure writer
                writer_config = {
                    "fast_mode": fast_mode,
                    "report_config": state.report_config
                }
                
                # Execute writer
                writer_state = writer(state, context_llm, logger, writer_config)
                if writer_state:
                    state = writer_state
                    metrics['steps_completed'] += 1
                    logger.info("Writer completed successfully")
                else:
                    logger.warning("Writer returned None, keeping original state")
            except Exception as e:
                logger.error(f"Error in writer: {str(e)}", exc_info=True)
                await handle_error("writing", e)
                # Continue to next step even with error
            
            await update_client_progress(state, "writing", 100)
            
            # STEP 3: Visualization Agent - CRITICAL STEP
            logger.info(f"Starting visualization agent for {project_name}")
            state.update_progress(f"Generating visualizations for {project_name}...")
            await update_client_progress(state, "visualization", 0)
            
            try:
                # Configure visualization agent
                vis_config = {
                    "fast_mode": fast_mode,
                    "report_config": state.report_config,
                    "limit_charts": fast_mode,  # Limit charts in fast mode
                    "skip_expensive_descriptions": fast_mode,  # Skip descriptions in fast mode
                    "refresh_api_data": True  # Always refresh API data for latest information
                }
                
                # Execute visualization agent
                vis_state = visualization_agent(state, context_llm, logger, vis_config)
                if vis_state:
                    state = vis_state
                    metrics['steps_completed'] += 1
                    logger.info(f"Visualization agent completed with {len(state.visualizations)} visualizations")
                else:
                    logger.warning("Visualization agent returned None, keeping original state")
            except Exception as e:
                logger.error(f"Error in visualization_agent: {str(e)}", exc_info=True)
                await handle_error("visualization", e)
                # Continue to next step even with error
            
            await update_client_progress(state, "visualization", 100)
            
            # STEP 4: Reviewer (optional in fast mode)
            if not fast_mode:
                logger.info(f"Starting reviewer for {project_name}")
                state.update_progress(f"Reviewing report for {project_name}...")
                await update_client_progress(state, "review", 0)
                
                try:
                    # Configure reviewer
                    reviewer_config = {
                        "report_config": state.report_config
                    }
                    
                    # Execute reviewer
                    reviewer_state = reviewer(state, context_llm, logger, reviewer_config)
                    if reviewer_state:
                        state = reviewer_state
                        metrics['steps_completed'] += 1
                        logger.info("Reviewer completed successfully")
                    else:
                        logger.warning("Reviewer returned None, keeping original state")
                except Exception as e:
                    logger.error(f"Error in reviewer: {str(e)}", exc_info=True)
                    await handle_error("review", e)
                    # Continue to next step even with error
                
                await update_client_progress(state, "review", 100)
            
            # STEP 5: Editor
            logger.info(f"Starting editor for {project_name}")
            state.update_progress(f"Editing report for {project_name}...")
            await update_client_progress(state, "editing", 0)
            
            try:
                # Configure editor
                editor_config = {
                    "fast_mode": fast_mode,
                    "report_config": state.report_config
                }
                
                # Execute editor
                editor_state = editor(state, context_llm, logger, editor_config)
                if editor_state:
                    state = editor_state
                    metrics['steps_completed'] += 1
                    logger.info("Editor completed successfully")
                else:
                    logger.warning("Editor returned None, keeping original state")
            except Exception as e:
                logger.error(f"Error in editor: {str(e)}", exc_info=True)
                await handle_error("editing", e)
                # Continue to next step even with error
            
            await update_client_progress(state, "editing", 100)
            
            # STEP 6: Publisher
            logger.info(f"Starting publisher for {project_name}")
            state.update_progress(f"Publishing report for {project_name}...")
            await update_client_progress(state, "publishing", 0)
            
            try:
                # Configure publisher
                publisher_config = {
                    "fast_mode": fast_mode,
                    "report_config": state.report_config
                }
                
                # Execute publisher
                publisher_state = publisher(state, context_llm, logger, publisher_config)
                if publisher_state:
                    state = publisher_state
                    metrics['steps_completed'] += 1
                    logger.info("Publisher completed successfully")
                else:
                    logger.warning("Publisher returned None, keeping original state")
            except Exception as e:
                logger.error(f"Error in publisher: {str(e)}", exc_info=True)
                await handle_error("publishing", e)
            
            await update_client_progress(state, "publishing", 100)
            
            # STEP 7: Final Report
            logger.info(f"Report generation completed for {project_name}")
            state.update_progress(f"Report for {project_name} is ready!")
            
            # Calculate metrics
            metrics['end_time'] = time.time()
            metrics['total_time'] = metrics['end_time'] - metrics['start_time']
            metrics['total_steps'] = metrics['steps_completed']
            
            # Get report path
            if hasattr(state, 'final_report') and state.final_report:
                metrics['report_path'] = state.final_report
            
            # Send completion message
            await sio.emit('complete', {
                'message': f"Report for {project_name} completed in {metrics['total_time']:.2f} seconds",
                'report_path': metrics['report_path'],
                'metrics': metrics
            }, to=sid)
            
            # Clean up
            logger.removeHandler(socket_handler)
            
        except Exception as e:
            logger.error(f"Unexpected error in workflow: {str(e)}", exc_info=True)
            await handle_error("workflow", e)
            await sio.emit('error', f"Error: {str(e)}", to=sid)
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        await sio.emit('error', f"Error: {str(e)}", to=sid)

# Mount Socket.IO app
app = socket_app

# Start the server
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting XplainCrypto server on port 8000")
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)

logger.info("Main module loaded successfully")