# XplainCrypto Environment Setup

This document provides instructions for setting up the environment variables required for the XplainCrypto application.

## Required Environment Variables

Create a `.env` file in the root directory of the project with the following variables:

```
# API Keys
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=gcp-starter
HUGGINGFACE_API_KEY=your_huggingface_api_key

# LLM Model Selection
RESEARCHER_LLM_MODEL=gpt-4o-mini
WRITER_LLM_MODEL=mistral-7b-instruct
REVIEWER_LLM_MODEL=gpt-4o-mini
EDITOR_LLM_MODEL=gpt-4o-mini
RAG_LLM_MODEL=llama-3-8b

# Visualization Settings
VISUALIZATION_THEME=dark
PDF_OPTIMIZED=true

# Report Settings
REPORT_OUTPUT_DIR=reports
```

## Model Selection Guide

For optimal performance and cost efficiency, we recommend the following model selection:

### OpenAI Models
- `gpt-4o`: Best for complex reasoning tasks (most expensive)
- `gpt-4o-mini`: Good balance of performance and cost
- `gpt-3.5-turbo`: Suitable for simpler tasks (least expensive)

### Hugging Face Models
- `mistral-7b-instruct`: Good general-purpose model
- `llama-3-8b`: Good for RAG and routing tasks
- `google/pegasus-xsum`: Specialized for summarization

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Gerard161-Site/xplaincrypto.git
cd xplaincrypto
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install pinecone-client langchain-pinecone sentence-transformers matplotlib seaborn plotly weasyprint langchain-mcp-adapters
```

4. Initialize Pinecone endpoints:
```bash
python -c "from backend.orchestration.mcp.initialize_endpoints import initialize_pinecone_endpoints; import asyncio; asyncio.run(initialize_pinecone_endpoints())"
```

5. Run the application:
```bash
python main.py
```
