from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
import os

class VectorStore:
    def __init__(self, api_key: str, index_name: str = "xplaincrypto-endpoints"):
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")

        # Create or connect to Pinecone index
        if index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=index_name,
                dimension=384,  # Dimension of the sentence transformer model
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        self.index = self.pc.Index(index_name)

    def upsert_endpoint(self, endpoint_id: str, description: str):
        """Upsert metadata for an MCP endpoint into Pinecone."""
        vector = self.encoder.encode(description).tolist()
        self.index.upsert(vectors=[(endpoint_id, vector, {"description": description})])

    def query(self, query: str, top_k: int = 3):
        """Query Pinecone for the most relevant MCP endpoints."""
        query_vector = self.encoder.encode(query).tolist()
        results = self.index.query(vector=query_vector, top_k=top_k, include_metadata=True)
        return [(match["id"], match["metadata"]["description"]) for match in results["matches"]]

# Initialize with environment variable
def get_vector_store():
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY environment variable not set")
    return VectorStore(api_key=api_key)
