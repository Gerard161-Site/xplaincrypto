import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from backend.visualizations.plotly_visualizer import PlotlyVisualizer
from backend.utils.style_utils import StyleManager

class TableVisualizer(PlotlyVisualizer):
    """
    Visualizer for creating table visualizations using Plotly.
    Handles key metrics, adoption metrics, and other tabular data.
    """
    
    def __init__(self, theme: str = 'light', pdf_optimized: bool = True, project_name: str = None, 
                 style_manager: Optional[StyleManager] = None, logger=None):
        """
        Initialize the table visualizer
        
        Args:
            theme: Visual theme ('light' or 'dark')
            pdf_optimized: Whether to optimize for PDF output
            project_name: Project name for file paths
            style_manager: Optional StyleManager for consistent styling
            logger: Optional logger instance
        """
        super().__init__(theme, pdf_optimized, project_name, style_manager, logger)
        self.using_real_data = False
    
    def create(self, viz_type: str, config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a table visualization.
        
        Args:
            viz_type: Type of visualization
            config: Configuration for the visualization 
            data: Data for the visualization
            
        Returns:
            Dict with visualization result information
        """
        try:
            self.logger.info(f"Creating {viz_type} visualization")
            
            # Output filename
            output_filename = config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            
            # Create title from viz_type if not provided
            title = config.get("title", viz_type.replace("_", " ").title())
            
            # Process data based on table type
            if viz_type == "key_metrics_table":
                try:
                    metrics = self._extract_key_metrics(data, viz_type)
                    # Convert metrics dictionary to list of row data for Plotly
                    table_data = [{"Metric": k, "Value": v} for k, v in metrics.items()]
                except Exception as e:
                    self.logger.error(f"Error extracting key metrics: {str(e)}")
                    return self.create_error_chart(f"Error creating metrics table: {str(e)}", output_path)
                
            elif viz_type == "adoption_metrics_table":
                try:
                    metrics = self._extract_adoption_metrics(data)
                    # Convert metrics dictionary to list of row data for Plotly
                    table_data = [{"Metric": k, "Value": v} for k, v in metrics.items()]
                except Exception as e:
                    self.logger.error(f"Error extracting adoption metrics: {str(e)}")
                    return self.create_error_chart(f"Error creating adoption metrics table: {str(e)}", output_path)
                
            else:
                # Generic table data
                try:
                    generic_data = self._extract_generic_table_data(data, viz_type)
                    
                    # Convert to a standard format depending on input
                    if isinstance(generic_data, dict):
                        table_data = [{"Metric": k, "Value": v} for k, v in generic_data.items()]
                    elif isinstance(generic_data, pd.DataFrame):
                        table_data = generic_data.to_dict('records')
                    elif isinstance(generic_data, list) and all(isinstance(item, dict) for item in generic_data):
                        table_data = generic_data
                    else:
                        self.logger.warning(f"Unsupported data format for table: {type(generic_data)}")
                        return self.create_error_chart("Unsupported data format for table visualization", output_path)
                except Exception as e:
                    self.logger.error(f"Error processing table data: {str(e)}")
                    return self.create_error_chart(f"Error creating table: {str(e)}", output_path)
            
            # Create Plotly table figure
            return self._create_plotly_table(viz_type, title, table_data, output_path)
            
        except Exception as e:
            self.logger.error(f"Error in TableVisualizer.create: {str(e)}")
            return {
                "error": f"Error creating table visualization: {str(e)}",
                "success": False
            }
    
    def _create_table(self, viz_type: str, config: Dict[str, Any], table_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a table visualization.
        
        Args:
            viz_type: Type of visualization
            config: Visualization configuration
            table_data: Data for the table
            
        Returns:
            Dictionary with visualization result
        """
        try:
            # Output filename
            output_filename = config.get("output_filename", f"{self.project_name.lower()}_{viz_type}")
            output_path = os.path.join(self.output_dir, f"{output_filename}.png")
            
            # Get title from config or default
            title = config.get("title", f"{self.project_name} Metrics")
            
            # Create HTML table
            html = self._generate_table_html(table_data, title, config)
            
            # Save HTML to a file
            html_path = os.path.join(self.output_dir, f"{output_filename}.html")
            with open(html_path, "w") as f:
                f.write(html)
            
            # Convert HTML to image
            success, img_path = self._export_html_to_image(html_path, output_path)
            
            if success:
                self.logger.info(f"Successfully created table visualization at {img_path}")
                return {
                    "file_path": img_path,
                    "html_path": html_path,
                    "success": True
                }
            else:
                self.logger.error(f"Failed to create image from HTML table")
                return {
                    "error": "Failed to create image from HTML table",
                    "html_path": html_path,
                    "success": False
                }
                
        except Exception as e:
            self.logger.error(f"Error creating table visualization: {str(e)}")
            return {"error": f"Error creating table: {str(e)}", "success": False}
    
    def _create_plotly_table(self, viz_type: str, title: str, data: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
        """
        Create a table visualization using Plotly.
        
        Args:
            viz_type: Type of visualization
            title: Table title
            data: List of dictionaries with row data
            output_path: Path to save the output
            
        Returns:
            Dictionary with visualization result
        """
        try:
            # Extract headers and cells from data
            if not data:
                return self.create_error_chart("No data available for table visualization", output_path)
                
            # Get column headers
            headers = list(data[0].keys())
            
            # Get values for each column
            cells = []
            for header in headers:
                column_values = [str(row.get(header, "N/A")) for row in data]
                cells.append(column_values)
            
            # Configure colors based on theme
            if self.theme == 'dark':
                header_color = '#2c3e50'
                cell_color = '#1e293b'
                font_color = 'white'
                line_color = '#475569'
            else:
                header_color = '#2c3e50'
                cell_color = 'white'
                font_color = 'black'
                line_color = '#e2e8f0'
            
            # Create Plotly table
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=headers,
                    line_color=line_color,
                    fill_color=header_color,
                    align='left',
                    font=dict(color=font_color, size=14),
                    height=40
                ),
                cells=dict(
                    values=cells,
                    line_color=line_color,
                    fill_color=cell_color,
                    align='left',
                    font=dict(color=font_color, size=12),
                    height=30
                )
            )])
            
            # Update layout
            fig.update_layout(
                title=title,
                title_font=dict(size=18, color=font_color if self.theme == 'dark' else '#2c3e50'),
                margin=dict(l=20, r=20, t=50, b=20),
                height=100 + (len(data) * 30) + 50,  # Dynamic height based on number of rows
                width=self.width,
                paper_bgcolor='rgba(0,0,0,0)' if self.theme == 'dark' else 'white',
                plot_bgcolor='rgba(0,0,0,0)' if self.theme == 'dark' else 'white'
            )
            
            # Create the directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save the figure
            fig.write_image(output_path, scale=2)
            
            return {
                "success": True,
                "file_path": output_path,
                "title": title
            }
        
        except Exception as e:
            self.logger.error(f"Error creating Plotly table: {str(e)}")
            return self.create_error_chart(f"Error creating table: {str(e)}", output_path)
    
    def _prepare_table_data(self, data: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
        """
        Prepare data for table visualization
        
        Args:
            data: Input data in various formats
            
        Returns:
            Tuple of (headers, values)
        """
        # For dictionary-style data (common for metrics tables)
        if isinstance(data, dict) and not any(isinstance(v, dict) for v in data.values()):
            headers = ["Metric", "Value"]
            # Transpose data into columns format
            metrics = list(data.keys())
            values = [
                metrics,
                [self._format_table_value(data[metric], metric) for metric in metrics]
            ]
            return headers, values
        
        # For list of dictionaries
        elif isinstance(data, list) and all(isinstance(item, dict) for item in data):
            # Get all unique keys
            all_keys = set()
            for item in data:
                all_keys.update(item.keys())
            
            headers = list(all_keys)
            values = []
            for key in headers:
                values.append([self._format_table_value(item.get(key, "N/A"), key) for item in data])
            
            return headers, values
        
        # For DataFrame
        elif isinstance(data, pd.DataFrame):
            headers = list(data.columns)
            values = [data[col].tolist() for col in headers]
            return headers, values
        
        # Fallback for simple list/tuple data
        elif isinstance(data, (list, tuple)):
            if len(data) == 2 and isinstance(data[0], list) and isinstance(data[1], list):
                # Assume it's already in [headers, values] format
                return data[0], [data[1]]
            else:
                # Convert simple list to single column
                return ["Value"], [data]
        
        # Default empty table
        return ["Metric", "Value"], [[], []]
    
    def _format_table_value(self, value: Any, key: str = None) -> str:
        """
        Format a value for display in a table
        
        Args:
            value: Value to format
            key: Table key/header associated with the value
            
        Returns:
            Formatted string
        """
        if value is None or pd.isna(value):
            return "N/A"
        
        # Check if value needs special formatting
        if key and key.lower():
            key_lower = key.lower()
            
            # Currency formatting for financial metrics
            if any(term in key_lower for term in ["price", "market_cap", "tvl", "volume", "liquidity", "value"]):
                return self._format_currency(value)
                
            # Percentage formatting
            elif any(term in key_lower for term in ["percent", "change", "growth", "apy", "yield", "rate"]):
                return self._format_percentage(value)
                
            # Integer formatting
            elif any(term in key_lower for term in ["count", "number", "supply", "holders", "wallets", "rank"]):
                if isinstance(value, (int, float)):
                    return self._format_number(value)
        
        # Default formatting
        if isinstance(value, (int, float)):
            return self._format_number(value)
        
        # Return as string
        return str(value)
    
    def _format_currency(self, value: Union[int, float, str]) -> str:
        """Format a currency value with appropriate symbols"""
        try:
            if isinstance(value, str):
                # Remove any currency symbols and commas
                value = value.replace('$', '').replace(',', '')
                value = float(value)
            
            if value < 0.01:
                return f"${value:.8f}"
            elif value < 1:
                return f"${value:.4f}"
            elif value < 1000:
                return f"${value:.2f}"
            elif value < 1000000:
                return f"${value/1000:.2f}K"
            elif value < 1000000000:
                return f"${value/1000000:.2f}M"
            else:
                return f"${value/1000000000:.2f}B"
        except Exception:
            return str(value)
    
    def _format_number(self, value: Union[int, float, str]) -> str:
        """Format a large number with appropriate separators"""
        try:
            if isinstance(value, str):
                # Remove any commas
                value = value.replace(',', '')
                value = float(value)
            
            if value < 1000:
                return f"{value:.0f}"
            elif value < 1000000:
                return f"{value/1000:.2f}K"
            elif value < 1000000000:
                return f"{value/1000000:.2f}M"
            else:
                return f"{value/1000000000:.2f}B"
        except Exception:
            return str(value)
    
    def _format_percentage(self, value: Union[int, float, str]) -> str:
        """Format a percentage value"""
        try:
            if isinstance(value, str):
                # Remove any % signs
                value = value.replace('%', '')
                value = float(value)
            
            return f"{value:.2f}%"
        except Exception:
            return str(value)
    
    def _extract_key_metrics(self, data: Dict[str, Any], viz_type: str) -> Dict[str, Any]:
        """
        Extract key metrics from various sources with improved data mapping.
        
        Args:
            data: Data dictionary from multiple potential sources
            viz_type: Type of visualization
            
        Returns:
            Dictionary with metrics suitable for tabular display
        """
        metrics = {}
        found_any_metrics = False
        
        # First define expected metrics based on visualization type
        if viz_type == 'key_metrics_table':
            expected_metrics = {
                "Price (USD)": "N/A",
                "Market Cap (USD)": "N/A",
                "24h Volume (USD)": "N/A",
                "Circulating Supply": "N/A",
                "Total Supply": "N/A",
                "Max Supply": "N/A",
                "24h Change (%)": "N/A"
            }
        elif viz_type == 'adoption_metrics_table':
            expected_metrics = {
                "Total Value Locked (USD)": "N/A",
                "Active Addresses (24h)": "N/A",
                "Transactions (24h)": "N/A",
                "Exchange Count": "N/A",
                "GitHub Activity (30d)": "N/A",
                "Social Media Activity": "N/A",
                "Developer Count": "N/A"
            }
        else:
            # Generic metrics table
            expected_metrics = {}
            
        # Start with placeholder values
        metrics = expected_metrics.copy()
            
        try:
            # Extract metrics from CoinMarketCap data
            if 'coinmarketcap' in data:
                cmc_data = data['coinmarketcap']
                
                # Map fields to metric names for key_metrics_table
                if viz_type == 'key_metrics_table':
                    field_map = {
                        'current_price': 'Price (USD)',
                        'market_cap': 'Market Cap (USD)',
                        '24h_volume': '24h Volume (USD)',
                        'volume_24h': '24h Volume (USD)',
                        'circulating_supply': 'Circulating Supply',
                        'total_supply': 'Total Supply',
                        'max_supply': 'Max Supply',
                        'price_change_percentage_24h': '24h Change (%)'
                    }
                    
                    for field, metric in field_map.items():
                        if field in cmc_data and cmc_data[field] is not None:
                            if 'price' in field.lower() or 'volume' in field.lower() or 'market' in field.lower():
                                # Format currency values
                                metrics[metric] = self._format_currency(cmc_data[field])
                            elif 'supply' in field.lower():
                                # Format large numbers
                                metrics[metric] = self._format_number(cmc_data[field])
                            elif 'percentage' in field.lower() or 'change' in field.lower():
                                # Format percentages
                                metrics[metric] = self._format_percentage(cmc_data[field])
                            else:
                                metrics[metric] = str(cmc_data[field])
                            
                            found_any_metrics = True
                
                # Map fields for adoption metrics table
                elif viz_type == 'adoption_metrics_table':
                    if 'exchange_count' in cmc_data:
                        metrics['Exchange Count'] = cmc_data['exchange_count']
                        found_any_metrics = True
                    if 'social_score' in cmc_data:
                        metrics['Social Media Activity'] = cmc_data['social_score']
                        found_any_metrics = True
            
            # Extract metrics from DeFiLlama
            if 'defillama' in data:
                tvl_data = data['defillama']
                if isinstance(tvl_data, dict):
                    if 'tvl' in tvl_data and tvl_data['tvl'] is not None:
                        metrics['Total Value Locked (USD)'] = self._format_currency(tvl_data['tvl'])
                        found_any_metrics = True
                    
                    # Try to extract other DeFiLlama metrics for adoption table
                    if viz_type == 'adoption_metrics_table':
                        if 'active_addresses_24h' in tvl_data:
                            metrics['Active Addresses (24h)'] = self._format_number(tvl_data['active_addresses_24h'])
                            found_any_metrics = True
                        if 'transactions_24h' in tvl_data:
                            metrics['Transactions (24h)'] = self._format_number(tvl_data['transactions_24h'])
                            found_any_metrics = True
                        
            # Extract metrics from CoinGecko
            if 'coingecko' in data:
                cg_data = data['coingecko']
                
                # Similar field mapping as CMC but for CoinGecko
                field_map = {
                    'current_price': 'Price (USD)',
                    'market_cap': 'Market Cap (USD)',
                    'total_volume': '24h Volume (USD)',
                    'circulating_supply': 'Circulating Supply',
                    'total_supply': 'Total Supply',
                    'max_supply': 'Max Supply',
                    'price_change_percentage_24h': '24h Change (%)'
                }
                
                for field, metric in field_map.items():
                    if isinstance(cg_data, dict) and field in cg_data and cg_data[field] is not None:
                        if 'price' in field.lower() or 'volume' in field.lower() or 'market' in field.lower():
                            metrics[metric] = self._format_currency(cg_data[field])
                        elif 'supply' in field.lower():
                            metrics[metric] = self._format_number(cg_data[field])
                        elif 'percentage' in field.lower() or 'change' in field.lower():
                            metrics[metric] = self._format_percentage(cg_data[field])
                        else:
                            metrics[metric] = str(cg_data[field])
                        
                        found_any_metrics = True
            
            # If we didn't find any metrics but we have data, log a warning
            if not found_any_metrics and data:
                self.logger.warning("No price data found in any cache source")
                self.logger.warning("Using 'Data Unavailable' placeholders")
                
                # We'll still return the metrics dictionary with placeholders
                # This ensures we always show something and won't fail
            
            return metrics
        
        except Exception as e:
            self.logger.error(f"Error extracting key metrics: {str(e)}")
            # Return placeholder metrics if extraction fails
            return expected_metrics
    
    def _extract_adoption_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract adoption metrics from various sources with improved data mapping.
        
        Args:
            data: Data dictionary from multiple potential sources
            
        Returns:
            Dictionary with adoption metrics
        """
        metrics = {}
        
        try:
            # First try to use the provided data
            if isinstance(data, dict) and data:
                # Check for TVL and chain data from defillama
                if "defillama" in data:
                    dl_data = data["defillama"]
                    
                    # Extract data field if present
                    if isinstance(dl_data, dict):
                        if "data" in dl_data:
                            dl_data = dl_data["data"]
                        
                        # Extract TVL with flexible field mapping
                        tvl_fields = ["tvl", "totalLiquidityUSD", "total_value_locked", "value_locked"]
                        for field in tvl_fields:
                            if field in dl_data and isinstance(dl_data[field], (int, float)):
                                metrics["TVL (USD)"] = dl_data[field]
                                break
                        
                        # Try TVL from history array if direct field not found
                        if "TVL (USD)" not in metrics and "tvl" in dl_data and isinstance(dl_data["tvl"], list) and dl_data["tvl"]:
                            latest_tvl = dl_data["tvl"][-1]
                            if isinstance(latest_tvl, dict) and "totalLiquidityUSD" in latest_tvl:
                                metrics["TVL (USD)"] = latest_tvl["totalLiquidityUSD"]
                            elif isinstance(latest_tvl, dict) and "tvl" in latest_tvl:
                                metrics["TVL (USD)"] = latest_tvl["tvl"]
                            elif isinstance(latest_tvl, list) and len(latest_tvl) >= 2:
                                metrics["TVL (USD)"] = latest_tvl[1]  # [timestamp, value] format
                        
                        # Extract chain count
                        if "chains" in dl_data:
                            chains = dl_data["chains"]
                            if isinstance(chains, list):
                                metrics["Blockchain Networks"] = len(chains)
                            elif isinstance(chains, dict):
                                metrics["Blockchain Networks"] = len(chains.keys())
                
                # Check for market data from coinmarketcap
                if "coinmarketcap" in data:
                    cmc_data = data["coinmarketcap"]
                    
                    # Extract data field if present
                    if isinstance(cmc_data, dict):
                        if "data" in cmc_data:
                            cmc_data = cmc_data["data"]
                        
                        # Extract market info with flexible field mapping
                        field_mappings = [
                            (["num_market_pairs", "marketPairs", "exchange_count"], "Exchange Listings"),
                            (["market_cap", "marketCap"], "Market Cap (USD)"),
                            (["volume_24h", "24h_volume", "volume", "total_volume"], "24h Volume (USD)"),
                            (["active_addresses", "address_count"], "Active Addresses"),
                            (["social_activity", "social_volume"], "Social Activity Score")
                        ]
                        
                        for field_options, display_name in field_mappings:
                            for field in field_options:
                                if field in cmc_data and cmc_data[field] is not None:
                                    metrics[display_name] = cmc_data[field]
                                    break
                
                # Additional data from Coingecko
                if "coingecko" in data and len(metrics) < 3:
                    cg_data = data["coingecko"]
                    
                    # Extract data field if present
                    if isinstance(cg_data, dict):
                        if "data" in cg_data:
                            cg_data = cg_data["data"]
                        
                        # Add missing metrics if available in coingecko data
                        if "Market Cap (USD)" not in metrics and "market_cap" in cg_data:
                            metrics["Market Cap (USD)"] = cg_data["market_cap"]
                        if "24h Volume (USD)" not in metrics and "total_volume" in cg_data:
                            metrics["24h Volume (USD)"] = cg_data["total_volume"]
                        if "community_data" in cg_data and isinstance(cg_data["community_data"], dict):
                            comm_data = cg_data["community_data"]
                            if "Social Activity Score" not in metrics and "twitter_followers" in comm_data:
                                metrics["Social Activity Score"] = comm_data["twitter_followers"]
            
            # If metrics are still empty, use direct cache loading
            if not metrics:
                # Try loading from defillama cache
                try:
                    dl_data = self._extract_data_from_cache("tvl", ["defillama"])
                    if dl_data:
                        self.using_real_data = True
                        
                        # Extract data field if present
                        if isinstance(dl_data, dict) and "data" in dl_data:
                            dl_data = dl_data["data"]
                        
                        # Extract TVL with flexible field mapping
                        tvl_fields = ["tvl", "totalLiquidityUSD", "total_value_locked", "value_locked"]
                        for field in tvl_fields:
                            if field in dl_data and isinstance(dl_data[field], (int, float)):
                                metrics["TVL (USD)"] = dl_data[field]
                                break
                        
                        # Try TVL from history array if direct field not found
                        if "TVL (USD)" not in metrics and "tvl" in dl_data and isinstance(dl_data["tvl"], list) and dl_data["tvl"]:
                            latest_tvl = dl_data["tvl"][-1]
                            if isinstance(latest_tvl, dict) and "totalLiquidityUSD" in latest_tvl:
                                metrics["TVL (USD)"] = latest_tvl["totalLiquidityUSD"]
                            elif isinstance(latest_tvl, dict) and "tvl" in latest_tvl:
                                metrics["TVL (USD)"] = latest_tvl["tvl"]
                            elif isinstance(latest_tvl, list) and len(latest_tvl) >= 2:
                                metrics["TVL (USD)"] = latest_tvl[1]  # [timestamp, value] format
                        
                        # Extract chain count
                        if "chains" in dl_data:
                            chains = dl_data["chains"]
                            if isinstance(chains, list):
                                metrics["Blockchain Networks"] = len(chains)
                            elif isinstance(chains, dict):
                                metrics["Blockchain Networks"] = len(chains.keys())
                except Exception as e:
                    self.logger.warning(f"Error loading defillama data: {str(e)}")
                
                # Try loading from coinmarketcap cache
                try:
                    cmc_data = self._extract_data_from_cache("data", ["coinmarketcap"])
                    if not cmc_data:
                        # Try alternate file formats
                        cmc_data = self._extract_data_from_cache("price", ["coinmarketcap"])
                    
                    if cmc_data:
                        self.using_real_data = True
                        
                        # Extract data field if present
                        if isinstance(cmc_data, dict) and "data" in cmc_data:
                            cmc_data = cmc_data["data"]
                        
                        # Extract market info with flexible field mapping
                        field_mappings = [
                            (["num_market_pairs", "marketPairs", "exchange_count"], "Exchange Listings"),
                            (["market_cap", "marketCap"], "Market Cap (USD)"),
                            (["volume_24h", "24h_volume", "volume", "total_volume"], "24h Volume (USD)"),
                            (["active_addresses", "address_count"], "Active Addresses"),
                            (["social_activity", "social_volume"], "Social Activity Score")
                        ]
                        
                        for field_options, display_name in field_mappings:
                            for field in field_options:
                                if field in cmc_data and cmc_data[field] is not None:
                                    metrics[display_name] = cmc_data[field]
                                    break
                except Exception as e:
                    self.logger.warning(f"Error loading coinmarketcap data: {str(e)}")
            
            # If still not enough metrics, display unavailable indicators
            # but NEVER use synthetic/fake data
            if len(metrics) < 2:
                self.logger.warning("Insufficient metrics found, adding 'Data Unavailable' placeholders")
                missing_keys = [
                    "TVL (USD)", "Exchange Listings", "Blockchain Networks", 
                    "Market Cap (USD)", "24h Volume (USD)", "Active Addresses"
                ]
                
                for key in missing_keys:
                    if key not in metrics:
                        # Use unavailable marker instead of fake data
                        metrics[key] = "Data Unavailable"
            
            # Return metrics
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error extracting adoption metrics: {str(e)}")
            return {
                "TVL (USD)": "Data Unavailable",
                "Exchange Listings": "Data Unavailable",
                "Blockchain Networks": "Data Unavailable",
                "Market Cap (USD)": "Data Unavailable",
                "24h Volume (USD)": "Data Unavailable",
                "Active Addresses": "Data Unavailable"
            }
    
    def _extract_generic_table_data(self, data: Dict[str, Any], viz_type: str) -> Dict[str, Any]:
        """
        Extract generic table data from various sources
        
        Args:
            data: Data dictionary
            viz_type: Type of visualization
            
        Returns:
            Dictionary or list with table data
        """
        try:
            # If data is already in table format, return it
            if isinstance(data, (pd.DataFrame, list)):
                return data
            
            # Extract potential table data from the input data
            if isinstance(data, dict):
                # Check if there's a section matching the viz_type
                section_name = viz_type.replace("_table", "")
                
                if section_name in data:
                    return data[section_name]
                
                # Check in data field
                if "data" in data:
                    data_obj = data["data"]
                    
                    # Check for section in data
                    if isinstance(data_obj, dict) and section_name in data_obj:
                        return data_obj[section_name]
                    
                    # Try to find a key that contains the section name
                    for key in data_obj:
                        if section_name in key.lower():
                            return data_obj[key]
                
                # If all else fails, return data as is
                return data
            
            # If data is None, return empty dict
            return {}
            
        except Exception as e:
            self.logger.error(f"Error extracting generic table data: {str(e)}")
            return {}
    
    def _create_table_html(self, viz_type: str, config: Dict[str, Any], table_data: Dict[str, Any]) -> str:
        """
        Create an HTML representation of the table.
        
        Args:
            viz_type: Type of visualization
            config: Visualization configuration
            table_data: Data for the table
            
        Returns:
            HTML string of the table
        """
        # Get title from config or default
        title = config.get("title", viz_type.replace("_", " ").title())
        
        # Set up the HTML with a nicer style
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    padding: 0;
                }}
                .table-container {{
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    margin-bottom: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    text-align: left;
                    font-size: 14px;
                }}
                th {{
                    background-color: #2c3e50;
                    color: white;
                    padding: 12px 15px;
                    font-weight: bold;
                }}
                td {{
                    padding: 12px 15px;
                    border-bottom: 1px solid #ddd;
                }}
                tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
                tr:hover {{
                    background-color: #e9e9e9;
                }}
                h2 {{
                    color: #2c3e50;
                    margin-bottom: 15px;
                    font-size: 20px;
                }}
                .data-unavailable {{
                    color: #999;
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <h2>{title}</h2>
            <div class="table-container">
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
        """
        
        # Add each row
        for metric, value in table_data.items():
            # If it's N/A or Data Unavailable, add special class
            if value == "N/A" or value == "Data Unavailable":
                html += f"""
                    <tr>
                        <td>{metric}</td>
                        <td class="data-unavailable">{value}</td>
                    </tr>
                """
            else:
                html += f"""
                    <tr>
                        <td>{metric}</td>
                        <td>{value}</td>
                    </tr>
                """
        
        # Close HTML
        html += """
                </table>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _export_html_to_image(self, html: str, output_path: str) -> None:
        """
        Export HTML to an image file.
        
        Args:
            html: HTML content to convert
            output_path: Path to save the image
        """
        try:
            # Try to import the required libraries
            try:
                import imgkit
                # ImgKit is available, use it
                options = {
                    'format': 'png',
                    'encoding': "UTF-8",
                    'width': 800,
                    'quiet': ''
                }
                imgkit.from_string(html, output_path, options=options)
                self.logger.info(f"Table saved to {output_path} using imgkit")
                return
            except ImportError:
                pass
            
            # If both libraries are missing, fall back to creating a text file
            self.logger.warning("HTML-to-image conversion libraries not available, using text fallback")
            
            # Create a text version of the table
            import re
            
            # Extract table data from HTML
            table_data = []
            rows = re.findall(r'<tr>(.*?)</tr>', html, re.DOTALL)
            
            for row in rows:
                cols = re.findall(r'<t[hd]>(.*?)</t[hd]>', row, re.DOTALL)
                table_data.append(cols)
            
            # Create a text representation
            text_table = ""
            if len(table_data) > 0:
                # Add title (extract from h2 tag)
                title_match = re.search(r'<h2>(.*?)</h2>', html)
                if title_match:
                    text_table += f"{title_match.group(1)}\n"
                    text_table += "=" * len(title_match.group(1)) + "\n\n"
                
                # Create the table
                if len(table_data) > 1:  # Has header row
                    header = table_data[0]
                    max_widths = [len(col) for col in header]
                    
                    # Calculate max width for each column
                    for row in table_data[1:]:
                        for i, col in enumerate(row):
                            if i < len(max_widths):
                                max_widths[i] = max(max_widths[i], len(col))
                    
                    # Print header
                    header_line = " | ".join(col.ljust(max_widths[i]) for i, col in enumerate(header))
                    text_table += header_line + "\n"
                    text_table += "-" * len(header_line) + "\n"
                    
                    # Print data rows
                    for row in table_data[1:]:
                        text_table += " | ".join(col.ljust(max_widths[i]) if i < len(max_widths) else col 
                                                 for i, col in enumerate(row)) + "\n"
            
            # Save as text file
            txt_path = output_path.replace('.png', '.txt')
            with open(txt_path, 'w') as f:
                f.write(text_table)
            
            # Return success with the text file path
            self.logger.info(f"Table saved as text file: {txt_path}")
            return
            
        except Exception as e:
            self.logger.error(f"Failed to export table to image or text: {str(e)}")
            # Create a simple emergency fallback
            fallback_path = output_path.replace('.png', '.txt')
            with open(fallback_path, 'w') as f:
                f.write(f"HTML Table Data (Error: {str(e)})\n\n{html[:500]}...")
            
            self.logger.info(f"Emergency fallback text file created: {fallback_path}")
            return
    
    def create_error_table(self, error_message: str, output_path: str) -> Dict[str, Any]:
        """
        Create an error table when visualization creation fails.
        
        Args:
            error_message: Error message to display
            output_path: Path to save the error table
            
        Returns:
            Dict with visualization result
        """
        # Create a simple HTML error table
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    padding: 0;
                }}
                .error-container {{
                    border: 1px solid #e74c3c;
                    border-radius: 8px;
                    padding: 15px;
                    background-color: #fff;
                    max-width: 800px;
                    margin: 0 auto;
                }}
                h2 {{
                    color: #e74c3c;
                    margin-top: 0;
                }}
                p {{
                    color: #333;
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h2>Data Visualization Error</h2>
                <p>{error_message}</p>
                <p>Please check the available data sources or try again later.</p>
            </div>
        </body>
        </html>
        """
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Try to export as image
        try:
            self._export_html_to_image(html, output_path)
            
            return {
                "success": False,
                "file_path": output_path,
                "error": error_message
            }
        except Exception as e:
            # If image export fails, create a text file as fallback
            fallback_path = output_path.replace('.png', '.txt')
            with open(fallback_path, 'w') as f:
                f.write(f"ERROR: {error_message}")
                
            return {
                "success": False,
                "file_path": fallback_path,
                "error": f"{error_message} (with image export error: {str(e)})"
            } 