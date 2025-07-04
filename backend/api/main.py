from fastapi import FastAPI
from backend.api.routes import router
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="XplainCrypto API with MCP Integration")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000)