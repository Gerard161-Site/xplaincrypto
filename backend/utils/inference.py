import json
from typing import Dict, List
from backend.retriever.huggingface_search import HuggingFaceSearch
import openai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Retry decorator for OpenAI API calls
def openai_retry_decorator(func):
    """Add exponential backoff retry logic to functions that make OpenAI API calls."""
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),  # Wait between 4-60 seconds with exponential backoff
        stop=stop_after_attempt(5),                          # Give up after 5 attempts
        retry=retry_if_exception_type((                      # Retry on specific error types
            openai.RateLimitError,                           # 429 errors
            openai.APITimeoutError,                          # Timeout
            openai.APIConnectionError                        # Connection issues
        ))
    )
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

def infer_missing_data(hf_search: HuggingFaceSearch, available_data: Dict, missing_fields: List[str], project_name: str, logger, model="distilbert-base-uncased-distilled-squad") -> Dict:
    inferred = {}
    logger.info(f"Inferring {len(missing_fields)} missing fields: {missing_fields}")
    context = json.dumps(available_data)
    for field in missing_fields:
        question = f"What is the {field} for {project_name}?"
        payload = {"question": question, "context": context}
        try:
            result = hf_search.query(model, payload)  # Pass dict instead of string
            inferred_value = result[0].get("answer", f"Unable to infer {field}").strip()
            inferred[field] = inferred_value
            logger.info(f"Inferred {field}: {inferred_value}")
        except Exception as e:
            logger.error(f"Failed to infer {field}: {str(e)}")
            inferred[field] = f"Unable to infer {field}"
    return inferred

