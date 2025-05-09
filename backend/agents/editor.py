# backend/agents/editor.py
from langchain_openai import ChatOpenAI
import logging
import re
from backend.state import ResearchState
from backend.utils.inference import openai_retry_decorator
from backend.utils.state_manager import StateManager
from typing import Dict
from datetime import datetime

@openai_retry_decorator
async def editor(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict:
    """Edit the report draft to ensure clarity, depth, and investment-grade quality."""
    try:
        logger.info("Editor agent starting")
        
        # Initialize StateManager for consistent state access
        state_manager = StateManager(logger=logger)
        
        # Get project name using StateManager
        project_name = state_manager.get_project_name(state)
        logger.info(f"Editor agent processing {project_name}")
        
        # Get draft from state using StateManager
        draft = state_manager.get_draft(state)
        if not draft:
            logger.error("No draft found in state")
            # Instead of raising an error, create a minimal draft
            draft = f"# {project_name} Research Report\n\n"
            draft += f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            draft += "## Executive Summary\n\n"
            draft += f"{project_name} is a cryptocurrency project. Due to technical limitations, a full analysis could not be generated.\n\n"
            draft += "## Tokenomics\n\n"
            draft += f"Tokenomics data for {project_name} is not available in this report.\n\n"
            draft += "## Disclaimer\n\nThis report was generated with limited data. Please consult additional sources for investment decisions."
            
            # Update state with the minimal draft using StateManager
            state = state_manager.update_draft(state, draft)
            state = state_manager.update_edited_draft(state, draft)
            state = state_manager.update_final_report(state, draft)
            
            logger.info(f"Created minimal draft with {len(draft.split())} words")
            return state

        logger.info(f"Performing comprehensive editing for {project_name}")
        
        # Update progress using StateManager
        state = state_manager.update_progress(state, f"Editing draft for {project_name}...")

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
        structured_response = await llm.ainvoke(structure_prompt)
        structured_draft = structured_response.content

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
        polished_response = await llm.ainvoke(quality_prompt)
        polished_draft = polished_response.content

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
            final_response = await llm.ainvoke(final_prompt)
            final_draft = final_response.content
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

{base_instructions}

Focus on:
1. Ensuring this section has AT LEAST {min_words} words of substantive content
2. Maintaining the section title exactly as is
3. Improving clarity, precision, and professional tone
4. Ensuring balanced analysis with both strengths and risks
5. Adding depth where content is thin without fabricating specific data
6. Ensuring consistency with other sections

{content}
"""
                
                try:
                    edited_response = await llm.ainvoke(section_prompt)
                    edited_sections[title] = edited_response.content
                    logger.info(f"Successfully edited section '{title}': {len(edited_response.content.split())} words")
                except Exception as e:
                    logger.error(f"Error editing section '{title}': {str(e)}")
                    edited_sections[title] = content
            
            # Combine edited sections in original order
            final_draft = ""
            for level, title in headers:
                if title in edited_sections:
                    final_draft += edited_sections[title] + "\n\n"
        
        # Add disclaimer if missing
        if "Disclaimer" not in final_draft:
            final_draft += "\n\n## Disclaimer\n\n"
            final_draft += "This research report is for informational purposes only. It does not constitute investment advice, "
            final_draft += "nor is it an offer to buy or sell any cryptocurrency or financial product. "
            final_draft += "The information contained in this report has been compiled from sources believed to be reliable, "
            final_draft += "but no representation or warranty, express or implied, is made as to its accuracy, completeness or correctness. "
            final_draft += "All opinions and estimates are given as of the date hereof and are subject to change without notice.\n\n"
            final_draft += f"*Generated on {datetime.now().strftime('%Y-%m-%d')}*\n\n"
        
        # Add generation date if missing
        if "*Generated on" not in final_draft:
            final_draft += f"\n\n*Generated on {datetime.now().strftime('%Y-%m-%d')}*\n\n"
        
        # Log summary of changes
        edited_words = len(final_draft.split())
        logger.info(f"Editing completed: {original_words} words → {edited_words} words ({edited_words - original_words:+d} words)")
        
        # Save edited content to state using StateManager
        state = state_manager.update_edited_draft(state, final_draft)
        
        # Save emergency backup of edited content
        import os
        os.makedirs(f"docs/{project_name}", exist_ok=True)
        backup_path = f"docs/{project_name}/edited_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        try:
            with open(backup_path, "w") as f:
                f.write(final_draft)
            logger.info(f"Saved emergency backup of edited content to {backup_path}")
        except Exception as e:
            logger.warning(f"Could not save backup of edited content: {str(e)}")
        
        # Update progress using StateManager
        state = state_manager.update_progress(state, "Comprehensive editing completed.")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in editor: {str(e)}", exc_info=True)
        return state

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