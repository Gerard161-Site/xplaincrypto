import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional

def setup_logging(
    log_file: str = "logs/xplaincrypto.log",
    log_level: str = "INFO",
    console_level: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Configure logging with both file and console output.
    
    Args:
        log_file: Path to the log file
        log_level: Level for the file logger (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_level: Level for the console logger (defaults to log_level if None)
        max_file_size: Maximum size of log file before rotation in bytes
        backup_count: Number of backup log files to keep
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Map string levels to logging constants
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    # Get the numeric log levels
    file_level = level_map.get(log_level.upper(), logging.INFO)
    console_level = level_map.get(console_level.upper() if console_level else log_level.upper(), file_level)
    
    # Get the main logger
    logger = logging.getLogger("XplainCrypto")
    logger.setLevel(logging.DEBUG)  # Set to lowest to let handlers control levels
    
    # Remove existing handlers to avoid duplicates during reinitialization
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatters
    verbose_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(module)s.%(funcName)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter(
        "%(levelname)s - %(message)s"
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Create file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_file_size,
        backupCount=backup_count
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(verbose_formatter)
    logger.addHandler(file_handler)
    
    # Disable noisy loggers
    for noisy_logger in ["matplotlib.font_manager", "matplotlib.pyplot", "PIL.PngImagePlugin", "httpx", "matplotlib"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    
    # Create a separate logger for Socket.IO
    socket_logger = logging.getLogger("socketio")
    socket_logger.setLevel(logging.WARNING)  # Set to WARNING to suppress INFO logs
    socket_logger.propagate = False  # Prevent propagation to root logger
    
    logger.info(f"Logging initialized: file level={log_level}, console level={console_level or log_level}")
    return logger

def get_log_handler_for_socket(socket_service) -> logging.Handler:
    """
    Create a custom log handler that sends logs to the frontend via Socket.IO.
    
    Args:
        socket_service: The socket service to use for sending logs
        
    Returns:
        A configured log handler
    """
    class SocketIOLogHandler(logging.Handler):
        """Custom logging handler that sends logs to the frontend via Socket.IO."""
        
        def __init__(self, socket_service):
            super().__init__()
            self.socket_service = socket_service
            self.setLevel(logging.INFO)  # Only send INFO level and above
            
            # Set a formatter that includes the level and message
            self.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            
        def emit(self, record):
            """Send the log record to the frontend."""
            try:
                log_entry = self.format(record)
                self.socket_service.emit_async('log_update', {'message': log_entry})
            except Exception:
                self.handleError(record)
    
    return SocketIOLogHandler(socket_service) 