import asyncio
import os
import sys
import logging
import time
import statistics
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAGPerformanceTest")

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

async def test_rag_performance():
    """Test the performance improvement from RAG caching."""
    logger.info("Starting RAG performance test")
    
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
    
    # Test queries - a mix of different types of queries
    test_queries = [
        "solana market analysis",
        "ethereum price prediction",
        "bitcoin tokenomics",
        "ondo yield farming",
        "defi protocol comparison",
        "layer 2 scaling solutions",
        "stablecoin mechanisms",
        "crypto regulation updates",
        "nft market trends",
        "web3 gaming platforms"
    ]
    
    # Number of runs for each phase
    num_runs = 3
    
    # Phase 1: No cache (cold start)
    logger.info(f"Phase 1: No cache (cold start) - {num_runs} runs for each query")
    no_cache_times = []
    
    for i in range(num_runs):
        logger.info(f"Run {i+1}/{num_runs}")
        for query in test_queries:
            start_time = time.time()
            endpoints = await rag_retriever.process_query(query)
            elapsed_time = time.time() - start_time
            no_cache_times.append(elapsed_time)
            logger.info(f"Query: '{query}' - Time: {elapsed_time:.4f}s - Endpoints: {len(endpoints)}")
    
    # Phase 2: With cache
    logger.info(f"\nPhase 2: With cache - {num_runs} runs for each query")
    cache_times = []
    
    for i in range(num_runs):
        logger.info(f"Run {i+1}/{num_runs}")
        for query in test_queries:
            start_time = time.time()
            endpoints = await rag_retriever.process_query(query)
            elapsed_time = time.time() - start_time
            cache_times.append(elapsed_time)
            logger.info(f"Query: '{query}' - Time: {elapsed_time:.4f}s - Endpoints: {len(endpoints)}")
    
    # Calculate statistics
    avg_no_cache = statistics.mean(no_cache_times)
    avg_cache = statistics.mean(cache_times)
    median_no_cache = statistics.median(no_cache_times)
    median_cache = statistics.median(cache_times)
    max_no_cache = max(no_cache_times)
    max_cache = max(cache_times)
    min_no_cache = min(no_cache_times)
    min_cache = min(cache_times)
    
    # Calculate speedup
    avg_speedup = avg_no_cache / avg_cache if avg_cache > 0 else float('inf')
    median_speedup = median_no_cache / median_cache if median_cache > 0 else float('inf')
    
    # Print results
    logger.info("\nPerformance Results:")
    logger.info(f"Number of queries: {len(test_queries)}")
    logger.info(f"Number of runs per phase: {num_runs}")
    logger.info(f"Total queries executed: {len(test_queries) * num_runs * 2}")
    logger.info("\nNo Cache (Cold Start):")
    logger.info(f"  Average time: {avg_no_cache:.4f}s")
    logger.info(f"  Median time: {median_no_cache:.4f}s")
    logger.info(f"  Min time: {min_no_cache:.4f}s")
    logger.info(f"  Max time: {max_no_cache:.4f}s")
    logger.info("\nWith Cache:")
    logger.info(f"  Average time: {avg_cache:.4f}s")
    logger.info(f"  Median time: {median_cache:.4f}s")
    logger.info(f"  Min time: {min_cache:.4f}s")
    logger.info(f"  Max time: {max_cache:.4f}s")
    logger.info("\nSpeedup:")
    logger.info(f"  Average speedup: {avg_speedup:.2f}x")
    logger.info(f"  Median speedup: {median_speedup:.2f}x")
    
    # Check cache files
    cache_files = list(cache_dir.glob("**/*.json"))
    logger.info(f"\nCache files created: {len(cache_files)}")
    
    # Calculate cache size
    total_size = sum(file.stat().st_size for file in cache_files)
    logger.info(f"Total cache size: {total_size / 1024:.2f} KB")
    
    logger.info("\nRAG performance test completed")

if __name__ == "__main__":
    asyncio.run(test_rag_performance()) 