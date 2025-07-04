"""
Initialize API endpoint metadata for MCP integration.
This module handles the initialization of Pinecone with endpoint metadata to help with service discovery.
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

try:
    from pinecone import Pinecone, ServerlessSpec
    NEW_PINECONE_SDK = True
except ImportError:
    import pinecone
    NEW_PINECONE_SDK = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PineconeEndpointManager:
    """Manager for Pinecone endpoint metadata for API service discovery."""
    
    def __init__(self, index_name: str = "xplaincrypto-endpoints"):
        self.index_name = index_name
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.environment = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
        self.dimension = 384
        
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            logger.error("Could not import SentenceTransformer. Please install it with: pip install sentence-transformers")
            self.model = None
            
        self.index = None
        self.pc = None
    
    async def initialize(self) -> bool:
        if not self.api_key:
            logger.error("PINECONE_API_KEY environment variable not set")
            return False
        
        try:
            self.pc = Pinecone(api_key=self.api_key)
            if self.index_name not in self.pc.list_indexes().names():
                logger.info(f"Creating Pinecone index: {self.index_name}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
            self.index = self.pc.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}")
            return False
    
    async def get_endpoint_count(self) -> int:
        if not self.index:
            logger.error("Pinecone index not initialized")
            return 0
        try:
            stats = self.index.describe_index_stats()
            return stats.get('total_vector_count', 0)
        except Exception as e:
            logger.error(f"Error getting endpoint count: {str(e)}")
            return 0
    
    async def index_endpoint(self, endpoint_id: str, description: str, metadata: Dict[str, Any] = None) -> bool:
        if not self.index:
            logger.error("Pinecone index not initialized")
            return False
        if not self.model:
            logger.error("Sentence transformer model not initialized")
            return False
        try:
            embedding = self.model.encode(description).tolist()
            complete_metadata = {"description": description}
            if metadata:
                complete_metadata.update(metadata)
            self.index.upsert(
                vectors=[(endpoint_id, embedding, complete_metadata)],
                namespace=""
            )
            logger.info(f"Successfully indexed endpoint: {endpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Error indexing endpoint {endpoint_id}: {str(e)}")
            return False

async def initialize_api_endpoints() -> bool:
    logger.info("Initializing Pinecone with API endpoint metadata")
    
    try:
        manager = PineconeEndpointManager()
        initialized = await manager.initialize()
        if not initialized:
            logger.error("Failed to initialize Pinecone")
            return False
        
        # Load servers from mcp_servers.json
        mcp_servers_file = Path("backend/config/mcp_servers.json")
        servers = []
        if mcp_servers_file.exists():
            with open(mcp_servers_file, "r") as f:
                servers = json.load(f)
        server_names = [server["server_name"] for server in servers]
        
        # Load metadata for each server
        count = 0
        for server in servers:
            server_name = server["server_name"]
            metadata_file = Path(server["metadata_file"])
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                for resource in metadata.get("resources", []):
                    await manager.index_endpoint(
                        resource["path"],
                        resource["description"],
                        {"endpoint": resource["endpoint"], "data_type": resource.get("data_type", "generic"), "source_name": server_name}
                    )
                    count += 1
                for tool in metadata.get("tools", []):
                    await manager.index_endpoint(
                        f"{server_name}/{tool['name']}",
                        tool["description"],
                        {"endpoint": tool["endpoint"], "data_type": tool.get("data_type", "generic"), "source_name": server_name}
                    )
                    count += 1
                # Index the server itself
                await manager.index_endpoint(
                    server_name,
                    f"{server_name.capitalize()} API for cryptocurrency data.",
                    {"source_name": server_name}
                )
                count += 1
        
        vector_count = await manager.get_endpoint_count()
        logger.info(f"Index contains {vector_count} endpoint vectors after initialization")
        logger.info(f"Successfully indexed {count} API endpoints in Pinecone")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize API endpoints: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    asyncio.run(initialize_api_endpoints())