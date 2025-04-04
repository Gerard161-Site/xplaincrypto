import logging
import os
from fastapi import FastAPI
import socketio
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional

from backend.services.reporting.logging_config import setup_logging
from backend.services.reporting.progress_tracker import ProgressTracker
from backend.services.reporting.error_reporter import ErrorReporter
from backend.services.communication.socket_service import SocketService
from backend.orchestration.workflow_manager import WorkflowManager
from backend.core.server import register_routes
from backend.core.config_loader import get_config_with_env_override

def create_app(config_path: str = "backend/config/app_config.json"):
    """
    Factory function to create and configure the FastAPI application.
    
    Args:
        config_path: Path to the application configuration file
        
    Returns:
        Configured ASGI application with FastAPI and Socket.IO
    """
    # Load configuration with environment overrides
    config = get_config_with_env_override(config_path, "XC")
    
    # Set up logging
    log_config = config.get("logging", {})
    logger = setup_logging(
        log_file=log_config.get("file", "logs/xplaincrypto.log"),
        log_level=log_config.get("level", "INFO"),
        console_level=log_config.get("console_level")
    )
    
    # Create FastAPI app
    fastapi_app = FastAPI(
        title=config.get("app_name", "XplainCrypto"),
        description=config.get("app_description", "Cryptocurrency Research Platform"),
        version=config.get("app_version", "1.0.0")
    )
    
    # Add CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=config.get("cors_allowed_origins", ["http://localhost:3000"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize Socket.IO
    sio_config = config.get("socketio", {})
    sio = socketio.AsyncServer(
        async_mode='asgi',
        cors_allowed_origins=sio_config.get("cors_allowed_origins", ["http://localhost:3000"]),
        logger=logging.getLogger("socketio"),
        ping_timeout=sio_config.get("ping_timeout", 60),
        ping_interval=sio_config.get("ping_interval", 25),
        max_http_buffer_size=sio_config.get("max_buffer_size", 5 * 1024 * 1024)
    )
    
    # Initialize services
    progress_tracker = ProgressTracker(logger, verbosity=log_config.get("progress_verbosity", "info"))
    error_reporter = ErrorReporter(logger, config.get("error_categories_file", "backend/config/error_categories.json"))
    socket_service = SocketService(sio, logger, progress_tracker, error_reporter)
    
    # Initialize workflow manager
    workflow_manager = WorkflowManager(
        logger=logger,
        progress_tracker=progress_tracker,
        error_reporter=error_reporter,
        config_path=config.get("report_config_file", "backend/config/report_config.json")
    )
    
    # Store services in app state for access
    fastapi_app.state.socket_service = socket_service
    fastapi_app.state.workflow_manager = workflow_manager
    fastapi_app.state.config = config
    fastapi_app.state.logger = logger
    
    # Create the Socket.IO application, mounting the FastAPI app under it
    app = socketio.ASGIApp(sio, fastapi_app)
    
    # Register routes and handlers
    register_routes(
        fastapi_app=fastapi_app,
        socket_service=socket_service,
        workflow_manager=workflow_manager,
        static_dir=config.get("static_dir", "docs")
    )
    
    @fastapi_app.on_event("startup")
    async def startup_event():
        """Initialize async components on startup."""
        logger.info("Starting application initialization")
        
        # Initialize LLM
        if "openai" in config:
            openai_config = config["openai"]
            model_name = openai_config.get("model_name", "gpt-4o-mini")
            api_key = openai_config.get("api_key") or os.getenv("OPENAI_API_KEY")
            
            if api_key:
                fastapi_app.state.workflow_manager.initialize_llm(model_name=model_name, api_key=api_key)
            else:
                logger.warning("OPENAI_API_KEY not provided in config or environment variables")
        
        # Create workflow
        fastapi_app.state.workflow_manager.create_workflow()
        
        logger.info(f"Application initialized: {config.get('app_name', 'XplainCrypto')}")
    
    return app 