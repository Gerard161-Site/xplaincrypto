"""Utility for formatting numbers in a human-readable way."""

from typing import Union, Tuple
import math

class NumberFormatter:
    """Formats numbers in a human-readable way."""
    
    @staticmethod
    def format_number(value: Union[int, float], precision: int = 1) -> str:
        """
        Format a number to human readable format with B/M/K suffixes.
        
        Args:
            value: Number to format
            precision: Number of decimal places to show
            
        Returns:
            Formatted string like "1.2B", "3M", "500K", etc.
        """
        if value is None:
            return "N/A"
            
        try:
            value = float(value)
        except (TypeError, ValueError):
            return str(value)
            
        if value == 0:
            return "0"
            
        # Handle negative numbers
        sign = "-" if value < 0 else ""
        value = abs(value)
        
        # Define suffixes and their corresponding powers of 1000
        suffixes = [
            (1e12, "T"),  # Trillion
            (1e9, "B"),   # Billion
            (1e6, "M"),   # Million
            (1e3, "K"),   # Thousand
            (1, "")       # No suffix
        ]
        
        # Find appropriate suffix
        for factor, suffix in suffixes:
            if value >= factor:
                scaled = value / factor
                # If the scaled value is an integer, don't show decimal places
                if scaled.is_integer():
                    return f"{sign}{int(scaled)}{suffix}"
                # Otherwise format with specified precision
                return f"{sign}{scaled:.{precision}f}{suffix}"
        
        # For very small numbers, use scientific notation
        return f"{sign}{value:.{precision}e}"
    
    @staticmethod
    def format_currency(value: Union[int, float], currency: str = "$", precision: int = 2) -> str:
        """
        Format a currency value with appropriate suffix.
        
        Args:
            value: Number to format
            currency: Currency symbol to use
            precision: Number of decimal places for non-integer values
            
        Returns:
            Formatted string like "$1.2B", "$3M", etc.
        """
        if value is None:
            return "N/A"
            
        try:
            value = float(value)
        except (TypeError, ValueError):
            return str(value)
            
        # Special handling for values less than 1
        if 0 < abs(value) < 1:
            return f"{currency}{value:.{precision}f}"
            
        formatted = NumberFormatter.format_number(value, precision)
        if formatted == "N/A" or formatted.startswith("-"):
            return f"{formatted}"
        return f"{currency}{formatted}"
    
    @staticmethod
    def format_percentage(value: Union[int, float], precision: int = 1) -> str:
        """
        Format a number as a percentage.
        
        Args:
            value: Number to format (actual value, not percentage)
            precision: Number of decimal places to show
            
        Returns:
            Formatted string like "12.3%"
        """
        if value is None:
            return "N/A"
            
        try:
            value = float(value) * 100  # Convert to percentage
            if value.is_integer():
                return f"{int(value)}%"
            return f"{value:.{precision}f}%"
        except (TypeError, ValueError):
            return str(value) 