# test_tavily_parallel.py
import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from backend.retriever.tavily_search import TavilySearch
from backend.retriever.huggingface_search import HuggingFaceSearch
from backend.utils.inference import infer_missing_data
from backend.state import ResearchState

load_dotenv()

async def test_parallel_tavily():
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("TestTavilyParallel")
    logger.debug("Test script started")

    tavily_api_key = os.getenv("TAVILY_API_KEY")
    hf_api_key = os.getenv("HUGGINGFACE_API_KEY")
    logger.debug(f"TAVILY_API_KEY: {'set' if tavily_api_key else 'not set'}")
    logger.debug(f"HUGGINGFACE_API_KEY: {'set' if hf_api_key else 'not set'}")
    if not tavily_api_key or not hf_api_key:
        logger.error("Missing API keys: TAVILY_API_KEY or HUGGINGFACE_API_KEY not set in .env")
        print("Test aborted: API keys missing")
        return

    try:
        tavily = TavilySearch(logger=logger)
        hf_search = HuggingFaceSearch(api_token=hf_api_key, logger=logger)
        logger.debug("TavilySearch and HuggingFaceSearch initialized")
    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}", exc_info=True)
        print(f"Test aborted: Initialization error - {str(e)}")
        return

    state = ResearchState(project_name="ONDO")
    state.data = {"market_cap": "1000000000", "current_price": "0.5"}
    available_data = state.data
    logger.debug(f"ResearchState initialized with data: {json.dumps(available_data)}")

    queries = [
        "ONDO tokenomics",
        "ONDO market analysis",
        "ONDO technical architecture",
        "ONDO governance",
        "ONDO team development"
    ]
    logger.info(f"Starting test with {len(queries)} queries: {queries}")

    start_time = asyncio.get_event_loop().time()
    try:
        results = await tavily.search_batch(queries, max_results=5)
        logger.debug(f"Raw results from search_batch: {results}")
    except Exception as e:
        logger.error(f"Search batch failed: {str(e)}", exc_info=True)
        print(f"Test failed during search: {str(e)}")
        return
    elapsed = asyncio.get_event_loop().time() - start_time

    for i, result in enumerate(results):
        if "needs_inference" in result:
            logger.info(f"Query '{queries[i]}' needs inference")
            try:
                inferred = infer_missing_data(hf_search, available_data, ["summary"], "ONDO", logger)
                results[i] = {"results": [{"href": "https://huggingface.co", "body": inferred.get("summary", "Inferred data")}]}
            except Exception as e:
                logger.error(f"Inference failed for '{queries[i]}': {str(e)}", exc_info=True)
        try:
            assert isinstance(result, dict) and "results" in result, f"Result {i} malformed: {result}"
            assert all("href" in r and "body" in r for r in result["results"]), f"Result {i} missing fields: {result['results']}"
            logger.info(f"Query '{queries[i]}' returned {len(result['results'])} results")
        except AssertionError as e:
            logger.error(f"Assertion failed for result {i}: {str(e)}")
            print(f"Test failed: {str(e)}")
            return

    logger.info(f"Completed {len(queries)} queries in {elapsed:.2f} seconds")
    try:
        assert elapsed < 10, f"Execution took {elapsed:.2f}s, expected <10s with parallelism"
    except AssertionError as e:
        logger.error(f"Parallelism assertion failed: {str(e)}")
        print(f"Test failed: {str(e)}")
        return

    # Test failure case (invalid query)
    try:
        await tavily.search_batch([""])
        logger.error("Empty query should have raised an exception")
        print("Test failed: Empty query did not raise ValueError")
        return
    except ValueError as e:
        logger.info(f"Correctly caught invalid query: {str(e)}")

    logger.info("All tests passed")
    print("Test completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(test_parallel_tavily())
    except Exception as e:
        logging.getLogger("TestTavilyParallel").error(f"Test execution failed: {str(e)}", exc_info=True)
        print(f"Test crashed: {str(e)}")