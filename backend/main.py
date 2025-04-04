import logging
from dotenv import load_dotenv
import os

from backend.core.app_factory import create_app

# Load environment variables
load_dotenv()

# Create the FastAPI application using the app factory
app = create_app()

# This allows the application to be run directly
if __name__ == "__main__":
    import uvicorn
    logger = logging.getLogger("backend")
    logger.info("Starting XplainCrypto server on port 8000")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)