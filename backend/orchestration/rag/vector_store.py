try:
    from pinecone import Pinecone, ServerlessSpec
    NEW_PINECONE_SDK = True
except ImportError:
    # Fall back to old SDK
    import pinecone
    NEW_PINECONE_SDK = False
from sentence_transformers import SentenceTransformer
import os
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, api_key: str, index_name: str = "xplaincrypto-endpoints"):
        self.api_key = api_key
        self.index_name = index_name
        
        try:
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"Error initializing SentenceTransformer: {str(e)}")
            self.encoder = None

        # Create or connect to Pinecone index
        try:
            if NEW_PINECONE_SDK:
                logger.info("Using new Pinecone SDK")
                self.pc = Pinecone(api_key=api_key)
                
                # Check if index exists
                if index_name not in self.pc.list_indexes().names():
                    logger.info(f"Creating index: {index_name}")
                    self.pc.create_index(
                        name=index_name,
                        dimension=384,  # Dimension of the sentence transformer model
                        metric="cosine",
                        spec=ServerlessSpec(cloud="aws", region="us-east-1")
                    )
                self.index = self.pc.Index(index_name)
            else:
                logger.info("Using legacy Pinecone SDK")
                pinecone.init(api_key=api_key, environment=os.getenv("PINECONE_ENVIRONMENT", "gcp-starter"))
                
                # Check if index exists
                if index_name not in pinecone.list_indexes():
                    logger.info(f"Creating index: {index_name}")
                    pinecone.create_index(
                        name=index_name,
                        dimension=384,  # Dimension of the sentence transformer model
                        metric="cosine"
                    )
                self.index = pinecone.Index(index_name)
                
            logger.info(f"Successfully connected to Pinecone index: {index_name}")
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}")
            self.index = None
            
    def is_healthy(self) -> bool:
        """Check if the store is properly initialized and connected."""
        return self.index is not None and self.encoder is not None

    def upsert_endpoint(self, endpoint_id: str, description: str, metadata: Dict[str, Any] = None):
        """
        Upsert metadata for an MCP endpoint into Pinecone.
        
        Args:
            endpoint_id: Unique ID for the endpoint
            description: Text description of the endpoint's capabilities
            metadata: Optional additional metadata
        """
        if not self.is_healthy():
            logger.error("Vector store is not healthy, cannot upsert endpoint")
            return False
            
        # Create complete metadata object
        complete_metadata = {"description": description}
        if metadata:
            complete_metadata.update(metadata)
            
        try:
            # Encode description
            vector = self.encoder.encode(description).tolist()
            
            # Upsert to Pinecone
            if NEW_PINECONE_SDK:
                self.index.upsert(vectors=[(endpoint_id, vector, complete_metadata)])
            else:
                # Format for old SDK
                self.index.upsert(vectors=[{
                    "id": endpoint_id,
                    "values": vector,
                    "metadata": complete_metadata
                }])
                
            logger.info(f"Successfully upserted endpoint: {endpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Error upserting endpoint {endpoint_id}: {str(e)}")
            return False

    def query(self, query: str, top_k: int = 3) -> List[Tuple[str, str, float]]:
        """
        Query Pinecone for the most relevant MCP endpoints.
        
        Args:
            query: The search query
            top_k: Number of results to return
            
        Returns:
            List of tuples (id, description, score)
        """
        if not self.is_healthy():
            logger.error("Vector store is not healthy, cannot query")
            return []
            
        try:
            # Encode query
            query_vector = self.encoder.encode(query).tolist()
            
            # Query Pinecone
            if NEW_PINECONE_SDK:
                results = self.index.query(vector=query_vector, top_k=top_k, include_metadata=True)
            else:
                # Format for old SDK
                results = self.index.query(
                    queries=[query_vector],
                    top_k=top_k,
                    include_metadata=True
                )
                # Extract nested results if needed
                if "results" in results and len(results["results"]) > 0:
                    results = results["results"][0]
            
            # Extract results
            matches = []
            if NEW_PINECONE_SDK:
                for match in results.matches:
                    endpoint_id = match.id
                    description = match.metadata.get("description", "")
                    score = match.score
                    matches.append((endpoint_id, description, score))
            else:
                # Format for old SDK
                for match in results.get("matches", []):
                    endpoint_id = match.get("id", "")
                    description = match.get("metadata", {}).get("description", "")
                    score = match.get("score", 0)
                    matches.append((endpoint_id, description, score))
                
            logger.info(f"Query returned {len(matches)} matches")
            return matches
        except Exception as e:
            logger.error(f"Error querying vector store: {str(e)}")
            return []
        
    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete an endpoint from the vector store."""
        if not self.is_healthy():
            logger.error("Vector store is not healthy, cannot delete endpoint")
            return False
            
        try:
            if NEW_PINECONE_SDK:
                self.index.delete(ids=[endpoint_id])
            else:
                # Format for old SDK
                self.index.delete(ids=[endpoint_id])
            logger.info(f"Successfully deleted endpoint: {endpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting endpoint {endpoint_id}: {str(e)}")
            return False
            
    def clear_all(self) -> bool:
        """Delete all endpoints from the vector store."""
        if not self.is_healthy():
            logger.error("Vector store is not healthy, cannot clear all")
            return False
            
        try:
            if NEW_PINECONE_SDK:
                self.index.delete(delete_all=True)
            else:
                # Format for old SDK
                self.index.delete(delete_all=True)
            logger.info("Successfully cleared all endpoints")
            return True
        except Exception as e:
            logger.error(f"Error clearing all endpoints: {str(e)}")
            return False

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding for the given text.
        
        Args:
            text: The text to embed
            
        Returns:
            A list of floats representing the embedding
        """
        try:
            from sentence_transformers import SentenceTransformer
            
            # Use a shared instance of the model to avoid reloading
            if not hasattr(self, "_embedding_model"):
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                
            # Generate embedding
            embedding = self._embedding_model.encode(text)
            
            # Convert to list of floats
            return embedding.tolist()
        except Exception as e:
            self.logger.error(f"Error generating embedding: {str(e)}", exc_info=True)
            return None
            
    async def search(self, embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search the vector store for similar vectors.
        
        Args:
            embedding: The embedding to search for
            top_k: The number of results to return
            
        Returns:
            A list of dictionaries containing the search results
        """
        try:
            if not self.index:
                self.logger.error("Vector store index not initialized")
                return []
                
            # Query the index
            results = self.index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            # Format results
            formatted_results = []
            for match in results.matches:
                formatted_results.append({
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata
                })
                
            return formatted_results
        except Exception as e:
            self.logger.error(f"Error searching vector store: {str(e)}", exc_info=True)
            return []

# Initialize with environment variable
def get_vector_store():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
        
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        logger.error("PINECONE_API_KEY environment variable not set")
        raise ValueError("PINECONE_API_KEY environment variable not set")
        
    try:
        return VectorStore(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {str(e)}")
        raise
