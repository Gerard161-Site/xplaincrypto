# backend/agents/publisher.py
import logging
import os
import datetime
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from backend.state import ResearchState
from backend.utils.style_utils import StyleManager
from PIL import Image as PilImage
from backend.utils.logging_utils import log_safe  # Import from utils module
from backend.utils.inference import openai_retry_decorator  # Import the decorator for potential future use

logger = logging.getLogger(__name__)

def escape_xml(text):
    """Escape XML characters for proper rendering in ReportLab."""
    if not text:
        return ""
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&apos;'
    }
    for original, escaped in replacements.items():
        text = text.replace(original, escaped)
    return text

def add_page_number(canvas, doc):
    """Add page numbers and footer to each page."""
    page_num = canvas.getPageNumber()
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(8*inch, 0.5*inch, f"Page {page_num}")
    
    canvas.setFont("Helvetica", 8)
    canvas.setFillColorRGB(0.5, 0.5, 0.5)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    canvas.drawString(0.75*inch, 0.5*inch, f"XPlainCrypto Research Report • {today}")
    canvas.drawCentredString(4.25*inch, 0.5*inch, "www.xplaincrypto.com")

def publisher(state, llm, logger, config=None):
    """Process the report content and create a PDF."""
    try:
        logger.info("Publisher agent starting")
        
        # Get project name from state (try dict first, then attribute)
        if isinstance(state, dict):
            project_name = state.get("project_name", "Unknown Project")
            report_config = state.get("report_config", {})
        else:
            project_name = getattr(state, "project_name", "Unknown Project")
            report_config = getattr(state, "report_config", {})
        
        logger.info(f"Publisher agent processing report for project: '{project_name}'")
        
        # Update progress
        if isinstance(state, dict):
            state["progress"] = f"Publishing report for {project_name}..."
        elif hasattr(state, 'update_progress'):
            state.update_progress(f"Publishing report for {project_name}...")
        
        # CRITICAL: LOG STATE CONTENT
        draft_sources = ["draft", "edited_draft", "final_report"]
        if isinstance(state, dict):
            for source in draft_sources:
                if source in state:
                    content_length = len(state[source]) if isinstance(state[source], str) else 0
                    logger.info(f"Found state['{source}'] with {content_length} chars")
                
        # Try multiple sources for the draft content, in order of preference
        draft = None
        possible_sources = ["edited_draft", "draft", "final_report"]
        
        # First check if state is a dictionary
        if isinstance(state, dict):
            for source in possible_sources:
                if source in state and isinstance(state[source], str) and len(state[source]) > 500:
                    draft = state[source]
                    logger.info(f"Using content from state['{source}'] ({len(draft)} chars)")
                    break
                elif source in state and isinstance(state[source], str):
                    logger.warning(f"Content in state['{source}'] is too short: {len(state[source])} chars")
        
        # Then fall back to attribute access if needed
        if not draft:
            logger.info("No suitable draft found in state dict, checking attributes")
            for source in possible_sources:
                content = getattr(state, source, None) if hasattr(state, source) else None
                if content and isinstance(content, str) and len(content) > 500:  # Ensure meaningful content
                    draft = content
                    logger.info(f"Using content from state.{source} ({len(draft)} chars)")
                    break
                elif content and isinstance(content, str):
                    logger.warning(f"Content in state.{source} is too short: {len(content)} chars")
        
        # If no substantial draft was found, attempt to generate a minimal one
        if not draft or len(draft) < 500:
            logger.warning(f"No substantial draft found in state (best length: {len(draft) if draft else 0} chars)")
            
            # Emergency: try to extract any text content from state for emergency report
            emergency_content = ""
            
            if isinstance(state, dict):
                # Try to extract any text fields from the state dictionary
                for key, value in state.items():
                    if isinstance(value, str) and len(value) > 100 and key not in ["progress", "errors"]:
                        emergency_content += f"\n\n## {key.replace('_', ' ').title()}\n\n{value}"
                        logger.info(f"Added emergency content from state['{key}'] ({len(value)} chars)")
            
            # Generate a minimal draft from any available content
            minimal_draft = f"# {project_name} Research Report\n\n"
            minimal_draft += f"*Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            minimal_draft += "## Executive Summary\n\n"
            
            if emergency_content:
                minimal_draft += emergency_content
            elif isinstance(state, dict) and "research_summary" in state and state["research_summary"]:
                minimal_draft += state["research_summary"] + "\n\n"
            elif hasattr(state, "research_summary") and getattr(state, "research_summary"):
                minimal_draft += getattr(state, "research_summary") + "\n\n"
            else:
                minimal_draft += f"{project_name} is a cryptocurrency project. Due to technical limitations, a full analysis could not be generated.\n\n"
                
            # Try to add basic tokenomics info if available
            minimal_draft += "## Tokenomics\n\n"
            
            if isinstance(state, dict) and "tokenomics" in state and state["tokenomics"]:
                minimal_draft += state["tokenomics"] + "\n\n"
            elif hasattr(state, "tokenomics") and getattr(state, "tokenomics"):
                minimal_draft += getattr(state, "tokenomics") + "\n\n"
            else:
                minimal_draft += f"Tokenomics data for {project_name} is not available in this report.\n\n"
            
            # Add disclaimer
            minimal_draft += "\n\n## Disclaimer\n\nThis report was generated with limited data. Please consult additional sources for investment decisions."
            
            draft = minimal_draft
            logger.info(f"Generated minimal draft with {len(draft.split())} words")
            
            # Save the minimal draft to state to avoid future problems
            if isinstance(state, dict):
                state["draft"] = draft
                state["edited_draft"] = draft  # Also set as edited_draft for future runs
            else:
                state.draft = draft
                state.edited_draft = draft
        
        # Get visualizations
        if isinstance(state, dict):
            vis_list = state.get("visualizations", [])
        else:
            vis_list = getattr(state, "visualizations", [])
        
        # Debug log the visualizations
        logger.info(f"Found {len(vis_list)} visualizations in state")
        if vis_list:
            logger.info(f"Visualization types: {[v.get('type', 'unknown') for v in vis_list]}")
        
        # Add section mapping for visualizations
        section_vis_map = {}
        if report_config and "sections" in report_config:
            for section in report_config.get("sections", []):
                if "visualizations" in section and section["title"]:
                    section_vis_map[section["title"].lower()] = section["visualizations"]
        
        # Process visualizations to ensure they have all required fields
        processed_vis_list = []
        for vis in vis_list:
            if isinstance(vis, dict):
                # Ensure all visualizations have required fields
                vis_type = vis.get("type", "unknown")
                vis_path = vis.get("path")
                
                # Only include visualizations with valid paths
                if vis_path and os.path.exists(vis_path):
                    # Try to determine target section
                    target_section = vis.get("target_section_title")
                    
                    # If no target section, try to match based on type and section mapping
                    if not target_section:
                        for section_title, vis_types in section_vis_map.items():
                            if vis_type in vis_types:
                                target_section = section_title
                                logger.info(f"Mapped visualization '{vis_type}' to section '{section_title}'")
                                break
                    
                    processed_vis_list.append({
                        "path": vis_path,
                        "title": vis.get("title", vis_type.replace("_", " ").title()),
                        "description": vis.get("description", ""),
                        "type": vis_type,
                        "target_section_title": target_section
                    })
                    logger.info(f"Included visualization: {vis_type} -> {target_section}")
                else:
                    logger.warning(f"Skipping visualization '{vis_type}' - missing or invalid path: {vis_path}")
        
        # Use processed list for further processing
        vis_list = processed_vis_list
        logger.info(f"Processed {len(vis_list)} valid visualizations")
        
        safe_project_name = project_name.lower().replace(" ", "_")
        output_dir = os.path.join("docs", safe_project_name)
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Using output directory: {output_dir}")
        
        # Save the raw draft for debugging
        raw_draft_path = os.path.join(output_dir, f"{safe_project_name}_raw_draft.md")
        with open(raw_draft_path, "w", encoding="utf-8") as f:
            f.write(draft)
        logger.info(f"Saved raw draft to {raw_draft_path}")
        
        # Log draft stats for debugging
        lines = draft.split("\n")
        logger.info(f"Draft contains {len(lines)} lines and {len(draft.split())} words")
        
        # Log the first few non-empty lines to understand structure
        non_empty_lines = [line for line in lines[:10] if line.strip()]
        logger.info(f"Draft starts with: {non_empty_lines[:3]}")
        
        sections = []
        seen_titles = set()
        current_section = {"title": None, "content": [], "subsections": []}
        current_subsection = None
        
        # Normalize heading formats
        normalized_lines = []
        for line in lines:
            # Convert various heading formats to standard ones
            if line.startswith("###") and not line.startswith("####"):
                line = "## " + line[3:].lstrip()  # Convert ### to ##
            elif line.startswith("##") and not line.startswith("###"):
                if not line.startswith("## "):
                    line = "## " + line[2:].lstrip()  # Ensure space after ## for subsections
            elif line.startswith("#") and not line.startswith("##"):
                if not line.startswith("# "):
                    line = "# " + line[1:].lstrip()  # Ensure space after # for main headings
            normalized_lines.append(line)
        
        logger.info(f"Normalized {len(normalized_lines)} lines for processing")
        
        # Get the expected sections from report_config
        expected_section_titles = {s["title"] for s in report_config.get("sections", [])}
        expected_section_details = {s["title"]: s for s in report_config.get("sections", [])}
        logger.info(f"Expected sections from report_config: {list(expected_section_titles)}")
        
        # Parse sections from normalized content
        in_header = True  # Flag to skip title page content
        for line in normalized_lines:
            # Skip title page content (everything before first section heading)
            if in_header:
                # Check for both # and ## section markers to end the header section
                if (line.startswith("# ") and not any(x in line.lower() for x in ["research report", "generated on", "disclaimer"])) or \
                   (line.startswith("## ") and not any(x in line.lower() for x in ["research report", "generated on", "disclaimer"])):
                    in_header = False
                    logger.info(f"Found first content section: {line.strip()}")
                else:
                    continue
                    
            # Now handle both # and ## as main sections
            if line.startswith("# ") or line.startswith("## "):
                # Extract title properly from both formats
                title = line[2:].strip() if line.startswith("# ") else line[3:].strip()
                
                if title in expected_section_titles:
                    logger.info(f"Found expected section: {title}")
                else:
                    logger.warning(f"Found unexpected section: {title} (not in report_config)")
                
                if current_section["title"] and current_section["title"] not in seen_titles:
                    sections.append(current_section)
                    seen_titles.add(current_section["title"])
                current_section = {"title": title, "content": [], "subsections": []}
                current_subsection = None
            elif line.startswith("### "):
                if current_subsection:
                    current_section["subsections"].append(current_subsection)
                current_subsection = {"title": line[4:].strip(), "content": []}
                logger.info(f"Found subsection: {current_subsection['title']} in {current_section['title']}")
            elif line.strip():
                if current_subsection:
                    current_subsection["content"].append(line)
                else:
                    current_section["content"].append(line)
        
        if current_subsection:
            current_section["subsections"].append(current_subsection)
        if current_section["title"] and current_section["title"] not in seen_titles:
            sections.append(current_section)
            seen_titles.add(current_section["title"])
        
        logger.info(f"Parsed {len(sections)} unique main sections from draft")
        
        # Count word counts against min/max requirements and verify we have all required sections
        for i, section in enumerate(sections):
            section_config = expected_section_details.get(section["title"])
            if section_config:
                min_words = section_config.get("min_words", 0)
                max_words = section_config.get("max_words", 0)
                
                all_content = " ".join(section["content"])
                for subsection in section["subsections"]:
                    all_content += " " + " ".join(subsection["content"])
                
                word_count = len(all_content.split())
                
                if word_count < min_words:
                    logger.warning(f"Section '{section['title']}' has {word_count} words, below minimum requirement of {min_words}")
                elif max_words > 0 and word_count > max_words:
                    logger.warning(f"Section '{section['title']}' has {word_count} words, exceeding maximum requirement of {max_words}")
                else:
                    logger.info(f"Section '{section['title']}' has {word_count} words, within requirements ({min_words}-{max_words})")
                
                content_preview = " ".join(section["content"][:20])
                logger.info(f"Section {i+1}: {section['title']} - Content preview: {log_safe(content_preview, max_length=100)}...")
                logger.info(f"  Subsections: {[s['title'] for s in section['subsections']]}")
        
        # Create any missing sections from report_config
        missing_sections = expected_section_titles - seen_titles
        if missing_sections:
            logger.warning(f"Missing sections from draft: {missing_sections}")
            for title in missing_sections:
                section_config = expected_section_details.get(title)
                min_words = section_config.get("min_words", 200) if section_config else 200
                sections.append({
                    "title": title, 
                    "content": [f"Data unavailable for {title}. This section requires a minimum of {min_words} words."], 
                    "subsections": []
                })
                logger.info(f"Added placeholder for missing section: {title}")
        
        # Reorder sections to match report_config order
        ordered_sections = []
        for section_title in [s["title"] for s in report_config.get("sections", [])]:
            matching_sections = [s for s in sections if s["title"] == section_title]
            if matching_sections:
                ordered_sections.append(matching_sections[0])
        
        if len(ordered_sections) != len(sections):
            logger.warning(f"Some sections weren't in report_config: {len(sections) - len(ordered_sections)} sections ignored")
        
        sections = ordered_sections
        logger.info(f"Reordered sections to match report_config order: {[s['title'] for s in sections]}")
        
        pdf_file = os.path.join(output_dir, f"{safe_project_name}_report.pdf")
        
        doc = SimpleDocTemplate(
            pdf_file,
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch,
            title=f"{project_name} Research Report",
            author="XPlainCrypto",
            subject=f"Research Report on {project_name}",
            creator="XPlainCrypto Publisher"
        )
        
        style_manager = StyleManager(logger)
        styles = style_manager.get_reportlab_styles()
        
        story = []
        
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph(escape_xml(f"{project_name} Research Report"), styles['Title']))
        story.append(Spacer(1, 0.5*inch))
        today = datetime.datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(escape_xml(f"Generated on {today}"), styles['CenteredText']))
        story.append(Spacer(1, 2*inch))
        disclaimer_text = "This report is AI-generated and should not be considered financial advice. Always conduct your own research before making investment decisions."
        story.append(Paragraph(escape_xml(disclaimer_text), styles['Disclaimer']))
        story.append(PageBreak())
        
        story.append(Paragraph("Table of Contents", styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        section_counter = 1
        for section in sections:
            story.append(Paragraph(f"{section_counter}. {escape_xml(section['title'])}", styles['TOCEntry']))
            story.append(Spacer(1, 0.1*inch))
            section_counter += 1
        story.append(PageBreak())
        
        for section in sections:
            section_vis = [vis for vis in vis_list if vis["target_section_title"] == section["title"].lower()]
            process_section_content(section, section_vis, story, styles, logger)
        
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        
        logger.info(f"Generated PDF report: {pdf_file}")
        # Set final_report path in state using dict or attribute access
        if isinstance(state, dict):
            state["final_report"] = pdf_file
        else:
            state.final_report = pdf_file
            
        # Update progress
        if isinstance(state, dict):
            state["progress"] = f"Report published for {project_name}"
        elif hasattr(state, 'update_progress'):
            state.update_progress(f"Report published for {project_name}")
            
        return state
        
    except Exception as e:
        logger.error(f"Error in publisher: {str(e)}", exc_info=True)
        # Update progress with error
        if isinstance(state, dict):
            state["progress"] = f"Error publishing report: {str(e)}"
        elif hasattr(state, 'update_progress'):
            state.update_progress(f"Error publishing report: {str(e)}")
        return state

def process_section_content(section, visualizations, story, styles, logger):
    """Process a section for the PDF report, including text content and visualizations."""
    try:
        section_elements = []
        section_title = section.get("title", "")
        
        # Add section title
        section_elements.append(Paragraph(escape_xml(section_title), styles['SectionHeading']))
        section_elements.append(Spacer(1, 0.2*inch))
        
        # Even if content is minimal, include it
        content_lines = section.get("content", [])
        content_text = " ".join(content_lines).strip() if content_lines else ""
        
        # Log content stats for debugging
        logger.info(f"Processing section '{section_title}' with {len(content_lines)} content lines")
        
        # Only show the placeholder if content is completely empty or just contains data unavailable message
        if (not content_text or 
            ("Data unavailable for" in content_text and len(content_lines) <= 2) and
            not section.get("subsections", [])):
            logger.warning(f"No meaningful content for section '{section_title}'")
            section_elements.append(Paragraph(escape_xml(f"No detailed content available for {section_title}."), styles['BodyText']))
            section_elements.append(Spacer(1, 0.2*inch))
        else:
            # Process content as multiple paragraphs
            paragraphs = []
            current_para = []
            in_list = False
            
            # Process content line by line
            for line in content_lines:
                line = line.strip() if line else ""
                if not line:
                    # End of paragraph
                    if current_para:
                        paragraphs.append((current_para, in_list))
                        current_para = []
                        in_list = False
                # Check for list items
                elif line.startswith("- ") or line.startswith("* "):
                    if not in_list and current_para:
                        # End the current paragraph before starting a list
                        paragraphs.append((current_para, False))
                        current_para = []
                    in_list = True
                    current_para.append(line)
                else:
                    if in_list and not (line.startswith("- ") or line.startswith("* ")):
                        # End the list and start a new paragraph
                        if current_para:
                            paragraphs.append((current_para, True))
                            current_para = []
                        in_list = False
                    current_para.append(line)
            
            # Add final paragraph if any
            if current_para:
                paragraphs.append((current_para, in_list))
            
            logger.info(f"Found {len(paragraphs)} content blocks in section '{section_title}'")
            
            # Render paragraphs with appropriate styling
            for para_lines, is_list in paragraphs:
                if is_list:
                    # Format as a bulleted list
                    list_text = ""
                    for item in para_lines:
                        item = item.strip()
                        if item.startswith("- ") or item.startswith("* "):
                            item = "• " + item[2:]
                        list_text += item + "<br/>"
                    section_elements.append(Paragraph(escape_xml(list_text), styles['BulletList']))
                    section_elements.append(Spacer(1, 0.1*inch))
                else:
                    # Format as regular paragraph
                    para_text = " ".join(para_lines)
                    section_elements.append(Paragraph(escape_xml(para_text), styles['BodyText']))
                    section_elements.append(Spacer(1, 0.1*inch))
        
        # Process subsections
        subsections = section.get("subsections", [])
        for subsection in subsections:
            subsection_title = subsection.get("title", "")
            if subsection_title:
                section_elements.append(Paragraph(escape_xml(subsection_title), styles['SubsectionHeading']))
                section_elements.append(Spacer(1, 0.1*inch))
            
                subsection_content = subsection.get("content", [])
                subsection_text = " ".join(subsection_content).strip() if subsection_content else ""
                
                if not subsection_text:
                    section_elements.append(Paragraph(escape_xml(f"No detailed content available for {subsection_title}."), styles['BodyText']))
                    section_elements.append(Spacer(1, 0.1*inch))
                else:
                    # Process subsection content similarly to main content
                    paragraphs = []
                    current_para = []
                    in_list = False
                    
                    for line in subsection_content:
                        line = line.strip() if line else ""
                        if not line:
                            if current_para:
                                paragraphs.append((current_para, in_list))
                                current_para = []
                                in_list = False
                        elif line.startswith("- ") or line.startswith("* "):
                            if not in_list and current_para:
                                paragraphs.append((current_para, False))
                                current_para = []
                            in_list = True
                            current_para.append(line)
                        else:
                            if in_list and not (line.startswith("- ") or line.startswith("* ")):
                                if current_para:
                                    paragraphs.append((current_para, True))
                                    current_para = []
                                in_list = False
                            current_para.append(line)
                    
                    if current_para:
                        paragraphs.append((current_para, in_list))
                    
                    for para_lines, is_list in paragraphs:
                        if is_list:
                            list_text = ""
                            for item in para_lines:
                                item = item.strip()
                                if item.startswith("- ") or item.startswith("* "):
                                    item = "• " + item[2:]
                                list_text += item + "<br/>"
                            section_elements.append(Paragraph(escape_xml(list_text), styles['BulletList']))
                            section_elements.append(Spacer(1, 0.1*inch))
                        else:
                            para_text = " ".join(para_lines)
                            section_elements.append(Paragraph(escape_xml(para_text), styles['BodyText']))
                            section_elements.append(Spacer(1, 0.1*inch))
        
        # Add visualizations if available
        if visualizations:
            logger.info(f"Adding {len(visualizations)} visualizations to section '{section_title}'")
            for vis in visualizations:
                if "path" in vis and vis["path"] and os.path.exists(vis["path"]):
                    try:
                        # Add visualization title
                        if "title" in vis and vis["title"]:
                            section_elements.append(Paragraph(escape_xml(vis["title"]), styles['CaptionTitle']))
                        
                        # Add the image
                        section_elements.append(Spacer(1, 0.1*inch))
                        section_elements.append(Image(vis["path"], width=5*inch, height=3*inch))
                        section_elements.append(Spacer(1, 0.1*inch))
                        
                        # Add description if available
                        if "description" in vis and vis["description"]:
                            section_elements.append(Paragraph(escape_xml(vis["description"]), styles['Caption']))
                            section_elements.append(Spacer(1, 0.2*inch))
                        
                        logger.info(f"Added visualization: {vis.get('title', 'Untitled')} - {vis.get('path')}")
                    except Exception as e:
                        logger.error(f"Error adding visualization {vis.get('title', 'unknown')}: {str(e)}")
                        section_elements.append(Paragraph(escape_xml(f"Visualization could not be included due to an error: {str(e)}"), styles['Caption']))
                else:
                    logger.warning(f"Visualization path invalid or missing: {vis.get('path')}")
                    section_elements.append(Paragraph(escape_xml("Visualization unavailable"), styles['Caption']))
        
        # Add all elements to the story
        story.extend(section_elements)
        story.append(PageBreak())
        logger.info(f"Completed processing section '{section_title}'")
    
    except Exception as e:
        logger.error(f"Error processing section '{section.get('title', 'unknown')}': {str(e)}")
        # Add error message to PDF
        story.append(Paragraph(escape_xml(f"Error processing section: {str(e)}"), styles['BodyText']))
        story.append(PageBreak())