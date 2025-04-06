from mcp.server.fastmcp import FastMCP
from retriever.huggingface_search import HuggingFaceAPI

mcp = FastMCP("HuggingFace")

@mcp.resource("data://huggingface/model/{model_id}")
async def get_model_info(model_id: str) -> dict:
    """Fetch model information from HuggingFace for a given model ID."""
    api = HuggingFaceAPI()
    return await api.get_model_info(model_id)

@mcp.resource("data://huggingface/dataset/{dataset_id}")
async def get_dataset_info(dataset_id: str) -> dict:
    """Fetch dataset information from HuggingFace for a given dataset ID."""
    api = HuggingFaceAPI()
    return await api.get_dataset_info(dataset_id)

@mcp.tool()
async def search_models(query: str, task: str = None, library: str = None) -> list:
    """
    Search for models on HuggingFace.
    
    Args:
        query: The search query
        task: Filter by task (e.g., "text-classification", "token-classification")
        library: Filter by library (e.g., "pytorch", "tensorflow")
    """
    api = HuggingFaceAPI()
    return await api.search_models(query, task=task, library=library)

@mcp.tool()
async def search_datasets(query: str, task: str = None) -> list:
    """
    Search for datasets on HuggingFace.
    
    Args:
        query: The search query
        task: Filter by task (e.g., "text-classification", "question-answering")
    """
    api = HuggingFaceAPI()
    return await api.search_datasets(query, task=task)

if __name__ == "__main__":
    mcp.run(transport="stdio")
