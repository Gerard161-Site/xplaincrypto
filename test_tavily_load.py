from backend.retriever.tavily_search import TavilySearch
from backend.utils.cache_utils import CacheManager
import asyncio
import json
import glob

async def test_load():
    # Find the test cache file
    files = glob.glob('docs/ondo/cache/tavily/research_ONDO_test*.json')
    if not files:
        print("No test cache file found")
        return
    
    cache_path = files[0]
    print(f"Found cache file: {cache_path}")
    
    # Load the cache file directly
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
        print("Successfully loaded JSON directly")
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to load JSON directly: {str(e)}")
        return
    
    # Load the cache file using CacheManager
    cache_manager = CacheManager(project_name='ondo')
    query = "ONDO_test query with unicode: \u2028\u2029 characters"
    
    print("Loading cache using CacheManager...")
    cached_result = cache_manager.load("tavily", "research", query)
    
    if cached_result:
        print("Successfully loaded cache using CacheManager")
        print(f"Query from cache: {cached_result.get('query', 'Not found')}")
        
        # Check if the structure is correct
        if "results" in cached_result:
            print(f"Number of results: {len(cached_result['results'])}")
        else:
            print("No results found in cached data")
    else:
        print("ERROR: Failed to load cache using CacheManager")

# Run the test
asyncio.run(test_load()) 