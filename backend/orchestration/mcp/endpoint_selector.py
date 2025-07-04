from typing import List, Dict, Any, Optional
import json
from pathlib import Path
import logging
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from backend.orchestration.rag.vector_store import VectorStore
from backend.utils.cache_utils import CacheManager
import os

logger = logging.getLogger(__name__)

class EndpointSelector:
    """
    Selects MCP endpoints for report generation and chatbot queries.
    - Reports: Uses data_type from visualization_mapping.json to select endpoints.
    - Chatbot: Uses RAG (via Pinecone) for semantic endpoint selection.
    Includes fallbacks to huggingface and tavily.
    """

    def __init__(self, vector_store: VectorStore, client_manager, report_config_path: str = "backend/config/report_structure.json"):
        self.vector_store = vector_store
        self.client_manager = client_manager
        self.cache_manager = CacheManager(project_name="system", logger=logger)
        self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
        self.use_rag = os.getenv("USE_RAG", "false").lower() == "true"
        self.logger = logger

        # Load report configuration
        try:
            with open(report_config_path, "r") as f:
                self.report_config = json.load(f)
            self.logger.info(f"Loaded report configuration from {report_config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load report configuration from {report_config_path}: {str(e)}")
            self.report_config = {}

        # Load visualization mapping
        visualization_mapping_path = "backend/config/visualization_mapping.json"
        try:
            with open(visualization_mapping_path, "r") as f:
                self.viz_mapping = json.load(f)
            self.logger.info(f"Loaded visualization mapping from {visualization_mapping_path}")
        except Exception as e:
            self.logger.error(f"Failed to load visualization mapping from {visualization_mapping_path}: {str(e)}")
            self.viz_mapping = {"visualization_types": {}}

    async def select_endpoints(self, context: str, query: str = None, project_name: str = "unknown") -> List[str]:
        """
        Select endpoints based on the context (report or chatbot).

        Args:
            context: "report" for report generation, "chatbot" for chat queries
            query: The query or section title (for reports)
            project_name: The project name (e.g., "bitcoin")

        Returns:
            A list of selected endpoint strings
        """
        if context == "report":
            return await self.select_for_report(query, project_name)
        elif context == "chatbot":
            return await self.select_for_chatbot(query, project_name)
        self.logger.error(f"Invalid context: {context}")
        raise ValueError(f"Invalid context: {context}")

    async def select_for_report(self, section: str, project_name: str) -> List[str]:
        """
        Select endpoints for a report section based on visualization data_type requirements.

        Args:
            section: The report section title (e.g., "Market Analysis")
            project_name: The project name (e.g., "bitcoin")

        Returns:
            A list of endpoint strings
        """
        cache_key = f"report_{section}_{project_name}"
        cached = self.cache_manager.load("endpoints", "report", cache_key)
        if cached:
            self.logger.info(f"Using cached endpoints for section {section}")
            return cached

        # Find the section configuration
        section_config = next((s for s in self.report_config.get("sections", []) if s["title"].lower() == section.lower()), None)
        if not section_config:
            self.logger.warning(f"No section configuration found for {section}")
            return []

        endpoints = []
        # Iterate through visualizations in the section
        for viz in section_config.get("visualizations", []):
            viz_config = self.viz_mapping["visualization_types"].get(viz)
            if viz_config:
                data_type = viz_config.get("data_type")
                if not data_type:
                    self.logger.warning(f"No data_type defined for visualization {viz}")
                    continue
                self.logger.info(f"Selecting endpoints for visualization {viz} with data_type {data_type}")
                # Find endpoints matching the data_type
                for config in self.client_manager.server_configs:
                    for resource in config.get("resources", []):
                        if resource.get("data_type") == data_type:
                            endpoint = resource["path"].replace("{coin}", project_name).replace("{protocol}", project_name).replace("{days}", "30")
                            endpoints.append(endpoint)
                    for tool in config.get("tools", []):
                        if tool.get("data_type") == data_type:
                            endpoint = f"{config['server_name']}/{tool['name']}"
                            endpoints.append(endpoint)

        # If endpoints found, prioritize the first one (e.g., prefer coinmarketcap over defillama for tvl)
        if endpoints:
            preferred = endpoints[0]
            endpoints = [preferred]
            self.cache_manager.save(endpoints, "endpoints", "report", cache_key)
            self.logger.info(f"Selected endpoints for section {section}: {endpoints}")
            return endpoints

        # Fallback to servers in order (huggingface, then tavily)
        self.logger.warning(f"No endpoints found for data_type {data_type}, using fallback servers")
        for fallback_server in section_config.get("fallback_servers", ["huggingface", "tavily"]):
            for config in self.client_manager.server_configs:
                if config["server_name"] == fallback_server:
                    for resource in config.get("resources", []):
                        if resource.get("data_type") == "research":
                            endpoint = resource["path"].replace("{query}", project_name)
                            self.cache_manager.save([endpoint], "endpoints", "report", cache_key)
                            self.logger.info(f"Fallback to {fallback_server}: {endpoint}")
                            return [endpoint]
        self.logger.error(f"No fallback endpoints available for section {section}")
        return []

    async def select_for_chatbot(self, query: str, project_name: str) -> List[str]:
        """
        Select endpoints for a chatbot query using RAG or keyword matching.

        Args:
            query: The user query (e.g., "Bitcoin price trend")
            project_name: The project name (e.g., "bitcoin")

        Returns:
            A list of endpoint strings
        """
        cache_key = f"chatbot_{query}_{project_name}"
        cached = self.cache_manager.load("endpoints", "chatbot", cache_key)
        if cached:
            self.logger.info(f"Using cached endpoints for chatbot query: {query}")
            return cached

        # Try RAG if enabled and vector store is healthy
        if self.use_rag and self.vector_store.is_healthy():
            try:
                results = await self.vector_store.search(query, top_k=3)
                endpoints = [
                    r["id"].replace("{coin}", project_name).replace("{protocol}", project_name).replace("{query}", query).replace("{days}", "30")
                    for r in results if r["score"] >= 0.7
                ]
                if endpoints and self.llm:
                    prompt = ChatPromptTemplate.from_template(
                        "Given the query: '{query}'\nSelect the top 3 most relevant endpoints:\n{endpoints}\nReturn a JSON array."
                    )
                    response = await self.llm.ainvoke(prompt.format(query=query, endpoints="\n".join(endpoints)))
                    endpoints = json.loads(response.content.strip())[:3]
                if endpoints:
                    self.cache_manager.save(endpoints, "endpoints", "chatbot", cache_key)
                    self.logger.info(f"RAG selected endpoints for query {query}: {endpoints}")
                    return endpoints
            except Exception as e:
                self.logger.error(f"Error in RAG selection: {str(e)}")

        # Fallback to keyword matching
        self.logger.info(f"Falling back to keyword matching for query: {query}")
        endpoints = []
        query_lower = query.lower()
        for config in self.client_manager.server_configs:
            for resource in config.get("resources", []):
                if any(term in resource["description"].lower() for term in query_lower.split()):
                    endpoint = resource["path"].replace("{coin}", project_name).replace("{protocol}", project_name).replace("{query}", query).replace("{days}", "30")
                    endpoints.append(endpoint)
            for tool in config.get("tools", []):
                if any(term in tool["description"].lower() for term in query_lower.split()):
                    endpoint = f"{config['server_name']}/{tool['name']}"
                    endpoints.append(endpoint)
        endpoints = list(set(endpoints))
        if endpoints:
            self.cache_manager.save(endpoints, "endpoints", "chatbot", cache_key)
            self.logger.info(f"Keyword matching selected endpoints: {endpoints}")
            return endpoints

        # Fallback to servers in order (huggingface, then tavily)
        self.logger.warning(f"No endpoints found via keyword matching, using fallback servers")
        for fallback_server in ["huggingface", "tavily"]:
            for config in self.client_manager.server_configs:
                if config["server_name"] == fallback_server:
                    for resource in config.get("resources", []):
                        if resource.get("data_type") == "research":
                            endpoint = resource["path"].replace("{query}", query)
                            self.cache_manager.save([endpoint], "endpoints", "chatbot", cache_key)
                            self.logger.info(f"Fallback to {fallback_server}: {endpoint}")
                            return [endpoint]
        self.logger.error(f"No fallback endpoints available for query {query}")
        return []