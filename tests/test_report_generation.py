#!/usr/bin/env python3
"""
Test script for generating an enhanced cryptocurrency report
"""

import os
import logging
import sys
from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Report_Test")

def main():
    """Test the enhanced report generation"""
    try:
        # Check if API key is available
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            return 1
        
        # Import research components
        from backend.research.orchestrator import ResearchOrchestrator
        from backend.agents.publisher import publisher
        
        # Create language model
        llm = ChatOpenAI(model_name='gpt-3.5-turbo')
        logger.info("Created language model")
        
        # Choose which cryptocurrency to research
        project_name = "BTC"
        if len(sys.argv) > 1:
            project_name = sys.argv[1]
        logger.info(f"Testing report generation for {project_name}")
        
        # Create orchestrator and run research
        orchestrator = ResearchOrchestrator(llm, logger)
        logger.info("Starting research process...")
        state = orchestrator.research(project_name)
        logger.info("Research completed")
        
        # Check key state attributes
        if hasattr(state, 'enhanced_data') and state.enhanced_data:
            logger.info(f"Enhanced data included: {list(state.enhanced_data.keys())}")
        else:
            logger.warning("No enhanced data found in state")
            
        # Ensure state has project_name attribute
        if not hasattr(state, 'project_name'):
            logger.warning("Adding project_name to state")
            state.project_name = project_name
        
        # Generate PDF report
        logger.info("Generating PDF report...")
        publisher_config = {"use_report_config": True}
        final_state = publisher(state, logger, publisher_config)
        
        # Check result
        pdf_path = f"docs/{project_name}_report.pdf"
        if os.path.exists(pdf_path):
            logger.info(f"Successfully generated report at {pdf_path}")
            logger.info(f"PDF size: {os.path.getsize(pdf_path)/1024:.1f} KB")
            return 0
        else:
            logger.error(f"Failed to generate PDF at {pdf_path}")
            return 1
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 