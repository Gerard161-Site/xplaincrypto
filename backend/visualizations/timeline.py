"""Timeline visualizer for XplainCrypto."""

import os
import logging
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta

from .base_visualizer import BaseVisualizer


class TimelineVisualizer(BaseVisualizer):
    """
    Visualizer for creating timeline visualizations showing events over time.
    """
    
    def __init__(self, project_name: str, style_manager, logger: Optional[logging.Logger] = None):
        """Initialize the timeline visualizer."""
        super().__init__(project_name, style_manager, logger)
    
    def create_visualization(self, viz_type: str, viz_config: Dict[str, Any], data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Create a timeline visualization.
        
        Args:
            viz_type: Type of visualization to create
            viz_config: Configuration for the visualization
            data: Data for the visualization
            
        Returns:
            Tuple of (success: bool, file_path: str, message: str)
        """
        self.logger.info(f"Creating timeline visualization for {viz_config.get('id', 'unknown')}")
        
        try:
            # Extract configuration parameters
            viz_id = viz_config.get("id", "timeline_visualization")
            title = viz_config.get("title", f"{self.project_name} Timeline")
            data_source = viz_config.get("data_source", "")
            data_field = viz_config.get("data_field", "")
            
            # Get the timeline events data
            events_data = self._extract_timeline_data(data, data_source, data_field)
            
            if not events_data or len(events_data) == 0:
                self.logger.warning(f"No events data available for timeline {viz_id}")
                return False, "", f"No events data available for timeline {viz_id}"
            
            # Sort events by date
            events_data = self._sort_events_by_date(events_data)
            
            # Create the timeline figure
            fig = self._create_timeline_figure(events_data, title)
            
            # Save the timeline
            chart_name = f"{viz_id.lower().replace(' ', '_')}.png"
            chart_path = os.path.join("reports", self.project_name, chart_name)
            os.makedirs(os.path.dirname(chart_path), exist_ok=True)
            
            fig.write_image(chart_path, scale=2)
            
            self.logger.info(f"Timeline visualization saved to {chart_path}")
            
            return True, chart_path, "Timeline visualization created successfully"
            
        except Exception as e:
            self.logger.error(f"Error creating timeline visualization: {str(e)}")
            return False, "", f"Error creating timeline visualization: {str(e)}"
    
    def _extract_timeline_data(self, data: Dict[str, Any], data_source: str, data_field: str) -> List[Dict[str, Any]]:
        """
        Extract timeline events data from various data formats.
        
        Args:
            data: Input data dictionary
            data_source: Name of the data source
            data_field: Name of the field to extract
            
        Returns:
            List of event dictionaries with date, title, description fields
        """
        self.logger.info(f"Extracting timeline data from {data_source}/{data_field}")
        
        # Try to get data from the specified source and field
        if data_source and data_source in data:
            source_data = data[data_source]
            
            # If data_field is specified, extract that field
            if data_field and isinstance(source_data, dict) and data_field in source_data:
                field_data = source_data[data_field]
                
                if isinstance(field_data, list):
                    self.logger.info(f"Found events list at {data_source}.{data_field}")
                    return self._normalize_events_data(field_data)
                    
            # Try to use entire source data if it looks like events
            elif isinstance(source_data, list):
                self.logger.info(f"Using entire {data_source} as events list")
                return self._normalize_events_data(source_data)
        
        # Try standardized extraction for common event data paths
        self.logger.info("Trying standardized data extraction")
        path_options = [
            f"{data_source}.{data_field}",
            f"data.{data_source}.{data_field}",
            f"market_analysis.{data_source}.events",
            f"timeline.events",
            f"data.timeline.events",
            f"events"
        ]
        
        extracted_data = self._extract_standardized_data(data, path_options)
        if extracted_data is not None and isinstance(extracted_data, list):
            self.logger.info(f"Found events data via standardized extraction")
            return self._normalize_events_data(extracted_data)
        
        # Look for events in data directly
        for key, value in data.items():
            if key.lower() in ["events", "timeline", "milestones", "history"] and isinstance(value, list):
                self.logger.info(f"Found events data in {key}")
                return self._normalize_events_data(value)
            elif isinstance(value, dict):
                for subkey, subvalue in value.items():
                    if subkey.lower() in ["events", "timeline", "milestones", "history"] and isinstance(subvalue, list):
                        self.logger.info(f"Found events data in {key}.{subkey}")
                        return self._normalize_events_data(subvalue)
        
        self.logger.warning(f"No suitable timeline events data found for {data_source}/{data_field}")
        return []
    
    def _normalize_events_data(self, events: List[Any]) -> List[Dict[str, Any]]:
        """
        Normalize events data into a standard format.
        
        Args:
            events: List of events in various formats
            
        Returns:
            List of normalized event dictionaries
        """
        normalized_events = []
        
        for event in events:
            if isinstance(event, dict):
                # Extract required fields with various possible key names
                date = self._extract_event_date(event)
                title = self._extract_event_title(event)
                description = self._extract_event_description(event)
                category = event.get("category", "default")
                
                if date and title:
                    normalized_events.append({
                        "date": date,
                        "title": title,
                        "description": description,
                        "category": category
                    })
            elif isinstance(event, list) and len(event) >= 2:
                # Format: [date, title, description?]
                date = self._parse_date(event[0])
                title = str(event[1])
                description = str(event[2]) if len(event) > 2 else ""
                
                if date and title:
                    normalized_events.append({
                        "date": date,
                        "title": title,
                        "description": description,
                        "category": "default"
                    })
        
        return normalized_events
    
    def _extract_event_date(self, event: Dict[str, Any]) -> Optional[datetime]:
        """Extract date from an event dictionary using various possible keys."""
        date_keys = ["date", "timestamp", "time", "event_date", "day", "milestone_date"]
        
        for key in date_keys:
            if key in event and event[key]:
                return self._parse_date(event[key])
        
        return None
    
    def _extract_event_title(self, event: Dict[str, Any]) -> str:
        """Extract title from an event dictionary using various possible keys."""
        title_keys = ["title", "name", "event", "milestone", "heading"]
        
        for key in title_keys:
            if key in event and event[key]:
                return str(event[key])
        
        return "Unnamed Event"
    
    def _extract_event_description(self, event: Dict[str, Any]) -> str:
        """Extract description from an event dictionary using various possible keys."""
        desc_keys = ["description", "desc", "details", "text", "info", "content"]
        
        for key in desc_keys:
            if key in event and event[key]:
                return str(event[key])
        
        return ""
    
    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Parse date from various formats."""
        if isinstance(date_value, datetime):
            return date_value
            
        if isinstance(date_value, (int, float)):
            # Check if milliseconds or seconds
            if date_value > 1_000_000_000_000:  # Likely milliseconds
                return datetime.fromtimestamp(date_value / 1000)
            else:  # Likely seconds
                return datetime.fromtimestamp(date_value)
                
        if isinstance(date_value, str):
            try:
                # Try parsing with various formats
                try:
                    return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                except:
                    pass
                    
                try:
                    return datetime.strptime(date_value, "%Y-%m-%d")
                except:
                    pass
                    
                try:
                    return datetime.strptime(date_value, "%b %Y")
                except:
                    pass
                    
                try:
                    return datetime.strptime(date_value, "%B %Y")
                except:
                    pass
                    
                try:
                    return datetime.strptime(date_value, "%Y")
                except:
                    pass
                    
                # Generic parsing using pandas
                return pd.to_datetime(date_value).to_pydatetime()
            except:
                return None
                
        return None
    
    def _sort_events_by_date(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort events by date in ascending order."""
        # Filter out any events without valid dates
        valid_events = [event for event in events if event.get("date") is not None]
        
        # Sort by date
        return sorted(valid_events, key=lambda x: x["date"])
    
    def _create_timeline_figure(self, events: List[Dict[str, Any]], title: str) -> go.Figure:
        """
        Create a timeline figure from event data.
        
        Args:
            events: List of event dictionaries
            title: Title for the visualization
            
        Returns:
            Plotly figure object
        """
        # Get unique categories
        categories = set(event.get("category", "default") for event in events)
        
        # Create figure with a single row
        fig = go.Figure()
        
        # Get colors for categories
        category_colors = {}
        colors = self.style_manager.get_color_scheme(len(categories))
        for i, category in enumerate(categories):
            category_colors[category] = colors[i % len(colors)]
        
        # Add events to the timeline
        for i, event in enumerate(events):
            date = event["date"]
            title = event["title"]
            description = event.get("description", "")
            category = event.get("category", "default")
            
            # Add marker for the event
            fig.add_trace(go.Scatter(
                x=[date],
                y=[1],
                mode="markers",
                marker=dict(
                    size=16,
                    color=category_colors.get(category, self.style_manager.get_color("primary")),
                    line=dict(
                        width=2,
                        color=self.style_manager.get_color("background")
                    )
                ),
                name=title,
                text=f"<b>{title}</b><br>{description}",
                hoverinfo="text",
                showlegend=False
            ))
            
            # Add labels for events
            fig.add_annotation(
                x=date,
                y=1.1 + (0.1 * (i % 3)),  # Stagger labels vertically to avoid overlap
                text=title,
                showarrow=True,
                arrowhead=1,
                arrowcolor=category_colors.get(category, self.style_manager.get_color("primary")),
                arrowsize=0.8,
                arrowwidth=1.5,
                ax=0,
                ay=-30
            )
        
        # Add a line connecting all events
        dates = [event["date"] for event in events]
        fig.add_trace(go.Scatter(
            x=dates,
            y=[1] * len(dates),
            mode="lines",
            line=dict(
                color=self.style_manager.get_color("neutral", "#757575"),
                width=2
            ),
            showlegend=False
        ))
        
        # Apply styling
        fig.update_layout(
            title=title,
            xaxis=dict(
                showgrid=True,
                zeroline=False,
                showticklabels=True,
                title="Date",
                gridcolor=self.style_manager.get_grid_color()
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[0, 2]
            ),
            width=self.style_manager.get_chart_width(),
            height=self.style_manager.get_chart_height(),
            margin=dict(l=50, r=50, t=80, b=50),
            plot_bgcolor=self.style_manager.get_color("background"),
            paper_bgcolor=self.style_manager.get_color("background"),
            font=dict(
                family=self.style_manager.get_font("body"),
                size=12,
                color=self.style_manager.get_color("text")
            ),
            title_font=dict(
                family=self.style_manager.get_font("headings"),
                size=16
            ),
            hovermode="closest"
        )
        
        return fig
    
    def get_required_data_sources(self) -> Dict[str, List[str]]:
        """
        Get required data sources for timeline visualization.
        
        Returns:
            Dictionary mapping visualization types to lists of required data sources
        """
        return {
            "timeline": ["events"],
            "milestones": ["events"]
        }
    
    def check_data_usability(self, data: Dict[str, Any], viz_type: str = None) -> bool:
        """Check if data is usable for a timeline visualization."""
        timeline_data = self._extract_timeline_data(data)
        return len(timeline_data) > 0 