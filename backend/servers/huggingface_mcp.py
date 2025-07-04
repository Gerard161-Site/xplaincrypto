from mcp.server.fastmcp import FastMCP
import aiohttp
import logging
import os
import json
import asyncio
import uvicorn
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger("HuggingFaceMCP")
mcp = FastMCP("HuggingFace")

class HuggingFaceApiClient:
    """
    An asynchronous client for interacting with the Hugging Face Inference API.
    Handles model queries, and searching for models/datasets (simulated as per original).
    """
    BASE_MODELS_URL = "https://api-inference.huggingface.co/models"
    # Note: Actual public API for searching models/datasets is not directly used here.
    # The search_models/datasets methods are simulated as in the original HuggingFaceSearch class.

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_token:
            # Allow operation without API key for public models, but log a warning.
            logger.warning("HUGGINGFACE_API_KEY not found. Access to private models or higher rate limits will be unavailable.")
            self.headers = {}
        else:
            self.headers = {"Authorization": f"Bearer {self.api_token}"}
        self.headers["Content-Type"] = "application/json"

    async def _request(
        self, 
        model_id_or_url: str, 
        payload: Optional[Dict[str, Any]] = None,
        is_model_query: bool = True,
        retries: int = 3,
        timeout_seconds: int = 30
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Makes an asynchronous POST (for model query) or GET request.
        """
        url = f"{self.BASE_MODELS_URL}/{model_id_or_url}" if is_model_query else model_id_or_url
        
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession(headers=self.headers) as session:
                    logger.debug(f"Requesting HuggingFace URL: {url} (Attempt {attempt + 1})")
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 503: # Service Temporarily Unavailable
                            logger.warning(f"HuggingFace API 503 error for {url} (Attempt {attempt+1}/{retries}). Retrying...")
                            if attempt == retries - 1:
                                logger.error(f"All retries failed for {url} (503). Returning error.")
                                return {"error": "Service temporarily unavailable after multiple retries", "status_code": 503}
                            await asyncio.sleep(2 * (attempt + 1)) # Exponential backoff
                            continue # Retry the loop
                        else:
                            response_text = await response.text()
                            logger.error(f"HuggingFace API error at {url}: {response.status} - {response_text}")
                            return {"error": response_text, "status_code": response.status}
            except aiohttp.ClientConnectionError as e:
                logger.error(f"HuggingFace connection error for {url}: {str(e)}")
                return {"error": f"Connection error: {str(e)}"}
            except asyncio.TimeoutError:
                logger.warning(f"HuggingFace API timeout for {url} (Attempt {attempt+1}/{retries})")
                if attempt == retries - 1:
                    return {"error": "Request timed out after multiple retries"}
                await asyncio.sleep(2 * (attempt + 1))
            except json.JSONDecodeError as e:
                logger.error(f"HuggingFace JSON decode error for {url}: {str(e)}")
                # Attempt to get text if JSON decoding fails
                async with aiohttp.ClientSession(headers=self.headers) as session:
                     async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as response:
                        response_text_on_error = await response.text()
                        logger.error(f"Raw response on JSON error: {response_text_on_error}")
                        return {"error": f"JSON decode error: {str(e)}", "raw_response": response_text_on_error}
            except Exception as e:
                logger.error(f"Unexpected error requesting HuggingFace API {url}: {str(e)}")
                if attempt == retries -1:
                    return {"error": f"Unexpected error after multiple retries: {str(e)}"}
                await asyncio.sleep(2 * (attempt+1))
        
        return {"error": "All retries failed for HuggingFace API request."}

    async def query_model(self, model_id: str, input_text: str, params: Optional[Dict[str, Any]] = None) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Queries a specified Hugging Face model with input text."""
        payload = {"inputs": input_text, **(params or {})}
        logger.info(f"Querying HuggingFace model: {model_id}")
        response = await self._request(model_id, payload=payload, is_model_query=True)
        # Standardize to list output for consistency, even if API returns a dict for single output.
        if isinstance(response, dict) and "error" not in response:
            return [response]
        elif isinstance(response, list):
            return response
        return response # Return as is if it's an error dict

    # Simulated search methods as per original HuggingFaceSearch, to be replaced if real API access is desired
    async def search_models_simulated(self, query: str, task: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        logger.info(f"Simulating model search for: '{query}', task: '{task}'")
        # Simulate async behavior
        await asyncio.sleep(0.05)
        models = [
            {
                "id": f"simulated/{query.lower().replace(' ', '-')}-{i+1}",
                "name": f"Simulated Model {query.capitalize()} {i+1}",
                "task": task or "text-generation",
                "downloads": 100 * (i + 1),
                "likes": 10 * (i + 1)
            } for i in range(limit)
        ]
        return {"query": query, "task": task, "results": models, "count": len(models), "source": "simulated_search"}

    async def search_datasets_simulated(self, query: str, task: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        logger.info(f"Simulating dataset search for: '{query}', task: '{task}'")
        await asyncio.sleep(0.05)
        datasets = [
            {
                "id": f"simulated-data/{query.lower().replace(' ', '-')}-{i+1}",
                "name": f"Simulated Dataset {query.capitalize()} {i+1}",
                "task": task,
                "downloads": 80 * (i + 1),
                "likes": 8 * (i + 1)
            } for i in range(limit)
        ]
        return {"query": query, "task": task, "results": datasets, "count": len(datasets), "source": "simulated_search"}

    async def get_model_info_simulated(self, model_id: str) -> Dict[str, Any]:
        logger.info(f"Simulating get_model_info for: {model_id}")
        await asyncio.sleep(0.05)
        return {
            "id": model_id,
            "name": model_id.split('/')[-1] if '/' in model_id else model_id,
            "description": f"Simulated detailed information for model {model_id}. This model is a generic transformer suitable for various NLP tasks.",
            "tags": ["nlp", "transformer", "simulated"],
            "pipeline_tag": "text-generation",
            "downloads": 12345,
            "likes": 678,
            "source": "simulated_info"
        }

# --- MCP Resources ---
@mcp.resource("data://huggingface/model/{model_id}")
async def get_model_info_mcp(model_id: str) -> Dict[str, Any]:
    """Fetch (simulated) model information from HuggingFace for a given model ID."""
    client = HuggingFaceApiClient()
    return await client.get_model_info_simulated(model_id)

@mcp.resource("data://huggingface/query/{model_id}/{input_text}")
async def query_model_mcp_resource(model_id: str, input_text: str) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Query a HuggingFace model. Input text should be URL-encoded if it contains special characters."""
    # Basic input sanitization for model_id might be needed if it comes from untrusted URL paths
    client = HuggingFaceApiClient()
    # Here, we assume input_text is already decoded if it was URL encoded.
    # If using query parameters in JSON body in a real scenario, this would be simpler.
    return await client.query_model(model_id, input_text)

@mcp.resource("data://huggingface/research/{query}")
async def research_query_mcp(query: str) -> Dict[str, Any]:
    """(Simulated) Perform comprehensive research on a query using HuggingFace resources."""
    client = HuggingFaceApiClient()
    # This will use the simulated search for models and datasets
    models_result = await client.search_models_simulated(query)
    datasets_result = await client.search_datasets_simulated(query)
    return {
        "query": query,
        "models": models_result.get("results", []),
        "datasets": datasets_result.get("results", []),
        "summary": f"Simulated research: Found {models_result.get('count',0)} models and {datasets_result.get('count',0)} datasets for '{query}'"
    }

# --- MCP Tools ---
@mcp.tool()
async def query_hf_model(model_id: str, input_text: str, parameters: Optional[Dict[str, Any]] = None) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Tool to query a specified Hugging Face model with input text and optional parameters.
    Args:
        model_id: The ID of the Hugging Face model (e.g., "gpt2", "distilbert-base-uncased-finetuned-sst-2-english").
        input_text: The text input for the model.
        parameters: Optional dictionary of parameters for the model query (e.g., {"max_length": 50}).
    Returns:
        The model's output, typically a list of dictionaries or a dictionary for errors.
    """
    logger.info(f"Tool 'query_hf_model' called for model: {model_id}")
    client = HuggingFaceApiClient()
    return await client.query_model(model_id, input_text, params=parameters)

@mcp.tool()
async def search_hf_models(query: str, task: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Tool to (simulated) search for Hugging Face models.
    Args:
        query: The search query string.
        task: Optional task to filter by (e.g., "text-generation", "translation").
        limit: Maximum number of results to return.
    Returns:
        A dictionary containing a list of (simulated) model details.
    """
    logger.info(f"Tool 'search_hf_models' called with query: {query}")
    client = HuggingFaceApiClient()
    return await client.search_models_simulated(query, task=task, limit=limit)

@mcp.tool()
async def search_hf_datasets(query: str, task: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Tool to (simulated) search for Hugging Face datasets.
    Args:
        query: The search query string.
        task: Optional task to filter by.
        limit: Maximum number of results to return.
    Returns:
        A dictionary containing a list of (simulated) dataset details.
    """
    logger.info(f"Tool 'search_hf_datasets' called with query: {query}")
    client = HuggingFaceApiClient()
    return await client.search_datasets_simulated(query, task=task, limit=limit)

@mcp.tool()
async def get_hf_model_details(model_id: str) -> Dict[str, Any]:
    """
    Tool to get (simulated) detailed information about a specific HuggingFace model.
    Args:
        model_id: The ID of the model (e.g., "gpt2").
    Returns:
        A dictionary containing (simulated) model information.
    """
    logger.info(f"Tool 'get_hf_model_details' called for model_id: {model_id}")
    client = HuggingFaceApiClient()
    return await client.get_model_info_simulated(model_id)

async def run_mcp_server(port: int):
    """
    Run the MCP server with Uvicorn on the specified port.
    """
    config = uvicorn.Config(app=mcp.get_asgi_app(), host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    import selectors
    selectors.DefaultSelector = selectors.PollSelector
    print("Entered main block", flush=True)
    logger.info("Entered main block")
    logger.info("Starting HuggingFace MCP server with stdio")
    print("Starting HuggingFace MCP server with stdio", flush=True)
    try:
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        logger.debug("New event loop set")
        print("New event loop set", flush=True)
        logging.getLogger("mcp.server").setLevel(logging.DEBUG)
        logger.debug("Calling mcp.run with stdio")
        print("Calling mcp.run with stdio", flush=True)
        try:
            mcp.run(transport="stdio")
        except Exception as e:
            logger.error(f"Error in mcp.run: {str(e)}")
            print(f"Error in mcp.run: {str(e)}", flush=True)
            raise
        logger.debug("MCP server running")
        print("MCP server running", flush=True)
    except Exception as e:
        logger.error(f"Error in mcp.run: {str(e)}")
        print(f"Error in mcp.run: {str(e)}", flush=True)
        raise
