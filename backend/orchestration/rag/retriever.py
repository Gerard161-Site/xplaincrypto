from langchain_openai import ChatOpenAI
from .vector_store import VectorStore
import os

class RAGRetriever:
    def __init__(self, vector_store: VectorStore, llm_model: str = "gpt-4o"):
        self.vector_store = vector_store
        self.llm = ChatOpenAI(model=llm_model, api_key=os.getenv("OPENAI_API_KEY"))

    async def process_query(self, query: str) -> list[str]:
        """Process a query and return a list of MCP endpoints to call."""
        # Retrieve relevant endpoints from Pinecone
        candidates = self.vector_store.query(query, top_k=5)
        candidate_ids = [endpoint_id for endpoint_id, _ in candidates]
        candidate_descriptions = [desc for _, desc in candidates]

        # Use LLM to decide which endpoints are most relevant
        prompt = f"""
        Given the query: "{query}"
        Here are some available data sources:
        {', '.join(f"{endpoint_id}: {desc}" for endpoint_id, desc in candidates)}
        
        Which endpoints should be called to answer this query? Return a list of endpoint IDs.
        """
        response = await self.llm.ainvoke(prompt)
        
        # Parse the response to extract endpoint IDs
        # This is a simple implementation; in production, you might want more robust parsing
        response_text = response.content
        selected_endpoints = []
        
        for endpoint_id in candidate_ids:
            if endpoint_id in response_text:
                selected_endpoints.append(endpoint_id)
        
        # If no endpoints were selected, use the top candidate
        if not selected_endpoints and candidate_ids:
            selected_endpoints = [candidate_ids[0]]
            
        return selected_endpoints

class LLMDecision:
    @staticmethod
    async def refine_endpoints(query: str, endpoints: list[str], llm=None) -> list[str]:
        """Refine the list of endpoints based on query context."""
        if not llm:
            llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
            
        # For now, return as-is; in the future, this could be enhanced with more sophisticated logic
        return endpoints
