# test_hf_api.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_token = os.getenv("HUGGINGFACE_API_KEY")
print(f"API Key: {api_token}")

url = "https://api-inference.huggingface.co/models/distilgpt2"
headers = {"Authorization": f"Bearer {api_token}"}
payload = {"inputs": "Test query"}
response = requests.post(url, headers=headers, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")