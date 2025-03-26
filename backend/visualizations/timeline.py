"""
Timeline visualization module.

This module provides the TimelineVisualizer class for creating timeline visualizations
for project milestones, roadmaps, and historical events.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import matplotlib.dates as mdates

from backend.visualizations.base import BaseVisualizer

class TimelineVisualizer(BaseVisualizer):
    """
    Specialized visualizer for timelines.
    
    Handles creation of timeline visualizations for project milestones,
    roadmaps, and historical events.
    """
    
    def create(self, vis_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a timeline visualization based on the provided configuration and data.
        
        Args:
            vis_type: Type of visualization (e.g., project_roadmap, milestone_timeline)
            config: Configuration for the visualization
            data: Data to visualize
            
        Returns:
            Dictionary containing visualization result information
        """
        self.logger.info(f"Creating timeline: {vis_type}")
        
        # Validate output directory
        if not self.validate_output_dir():
            return {"error": "Invalid output directory"}
        
        # Get the data field from config
        data_field = config.get("data_field", "")
        
        # Get the data based on visualization type
        events, field_used = self._get_timeline_data(vis_type, data_field, data)
        if not events:
            return {"error": f"No data available for {vis_type}"}
        
        # Create the chart
        try:
            # Sort events by date
            events.sort(key=lambda x: x.get('date', ''))
            
            # Set up figure with appropriate dimensions
            plt.figure(figsize=(8, 6))
            
            # Prepare data for plotting
            dates = [self._parse_date(event.get('date', '')) for event in events]
            y_positions = range(len(events))
            labels = [event.get('title', f"Event {i+1}") for i, event in enumerate(events)]
            descriptions = [event.get('description', '') for event in events]
            
            # Create the timeline
            plt.plot_date(dates, y_positions, 'bo-', markersize=8)
            
            # Add event labels and descriptions
            for i, (date, label, desc) in enumerate(zip(dates, labels, descriptions)):
                plt.annotate(
                    label, 
                    (date, i), 
                    xytext=(10, 0), 
                    textcoords='offset points',
                    fontsize=10, 
                    fontweight='bold',
                    va='center'
                )
                
                if desc:
                    plt.annotate(
                        desc,
                        (date, i),
                        xytext=(10, -12),
                        textcoords='offset points',
                        fontsize=8,
                        va='top',
                        wrap=True
                    )
            
            # Format the plot
            ax = plt.gca()
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.yticks([])  # Hide y-axis ticks
            
            # Add title
            title = config.get("title", vis_type.replace("_", " ").title())
            plt.title(title, pad=20, fontsize=14)
            
            # Add grid and layout
            plt.grid(True, axis='x', alpha=0.3)
            plt.tight_layout()
            
            # Save the chart
            file_path = self._save_chart(vis_type)
            if not file_path:
                return {"error": f"Failed to save timeline for {vis_type}"}
            
            # Return the result
            return {
                "file_path": file_path,
                "title": title,
                "data_summary": {
                    "events": len(events),
                    "start_date": dates[0].strftime('%Y-%m-%d') if dates else "",
                    "end_date": dates[-1].strftime('%Y-%m-%d') if dates else "",
                    "data_field": field_used
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error creating timeline: {str(e)}", exc_info=True)
            plt.close()
            return {"error": f"Failed to create timeline: {str(e)}"}
    
    def _get_timeline_data(self, vis_type: str, data_field: str, data: Dict[str, Any]) -> Tuple[List[Dict], str]:
        """
        Get the appropriate data for the timeline based on visualization type.
        
        Args:
            vis_type: Type of visualization
            data_field: Field name from config
            data: Data dictionary
            
        Returns:
            Tuple of (events_list, field_name_used)
        """
        events = []
        field_used = data_field
        
        # Try different data fields based on visualization type
        potential_fields = [data_field] if data_field else []
        
        if "roadmap" in vis_type.lower():
            potential_fields.extend(["roadmap", "project_roadmap", "milestones", "development_roadmap"])
        elif "milestone" in vis_type.lower():
            potential_fields.extend(["milestones", "project_milestones", "key_milestones"])
        elif "history" in vis_type.lower() or "historical" in vis_type.lower():
            potential_fields.extend(["history", "historical_events", "project_history", "timeline"])
        else:
            potential_fields.extend(["timeline", "events", "key_events"])
        
        # Try each field
        for field in potential_fields:
            if field in data and data[field]:
                events_data = data[field]
                field_used = field
                self.logger.info(f"Using timeline data from '{field}'")
                
                # Parse events based on data format
                if isinstance(events_data, list):
                    # List of event objects
                    if all(isinstance(event, dict) for event in events_data):
                        # Check if we have the required fields
                        if all('date' in event for event in events_data):
                            events = events_data
                            break
                        
                    # List of [date, title, description] entries
                    elif all(isinstance(event, (list, tuple)) for event in events_data):
                        events = []
                        for event in events_data:
                            if len(event) >= 2:
                                event_obj = {
                                    'date': event[0],
                                    'title': event[1],
                                    'description': event[2] if len(event) > 2 else ''
                                }
                                events.append(event_obj)
                        if events:
                            break
                
                # Dictionary with dates as keys
                elif isinstance(events_data, dict):
                    events = []
                    for date, event_info in events_data.items():
                        if isinstance(event_info, str):
                            event_obj = {
                                'date': date,
                                'title': event_info,
                                'description': ''
                            }
                        elif isinstance(event_info, dict):
                            event_obj = {
                                'date': date,
                                'title': event_info.get('title', ''),
                                'description': event_info.get('description', '')
                            }
                        else:
                            continue
                        events.append(event_obj)
                    if events:
                        break
        
        # If no events found, return empty list
        if not events:
            self.logger.warning(f"No valid timeline data found for {vis_type}")
            self.logger.debug(f"Tried fields: {potential_fields}")
            return [], ""
        
        # Ensure all events have the required fields
        for i, event in enumerate(events):
            if 'date' not in event or not event['date']:
                self.logger.warning(f"Event {i} is missing a date, skipping")
                continue
                
            if 'title' not in event or not event['title']:
                event['title'] = f"Event {i+1}"
                
            if 'description' not in event:
                event['description'] = ''
        
        # Filter out events without dates
        events = [event for event in events if 'date' in event and event['date']]
            
        return events, field_used
    
    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse a date string into a datetime object.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            Datetime object
        """
        if not date_str:
            return datetime.now()
            
        try:
            # Try various date formats
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y-%m', '%b %Y', '%B %Y', '%Y'):
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
                    
            # If all formats fail, try to extract year
            if date_str.isdigit() and len(date_str) == 4:
                return datetime(int(date_str), 1, 1)
                
            # Default to current date if parsing fails
            self.logger.warning(f"Failed to parse date: {date_str}")
            return datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error parsing date '{date_str}': {str(e)}")
            return datetime.now()
    
    def _save_chart(self, vis_type: str) -> str:
        """
        Save the chart to a file.
        
        Args:
            vis_type: Type of visualization
            
        Returns:
            File path if successful, empty string otherwise
        """
        # Generate filename
        filename = self.get_safe_filename(vis_type)
        file_path = os.path.join(self.output_dir, filename)
        
        self.logger.info(f"Saving timeline to: {file_path}")
        
        try:
            # Save the figure
            plt.savefig(file_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # Verify the file was saved correctly
            if self.verify_file_saved(file_path):
                return file_path
            return ""
        except Exception as e:
            self.logger.error(f"Error saving timeline: {str(e)}")
            plt.close()
            return "" 