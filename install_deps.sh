#!/bin/bash

echo "Installing dependencies for XplainCrypto..."

# Create necessary directories if they don't exist
mkdir -p backend/research
mkdir -p docs

# Install Python dependencies
pip install -r requirements.txt

echo "Installing additional dependencies..."
pip install matplotlib python-dotenv langchain langgraph pydantic requests

echo "Creating empty test file for dependencies check..."
cat > dependency_test.py << 'EOF'
# Test imports
try:
    import logging
    import os
    import json
    import matplotlib.pyplot as plt
    from typing import Dict, List, Optional
    from langchain_openai import ChatOpenAI
    from langgraph.graph import StateGraph
    from pydantic import BaseModel
    import requests
    print("Basic imports successful!")
    
    # Check for project-specific modules
    import backend.research.core
    import backend.research.agents
    import backend.research.data_modules
    import backend.research.orchestrator
    print("Project-specific imports successful!")
    
    print("All dependencies are properly installed!")
except ImportError as e:
    print(f"Import error: {e}")
    print("Please check that all dependencies are properly installed.")
EOF

echo "Running dependency check..."
python dependency_test.py

echo "Setup complete! You can now run the application with: python -m uvicorn main:app --reload" 