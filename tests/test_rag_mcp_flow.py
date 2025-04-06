"""
Test script for the RAG > MCP flow in XplainCrypto.
This script tests the complete flow from query to report generation,
ensuring all components work together properly.
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("xplaincrypto_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("xplaincrypto_test")

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import components
from backend.orchestration.mcp.initialize_endpoints import initialize_pinecone_endpoints
from backend.orchestration.workflow_manager import WorkflowManagerWithMCP
from backend.report.report_generator import ReportGenerator
from backend.config.report_config import get_report_config

# Load environment variables
load_dotenv()

async def test_rag_mcp_flow(project_name: str = "Ondo Finance"):
    """
    Test the complete RAG > MCP flow from query to report generation.
    
    Args:
        project_name: Name of the crypto project to research
    """
    logger.info(f"Starting RAG > MCP flow test for {project_name}")
    
    # Step 1: Initialize Pinecone with MCP endpoints
    logger.info("Step 1: Initializing Pinecone with MCP endpoints")
    endpoints_initialized = await initialize_pinecone_endpoints()
    if not endpoints_initialized:
        logger.error("Failed to initialize Pinecone with MCP endpoints")
        return False
    logger.info("Pinecone endpoints initialized successfully")
    
    # Step 2: Initialize workflow manager
    logger.info("Step 2: Initializing workflow manager")
    workflow_manager = WorkflowManagerWithMCP()
    await workflow_manager.initialize()
    logger.info("Workflow manager initialized successfully")
    
    # Step 3: Execute research workflow
    logger.info("Step 3: Executing research workflow")
    query = f"Provide comprehensive research about {project_name} cryptocurrency"
    context = {"project_name": project_name}
    
    try:
        research_result = await workflow_manager.execute_research_workflow(query, context)
        logger.info("Research workflow executed successfully")
        
        # Save research result for debugging
        with open(f"{project_name.lower().replace(' ', '_')}_research_result.json", "w") as f:
            json.dump(research_result, f, indent=2)
    except Exception as e:
        logger.error(f"Error executing research workflow: {str(e)}")
        return False
    
    # Step 4: Generate report
    logger.info("Step 4: Generating report")
    try:
        # Get report configuration
        report_config = get_report_config()
        
        # Initialize report generator
        report_generator = ReportGenerator(theme="dark", output_dir="reports")
        
        # Generate report
        report_path = report_generator.generate_report(research_result, report_config)
        logger.info(f"Report generated successfully: {report_path}")
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return False
    
    logger.info("RAG > MCP flow test completed successfully")
    return True

if __name__ == "__main__":
    # Get project name from command line argument or use default
    project_name = sys.argv[1] if len(sys.argv) > 1 else "Ondo Finance"
    
    # Run the test
    asyncio.run(test_rag_mcp_flow(project_name))
