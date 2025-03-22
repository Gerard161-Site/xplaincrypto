import logging
from backend.state import ResearchState
from langchain_openai import ChatOpenAI

def reviewer(state: ResearchState, llm: ChatOpenAI, logger: logging.Logger, config=None) -> ResearchState:
    """
    Reviews the report content for quality and completeness
    """
    logger.info("Reviewing report quality for " + state.project_name)
    state.update_progress("Performing quality review for " + state.project_name + "...")
    
    # Extract sections from the draft
    sections = extract_sections(state.draft)
    
    # Review each section
    for section_name, section_content in sections.items():
        logger.info("Reviewing section: " + section_name)
        
        # Generate review criteria based on section type
        review_criteria = get_review_criteria(section_name)
        
        # Review the section
        review_prompt = (
            "Review this " + section_name + " section for a cryptocurrency report on " + state.project_name + ":\n\n" +
            section_content + "\n\n" +
            "Criteria to evaluate:\n" +
            review_criteria + "\n\n" +
            "Are there gaps, inaccuracies, or missing information? \n" +
            "Is it sufficiently detailed and comprehensive?\n" +
            "Does it meet all the criteria above?\n\n" +
            "Provide:\n" +
            "1. A score from 1-10\n" +
            "2. Critical gaps or missing information\n" +
            "3. Specific suggestions for improvement"
        )
        
        try:
            review = llm.invoke(review_prompt).content
            
            # Extract score to determine if enhancement is needed
            score = extract_score(review)
            
            # If score is below threshold, enhance the section
            if score < 7:
                logger.info("Section " + section_name + " needs improvement (score: " + str(score) + ")")
                improved_section = enhance_section(state.project_name, section_name, section_content, review, llm)
                
                # Replace the section in the draft
                state.draft = replace_section(state.draft, section_name, improved_section)
        except Exception as e:
            logger.error("Error reviewing section " + section_name + ": " + str(e))
    
    logger.info("Quality review completed for " + state.project_name)
    state.update_progress("Quality review completed.")
    return state

def extract_sections(draft):
    """Extract sections from the draft"""
    import re
    
    sections = {}
    # Match section headers (## Section Title) and capture content until next section
    pattern = r'##\s+([^\n]+)\n(.*?)(?=##\s+|$)'
    matches = re.findall(pattern, draft, re.DOTALL)
    
    for title, content in matches:
        sections[title.strip()] = content.strip()
    
    return sections

def get_review_criteria(section_name):
    """Generate review criteria based on section type"""
    section_name = section_name.lower()
    
    if "introduction" in section_name:
        return """
        - Clearly explains what the project is
        - Covers when it was launched
        - Describes its primary purpose
        - Places it in context of the crypto ecosystem
        """
    elif "tokenomics" in section_name:
        return """
        - Includes token supply information (total, circulating)
        - Describes token utility and use cases
        - Explains token distribution model
        - Covers economic mechanisms (inflation/deflation, staking, etc.)
        - Includes relevant metrics with actual numbers
        """
    elif "feature" in section_name or "scalability" in section_name:
        return """
        - Explains technical architecture
        - Describes specific features with details
        - Compares capabilities to competitors
        - Provides concrete examples or metrics
        - Addresses technical limitations honestly
        """
    # Add more criteria for other section types
    else:
        return """
        - Provides comprehensive information
        - Includes specific details and metrics
        - Covers both positive and negative aspects
        - Connects information to the broader context
        """

def extract_score(review):
    """Extract numerical score from review text"""
    import re
    
    # Look for patterns like "score: 7/10" or "score: 7" or "7/10"
    score_patterns = [
        r'score:?\s*(\d+)(?:/10)?',
        r'(\d+)/10'
    ]
    
    for pattern in score_patterns:
        match = re.search(pattern, review.lower())
        if match:
            return int(match.group(1))
    
    # Default score if not found
    return 5

def enhance_section(project_name, section_name, section_content, review, llm):
    """Enhance a section based on review feedback"""
    
    enhance_prompt = (
        "The following " + section_name + " section for " + project_name + " needs improvement:\n\n" +
        section_content + "\n\n" +
        "Review feedback:\n" +
        review + "\n\n" +
        "Please rewrite this section to address all the issues in the review feedback.\n" +
        "Make it more comprehensive, detailed, and accurate. Include specific metrics,\n" +
        "examples, and comparisons where appropriate.\n\n" +
        "Maintain the original section heading format and structure, but enhance the content."
    )
    
    try:
        improved_section = llm.invoke(enhance_prompt).content
        return improved_section
    except Exception as e:
        return section_content  # Return original if enhancement fails

def replace_section(draft, section_name, new_content):
    """Replace a section in the draft with new content"""
    import re
    
    # Pattern to match the section and its content
    # Use raw string (r prefix) to avoid backslash escaping issues
    pattern = r'(##\s+' + re.escape(section_name) + r'\n).*?((?=##\s+)|$)'
    
    # Replace with new content
    updated_draft = re.sub(pattern, r'\1' + new_content + r'\n\n', draft, flags=re.DOTALL)
    
    return updated_draft
