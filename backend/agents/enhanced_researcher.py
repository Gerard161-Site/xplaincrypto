import logging
import json
import os
import time
import hashlib
from typing import List, Dict, Any, Optional
from backend.state import ResearchState
from langchain_openai import ChatOpenAI
from backend.research.orchestrator import ResearchOrchestrator

# Cache directory for storing research results
CACHE_DIR = os.path.join("docs", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def enhanced_researcher(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config=None) -> ResearchState:
    """
    Advanced researcher agent that uses the hierarchical research approach with specialized agents
    and real-time data integration.
    """
    logger.info(f"Starting enhanced research for {state.project_name}")
    state.update_progress(f"Initiating enhanced research on {state.project_name}...")
    
    # Check if we have cached results for this project
    cache_file = get_cache_filename(state.project_name)
    if os.path.exists(cache_file):
        try:
            logger.info(f"Found cached research for {state.project_name}")
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            
            # Check if cache is recent (less than 24 hours old)
            cache_timestamp = cached_data.get('timestamp', 0)
            if time.time() - cache_timestamp < 86400:  # 24 hours
                logger.info(f"Using cached research for {state.project_name} (less than 24h old)")
                state.research_summary = cached_data.get('research_summary', '')
                state.references = cached_data.get('references', [])
                state.tokenomics = cached_data.get('tokenomics', '')
                state.price_analysis = cached_data.get('price_analysis', '')
                state.governance = cached_data.get('governance', '')
                state.research_data = cached_data.get('research_data', {})
                state.update_progress(f"Loaded cached research for {state.project_name}")
                return state
            else:
                logger.info(f"Cached research for {state.project_name} is outdated, refreshing")
        except Exception as e:
            logger.warning(f"Error reading cache for {state.project_name}: {e}")
    
    # Load report configuration
    try:
        with open("backend/config/report_config.json", "r") as f:
            report_config = json.load(f)
        logger.info("Loaded report configuration from file")
        state.report_config = report_config
    except Exception as e:
        logger.warning(f"Could not load report configuration: {str(e)}")
        report_config = {}
    
    # Start the research workflow
    logger.info(f"Starting research workflow for {state.project_name}")
    state.update_progress(f"Researching {state.project_name}...")
    
    # Generate a concise research tree with fewer, more targeted questions
    # This reduces API calls while still covering key aspects
    research_questions = generate_research_tree(state.project_name, llm, logger)
    
    # Batch research questions to reduce API calls
    # Instead of asking each question individually, we'll group them
    batch_size = 3  # Process questions in batches
    batches = [research_questions[i:i+batch_size] for i in range(0, len(research_questions), batch_size)]
    
    research_results = []
    for batch in batches:
        batch_prompt = f"Research the following questions about {state.project_name} cryptocurrency:\n\n"
        for i, question in enumerate(batch, 1):
            batch_prompt += f"{i}. {question}\n"
        batch_prompt += f"\nProvide concise but comprehensive answers to each question, with clear section separations."
        
        try:
            batch_response = llm.invoke(batch_prompt).content
            research_results.append(batch_response)
        except Exception as e:
            logger.error(f"Error researching batch of questions: {e}")
            # Add placeholder for failed batch
            research_results.append(f"Unable to research: {', '.join(batch)}")
    
    # Process and structure the research results into required sections
    structured_data = structure_research_data(state.project_name, research_results, logger)
    
    # Update state with structured data
    state.research_summary = structured_data.get('research_summary', f"Analysis of {state.project_name} cryptocurrency.")
    state.references = structured_data.get('references', [])
    state.tokenomics = structured_data.get('tokenomics', f"Tokenomics information for {state.project_name}.")
    state.price_analysis = structured_data.get('price_analysis', f"Price analysis for {state.project_name}.\n60-Day Change: 0%")
    state.governance = structured_data.get('governance', f"Governance structure of {state.project_name}.")
    state.research_data = structured_data.get('research_data', {})
    
    # Cache the research results
    try:
        cache_data = {
            'timestamp': time.time(),
            'research_summary': state.research_summary,
            'references': state.references,
            'tokenomics': state.tokenomics,
            'price_analysis': state.price_analysis,
            'governance': state.governance,
            'research_data': state.research_data
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        logger.info(f"Cached research results for {state.project_name}")
    except Exception as e:
        logger.warning(f"Error caching research results: {e}")
    
    state.update_progress(f"Completed research for {state.project_name}")
    return state

def get_cache_filename(project_name: str) -> str:
    """Generate a standardized cache filename for a project."""
    # Create a hash of the project name to ensure filename compatibility
    project_hash = hashlib.md5(project_name.lower().encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{project_hash}_research.json")

def generate_research_tree(project_name: str, llm, logger: logging.Logger) -> List[str]:
    """
    Generate an optimized set of research questions.
    Reduces the number of questions while ensuring comprehensive coverage.
    """
    logger.info(f"Generating research tree for: {project_name}")
    
    # Use a single API call to generate all research questions together
    # This is much more efficient than multiple separate calls
    prompt = f"""
    Generate 10 comprehensive research questions about {project_name} cryptocurrency covering:
    1. Basic information and purpose
    2. Tokenomics and supply metrics
    3. Market position and competition
    4. Technology and architecture
    5. Governance and community
    6. Use cases and adoption
    7. Partnerships and ecosystem
    8. Risk factors and challenges
    9. Recent developments and roadmap
    10. Price performance and trends
    
    Make each question specific and information-rich. Format as a numbered list.
    """
    
    try:
        response = llm.invoke(prompt).content
        questions = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line[0] == '•' or line.startswith('-')):
                # Remove numbering/bullets and clean up
                cleaned_line = line.lstrip('0123456789.-• \t')
                if cleaned_line:
                    questions.append(cleaned_line)
        
        # Ensure we have at least some questions
        if not questions:
            logger.warning("Failed to extract questions from response, using defaults")
            questions = [
                f"What is {project_name} cryptocurrency and what problem does it solve?",
                f"What are the tokenomics and supply metrics of {project_name}?",
                f"How does {project_name} compare to its main competitors?",
                f"What is the technology behind {project_name} and how does it work?",
                f"What are the recent price trends for {project_name}?"
            ]
        
        logger.info(f"Generated {len(questions)} research questions")
        return questions
    except Exception as e:
        logger.error(f"Error generating research tree: {e}")
        # Return default questions as fallback
        return [
            f"What is {project_name} cryptocurrency and what problem does it solve?",
            f"What are the tokenomics and supply metrics of {project_name}?",
            f"How does {project_name} compare to its main competitors?",
            f"What is the technology behind {project_name} and how does it work?",
            f"What are the recent price trends for {project_name}?"
        ]

def structure_research_data(project_name: str, research_results: List[str], logger: logging.Logger) -> Dict[str, Any]:
    """
    Process and structure the research results into required sections.
    Uses a single consolidated approach to reduce processing overhead.
    """
    # Combine all research results 
    combined_research = "\n\n".join(research_results)
    
    # Process research data to extract and structure information
    structured_data = {
        'research_summary': f"Analysis of {project_name} cryptocurrency.",
        'key_features': f"Key features of {project_name}.",
        'tokenomics': f"Tokenomics information for {project_name}.\n60-Day Change: 0%",
        'price_analysis': f"Price analysis for {project_name}.\n60-Day Change: 0%",
        'governance': f"Governance structure of {project_name}.",
        'research_data': {},
        'references': []
    }
    
    # Extract key sections from combined research
    if "tokenomics" in combined_research.lower():
        tokenomics_section = extract_section(combined_research, ["tokenomics", "token supply", "token distribution"])
        if tokenomics_section:
            structured_data['tokenomics'] = tokenomics_section
            
            # Extract token distribution data for visualization
            token_distribution = extract_token_distribution(tokenomics_section)
            if token_distribution:
                structured_data['research_data']['token_distribution'] = token_distribution
    
    if "price" in combined_research.lower() or "market" in combined_research.lower():
        price_section = extract_section(combined_research, ["price", "market", "trading", "value"])
        if price_section:
            # Add a default 60-day change if not present
            if "60-Day Change:" not in price_section:
                price_section += "\n60-Day Change: Varies with market conditions"
            structured_data['price_analysis'] = price_section
    
    if "governance" in combined_research.lower() or "community" in combined_research.lower():
        governance_section = extract_section(combined_research, ["governance", "community", "voting", "dao"])
        if governance_section:
            structured_data['governance'] = governance_section
    
    # Generate comprehensive research summary
    if combined_research:
        summary_sections = []
        if "what is" in combined_research.lower() or "purpose" in combined_research.lower():
            intro = extract_section(combined_research, ["what is", "purpose", "introduction", "overview"])
            if intro:
                summary_sections.append(intro)
        
        if "technology" in combined_research.lower() or "architecture" in combined_research.lower():
            tech = extract_section(combined_research, ["technology", "architecture", "technical", "blockchain"])
            if tech:
                summary_sections.append(tech)
                structured_data['key_features'] = tech
        
        if summary_sections:
            structured_data['research_summary'] = "\n\n".join(summary_sections)
        else:
            # Fallback: use the first 500 characters as a summary
            structured_data['research_summary'] = combined_research[:500].strip() + "..."
    
    # Extract URLs for references
    urls = extract_urls(combined_research)
    structured_data['references'] = [{"url": url, "title": f"Reference {i+1}"} for i, url in enumerate(urls)]
    
    return structured_data

def extract_section(text: str, keywords: List[str]) -> str:
    """Extract a section from text based on keywords."""
    # Convert to lowercase for case-insensitive searching
    text_lower = text.lower()
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in text_lower:
            # Find the start of the section
            start_pos = text_lower.find(keyword_lower)
            
            # Look for the end of the section (next section header or end of text)
            end_pos = len(text)
            for end_marker in ["#", "==", "\n\n"]:
                next_marker = text.find(end_marker, start_pos + len(keyword))
                if next_marker != -1 and next_marker < end_pos:
                    end_pos = next_marker
            
            # Extract the section
            section = text[start_pos:end_pos].strip()
            
            # If it's too short, try another approach
            if len(section) < 50:
                # Get the paragraph containing the keyword
                paragraphs = text.split("\n\n")
                for para in paragraphs:
                    if keyword_lower in para.lower():
                        return para.strip()
            
            return section
    
    return ""

def extract_token_distribution(tokenomics_text: str) -> List[Dict[str, Any]]:
    """Extract token distribution data for visualization."""
    distribution = []
    
    # Look for common distribution patterns
    lines = tokenomics_text.split("\n")
    for line in lines:
        # Match patterns like "Team: 20%" or "Community (30%)"
        if ":" in line and ("%" in line or "percent" in line.lower()):
            parts = line.split(":")
            if len(parts) == 2:
                category = parts[0].strip()
                value_part = parts[1].strip()
                
                # Extract percentage value
                import re
                percentage_match = re.search(r'(\d+(\.\d+)?)%', value_part)
                if percentage_match:
                    percentage = float(percentage_match.group(1))
                    distribution.append({"name": category, "value": percentage})
    
    return distribution

def extract_urls(text: str) -> List[str]:
    """Extract URLs from text."""
    import re
    url_pattern = r'https?://[^\s)>]+'
    return list(set(re.findall(url_pattern, text)))

def transfer_data(research_state: ResearchState, state: ResearchState, logger: logging.Logger):
    """Transfer data from the research state to our state."""
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

def handle_exception(state: ResearchState, logger: logging.Logger, e: Exception):
    """Handle exceptions and update the state accordingly."""
    logger.error(f"Enhanced research failed: {str(e)}", exc_info=True)
    state.update_progress(f"Research error: {str(e)}")

def log_completion(state: ResearchState, logger: logging.Logger):
    """Log the completion of the research process."""
    logger.info(f"Enhanced research completed for {state.project_name}") 