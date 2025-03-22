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
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=['http://localhost:3000'], logger=socket_logger)
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
        logger.info(f"Starting report generation for {project_name}")
        state = ResearchState(project_name=project_name)
        
        logger.debug(f"Initial state: {vars(state)}")
        state = enhanced_researcher(state, llm, logger)
        logger.debug(f"Post-research state: {vars(state)}")
        await sio.emit('message', state.progress, to=sid)
        
        state = visualization_agent(state, llm, logger)
        logger.debug(f"Post-visualization state: {vars(state)}")
        await sio.emit('message', state.progress, to=sid)
        
        state = writer(state, llm, logger)
        logger.debug(f"Post-writer state: {vars(state)}")
        await sio.emit('message', state.progress, to=sid)
        
        state = reviewer(state, llm, logger)
        logger.debug(f"Post-reviewer state: {vars(state)}")
        await sio.emit('message', state.progress, to=sid)
        
        state = editor(state, llm, logger)
        logger.debug(f"Post-editor state: {vars(state)}")
        await sio.emit('message', state.progress, to=sid)
        
        state = publisher(state, logger, None, llm)
        logger.debug(f"Final state: {vars(state)}")
        await sio.emit('data', {
            'status': state.progress,
            'final_report': state.final_report
        }, to=sid)
        
        logger.info(f"Report generation completed for {project_name}")
    except Exception as e:
        logger.error(f"Error in report generation: {str(e)}", exc_info=True)
        await sio.emit('error', str(e), to=sid)

# Mount Socket.IO app
app = socket_app

logger.info("Main module loaded successfully")