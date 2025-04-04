# backend/agents/editor.py
from langchain_openai import ChatOpenAI
import logging
import re
from backend.state import ResearchState
from backend.utils.inference import openai_retry_decorator
from typing import Dict

@openai_retry_decorator
def editor(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    """Edit the report draft to ensure clarity, depth, and investment-grade quality."""
    try:
        logger.info("Editor agent starting")
        
        # Get project name
        project_name = state.get("project_name", "Unknown Project")
        
        # Get draft from state
        draft = state.get("draft", "")
        if not draft:
            logger.error("No draft found in state")
            raise ValueError("Draft missing from state")

        logger.info(f"Performing comprehensive editing for {project_name}")
        
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Editing draft for {project_name}...")
        else:
            state["progress"] = f"Editing draft for {project_name}..."

        # Fix initial formatting
        fixed_draft = fix_section_formatting(draft)
        original_words = len(fixed_draft.split())
        
        base_instructions = """
IMPORTANT INSTRUCTIONS:
1. Maintain all exact numerical values (prices, market cap, trading volume, etc.) throughout the document.
2. DO NOT replace specific figures with placeholders like '$X' or 'Y tokens'.
3. DO NOT attempt to add or reference tables or images directly in the text.
4. Focus on improving the quality of the existing text content.
5. Avoid repetition of information across sections—each section should have a unique focus as defined in the report configuration.
6. Ensure the report maintains a professional, investment-grade tone suitable for crypto investors and analysts.
7. CRITICAL: Every section MUST meet its minimum word count (typically 400-700 words per section).
8. NEVER change section titles - keep them exactly as they appear in the original document.
9. Target a total word count of 6000-7000 words, ensuring each section is detailed.
"""

        # Stage 1: Structure and Expand
        structure_prompt = f"""Enhance the structure and content depth of this crypto research report on {project_name}.
        
{base_instructions}

IMPORTANT FORMATTING AND WORD COUNT REQUIREMENTS:
1. Always use single hashtag (# Section Title) for main section titles
2. Always use double hashtag (## Subsection Title) for subsections
3. Never use ### or more for any headings
4. Every section must contain AT MINIMUM the following word counts:
   - Executive Summary: 200+ words
   - Introduction: 250+ words
   - Tokenomics and Distribution: 400+ words
   - Market Analysis: 600+ words
   - Technical Analysis: 500+ words
   - Developer Tools and User Experience: 400+ words
   - Security: 400+ words
   - Liquidity and Adoption Metrics: 500+ words
   - Governance and Community: 400+ words
   - Ecosystem and Partnerships: 400+ words
   - Risks and Opportunities: 450+ words
   - Team and Development Activity: 400+ words
   - Conclusion: 300+ words

Focus on:
1. Ensuring all MAIN section headings are properly formatted with SINGLE hashtag (# Section Title) and never changed.
2. Ensuring all SUBSECTION headings use DOUBLE hashtag (## Subsection Title).
3. Organizing content logically within each section, using subheadings where appropriate for clarity.
4. Expanding each section to meet its minimum word count with detailed analysis, preserving all existing facts and adding depth where possible.
5. Ensuring each section focuses on its unique scope, avoiding overlap with other sections.
6. Maintaining correct markdown formatting and adding smooth transitions between sections.

{fixed_draft}
        """
        
        logger.debug("Enhancing report structure and expanding content")
        structured_draft = llm.invoke(structure_prompt).content

        # Stage 2: Improve Quality and Consistency
        quality_prompt = f"""Polish this {project_name} research report for professional quality and factual consistency.
        
{base_instructions}
        
Focus on:
1. Ensuring a professional, objective tone suitable for crypto investors, avoiding speculative language unless supported by data.
2. Enhancing clarity and readability with precise wording, defining terms where needed.
3. Ensuring all numerical data (e.g., price, market cap, supply, TVL) is consistent across sections—cross-check values and correct discrepancies.
4. Verifying tokenomics figures (e.g., total supply, circulating supply) are uniform.
5. Expanding content to meet the 6000-7000 word target, adding depth where sections are below their minimum word count.
6. Using consistent tense (present unless historical) and third-person perspective.

{structured_draft}
        """
        
        logger.debug("Improving quality and ensuring consistency")
        polished_draft = llm.invoke(quality_prompt).content

        # Stage 3: Final Polish and Balance
        final_prompt = f"""Perform a final review and polish of this {project_name} cryptocurrency research report to ensure investment-grade quality.
        
{base_instructions}
        
CRITICAL: Any section containing placeholder text like "Data unavailable" or with fewer than the minimum required words MUST be replaced with substantive content. These sections need special attention:
- Ecosystem and Partnerships (need 400+ words)
- Governance and Community (need 400+ words)
- Risks and Opportunities (need 450+ words)
- Team and Development Activity (need 400+ words)
- Developer Tools and User Experience (need 400+ words)

Focus on:
1. Ensuring ALL sections have their required minimum word count - especially those with placeholder text.
2. Creating detailed content for any section with placeholder text based on general knowledge of similar cryptocurrency projects.
3. Ensuring an objective, balanced perspective—highlight strengths and risks without bias.
4. Verifying investment-relevant information is clear and actionable.
5. Emphasizing risk factors with clear investor implications, ensuring they are not downplayed.
6. Ensuring conclusions follow logically from evidence, avoiding unsupported claims.
7. Ensuring the Executive Summary reflects the full report with high-level insights.
8. Polishing language for clarity, impact, and professionalism.

{polished_draft}
        """
        
        logger.debug("Performing final polish and quality check")
        
        # Split draft into sections to avoid context limit issues
        import re
        
        # Extract sections
        sections = {}
        headers = re.findall(r'^(#+)\s+(.*?)$', polished_draft, re.MULTILINE)
        
        if not headers:
            # No sections found, treat as one document
            final_draft = llm.invoke(final_prompt).content
        else:
            # Process each section individually
            logger.info(f"Processing {len(headers)} sections separately to avoid context limit issues")
            
            # Extract content for each section
            for i, (level, title) in enumerate(headers):
                if i < len(headers) - 1:
                    # Find content between this header and next
                    pattern = fr'^{re.escape(level)}\s+{re.escape(title)}$.*?(?=^{re.escape(headers[i+1][0])}\s+{re.escape(headers[i+1][1])}$)'
                    content = re.search(pattern, polished_draft, re.MULTILINE | re.DOTALL)
                    if content:
                        sections[title] = content.group(0).strip()
                else:
                    # Last section to end of doc
                    pattern = fr'^{re.escape(level)}\s+{re.escape(title)}$.*'
                    content = re.search(pattern, polished_draft, re.MULTILINE | re.DOTALL)
                    if content:
                        sections[title] = content.group(0).strip()
            
            # Process each section with specific requirements
            edited_sections = {}
            for title, content in sections.items():
                # Skip very small sections
                if len(content.split()) < 30:
                    edited_sections[title] = content
                    continue
                
                # Prepare section-specific prompt
                min_words = 400
                
                # Set specific length requirements for known sections
                if "Ecosystem" in title or "Governance" in title or "Developer" in title or "Team" in title:
                    min_words = 400
                elif "Risks" in title:
                    min_words = 450
                elif "Executive" in title or "Conclusion" in title:
                    min_words = 250
                    
                section_prompt = f"""Polish and improve this section on '{title}' for a {project_name} cryptocurrency research report:

{content}

This section should be at least {min_words} words and meet investment-grade quality standards.

{base_instructions}

If this section contains placeholder text like "Data unavailable" or is shorter than {min_words} words, 
replace it with substantive, detailed content based on general knowledge of similar cryptocurrency projects.

Return ONLY the improved section content in markdown format with the same heading level.
"""
                try:
                    edited_content = llm.invoke(section_prompt).content
                    edited_sections[title] = edited_content
                    logger.info(f"Successfully edited section '{title}': {len(edited_content.split())} words")
                except Exception as e:
                    logger.error(f"Error editing section '{title}': {str(e)}")
                    edited_sections[title] = content
            
            # Combine sections in original order
            final_draft = "\n\n".join([edited_sections.get(title, sections[title]) for title in [h[1] for h in headers]])
            
        # Save to both draft and final_report in the state dictionary
        state["draft"] = final_draft
        state["edited_draft"] = final_draft  # Explicitly save to edited_draft key
        state["final_report"] = final_draft
        
        edited_words = len(final_draft.split())
        word_diff = edited_words - original_words
        
        # Add verification logging
        logger.info(f"Edited draft content updated - Preview: {final_draft[:300]}...")
        logger.info(f"Section headers: {re.findall(r'^# (.+)', final_draft, re.MULTILINE)[:10]}")
        logger.info(f"Stored edited content in state['draft'], state['edited_draft'], and state['final_report'] keys")
        
        # Save emergency backup copy to disk
        try:
            import os
            from datetime import datetime
            backup_dir = os.path.join("docs", project_name.lower().replace(" ", "_"))
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"edited_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(final_draft)
            logger.info(f"Saved emergency backup of edited content to {backup_path}")
        except Exception as e:
            logger.warning(f"Could not save content backup file: {str(e)}")
        
        logger.info(f"Editing completed: {original_words} words → {edited_words} words ({word_diff:+d} words)")
        
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress("Comprehensive editing completed.")
        else:
            state["progress"] = "Comprehensive editing completed."
            
        return state
    except Exception as e:
        logger.error(f"Editor agent encountered an error: {str(e)}", exc_info=True)
        raise

def fix_section_formatting(draft):
    """Fix common formatting issues with section headers."""
    # First, standardize all section headings
    # Convert ## Section to # Section for main sections
    fixed_draft = re.sub(r'^## ([^#\n]+)', r'# \1', draft, flags=re.MULTILINE)
    
    # Now fix remaining formatting issues
    fixed_draft = re.sub(r'^# ([^#\n]+)', r'# \1', fixed_draft, flags=re.MULTILINE)
    fixed_draft = re.sub(r'^##([^#\n]+)', r'## \1', fixed_draft, flags=re.MULTILINE)
    fixed_draft = re.sub(r'^###([^#\n]+)', r'### \1', fixed_draft, flags=re.MULTILINE)
    fixed_draft = re.sub(r'([^\n])\n(#+ )', r'\1\n\n\2', fixed_draft)
    fixed_draft = re.sub(r'^(\s*)-([^\s])', r'\1- \2', fixed_draft, flags=re.MULTILINE)
    fixed_draft = re.sub(r'^(#+ [^\n]+)\n([^#\n])', r'\1\n\n\2', fixed_draft, flags=re.MULTILINE)
    
    # Add extra logging to track section format
    section_headers = re.findall(r'^# (.+)$', fixed_draft, re.MULTILINE)
    if section_headers:
        print(f"Standardized {len(section_headers)} main section headers to # format")
    
    return fixed_draft