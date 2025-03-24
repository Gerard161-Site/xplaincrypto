import os
import json
import logging
from typing import Dict, Any, Optional
import matplotlib.pyplot as plt
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

class StyleManager:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.style_config = self._load_style_config()
        
    def _load_style_config(self) -> Dict[str, Any]:
        """Load the style configuration from JSON file"""
        try:
            config_path = os.path.join("backend", "config", "style_config.json")
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading style config: {e}")
            return {}
            
    def get_alignment(self, align_type: str) -> int:
        """Convert alignment string to ReportLab constant"""
        align_map = {
            "center": TA_CENTER,
            "justify": TA_JUSTIFY,
            "left": TA_LEFT
        }
        return align_map.get(self.style_config.get("pdf", {}).get("alignment", {}).get(align_type, "left"), TA_LEFT)
    
    def get_reportlab_styles(self) -> Dict[str, ParagraphStyle]:
        """Generate ReportLab paragraph styles from configuration"""
        fonts = self.style_config.get("fonts", {})
        sizes = self.style_config.get("font_sizes", {})
        spacing = self.style_config.get("spacing", {})
        
        return {
            'Title': ParagraphStyle(
                name='Title',
                fontName=fonts.get("bold", "Times-Bold"),
                fontSize=sizes.get("title", 16),
                alignment=self.get_alignment("title"),
                spaceAfter=spacing.get("section", {}).get("after", 24)
            ),
            'SubTitle': ParagraphStyle(
                name='SubTitle',
                fontName=fonts.get("bold", "Times-Bold"),
                fontSize=sizes.get("subtitle", 14),
                alignment=self.get_alignment("title"),
                spaceAfter=spacing.get("section", {}).get("after", 16)
            ),
            'SectionHeading': ParagraphStyle(
                name='SectionHeading',
                fontName=fonts.get("bold", "Times-Bold"),
                fontSize=sizes.get("section_heading", 12),
                alignment=self.get_alignment("section"),
                spaceBefore=spacing.get("section", {}).get("before", 24),
                spaceAfter=spacing.get("section", {}).get("after", 12)
            ),
            'SubsectionHeading': ParagraphStyle(
                name='SubsectionHeading',
                fontName=fonts.get("bold", "Times-Bold"),
                fontSize=sizes.get("subsection_heading", 10),
                alignment=self.get_alignment("section"),
                spaceBefore=spacing.get("subsection", {}).get("before", 12),
                spaceAfter=spacing.get("subsection", {}).get("after", 6)
            ),
            'BodyText': ParagraphStyle(
                name='BodyText',
                fontName=fonts.get("secondary", "Times-Roman"),
                fontSize=sizes.get("body_text", 10),
                alignment=self.get_alignment("body"),
                spaceBefore=spacing.get("paragraph", {}).get("before", 6),
                spaceAfter=spacing.get("paragraph", {}).get("after", 8),
                leading=spacing.get("line_height", 16),
                firstLineIndent=0
            ),
            'CenteredText': ParagraphStyle(
                name='CenteredText',
                fontName=fonts.get("secondary", "Times-Roman"),
                fontSize=sizes.get("body_text", 10),
                alignment=TA_CENTER,
                spaceBefore=spacing.get("paragraph", {}).get("before", 6),
                spaceAfter=spacing.get("paragraph", {}).get("after", 6),
                leading=12
            ),
            'Caption': ParagraphStyle(
                name='Caption',
                fontName=fonts.get("italic", "Times-Italic"),
                fontSize=sizes.get("caption", 9),
                alignment=self.get_alignment("caption"),
                spaceAfter=12
            ),
            'Disclaimer': ParagraphStyle(
                name='Disclaimer',
                fontName=fonts.get("italic", "Times-Italic"),
                fontSize=sizes.get("disclaimer", 8),
                alignment=TA_CENTER
            ),
            'Reference': ParagraphStyle(
                name='Reference',
                fontName=fonts.get("secondary", "Times-Roman"),
                fontSize=sizes.get("reference", 9),
                alignment=TA_LEFT,
                spaceBefore=2,
                spaceAfter=2,
                leading=11
            ),
            'TOCEntry': ParagraphStyle(
                name='TOCEntry',
                fontName=fonts.get("secondary", "Times-Roman"),
                fontSize=sizes.get("body_text", 10),
                alignment=TA_LEFT,
                leftIndent=20,
                firstLineIndent=-12,
                spaceBefore=2,
                spaceAfter=2,
                leading=12
            )
        }
    
    def configure_matplotlib(self):
        """Configure matplotlib with the style settings"""
        vis_config = self.style_config.get("visualization", {})
        mpl_config = vis_config.get("matplotlib", {})
        
        # Set style
        plt.style.use(mpl_config.get("style", "ggplot"))
        
        # Update rcParams
        plt.rcParams.update({
            'font.family': self.style_config.get("fonts", {}).get("primary", "Times New Roman"),
            'font.size': self.style_config.get("font_sizes", {}).get("body_text", 10),
            'axes.titlesize': mpl_config.get("axes", {}).get("title_size", 12),
            'axes.labelsize': mpl_config.get("axes", {}).get("label_size", 10),
            'xtick.labelsize': mpl_config.get("axes", {}).get("tick_size", 10),
            'ytick.labelsize': mpl_config.get("axes", {}).get("tick_size", 10),
            'legend.fontsize': mpl_config.get("legend", {}).get("font_size", 10),
            'figure.titlesize': mpl_config.get("axes", {}).get("title_size", 12),
            'axes.facecolor': self.style_config.get("colors", {}).get("background", "#f5f5f5"),
            'figure.facecolor': self.style_config.get("colors", {}).get("background", "white")
        })
    
    def get_visualization_config(self) -> Dict[str, Any]:
        """Get visualization configuration settings"""
        return self.style_config.get("visualization", {})
    
    def get_colors(self) -> Dict[str, str]:
        """Get color configuration"""
        return self.style_config.get("colors", {})
    
    def get_pdf_config(self) -> Dict[str, Any]:
        """Get PDF configuration settings"""
        return self.style_config.get("pdf", {}) 