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
socket_logger.setLevel(logging.DEBUG)  # Debug mode for Socket.IO

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
workflow.add_node("visualization_agent", lambda state, config=None: visualization_agent(state, llm, logger, config))
workflow.add_node("writer", lambda state, config=None: writer(state, llm, logger, config))
workflow.add_node("reviewer", lambda state, config=None: reviewer(state, llm, logger, config))
workflow.add_node("editor", lambda state, config=None: editor(state, llm, logger, config))
workflow.add_node("publisher", lambda state, config=None: publisher(state, logger, config, llm))
workflow.set_entry_point("enhanced_researcher")
workflow.add_edge("enhanced_researcher", "visualization_agent")
workflow.add_edge("visualization_agent", "writer")
workflow.add_edge("writer", "reviewer")
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
        fast_mode = data.get('fast_mode', True)  # Default to true for better performance
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
                "max_tokens": 500,
                "model": "gpt-4o-mini",  # Use the smaller model
            }
            logger.info("Using fast mode settings with optimized token usage")
        else:
            # Standard mode uses more comprehensive settings
            model_params = {
                "temperature": 0.7,
                "max_tokens": 1000,
                "model": llm.model_name,  # Use the default model
            }
            logger.info("Using standard mode settings")
        
        # Create a context-aware LLM configured with the appropriate model parameters
        context_llm = ChatOpenAI(
            model=model_params["model"],
            temperature=model_params["temperature"],
            max_tokens=model_params["max_tokens"]
        )
        
        # Enhanced Research Step with proper caching
        try:
            logger.info(f"Starting research for {project_name}")
            state.update_progress(f"Researching {project_name}...")
            await update_client_progress(state, "research", 0)
            
            # Create research configuration with report config requirements
            research_config = {
                "fast_mode": fast_mode,
                "api_limit": 5 if fast_mode else 15,  # Stricter API limit in fast mode
                "cache_enabled": True,  # Always use caching
                "cache_ttl": 21600,  # 6 hours TTL for cache to reduce API calls
                "report_sections": state.report_config.get("sections", [])  # Pass sections to researcher
            }
            
            # Run the enhanced researcher with custom configuration
            enhanced_research_state = enhanced_researcher(state, context_llm, logger, research_config)
            if enhanced_research_state:
                state = enhanced_research_state
                metrics['steps_completed'] += 1
            else:
                raise Exception("Enhanced research failed to return a valid state")
                
            logger.debug(f"Post-research state: {vars(state)}")
            await update_client_progress(state, "research", 100)
        except Exception as e:
            await handle_error("research", e)
            # Continue with empty research data instead of failing completely
            state.research_summary = f"Analysis of {project_name} cryptocurrency."
            state.key_features = f"Key features of {project_name}."
            state.tokenomics = f"Tokenomics information for {project_name}."
            state.price_analysis = f"Price analysis for {project_name}.\n60-Day Change: 0%"
            state.governance = f"Governance structure of {project_name}."
        
        # Visualization Step - CRITICAL FIX to ensure config-driven visualization generation
        # Load cached data directly if available
        try:
            # Try to load cached data files for ONDO if they exist
            project_lowercase = project_name.lower()
            
            # Load CoinGecko data
            cg_cache_path = f"cache/{project_name}_CoinGeckoModule.json"
            if os.path.exists(cg_cache_path):
                with open(cg_cache_path, 'r') as f:
                    state.coingecko_data = json.load(f)
                    logger.info(f"Loaded {len(state.coingecko_data)} fields from cached CoinGecko data")
            
            # Load CoinMarketCap data
            cmc_cache_path = f"cache/{project_name}_CoinMarketCapModule.json"
            if os.path.exists(cmc_cache_path):
                with open(cmc_cache_path, 'r') as f:
                    state.coinmarketcap_data = json.load(f)
                    logger.info(f"Loaded {len(state.coinmarketcap_data)} fields from cached CoinMarketCap data")
            
            # Load DeFiLlama data
            dl_cache_path = f"cache/{project_name}_DeFiLlamaModule.json"
            if os.path.exists(dl_cache_path):
                with open(dl_cache_path, 'r') as f:
                    state.defillama_data = json.load(f)
                    logger.info(f"Loaded {len(state.defillama_data)} fields from cached DeFiLlama data")
            
            # Combine all data into multi source
            state.data = {}
            if hasattr(state, 'coingecko_data') and state.coingecko_data:
                state.data.update(state.coingecko_data)
            if hasattr(state, 'coinmarketcap_data') and state.coinmarketcap_data:
                state.data.update(state.coinmarketcap_data)
            if hasattr(state, 'defillama_data') and state.defillama_data:
                state.data.update(state.defillama_data)
            
            logger.info(f"Combined data now has {len(state.data)} fields")
        except Exception as e:
            logger.error(f"Error loading cached data: {str(e)}")
            # Continue with empty data - visualization agent will handle this
        
        # Visualization Step - CRITICAL FIX to ensure config-driven visualization generation
        try:
            logger.info(f"Generating visualizations for {project_name}")
            state.update_progress(f"Creating visualizations based on report configuration...")
            await update_client_progress(state, "visualization", 0)
            
            # Create a configuration that references the report config
            vis_config = {
                "fast_mode": fast_mode,
                "limit_charts": fast_mode,  # Limit charts in fast mode
                "skip_expensive_descriptions": fast_mode,  # Skip LLM descriptions in fast mode
                "use_report_config": True  # Important flag to use the report_config
            }
            
            visualization_state = visualization_agent(state, context_llm, logger, vis_config)
            if visualization_state:
                state = visualization_state
                metrics['steps_completed'] += 1
                logger.info(f"Successfully generated visualizations, now in state: {len(state.visualizations)} items")
            else:
                raise Exception("Visualization agent failed to return a valid state")
                
            await update_client_progress(state, "visualization", 100)
        except Exception as e:
            await handle_error("visualization", e)
            # Ensure state has visualizations property even if empty
            if not hasattr(state, 'visualizations'):
                state.visualizations = {}
            
        # Skip resource-intensive steps in fast mode or accelerate them
        if fast_mode:
            logger.info("Fast mode enabled - Streamlining content generation")
            
            # Writer Step - simplified in fast mode, but with config awareness
            try:
                logger.info(f"Writing lightweight report for {project_name}")
                state.update_progress(f"Creating report content for {project_name}...")
                await update_client_progress(state, "writing", 0)
                
                # Create writer config with fast mode settings
                writer_config = {
                    "fast_mode": True,
                    "max_tokens_per_section": 250,  # Limit tokens per section
                    "include_visualizations": True  # Important - reference visualizations in content
                }
                
                writer_state = writer(state, context_llm, logger, writer_config)
                if writer_state:
                    state = writer_state
                    metrics['steps_completed'] += 1
                else:
                    raise Exception("Writer failed to return a valid state")
                    
                await update_client_progress(state, "writing", 100)
            except Exception as e:
                await handle_error("writer", e)
                # Continue with minimal draft content
                state.draft = f"Report on {project_name} cryptocurrency."
            
            # Skip review and edit in fast mode
            logger.info("Skipping detailed review and edit in fast mode")
            
            # Direct to publisher
            try:
                logger.info(f"Publishing report for {project_name}")
                state.update_progress(f"Creating PDF based on report configuration...")
                await update_client_progress(state, "publishing", 0)
                
                # Publisher with fast mode config but config awareness
                publisher_config = {
                    "fast_mode": True,
                    "use_report_config": True  # Critical flag to use the right configuration
                }
                
                publisher_state = publisher(state, logger, publisher_config, context_llm)
                if publisher_state:
                    state = publisher_state
                    metrics['steps_completed'] += 1
                else:
                    raise Exception("Publisher failed to return a valid state")
                    
                await update_client_progress(state, "publishing", 100)
            except Exception as e:
                await handle_error("publisher", e)
                state.final_report = f"Error publishing report for {project_name}: {str(e)}"
        else:
            # Full workflow for standard mode
            # Visualization Step
            try:
                logger.info(f"Generating visualizations for {project_name}")
                state.update_progress(f"Creating visualizations for {project_name}...")
                await update_client_progress(state, "visualization", 0)
                
                visualization_state = visualization_agent(state, llm, logger)
                if visualization_state:
                    state = visualization_state
                    metrics['steps_completed'] += 1
                else:
                    raise Exception("Visualization agent failed to return a valid state")
                    
                logger.debug(f"Post-visualization state: {vars(state)}")
                await update_client_progress(state, "visualization", 100)
            except Exception as e:
                await handle_error("visualization", e)
                # Ensure state has visualizations property even if empty
                if not hasattr(state, 'visualizations'):
                    state.visualizations = {}
            
            # Writer Step
            try:
                logger.info(f"Writing report for {project_name}")
                state.update_progress(f"Writing report for {project_name}...")
                await update_client_progress(state, "writing", 0)
                
                writer_state = writer(state, llm, logger)
                if writer_state:
                    state = writer_state
                    metrics['steps_completed'] += 1
                else:
                    raise Exception("Writer failed to return a valid state")
                    
                logger.debug(f"Post-writer state: {vars(state)}")
                await update_client_progress(state, "writing", 100)
            except Exception as e:
                await handle_error("writer", e)
            
            # Reviewer Step
            try:
                logger.info(f"Reviewing report for {project_name}")
                state.update_progress(f"Reviewing report for {project_name}...")
                await update_client_progress(state, "reviewing", 0)
                
                reviewer_state = reviewer(state, llm, logger)
                if reviewer_state:
                    state = reviewer_state
                    metrics['steps_completed'] += 1
                else:
                    raise Exception("Reviewer failed to return a valid state")
                    
                logger.debug(f"Post-reviewer state: {vars(state)}")
                await update_client_progress(state, "reviewing", 100)
            except Exception as e:
                await handle_error("reviewer", e)
            
            # Editor Step
            try:
                logger.info(f"Editing report for {project_name}")
                state.update_progress(f"Editing report for {project_name}...")
                await update_client_progress(state, "editing", 0)
                
                editor_state = editor(state, llm, logger)
                if editor_state:
                    state = editor_state
                    metrics['steps_completed'] += 1
                else:
                    raise Exception("Editor failed to return a valid state")
                    
                logger.debug(f"Post-editor state: {vars(state)}")
                await update_client_progress(state, "editing", 100)
            except Exception as e:
                await handle_error("editor", e)
            
            # Publisher Step
            try:
                logger.info(f"Publishing report for {project_name}")
                state.update_progress(f"Publishing final report for {project_name}...")
                await update_client_progress(state, "publishing", 0)
                
                publisher_state = publisher(state, logger, None, llm)
                if publisher_state:
                    state = publisher_state
                    metrics['steps_completed'] += 1
                else:
                    raise Exception("Publisher failed to return a valid state")
                    
                logger.debug(f"Final state: {vars(state)}")
                await update_client_progress(state, "publishing", 100)
            except Exception as e:
                await handle_error("publisher", e)
                state.final_report = f"Error publishing report for {project_name}: {str(e)}"
        
        # Send final data to client
        try:
            pdf_path = f"docs/{project_name}_report.pdf"
            pdf_exists = os.path.exists(pdf_path)
            pdf_size = os.path.getsize(pdf_path) if pdf_exists else 0
            
            if pdf_exists and pdf_size > 1000:  # Ensure PDF is not empty
                state.final_report = f"PDF generated at {pdf_path}"
                logger.info(f"Successfully created PDF report: {pdf_path} ({pdf_size} bytes)")
                metrics['report_path'] = pdf_path
            else:
                state.final_report = "Error: PDF was not created properly or is too small"
                logger.error(f"PDF issue: {'Not found' if not pdf_exists else f'Too small ({pdf_size} bytes)'}")
            
            # Calculate execution time
            metrics['end_time'] = time.time()
            metrics['duration'] = round(metrics['end_time'] - metrics['start_time'], 2)
            
            # Prepare report data including metrics
            result_data = {
                'status': state.progress,
                'final_report': state.final_report,
                'pdf_path': f"/{pdf_path}" if pdf_exists else None,
                'metrics': {
                    'duration': metrics['duration'],
                    'steps_completed': metrics['steps_completed'],
                    'errors': metrics['errors'],
                    'mode': 'fast' if fast_mode else 'standard'
                }
            }
            
            await sio.emit('data', result_data, to=sid)
            logger.info(f"Report generation completed in {metrics['duration']}s with {metrics['errors']} errors")
        except Exception as final_error:
            logger.error(f"Error sending final data: {str(final_error)}", exc_info=True)
            await sio.emit('error', f"Error completing report: {str(final_error)}", to=sid)
        finally:
            # Remove the socket handler when done
            logger.removeHandler(socket_handler)
        
        logger.info(f"Report generation process completed for {project_name}")
    except Exception as e:
        logger.error(f"Unhandled exception in message handler: {str(e)}", exc_info=True)
        await sio.emit('error', f"Critical error processing request: {str(e)}", to=sid)

# Mount Socket.IO app
app = socket_app

# Start the server
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting XplainCrypto server on port 8000")
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)

logger.info("Main module loaded successfully")