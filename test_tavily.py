from backend.retriever.tavily_search import TavilySearch
import asyncio
import os
import json

async def test():
    # Remove existing cache files
    try:
        for file in os.listdir("docs/ondo/cache/tavily"):
            if file.startswith("research_ONDO_test"):
                os.remove(os.path.join("docs/ondo/cache/tavily", file))
        print("Cleared existing test cache files")
    except:
        print("No existing cache files to clear")
    
    # Create Tavily search instance
    ts = TavilySearch(project_name='ondo')
    
    # Perform research with a test query
    print("Performing research...")
    result = await ts.research('ONDO_test query with unicode: \u2028\u2029 characters')
    print("Research completed")
    
    # Verify cache file exists
    cache_path = "docs/ondo/cache/tavily/research_ONDO_test query with unicode_ __ characters.json"
    if os.path.exists(cache_path):
        print(f"Cache file created: {cache_path}")
        
        # Try to load the cache file to verify it's valid JSON
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            print("Cache file contains valid JSON")
            
            # Check if the data structure is correct
            if "data" in cached_data and "metadata" in cached_data:
                print("Cache file has correct structure")
                
                # Verify that Unicode characters were properly handled
                if "query" in cached_data["data"]:
                    print(f"Query in cache: {cached_data['data']['query']}")
            else:
                print("Cache file has incorrect structure")
        except json.JSONDecodeError as e:
            print(f"ERROR: Cache file contains invalid JSON: {str(e)}")
    else:
        print(f"ERROR: Cache file not created at {cache_path}")

# Run the test
asyncio.run(test()) 