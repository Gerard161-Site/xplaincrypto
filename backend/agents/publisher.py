import logging
import os
import datetime
import json
import re
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from backend.state import ResearchState
from backend.utils.style_utils import StyleManager
from PIL import Image as PilImage
import matplotlib.pyplot as plt
from typing import List

def escape_xml(text):
    """Escape XML characters that might cause problems with ReportLab"""
    if not text:
        return ""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')  # Corrected to use single quotes consistently
    return text

def add_page_number(canvas, doc):
    """Add page numbers and footer to each page"""
    # Add page number
    page_num = canvas.getPageNumber()
    text = "Page %s" % page_num
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(8.25*inch, 0.75*inch, text)
    
    # Add footer with website and date
    canvas.setFont("Helvetica", 8)
    canvas.setFillColorRGB(0.5, 0.5, 0.5)  # Gray color
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    canvas.drawString(1*inch, 0.75*inch, f"XPlainCrypto Research Report • {today}")
    canvas.drawCentredString(4.25*inch, 0.75*inch, "www.xplaincrypto.com")

def publisher(state, llm, logger, config=None):
    """Process the report content and create a PDF."""
    try:
        logger.info("Publisher agent starting")
        
        # Get project name and report config from state
        if isinstance(state, dict):
            project_name = state.get("project_name", "Unknown Project")
            report_config = state.get("report_config", {})
        else:
            project_name = getattr(state, "project_name", "Unknown Project")
            report_config = getattr(state, "report_config", {})
                
        # Create output directory
        safe_project_name = project_name.lower().replace(" ", "_")
        output_dir = os.path.join("docs", safe_project_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # Get visualizations from state
        visualizations = {}
        if isinstance(state, dict):
            visualizations = state.get("visualizations", {})
        else:
            visualizations = getattr(state, "visualizations", {})
        
        logger.info(f"Found {len(visualizations)} visualizations in state")
        
        # Create visualization mapping from report config
        section_vis_map = {}
        if "sections" in report_config:
            for section in report_config["sections"]:
                section_title = section.get("title", "").lower()
                if section_title and "visualizations" in section:
                    section_vis_map[section_title] = section["visualizations"]
                    logger.info(f"Section '{section_title}' expects visualizations: {section['visualizations']}")
        
        # Convert visualizations to list format with section mapping
        vis_list = []
        for vis_id, vis_data in visualizations.items():
            if isinstance(vis_data, dict) and "file_path" in vis_data:
                # Find which section this visualization belongs to
                target_section = None
                for section_title, expected_vis in section_vis_map.items():
                    if vis_id in expected_vis:
                        target_section = section_title
                        break
                
                vis_list.append({
                    "path": vis_data["file_path"],
                    "title": vis_data.get("title", vis_id.replace("_", " ").title()),
                    "description": vis_data.get("description", ""),
                    "type": vis_id,
                    "target_section": target_section
                })
                logger.info(f"Visualization {vis_id} mapped to section: {target_section}")
        
        logger.info(f"Processed {len(vis_list)} visualizations")
        
        # Get draft content
        draft = ""
        if isinstance(state, dict):
            draft = state.get("draft", "")
        else:
            draft = getattr(state, "draft", "")
            
        if not draft:
            logger.error("No draft content available")
            return state
        
        # Parse sections
        lines = draft.split("\n")
        sections = []
        current_section = None
        current_content = []
        
        # Skip the initial title page content from the draft
        skip_initial_content = True
        for line in lines:
            if skip_initial_content:
                if line.startswith("# ") and not any(x in line.lower() for x in ["research report", "generated on", "disclaimer"]):
                    skip_initial_content = False
                else:
                    continue
            
            if line.startswith("# ") or line.startswith("## "):
                # Save previous section if exists
                if current_section:
                    sections.append({
                        "title": current_section,
                        "content": "\n".join(current_content)
                    })
                
                # Start new section
                if line.startswith("# "):
                    current_section = line[2:].strip()
                else:
                    current_section = line[3:].strip()
                current_content = [line]
            else:
                current_content.append(line)
        
        # Add the last section
        if current_section:
            sections.append({
                "title": current_section,
                "content": "\n".join(current_content)
            })
        
        logger.info(f"Parsed {len(sections)} sections from draft")
        
        # Generate PDF report
        pdf_file = os.path.join(output_dir, f"{safe_project_name}_report.pdf")
        
        try:
            # Create PDF using ReportLab
            doc = SimpleDocTemplate(
                pdf_file,
                pagesize=letter,
                leftMargin=1*inch,
                rightMargin=1*inch,
                topMargin=1*inch,
                bottomMargin=1*inch,
                title=f"{project_name} Research Report",
                author="XPlainCrypto",
                subject=f"Research Report on {project_name}",
                creator="XPlainCrypto Publisher"
            )
            
            # Initialize StyleManager
            style_manager = StyleManager(logger)
            styles = style_manager.get_reportlab_styles()
            
            # Build PDF content
            story = []
            
            # Add title page
            story.append(Spacer(1, 2*inch))
            story.append(Paragraph(escape_xml(f"{project_name} Research Report"), styles['Title']))
            story.append(Spacer(1, 0.5*inch))
            
            # Add date
            today = datetime.datetime.now().strftime("%B %d, %Y")
            story.append(Paragraph(escape_xml(f"Generated on {today}"), styles['CenteredText']))
            
            # Add disclaimer
            story.append(Spacer(1, 2*inch))
            disclaimer_text = "This report is AI-generated and should not be considered financial advice. Always conduct your own research before making investment decisions."
            story.append(Paragraph(escape_xml(disclaimer_text), styles['Disclaimer']))
            
            # Add page break after title page
            story.append(PageBreak())
            
            # Add table of contents
            story.append(Paragraph("Table of Contents", styles['SectionHeading']))
            story.append(Spacer(1, 0.2*inch))
            
            # Add TOC entries
            for i, section in enumerate(sections):
                story.append(Paragraph(f"{i+1}. {escape_xml(section['title'])}", styles['TOCEntry']))
                story.append(Spacer(1, 0.1*inch))
            
            # Add page break after TOC
            story.append(PageBreak())
            
            # Process each section
            for section in sections:
                # Get visualizations for this section based on report config mapping
                section_vis = []
                section_title = section["title"].lower()
                
                # First try exact match from report config mapping
                for vis in vis_list:
                    if vis["target_section"] == section_title:
                        section_vis.append(vis)
                        logger.info(f"Adding visualization {vis['type']} to section '{section['title']}' (exact match)")
                
                # If no visualizations found and this is a main section, check if it's in report config
                if not section_vis and section_title in section_vis_map:
                    expected_vis = section_vis_map[section_title]
                    for vis in vis_list:
                        if vis["type"] in expected_vis:
                            section_vis.append(vis)
                            logger.info(f"Adding visualization {vis['type']} to section '{section['title']}' (config match)")
                
                logger.info(f"Found {len(section_vis)} visualizations for section '{section['title']}'")
                process_section_content(section["content"], section_vis, story, styles, logger)
                story.append(PageBreak())
            
            # Build the PDF
            doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
            
            logger.info(f"Generated PDF report: {pdf_file}")
            
            # Update state with final report path
            if isinstance(state, dict):
                state["final_report"] = pdf_file
            else:
                state.final_report = pdf_file
            
            return state
            
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}", exc_info=True)
            return state
            
    except Exception as e:
        logger.error(f"Error in publisher: {str(e)}", exc_info=True)
        return state

def process_section_visualizations(section_data, state):
    """Process visualizations for a section and ensure they're included in the report."""
    section_title = section_data.get("title", "")
    visualization_paths = []
    
    # Check for visualizations in section data
    section_visualizations = section_data.get("visualizations", [])
    
    if section_visualizations:
        for vis in section_visualizations:
            if isinstance(vis, dict) and "path" in vis and vis["path"]:
                # Verify the file exists
                if os.path.exists(vis["path"]) and os.path.getsize(vis["path"]) > 0:
                    visualization_paths.append({
                        "path": vis["path"],
                        "title": vis.get("title", os.path.basename(vis["path"])),
                        "description": vis.get("description", "")
                    })
    
    # Look for visualizations in the global visualizations dict as backup
    if hasattr(state, "visualizations") and state.visualizations:
        for vis_type, vis_data in state.visualizations.items():
            # Check if this visualization belongs to this section
            section_match = False
            
            # Check visualization types in report config
            if hasattr(state, "report_config") and "visualization_types" in state.report_config:
                vis_config = state.report_config.get("visualization_types", {})
                if vis_config.get("section", "").lower() == section_title.lower():
                    section_match = True
            
            # Add the visualization if it matches this section and isn't already included
            if section_match and vis_data.get("file_path") and os.path.exists(vis_data["file_path"]):
                vis_path = vis_data["file_path"]
                if not any(v["path"] == vis_path for v in visualization_paths):
                    visualization_paths.append({
                        "path": vis_path,
                        "title": vis_data.get("title", os.path.basename(vis_path)),
                        "description": vis_data.get("description", "")
                    })
    
    return visualization_paths

def insert_visualizations_markdown(text, visualizations):
    """Insert visualization images into the markdown text."""
    if not visualizations:
        return text
    
    # Add visualizations at the end of the section
    vis_markdown = "\n\n"
    for vis in visualizations:
        vis_path = vis["path"]
        vis_title = vis.get("title", "")
        vis_description = vis.get("description", "")
        
        # Create relative path for markdown
        rel_path = os.path.relpath(vis_path, "docs")
        
        # Add the image with title and description
        vis_markdown += f"\n\n![{vis_title}]({rel_path})\n\n"
        if vis_description:
            vis_markdown += f"*{vis_description}*\n\n"
    
    # Append visualizations to the section content
    return text + vis_markdown

def _create_table_image(self, headers: List[str], data_rows: List[List[str]], title: str, output_path: str) -> bool:
    """Create a table image using matplotlib."""
    try:
        # Fixed width for all tables (reduced by 5%)
        FIXED_WIDTH = 11.4  # Reduced from 12 to 11.4 (5% reduction)
        MIN_HEIGHT = 3    # Minimum height
        ROW_HEIGHT = 0.5  # Height per row
        
        # Calculate height based on content
        content_height = len(data_rows) * ROW_HEIGHT
        title_and_padding = 1.5  # Space for title and padding
        height = max(MIN_HEIGHT, content_height + title_and_padding)
        
        # Create figure and axis
        fig = plt.figure(figsize=(FIXED_WIDTH, height))
        ax = fig.add_subplot(111)
        ax.axis('tight')
        ax.axis('off')
        
        # Create the table with fixed proportions
        table = ax.table(
            cellText=data_rows,
            colLabels=headers,
            loc='center',
            cellLoc='left',
            colWidths=[0.6, 0.4]  # Fixed proportions: 60% for metric, 40% for value
        )
        
        # Adjust table style
        table.auto_set_font_size(False)
        table.set_fontsize(11)  # Slightly reduced font size for better fit
        
        # Calculate scale based on content
        num_rows = len(data_rows) + 1  # +1 for header
        vertical_scale = min(2.0, 8.0 / num_rows)  # Adjust scale based on number of rows
        table.scale(1.2, vertical_scale)
        
        # Style header row
        for i, key in enumerate(headers):
            header_cell = table[(0, i)]
            header_cell.set_facecolor('#4472C4')
            header_cell.set_text_props(color='white', weight='bold')
            header_cell.set_text_props(ha='center')
            header_cell.set_height(0.15)  # Fixed header height
        
        # Style data rows
        row_colors = ['#f5f5f5', 'white']
        for i, row in enumerate(range(1, len(data_rows) + 1)):
            row_height = 0.1  # Fixed row height
            for j, col in enumerate(range(len(headers))):
                cell = table[(row, col)]
                cell.set_facecolor(row_colors[i % 2])
                cell.set_height(row_height)
                
                # Left-align first column (metrics), right-align second column (values)
                if j == 0:
                    cell.set_text_props(ha='left', va='center')
                    cell._text.set_x(0.05)  # 5% padding from left
                else:
                    cell.set_text_props(ha='right', va='center')
                    cell._text.set_x(0.95)  # 5% padding from right
                
                # Add subtle borders
                cell.set_edgecolor('#dddddd')
                cell.set_linewidth(0.5)
        
        # Add title with consistent padding
        plt.title(title.replace("_", " ").title(), pad=20, fontsize=13, weight='bold')
        
        # Adjust layout to ensure consistent spacing
        plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
        
        # Save the figure with high quality
        plt.savefig(
            output_path,
            dpi=300,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none',
            pad_inches=0.2  # Consistent padding around the figure
        )
        plt.close()
        
        return True
    except Exception as e:
        self.logger.error(f"Error creating table image: {str(e)}")
        plt.close()
        return False

def add_visualization_to_story(story, vis_path, title, description, logger):
    """Add a visualization to the PDF story with proper sizing and formatting."""
    try:
        if not os.path.exists(vis_path):
            logger.warning(f"Visualization file not found: {vis_path}")
            return
            
        # Open and get image dimensions
        img = PilImage.open(vis_path)
        width, height = img.size
        aspect = height / width
        
        # Calculate dimensions to fit page width
        max_width = 6.5 * inch  # Standard page width minus margins
        max_height = 8 * inch   # Max height to ensure it fits on one page
        
        # Calculate initial dimensions
        img_width = min(width, max_width)
        img_height = img_width * aspect
        
        # If height is too large, scale down proportionally
        if img_height > max_height:
            img_height = max_height
            img_width = img_height / aspect
        
        # Add some spacing before the visualization
        story.append(Spacer(1, 0.2*inch))
        
        # Add the visualization title if provided
        if title:
            story.append(Paragraph(escape_xml(title), heading2_style))
            story.append(Spacer(1, 0.1*inch))
        
        # Add the image
        story.append(Image(vis_path, width=img_width, height=img_height))
        
        # Add the description if provided
        if description:
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph(escape_xml(description), caption_style))
        
        # Add spacing after the visualization
        story.append(Spacer(1, 0.3*inch))
        
        logger.info(f"Successfully added visualization: {vis_path}")
        return True
    except Exception as e:
        logger.error(f"Error adding visualization {vis_path}: {str(e)}")
        return False

def process_section_content(section_content, visualizations, story, styles, logger):
    """Process section content and add it to the PDF story."""
    lines = section_content.split('\n')
    current_paragraph = []
    section_title = None
    
    # Calculate text width and reduce visualization width by 10%
    TEXT_WIDTH = 7.0 * inch
    VIS_WIDTH = TEXT_WIDTH * 0.9  # 10% smaller than text width
    
    for line in lines:
        if line.startswith("# ") or line.startswith("## "):
            # Handle section headers
            if current_paragraph:
                story.append(Paragraph(escape_xml(" ".join(current_paragraph)), styles['BodyText']))
                current_paragraph = []
            
            section_title = line[2:] if line.startswith("# ") else line[3:]
            style = styles['SectionHeading'] if line.startswith("# ") else styles['SubsectionHeading']
            story.append(Paragraph(escape_xml(section_title), style))
            story.append(Spacer(1, 0.2*inch))
            
        elif line.startswith("### "):
            # Skip subsection headers as they'll be handled with visualizations
            continue
            
        elif line.strip() == "":
            # Handle empty lines
            if current_paragraph:
                story.append(Paragraph(escape_xml(" ".join(current_paragraph)), styles['BodyText']))
                current_paragraph = []
                story.append(Spacer(1, 0.1*inch))
            
        else:
            # Add line to current paragraph
            current_paragraph.append(line)
    
    # Add any remaining paragraph
    if current_paragraph:
        story.append(Paragraph(escape_xml(" ".join(current_paragraph)), styles['BodyText']))
        story.append(Spacer(1, 0.2*inch))
    
    # After processing text, add relevant visualizations for this section
    if section_title and visualizations:
        logger.info(f"Looking for visualizations for section: {section_title}")
        for vis in visualizations:
            try:
                # Check if visualization exists and is readable
                if os.path.exists(vis["path"]) and os.path.getsize(vis["path"]) > 0:
                    logger.info(f"Adding visualization: {vis['path']}")
                    
                    # Get image dimensions
                    img = PilImage.open(vis["path"])
                    width, height = img.size
                    aspect = height / width
                    
                    # Calculate dimensions to fit the reduced width
                    img_width = min(width, VIS_WIDTH)
                    img_height = img_width * aspect
                    
                    # If height is too large, scale down proportionally
                    max_height = 9 * inch
                    if img_height > max_height:
                        img_height = max_height
                        img_width = img_height / aspect
                    
                    # Add spacing before visualization
                    story.append(Spacer(1, 0.3*inch))
                    
                    # Add the image without additional title (since it's embedded in the image)
                    story.append(Image(vis["path"], width=img_width, height=img_height))
                    
                    # Add description if available
                    if vis.get("description"):
                        story.append(Spacer(1, 0.1*inch))
                        story.append(Paragraph(escape_xml(vis["description"]), styles['Caption']))
                    
                    # Add spacing after visualization
                    story.append(Spacer(1, 0.3*inch))
                    
                    logger.info(f"Successfully added visualization: {vis['path']}")
                else:
                    logger.warning(f"Visualization file not found or empty: {vis['path']}")
            except Exception as e:
                logger.error(f"Error adding visualization {vis.get('path', 'unknown')}: {str(e)}")
                continue
    
    # Add page break only if this is a main section (not subsection)
    if section_title and line.startswith("# "):
        story.append(PageBreak())