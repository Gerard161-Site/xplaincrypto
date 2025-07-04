import logging
import os
import datetime
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from backend.state import ResearchState
from backend.utils.style_utils import StyleManager
from backend.utils.state_manager import StateManager
from PIL import Image as PILImage
from backend.utils.logging_utils import log_safe

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
    
    # Use StyleManager for styling
    style_manager = StyleManager(logging.getLogger(__name__))
    font_family = style_manager.get_font_family()
    font_size_caption = style_manager.get_font_size('caption')
    colors = style_manager.get_colors()
    
    canvas.setFont(font_family, font_size_caption)
    canvas.drawRightString(8*inch, 0.5*inch, f"Page {page_num}")
    
    canvas.setFont(font_family, font_size_caption - 1)
    canvas.setFillColor(colors["text"])
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    canvas.drawString(0.75*inch, 0.5*inch, f"XPlainCrypto Research Report • {today}")
    canvas.drawCentredString(4.25*inch, 0.5*inch, "www.xplaincrypto.com")

def publisher(state, llm, logger, config=None) -> dict:
    """Process the report content and create a PDF."""
    try:
        logger.info("Publisher agent starting")
        
        # Initialize StateManager for consistent state access
        state_manager = StateManager(logger=logger)
        
        # Get project name and report config using StateManager
        project_name = state_manager.get_project_name(state)
        report_config = state_manager.get_report_config(state)
        
        logger.info(f"Publisher agent processing report for project: '{project_name}'")
        
        # Update progress using StateManager
        state = state_manager.update_progress(state, f"Publishing report for {project_name}...")
        
        # Get draft content using StateManager
        draft = state_manager.get_final_report(state)
        if not draft:
            draft = state_manager.get_edited_draft(state)
        if not draft:
            draft = state_manager.get_draft(state)
            
        if not draft or len(draft) < 500:
            logger.warning(f"No substantial draft found in state (best length: {len(draft) if draft else 0} chars)")
            
            minimal_draft = f"# {project_name} Research Report\n\n"
            minimal_draft += f"*Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            minimal_draft += "## Executive Summary\n\n"
            minimal_draft += f"{project_name} is a cryptocurrency project. Due to technical limitations, a full analysis could not be generated.\n\n"
            minimal_draft += "## Tokenomics\n\n"
            minimal_draft += f"Tokenomics data for {project_name} is not available in this report.\n\n"
            minimal_draft += "## Disclaimer\n\nThis report was generated with limited data. Please consult additional sources for investment decisions."
            
            draft = minimal_draft
            logger.info(f"Generated minimal draft with {len(draft.split())} words")
            
            # Update state with minimal draft
            state = state_manager.update_draft(state, draft)
            state = state_manager.update_edited_draft(state, draft)
        
        # Get visualization list using StateManager
        vis_list = state_manager.get_visualization_list(state)
        
        logger.info(f"Found {len(vis_list)} visualizations in state")
        if vis_list:
            for i, viz in enumerate(vis_list):
                path = viz.get("path", "N/A")
                target = viz.get("target_section_title", "unknown")
                logger.info(f"Visualization {i+1}: {viz.get('type', 'unknown')} -> {target}, path: {path}")
                if path and os.path.exists(path):
                    file_size = os.path.getsize(path) / 1024
                    logger.info(f"  - File exists: {file_size:.1f} KB")
                else:
                    logger.warning(f"  - File doesn't exist: {path}")
        
        section_vis_map = {}
        if report_config and "sections" in report_config:
            for section in report_config.get("sections", []):
                if "visualizations" in section and section["title"]:
                    # Handle the case where visualizations are strings or dictionaries
                    vis_ids = []
                    for v in section["visualizations"]:
                        if isinstance(v, dict) and "id" in v:
                            vis_ids.append(v["id"])
                        elif isinstance(v, str):
                            vis_ids.append(v)
                    section_vis_map[section["title"].lower()] = vis_ids
        
        processed_vis_list = []
        seen_titles = set()  # Track titles to prevent duplicates
        for vis in vis_list:
            try:
                if isinstance(vis, dict) and "path" in vis:
                    vis_path = vis["path"]
                    
                    if vis_path and os.path.exists(vis_path):
                        target_section = vis.get("target_section_title")
                        vis_type = vis.get("type", "unknown")
                        
                        if not target_section:
                            for section_title, vis_types in section_vis_map.items():
                                if vis_type in vis_types:
                                    target_section = section_title
                                    logger.info(f"Mapped visualization '{vis_type}' to section '{section_title}'")
                                    break
                        
                        title = vis.get("title", vis_type.replace("_", " ").replace("chart", "").replace("table", "").replace("_trend", "").strip().title())
                        if title in seen_titles:
                            logger.info(f"Skipping duplicate visualization title: {title}")
                            continue
                        seen_titles.add(title)
                        
                        processed_vis_list.append({
                            "path": vis_path,
                            "title": title,
                            "description": vis.get("description", ""),
                            "type": vis_type,
                            "target_section_title": target_section
                        })
                        logger.info(f"Included visualization: {vis_type} -> {target_section}")
                    else:
                        logger.warning(f"Skipping visualization - missing or invalid path: {vis_path}")
            except Exception as e:
                logger.warning(f"Error processing visualization entry: {str(e)}")
                continue
        
        vis_list = processed_vis_list
        logger.info(f"Processed {len(vis_list)} valid visualizations")
        
        safe_project_name = project_name.lower().replace(" ", "_")
        output_dir = os.path.join("reports", safe_project_name)
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Using output directory: {output_dir}")
        
        raw_draft_path = os.path.join(output_dir, f"{safe_project_name}_raw_draft.md")
        with open(raw_draft_path, "w", encoding="utf-8") as f:
            f.write(draft)
        logger.info(f"Saved raw draft to {raw_draft_path}")
        
        lines = draft.split("\n")
        logger.info(f"Draft contains {len(lines)} lines and {len(draft.split())} words")
        
        non_empty_lines = [line for line in lines[:10] if line.strip()]
        logger.info(f"Draft starts with: {non_empty_lines[:3]}")
        
        sections = []
        seen_section_titles = set()
        current_section = {"title": None, "content": [], "subsections": []}
        current_subsection = None
        
        normalized_lines = []
        for line in lines:
            if line.startswith("###") and not line.startswith("####"):
                line = "## " + line[3:].lstrip()
            elif line.startswith("##") and not line.startswith("###"):
                if not line.startswith("## "):
                    line = "## " + line[2:].lstrip()
            elif line.startswith("#") and not line.startswith("##"):
                if not line.startswith("# "):
                    line = "# " + line[1:].lstrip()
            normalized_lines.append(line)
        
        logger.info(f"Normalized {len(normalized_lines)} lines for processing")
        
        expected_section_titles = {s["title"] for s in report_config.get("sections", [])}
        expected_section_details = {s["title"]: s for s in report_config.get("sections", [])}
        logger.info(f"Expected sections from report_config: {list(expected_section_titles)}")
        
        in_header = True
        for line in normalized_lines:
            if in_header:
                if (line.startswith("# ") and not any(x in line.lower() for x in ["research report", "generated on", "disclaimer"])) or \
                   (line.startswith("## ") and not any(x in line.lower() for x in ["research report", "generated on", "disclaimer"])):
                    in_header = False
                    logger.info(f"Found first content section: {line.strip()}")
                else:
                    continue
                    
            if line.startswith("# ") or line.startswith("## "):
                title = line[2:].strip() if line.startswith("# ") else line[3:].strip()
                
                if title in expected_section_titles:
                    logger.info(f"Found expected section: {title}")
                else:
                    logger.warning(f"Found unexpected section: {title} (not in report_config)")
                
                if current_section["title"] and current_section["title"] not in seen_section_titles:
                    sections.append(current_section)
                    seen_section_titles.add(current_section["title"])
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
        if current_section["title"] and current_section["title"] not in seen_section_titles:
            sections.append(current_section)
            seen_section_titles.add(current_section["title"])
        
        logger.info(f"Parsed {len(sections)} unique main sections from draft")
        
        # Validate sections against report_config requirements
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
        
        # Initialize PDF document
        output_path = os.path.join(output_dir, f"{safe_project_name}_report.pdf")
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Initialize styles only once
        styles = getSampleStyleSheet()
        if 'Title' not in styles.byName:
            styles.add(ParagraphStyle(
                name='Title',
                fontSize=24,
                leading=28,
                alignment=1,  # Center
                spaceAfter=20
            ))
        if 'Heading1' not in styles.byName:
            styles.add(ParagraphStyle(
                name='Heading1',
                fontSize=18,
                leading=22,
                spaceBefore=12,
                spaceAfter=6
            ))
        if 'Heading2' not in styles.byName:
            styles.add(ParagraphStyle(
                name='Heading2',
                fontSize=14,
                leading=18,
                spaceBefore=10,
                spaceAfter=5
            ))
        if 'Normal' not in styles.byName:
            styles.add(ParagraphStyle(
                name='Normal',
                fontSize=10,
                leading=12
            ))
        
        # Build the story for the PDF
        story = []
        
        # Add report title
        story.append(Paragraph(f"{project_name} Research Report", styles['Title']))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 24))
        
        # Process each section
        for section in sections:
            section_title = section["title"]
            section_content = section["content"]
            subsections = section["subsections"]
            
            # Add section title
            story.append(Paragraph(section_title, styles['Heading1']))
            story.append(Spacer(1, 6))
            
            # Add section content
            for paragraph in section_content:
                if paragraph.strip():
                    story.append(Paragraph(escape_xml(paragraph), styles['Normal']))
            
            # Add subsections
            for subsection in subsections:
                subsection_title = subsection["title"]
                subsection_content = subsection["content"]
                
                story.append(Paragraph(subsection_title, styles['Heading2']))
                story.append(Spacer(1, 4))
                
                for paragraph in subsection_content:
                    if paragraph.strip():
                        story.append(Paragraph(escape_xml(paragraph), styles['Normal']))
            
            # Add visualizations for this section
            section_vis = [vis for vis in vis_list if vis["target_section_title"] and vis["target_section_title"].lower() == section_title.lower()]
            if section_vis:
                logger.info(f"Adding {len(section_vis)} visualizations to section '{section_title}'")
                for vis in section_vis:
                    vis_path = vis["path"]
                    vis_title = vis["title"]
                    description = vis["description"]
                    
                    logger.info(f"Processing visualization: {vis_title} with path: {vis_path}")
                    if os.path.exists(vis_path):
                        logger.info(f"File exists for {vis_title}: {vis_path}")
                        # Add spacing before the visual group
                        story.append(Spacer(1, 0.2*inch))
                        
                        # Add visualization title
                        story.append(Paragraph(escape_xml(vis_title), styles['Normal']))
                        
                        # Add the image
                        img = PILImage.open(vis_path)
                        img_width, img_height = img.size
                        aspect = img_height / float(img_width)
                        
                        pdf_config = style_manager.get_pdf_config()
                        max_width = pdf_config.get("images", {}).get("max_width", 5.5) * inch
                        max_height = max_width * aspect
                        
                        # Ensure the image fits within the page width
                        logger.info(f"Adding image {vis_title} with dimensions: {img_width}x{img_height}, scaled to {max_width}x{max_height}")
                        story.append(Image(vis_path, width=max_width, height=max_height))
                        
                        # Add description (caption) without quotes
                        if description:
                            caption_text = escape_xml(description.strip('"'))
                            story.append(Paragraph(caption_text, styles['Normal']))
                        
                        # Add spacing after the visual group
                        story.append(Spacer(1, 0.1*inch))
                    else:
                        logger.warning(f"File does not exist for visualization {vis_title}: {vis_path}")
            else:
                logger.info(f"No visualizations found for section '{section_title}'")
            
            # Add a page break after each section
            story.append(PageBreak())
        
        # Build the PDF
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        
        logger.info(f"Successfully generated PDF at {output_path}")
        
        # Update report path in state using StateManager
        state = state_manager.update_report_path(state, output_path)
        
        return state
    
    except Exception as e:
        logger.error(f"Error in publisher: {str(e)}", exc_info=True)
        # Add error to state using StateManager
        state_manager = StateManager(logger=logger)
        state = state_manager.add_error(state, "publisher", str(e))
        state = state_manager.update_progress(state, f"Error publishing report: {str(e)}")
        return state