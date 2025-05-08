import asyncio
import os
import sys
import logging
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGCachingTest")

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# Import necessary modules
try:
    from backend.orchestration.rag.vector_store import VectorStore, get_vector_store
    from backend.orchestration.rag.retriever import RAGRetriever
except ImportError:
    logger.error("Failed to import required modules. Make sure you're running from the project root.")
    sys.exit(1)

async def test_rag_caching():
    """Test the RAG caching functionality."""
    logger.info("Starting RAG caching test")
    
    # Initialize vector store
    try:
        vector_store = get_vector_store()
        if not vector_store.is_healthy():
            logger.error("Vector store is not healthy. Check Pinecone connection.")
            return
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {str(e)}")
        return
    
    # Initialize RAG retriever
    rag_retriever = RAGRetriever(vector_store)
    
    # Clean up existing cache files
    cache_dir = Path("docs/system/cache/rag")
    if cache_dir.exists():
        logger.info(f"Removing existing cache directory: {cache_dir}")
        import shutil
        shutil.rmtree(cache_dir)
    
    # Test queries
    test_queries = [
        "solana market analysis",
        "ethereum price prediction",
        "bitcoin tokenomics"
    ]
    
    # First run - should hit vector store and LLM
    logger.info("First run - should query vector store and LLM")
    first_run_results = {}
    first_run_start = time.time()
    
    for query in test_queries:
        logger.info(f"Processing query: {query}")
        endpoints = await rag_retriever.process_query(query)
        first_run_results[query] = endpoints
        logger.info(f"Selected endpoints: {endpoints}")
    
    first_run_time = time.time() - first_run_start
    logger.info(f"First run completed in {first_run_time:.2f} seconds")
    
    # Check if cache files were created
    if not cache_dir.exists():
        logger.error("Cache directory was not created")
        return
    
    cache_files = list(cache_dir.glob("**/*.json"))
    logger.info(f"Cache files created: {len(cache_files)}")
    for file in cache_files:
        logger.info(f"  - {file}")
    
    # Second run - should use cache
    logger.info("\nSecond run - should use cache")
    second_run_results = {}
    second_run_start = time.time()
    
    for query in test_queries:
        logger.info(f"Processing query: {query}")
        endpoints = await rag_retriever.process_query(query)
        second_run_results[query] = endpoints
        logger.info(f"Selected endpoints: {endpoints}")
    
    second_run_time = time.time() - second_run_start
    logger.info(f"Second run completed in {second_run_time:.2f} seconds")
    
    # Verify results match
    all_match = True
    for query in test_queries:
        if set(first_run_results[query]) != set(second_run_results[query]):
            logger.error(f"Results for query '{query}' don't match between runs")
            logger.error(f"First run: {first_run_results[query]}")
            logger.error(f"Second run: {second_run_results[query]}")
            all_match = False
    
    if all_match:
        logger.info("All results match between runs")
    
    # Performance comparison
    speedup = first_run_time / second_run_time if second_run_time > 0 else float('inf')
    logger.info(f"\nPerformance comparison:")
    logger.info(f"First run (no cache): {first_run_time:.2f} seconds")
    logger.info(f"Second run (with cache): {second_run_time:.2f} seconds")
    logger.info(f"Speedup factor: {speedup:.2f}x")
    
    # Test with project name
    logger.info("\nTesting with project name")
    project_query = "market analysis"
    project_name = "ondo"
    
    # First run with project
    logger.info("First run with project - should query vector store and LLM")
    project_endpoints = await rag_retriever.get_endpoints_for_project(project_query, project_name)
    logger.info(f"Selected endpoints for '{project_query}' with project '{project_name}': {project_endpoints}")
    
    # Second run with project - should use cache
    logger.info("Second run with project - should use cache")
    cached_project_endpoints = await rag_retriever.get_endpoints_for_project(project_query, project_name)
    logger.info(f"Cached endpoints for '{project_query}' with project '{project_name}': {cached_project_endpoints}")
    
    # Verify project results match
    if set(project_endpoints) == set(cached_project_endpoints):
        logger.info("Project results match between runs")
    else:
        logger.error("Project results don't match between runs")
        logger.error(f"First run: {project_endpoints}")
        logger.error(f"Second run: {cached_project_endpoints}")
    
    logger.info("RAG caching test completed")

if __name__ == "__main__":
    asyncio.run(test_rag_caching()) 