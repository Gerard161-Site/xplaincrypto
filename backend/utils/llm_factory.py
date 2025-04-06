"""
LLM Factory module for dynamically selecting appropriate LLM models based on task requirements.
This module provides a flexible way to configure different LLM models for different components
of the XplainCrypto application.
"""

import os
import logging
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEndpoint

logger = logging.getLogger(__name__)

# Default model mapping if not specified in environment variables
DEFAULT_MODEL_MAPPING = {
    "RESEARCHER": "gpt-4o-mini",
    "WRITER": "gpt-4o-mini",
    "VISUALIZER": "gpt-4o-mini",
    "REVIEWER": "gpt-4o-mini",
    "EDITOR": "gpt-4o-mini",
    "PUBLISHER": "gpt-4o-mini",
    "RAG": "mistral-7b-instruct",
    "MCP_ROUTER": "mistral-7b-instruct"
}

class LLMFactory:
    """Factory class for creating LLM instances based on task requirements."""
    
    @staticmethod
    def get_llm_for_task(task_name: str, **kwargs) -> Any:
        """
        Get an appropriate LLM for a specific task.
        
        Args:
            task_name: The name of the task (e.g., "RESEARCHER", "WRITER", "RAG")
            **kwargs: Additional arguments to pass to the LLM constructor
            
        Returns:
            An initialized LLM instance appropriate for the task
        """
        task_upper = task_name.upper()
        
        # Get model name from environment variable or default mapping
        model_name = os.getenv(f"{task_upper}_LLM_MODEL")
        if not model_name:
            model_name = DEFAULT_MODEL_MAPPING.get(task_upper)
            if not model_name:
                logger.warning(f"No model specified for {task_name}, using gpt-4o-mini as fallback")
                model_name = "gpt-4o-mini"
        
        logger.info(f"Using model {model_name} for task {task_name}")
        
        # Determine if it's a HuggingFace or OpenAI model
        if "gpt" in model_name.lower() or "openai" in model_name.lower():
            # Get API key from environment or kwargs
            api_key = kwargs.get("api_key") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(f"OPENAI_API_KEY environment variable not set for {task_name}")
                
            return ChatOpenAI(model=model_name, api_key=api_key, **kwargs)
        else:
            # HuggingFace model
            hf_token = kwargs.get("hf_token") or os.getenv("HUGGINGFACE_API_KEY")
            if not hf_token:
                raise ValueError(f"HUGGINGFACE_API_KEY environment variable not set for {task_name}")
                
            return HuggingFaceEndpoint(
                endpoint_url=f"https://api-inference.huggingface.co/models/{model_name}",
                huggingface_api_key=hf_token,
                task="text-generation",
                **kwargs
            )
    
    @staticmethod
    def get_embedding_model(model_name: Optional[str] = None) -> Any:
        """
        Get an embedding model for vector embeddings.
        
        Args:
            model_name: Optional model name override
            
        Returns:
            An initialized embedding model
        """
        # Get model name from environment variable or use default
        model_name = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        
        # For now, we're using sentence-transformers which is imported directly where needed
        # This method is a placeholder for future expansion to support different embedding models
        logger.info(f"Using embedding model {model_name}")
        return model_name
