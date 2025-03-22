import logging
import json
import os
from backend.state import ResearchState
from langchain_openai import ChatOpenAI
from backend.research.orchestrator import ResearchOrchestrator

def enhanced_researcher(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config=None) -> ResearchState:
    """
    Advanced researcher agent that uses the hierarchical research approach with specialized agents
    and real-time data integration.
    """
    logger.info(f"Starting enhanced research for {state.project_name}")
    state.update_progress(f"Initiating enhanced research on {state.project_name}...")
    
    # Create the research orchestrator
    try:
        # Determine config path (use provided config path or default)
        config_path = config.get("report_config_path") if config and "report_config_path" in config else None
        
        # Create orchestrator with appropriate config
        orchestrator = ResearchOrchestrator(llm, logger, config_path)
        
        # Execute the full research workflow
        # Note: The orchestrator uses its own ResearchState, which we extract data from
        research_state = orchestrator.research(state.project_name)
        
        # Transfer data from the research state to our state
        if hasattr(research_state, 'research_summary') and research_state.research_summary:
            state.research_summary = research_state.research_summary
        
        if hasattr(research_state, 'references') and research_state.references:
            state.references = research_state.references
        
        if hasattr(research_state, 'tokenomics') and research_state.tokenomics:
            state.tokenomics = research_state.tokenomics
        
        if hasattr(research_state, 'price_analysis') and research_state.price_analysis:
            state.price_analysis = research_state.price_analysis
        
        # Transfer data for visualization agent
        if hasattr(research_state, 'coingecko_data'):
            state.coingecko_data = research_state.coingecko_data
        
        if hasattr(research_state, 'coinmarketcap_data'):
            state.coinmarketcap_data = research_state.coinmarketcap_data
        
        if hasattr(research_state, 'defillama_data'):
            state.defillama_data = research_state.defillama_data
        
        if hasattr(research_state, 'research_data'):
            state.research_data = research_state.research_data
        
        # Also transfer report config for other agents to use
        if hasattr(research_state, 'report_config'):
            state.report_config = research_state.report_config
        
        if hasattr(research_state, 'errors') and research_state.errors:
            logger.warning(f"Research completed with {len(research_state.errors)} errors")
            for error in research_state.errors:
                logger.warning(f"Research error: {error}")
        
        state.update_progress("Enhanced research completed successfully")
    except Exception as e:
        logger.error(f"Enhanced research failed: {str(e)}", exc_info=True)
        state.update_progress(f"Research error: {str(e)}")
    
    logger.info(f"Enhanced research completed for {state.project_name}")
    return state 