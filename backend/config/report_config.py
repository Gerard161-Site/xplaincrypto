"""
Report configuration for XplainCrypto.
This module provides the configuration for report generation.
"""

import os
from typing import Dict, Any, List

def get_report_config() -> Dict[str, Any]:
    """
    Get the report configuration.
    
    Returns:
        Dictionary containing report configuration
    """
    return {
        "sections": [
            {
                "id": "executive_summary",
                "title": "Executive Summary",
                "content_key": "executive_summary",
                "visualizations": [
                    {
                        "id": "investment_snapshot",
                        "type": "price_chart",
                        "title": "Investment Snapshot",
                        "data_key": "price_data",
                        "show_volume": True,
                        "add_indicators": True,
                        "moving_averages": [7, 30, 90]
                    },
                    {
                        "id": "risk_reward_gauge",
                        "type": "risk_matrix",
                        "title": "Risk-Reward Assessment",
                        "data_key": "risk_data"
                    }
                ]
            },
            {
                "id": "market_analysis",
                "title": "Market Analysis",
                "content_key": "market_analysis",
                "visualizations": [
                    {
                        "id": "market_position",
                        "type": "market_dominance",
                        "title": "Market Position",
                        "data_key": "market_dominance_data"
                    },
                    {
                        "id": "price_comparison",
                        "type": "comparison_chart",
                        "title": "Price Comparison with Major Cryptocurrencies",
                        "data_key": "price_comparison_data",
                        "normalize": True
                    },
                    {
                        "id": "correlation_matrix",
                        "type": "correlation_chart",
                        "title": "Correlation with Major Assets",
                        "data_key": "correlation_data"
                    }
                ]
            },
            {
                "id": "tokenomics",
                "title": "Tokenomics and Distribution",
                "content_key": "tokenomics",
                "visualizations": [
                    {
                        "id": "token_distribution",
                        "type": "token_distribution_pie",
                        "title": "Token Distribution",
                        "data_key": "token_distribution_data",
                        "explode_largest": True,
                        "donut": True
                    },
                    {
                        "id": "token_supply_schedule",
                        "type": "line_chart",
                        "title": "Token Supply Schedule",
                        "data_key": "token_supply_data"
                    },
                    {
                        "id": "token_unlock_events",
                        "type": "token_metrics",
                        "title": "Token Unlock Events",
                        "data_key": "token_unlock_data"
                    }
                ]
            },
            {
                "id": "technology",
                "title": "Technology and Architecture",
                "content_key": "technology",
                "visualizations": [
                    {
                        "id": "tech_stack_comparison",
                        "type": "comparison_bars",
                        "title": "Technology Stack Comparison",
                        "data_key": "tech_comparison_data"
                    }
                ]
            },
            {
                "id": "team",
                "title": "Team and Governance",
                "content_key": "team",
                "visualizations": []
            },
            {
                "id": "adoption",
                "title": "Adoption and Usage Metrics",
                "content_key": "adoption",
                "visualizations": [
                    {
                        "id": "user_growth",
                        "type": "line_chart",
                        "title": "User Growth Over Time",
                        "data_key": "user_growth_data"
                    },
                    {
                        "id": "transaction_volume",
                        "type": "line_chart",
                        "title": "Transaction Volume",
                        "data_key": "transaction_volume_data"
                    }
                ]
            },
            {
                "id": "ecosystem",
                "title": "Ecosystem and Partnerships",
                "content_key": "ecosystem",
                "visualizations": [
                    {
                        "id": "ecosystem_map",
                        "type": "nested_pie",
                        "title": "Ecosystem Map",
                        "data_key": "ecosystem_data"
                    }
                ]
            },
            {
                "id": "competition",
                "title": "Competitive Analysis",
                "content_key": "competition",
                "visualizations": [
                    {
                        "id": "competitor_comparison",
                        "type": "comparison_bars",
                        "title": "Competitor Comparison",
                        "data_key": "competitor_data"
                    },
                    {
                        "id": "market_share",
                        "type": "market_share_pie",
                        "title": "Market Share in Segment",
                        "data_key": "market_share_data",
                        "min_percentage": 3.0
                    }
                ]
            },
            {
                "id": "regulatory",
                "title": "Regulatory Landscape",
                "content_key": "regulatory",
                "visualizations": []
            },
            {
                "id": "risks",
                "title": "Risk Assessment",
                "content_key": "risks",
                "visualizations": [
                    {
                        "id": "risk_matrix",
                        "type": "risk_matrix",
                        "title": "Risk Assessment Matrix",
                        "data_key": "risk_matrix_data"
                    }
                ]
            },
            {
                "id": "roadmap",
                "title": "Roadmap and Future Developments",
                "content_key": "roadmap",
                "visualizations": []
            },
            {
                "id": "community",
                "title": "Community and Social Metrics",
                "content_key": "community",
                "visualizations": [
                    {
                        "id": "social_metrics",
                        "type": "comparison_bars",
                        "title": "Social Media Metrics",
                        "data_key": "social_metrics_data"
                    }
                ]
            },
            {
                "id": "financial",
                "title": "Financial Analysis",
                "content_key": "financial",
                "visualizations": [
                    {
                        "id": "revenue_model",
                        "type": "token_metrics",
                        "title": "Revenue Model",
                        "data_key": "revenue_data"
                    },
                    {
                        "id": "treasury_allocation",
                        "type": "token_distribution_pie",
                        "title": "Treasury Allocation",
                        "data_key": "treasury_data",
                        "explode_largest": False,
                        "donut": True
                    }
                ]
            },
            {
                "id": "conclusion",
                "title": "Conclusion and Investment Thesis",
                "content_key": "conclusion",
                "visualizations": [
                    {
                        "id": "valuation_range",
                        "type": "valuation_range",
                        "title": "Valuation Range Scenarios",
                        "data_key": "valuation_data"
                    }
                ]
            }
        ]
    }
