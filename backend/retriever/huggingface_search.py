import os
import requests
from typing import Dict, Any, List
import logging
from dotenv import load_dotenv
import time

load_dotenv()

class HuggingFaceSearch:
    def __init__(self, api_token: str = None, logger: logging.Logger = None):
        self.base_url = "https://api-inference.huggingface.co/models"
        self.api_token = api_token or os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_token:
            raise ValueError("HUGGINGFACE_API_KEY not found in environment")
        self.headers = {"Authorization": f"Bearer {self.api_token}"}
        self.logger = logger or logging.getLogger("HuggingFaceSearch")

    def query(self, model: str, inputs: Dict | str, parameters: Dict[str, Any] = None, retries: int = 2) -> List[Dict]:
        url = f"{self.base_url}/{model}"
        payload = inputs if isinstance(inputs, dict) else {"inputs": inputs}
        if parameters:
            payload.update(parameters)
        
        self.logger.info(f"Querying {url} with timeout=60s")
        for attempt in range(retries):
            start_time = time.time()
            try:
                response = requests.post(url, headers=self.headers, json=payload, timeout=60)
                response.raise_for_status()
                elapsed = time.time() - start_time
                self.logger.info(f"Response received in {elapsed:.2f} seconds")
                result = response.json()
                self.logger.debug(f"Hugging Face response for {model}: {result}")
                return result if isinstance(result, list) else [result]
            except requests.exceptions.RequestException as e:
                elapsed = time.time() - start_time
                self.logger.error(f"Hugging Face API error (attempt {attempt + 1}/{retries}, took {elapsed:.2f}s): {str(e)}")
                if attempt < retries - 1:
                    delay = (attempt + 1) * 10
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                self.logger.warning(f"All retries failed for {model}, using fallback")
                return [{"answer": inputs.get("question", inputs) if isinstance(inputs, dict) else inputs}]