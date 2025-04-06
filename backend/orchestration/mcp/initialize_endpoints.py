"""
Initialize Pinecone endpoints for MCP integration.
This module handles the initialization of Pinecone with MCP endpoints metadata.
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
import pinecone
from sentence_transformers import SentenceTransformer
import json

# Configure logging
logger = logging.getLogger(__name__)

class PineconeEndpointManager:
    """Manager for Pinecone endpoints for MCP integration."""
    
    def __init__(self, index_name: str = "xplaincrypto-endpoints"):
        """
        Initialize the Pinecone endpoint manager.
        
        Args:
            index_name: Name of the Pinecone index to use
        """
        self.index_name = index_name
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.environment = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
        self.dimension = 384  # Dimension for all-MiniLM-L6-v2
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = None
    
    async def initialize(self) -> bool:
        """
        Initialize Pinecone and create index if it doesn't exist.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if not self.api_key:
            logger.error("PINECONE_API_KEY environment variable not set")
            return False
        
        try:
            # Initialize Pinecone
            pinecone.init(api_key=self.api_key, environment=self.environment)
            
            # Check if index exists
            if self.index_name not in pinecone.list_indexes():
                logger.info(f"Creating Pinecone index: {self.index_name}")
                pinecone.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine"
                )
            
            # Connect to index
            self.index = pinecone.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}")
            return False
    
    async def get_endpoint_count(self) -> int:
        """
        Get the number of endpoints in the index.
        
        Returns:
            Number of endpoints in the index
        """
        if not self.index:
            logger.error("Pinecone index not initialized")
            return 0
        
        try:
            stats = self.index.describe_index_stats()
            return stats.get('total_vector_count', 0)
        except Exception as e:
            logger.error(f"Error getting endpoint count: {str(e)}")
            return 0
    
    async def upsert_endpoint(self, endpoint_id: str, description: str, metadata: Dict[str, Any]) -> bool:
        """
        Upsert an endpoint to the index.
        
        Args:
            endpoint_id: Unique identifier for the endpoint
            description: Description of the endpoint
            metadata: Additional metadata for the endpoint
            
        Returns:
            True if upsert was successful, False otherwise
        """
        if not self.index:
            logger.error("Pinecone index not initialized")
            return False
        
        try:
            # Generate embedding for description
            embedding = self.model.encode(description).tolist()
            
            # Upsert to index
            self.index.upsert(
                vectors=[(endpoint_id, embedding, metadata)],
                namespace=""
            )
            
            logger.info(f"Upserted endpoint: {endpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Error upserting endpoint: {str(e)}")
            return False
    
    async def query_endpoints(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Query endpoints based on similarity to query.
        
        Args:
            query: Query string
            top_k: Number of results to return
            
        Returns:
            List of matching endpoints with metadata
        """
        if not self.index:
            logger.error("Pinecone index not initialized")
            return []
        
        try:
            # Generate embedding for query
            embedding = self.model.encode(query).tolist()
            
            # Query index
            results = self.index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True,
                namespace=""
            )
            
            # Extract matches
            matches = []
            for match in results.get('matches', []):
                endpoint_data = {
                    'id': match.get('id', ''),
                    'score': match.get('score', 0),
                    'metadata': match.get('metadata', {})
                }
                matches.append(endpoint_data)
            
            return matches
        except Exception as e:
            logger.error(f"Error querying endpoints: {str(e)}")
            return []

async def initialize_pinecone_endpoints() -> bool:
    """
    Initialize Pinecone with MCP endpoints metadata.
    
    Returns:
        True if initialization was successful, False otherwise
    """
    logger.info("Initializing Pinecone with MCP endpoints metadata")
    
    # Initialize Pinecone endpoint manager
    manager = PineconeEndpointManager()
    if not await manager.initialize():
        return False
    
    # Check if endpoints already exist
    endpoint_count = await manager.get_endpoint_count()
    if endpoint_count > 0:
        logger.info(f"Pinecone already contains {endpoint_count} endpoints")
        return True
    
    # Define endpoints
    endpoints = [
        {
            "id": "coingecko",
            "description": "CoinGecko API for cryptocurrency price, market data, and metadata",
            "metadata": {
                "type": "price_data",
                "capabilities": ["price", "market_cap", "volume", "historical_data", "metadata"],
                "url": "https://api.coingecko.com/api/v3",
                "server_type": "rest"
            }
        },
        {
            "id": "coinmarketcap",
            "description": "CoinMarketCap API for cryptocurrency listings, quotes, and metadata",
            "metadata": {
                "type": "price_data",
                "capabilities": ["price", "market_cap", "volume", "listings", "metadata"],
                "url": "https://pro-api.coinmarketcap.com/v1",
                "server_type": "rest"
            }
        },
        {
            "id": "defillama",
            "description": "DeFiLlama API for DeFi protocol TVL, yields, and stablecoin data",
            "metadata": {
                "type": "defi_data",
                "capabilities": ["tvl", "yields", "stablecoins", "bridges", "protocols"],
                "url": "https://api.llama.fi",
                "server_type": "rest"
            }
        },
        {
            "id": "tavily",
            "description": "Tavily API for web search and information retrieval",
            "metadata": {
                "type": "search_data",
                "capabilities": ["web_search", "news_search", "image_search"],
                "url": "https://api.tavily.com",
                "server_type": "rest"
            }
        },
        {
            "id": "huggingface",
            "description": "Hugging Face API for machine learning models and embeddings",
            "metadata": {
                "type": "ml_data",
                "capabilities": ["embeddings", "text_generation", "classification"],
                "url": "https://api-inference.huggingface.co",
                "server_type": "rest"
            }
        },
        {
            "id": "etherscan",
            "description": "Etherscan API for Ethereum blockchain data and analytics",
            "metadata": {
                "type": "blockchain_data",
                "capabilities": ["transactions", "contracts", "tokens", "gas_prices"],
                "url": "https://api.etherscan.io/api",
                "server_type": "rest"
            }
        },
        {
            "id": "dune",
            "description": "Dune Analytics API for crypto analytics and dashboard data",
            "metadata": {
                "type": "analytics_data",
                "capabilities": ["queries", "dashboards", "charts", "metrics"],
                "url": "https://api.dune.com",
                "server_type": "rest"
            }
        },
        {
            "id": "messari",
            "description": "Messari API for crypto research, metrics, and market data",
            "metadata": {
                "type": "research_data",
                "capabilities": ["metrics", "assets", "markets", "profiles", "news"],
                "url": "https://data.messari.io/api",
                "server_type": "rest"
            }
        }
    ]
    
    # Upsert endpoints
    success_count = 0
    for endpoint in endpoints:
        if await manager.upsert_endpoint(
            endpoint_id=endpoint["id"],
            description=endpoint["description"],
            metadata=endpoint["metadata"]
        ):
            success_count += 1
    
    logger.info(f"Successfully initialized {success_count}/{len(endpoints)} endpoints")
    return success_count == len(endpoints)

if __name__ == "__main__":
    # Run initialization
    asyncio.run(initialize_pinecone_endpoints())
