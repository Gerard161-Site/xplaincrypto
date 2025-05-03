"""
Initialize API endpoint metadata for MCP integration.
This module handles the initialization of Pinecone with endpoint metadata to help with service discovery.
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
try:
    from pinecone import Pinecone, ServerlessSpec
    NEW_PINECONE_SDK = True
except ImportError:
    # For older versions of Pinecone SDK
    import pinecone
    NEW_PINECONE_SDK = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PineconeEndpointManager:
    """Manager for Pinecone endpoint metadata for API service discovery."""
    
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
        
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            logger.error("Could not import SentenceTransformer. Please install it with: pip install sentence-transformers")
            self.model = None
            
        self.index = None
        self.pc = None
    
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
            # Initialize Pinecone based on SDK version
            try:
                # Try new SDK first (post 3.0)
                self.pc = Pinecone(api_key=self.api_key)
                
                # Check if index exists
                if self.index_name not in self.pc.list_indexes().names():
                    logger.info(f"Creating Pinecone index: {self.index_name}")
                    
                    # Create with serverless spec if available
                    if ServerlessSpec:
                        self.pc.create_index(
                            name=self.index_name,
                            dimension=self.dimension,
                            metric="cosine",
                            spec=ServerlessSpec(cloud="aws", region="us-east-1")
                        )
                    else:
                        self.pc.create_index(
                            name=self.index_name,
                            dimension=self.dimension,
                            metric="cosine"
                        )
                
                # Connect to index
                self.index = self.pc.Index(self.index_name)
                
            except (ImportError, AttributeError):
                # Fall back to old SDK (pre 3.0)
                logger.info("Using legacy Pinecone SDK")
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
            if hasattr(self.index, 'describe_index_stats'):
                stats = self.index.describe_index_stats()
                return stats.get('total_vector_count', 0)
            else:
                stats = self.index.statistics()
                return stats.get('vector_count', 0)
        except Exception as e:
            logger.error(f"Error getting endpoint count: {str(e)}")
            return 0
    
    async def index_endpoint(self, endpoint_id: str, description: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Index an API endpoint in Pinecone for service discovery.
        
        Args:
            endpoint_id: Unique identifier for the endpoint
            description: Description of the endpoint's capabilities
            metadata: Additional metadata for the endpoint
            
        Returns:
            True if indexing was successful, False otherwise
        """
        if not self.index:
            logger.error("Pinecone index not initialized")
            return False
        
        if not self.model:
            logger.error("Sentence transformer model not initialized")
            return False
        
        try:
            # Generate embedding for description
            embedding = self.model.encode(description).tolist()
            
            # Create metadata object
            complete_metadata = {"description": description}
            if metadata:
                complete_metadata.update(metadata)
            
            # Upsert to index
            try:
                # New SDK version
                self.index.upsert(
                    vectors=[(endpoint_id, embedding, complete_metadata)],
                    namespace=""
                )
            except (TypeError, AttributeError):
                # Old SDK version might have different parameter structure
                self.index.upsert(
                    vectors=[{"id": endpoint_id, "values": embedding, "metadata": complete_metadata}],
                    namespace=""
                )
            
            logger.info(f"Successfully indexed endpoint: {endpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Error indexing endpoint {endpoint_id}: {str(e)}")
            return False

async def initialize_api_endpoints() -> bool:
    """
    Initialize Pinecone with cryptocurrency API endpoint metadata.
    
    Returns:
        True if initialization was successful, False otherwise
    """
    logger.info("Initializing Pinecone with API endpoint metadata")
    
    try:
        # Create endpoint manager
        manager = PineconeEndpointManager()
        
        # Initialize Pinecone
        initialized = await manager.initialize()
        if not initialized:
            logger.error("Failed to initialize Pinecone")
            return False
        
        # Define the standard server names with proper casing
        # This ensures consistent naming across the application
        STANDARD_SERVER_NAMES = {
            "defillama": "defillama",
            "defi_llama": "defillama",
            "DeFiLlama": "defillama",
            "coingecko": "coingecko",
            "CoinGecko": "coingecko",
            "coin_gecko": "coingecko",
            "coinmarketcap": "coinmarketcap",
            "CoinMarketCap": "coinmarketcap",
            "coin_market_cap": "coinmarketcap",
            "tavily": "tavily", 
            "huggingface": "huggingface",
            "Huggingface": "huggingface",
            "hugging_face": "huggingface",
            "tokenomics": "tokenomics"
        }
        
        # Function to get standardized server name
        def get_standard_name(name):
            """Get standardized server name to ensure consistent casing."""
            if name in STANDARD_SERVER_NAMES:
                return STANDARD_SERVER_NAMES[name]
            # Try case-insensitive matching
            name_lower = name.lower()
            for key, value in STANDARD_SERVER_NAMES.items():
                if key.lower() == name_lower:
                    return value
            # If no match, return the name as is
            return name
        
        # Define endpoints with detailed descriptions
        endpoints = [
            {
                "id": "data://coinmarketcap/price/{coin}",
                "description": "CoinMarketCap API for cryptocurrency price data. Fetches historical price data for a specific cryptocurrency. Best for queries about current and historical prices, price trends, and price analysis."
            },
            {
                "id": "data://coinmarketcap/volume/{coin}",
                "description": "CoinMarketCap API for trading volume data. Provides trading volume history and statistics for cryptocurrencies. Useful for understanding trading activity and market interest."
            },
            {
                "id": "data://coinmarketcap/market/{coin}",
                "description": "CoinMarketCap API for market capitalization data. Provides market cap information, circulation supply, and token ranking. Best for market position analysis and token comparison."
            },
            {
                "id": "data://coingecko/price/{coin}",
                "description": "CoinGecko API for cryptocurrency price data. Fetches current and historical prices with additional market metrics. Best for price analysis and market trends."
            },
            {
                "id": "data://coingecko/market/{coin}",
                "description": "CoinGecko API for comprehensive market data. Provides market cap, trading volume, and supply information. Ideal for market analysis and token metrics."
            },
            {
                "id": "data://defillama/tvl/{protocol}",
                "description": "DeFiLlama API for Total Value Locked data. Provides TVL metrics across multiple blockchains for DeFi protocols. Ideal for understanding protocol adoption and liquidity."
            },
            {
                "id": "data://defillama/yields/{protocol}",
                "description": "DeFiLlama API for yield data. Provides information on yield farming opportunities and returns. Best for yield analysis and comparison."
            },
            {
                "id": "data://tavily/{query}",
                "description": "Tavily API for basic web search. Performs a standard web search for cryptocurrency information, news, and analysis. Best for general queries and current information."
            },
            {
                "id": "data://tavily/research/{query}",
                "description": "Tavily API for in-depth research. Performs comprehensive research on cryptocurrency projects with detailed information. Ideal for thorough analysis and background research."
            },
            {
                "id": "data://huggingface/research/{query}",
                "description": "Hugging Face API for general cryptocurrency research. Leverages AI models to generate detailed information on crypto projects. Good for filling gaps when other APIs don't have data."
            },
            {
                "id": "data://tokenomics/distribution/{project}",
                "description": "Tokenomics API for token distribution data. Provides detailed information on token supply, allocation percentages, and vesting schedules. Essential for understanding token economics."
            },
            {
                "id": "data://project/whitepaper/{project}",
                "description": "Project API for whitepaper access. Retrieves whitepaper URLs and information for cryptocurrency projects. Useful for fundamental research and project analysis."
            }
        ]
        
        # Index endpoints
        count = 0
        for endpoint in endpoints:
            endpoint_id = endpoint["id"]
            description = endpoint["description"]
            
            # Handle endpoints with different structure
            if "capabilities" in endpoint:
                success = await manager.index_endpoint(
                    endpoint_id=endpoint_id,
                    description=description,
                    metadata={"capabilities": endpoint["capabilities"]}
                )
            else:
                success = await manager.index_endpoint(
                    endpoint_id=endpoint_id,
                    description=description
                )
            
            if success:
                count += 1
                logger.info(f"Indexed endpoint: {endpoint_id}")
            else:
                logger.warning(f"Failed to index endpoint: {endpoint_id}")
        
        # Also add simple server name endpoints for more direct service discovery
        for server in ["coingecko", "coinmarketcap", "defillama", "tavily", "huggingface", "tokenomics"]:
            # Use standardized server names
            standard_name = get_standard_name(server)
            await manager.index_endpoint(
                endpoint_id=standard_name,
                description=f"{server.capitalize()} API for cryptocurrency data."
            )
            count += 1
            logger.info(f"Indexed server endpoint: {standard_name}")
        
        # Get the count of vectors in the index
        vector_count = await manager.get_endpoint_count()
        logger.info(f"Index contains {vector_count} endpoint vectors after initialization")
        
        logger.info(f"Successfully indexed {count} API endpoints in Pinecone")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize API endpoints: {str(e)}")
        return False

if __name__ == "__main__":
    # Make sure dotenv is loaded if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
        
    # Run initialization
    asyncio.run(initialize_api_endpoints())
