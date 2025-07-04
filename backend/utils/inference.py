import logging
import asyncio
from typing import Dict, Any, List
from backend.orchestration.mcp.client_manager import MCPClientManager

logger = logging.getLogger(__name__)

class InferenceManager:
    def __init__(self):
        self.mcp_client = MCPClientManager()
        self.logger = logger

    async def infer_missing_data(self, data: Dict[str, Any], missing_keys: List[str]) -> Dict[str, Any]:
        """
        Infer missing data in the provided dictionary using the huggingface MCP server.
        
        Args:
            data: The input data dictionary
            missing_keys: List of keys that are missing and need to be inferred
            
        Returns:
            Updated data dictionary with inferred values
        """
        self.logger.info(f"Inferring missing data for keys: {missing_keys}")
        updated_data = data.copy()
        
        for key in missing_keys:
            try:
                # Construct a query to fetch missing data using the huggingface MCP server
                query = f"Information about {key} for project {updated_data.get('project_name', 'unknown')}"
                self.logger.info(f"Fetching missing data for key '{key}' with query: {query}")
                
                # Use MCPClientManager to call the huggingface server's research tool
                result = await self.mcp_client.execute_tool(
                    server_name="huggingface",
                    tool_name="research",
                    params={"query": query, "project_name": updated_data.get("project_name", "unknown")}
                )
                
                if result and "error" not in result:
                    updated_data[key] = result.get("data", result.get("results", "Inferred data not available"))
                    self.logger.info(f"Successfully inferred data for key '{key}': {updated_data[key]}")
                else:
                    updated_data[key] = "Inferred data not available"
                    self.logger.warning(f"Failed to infer data for key '{key}': {result.get('error', 'Unknown error')}")
            except Exception as e:
                self.logger.error(f"Error inferring data for key '{key}': {str(e)}")
                updated_data[key] = "Inferred data not available"
        
        return updated_data

# Singleton instance for synchronous access
_inference_manager = InferenceManager()

def infer_missing_data(data: Dict[str, Any], missing_keys: List[str]) -> Dict[str, Any]:
    """
    Synchronous wrapper for infer_missing_data.
    
    Args:
        data: The input data dictionary
        missing_keys: List of keys that are missing and need to be inferred
        
    Returns:
        Updated data dictionary with inferred values
    """
    return asyncio.run(_inference_manager.infer_missing_data(data, missing_keys))