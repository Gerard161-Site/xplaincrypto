from typing import List, Dict, Any
import logging
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from backend.research.core import ResearchNode, ResearchType
from backend.retriever.tavily_search import TavilySearch
import json

class ResearchAgent(ABC):
    """Base abstract class for all research agents."""
    
    def __init__(
        self, 
        llm: ChatOpenAI,
        logger: logging.Logger,
        include_domains: List[str] = None,
        exclude_domains: List[str] = None
    ):
        self.llm = llm
        self.logger = logger
        self.include_domains = include_domains or []
        self.exclude_domains = exclude_domains or []
    
    @abstractmethod
    def research(self, node: ResearchNode) -> ResearchNode:
        """Execute research on the given node."""
        pass
    
    def _search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Execute a web search using Tavily."""
        self.logger.info(f"Searching web for: {query}")
        
        try:
            tavily = TavilySearch(
                query=query,
                topic="general",
                include_domains=self.include_domains,
                exclude_domains=self.exclude_domains,
                logger=self.logger
            )
            self.logger.debug(f"Created TavilySearch instance with query: {query[:50]}...")
            results = tavily.search(max_results=max_results)
            self.logger.info(f"Web search returned {len(results)} results")
            self.logger.debug(f"First result URL: {results[0]['href'] if results else 'None'}")
            return results
        except Exception as e:
            self.logger.error(f"Web search error: {str(e)}", exc_info=True)
            return []
    
    def _summarize_content(self, content: str, query: str) -> str:
        """Summarize research content with a focus on factual information."""
        self.logger.info(f"Summarizing content for query: {query}")
        
        try:
            prompt = (
                f"Below is research content about cryptocurrency. Summarize it to answer the query: \"{query}\"\n\n"
                f"IMPORTANT GUIDELINES:\n"
                f"1. Focus ONLY on FACTUAL and VERIFIABLE information. Prioritize concrete data points like statistics, numbers, and metrics.\n"
                f"2. Include specific dates for events, exact numbers for metrics, and precise percentages when available.\n"
                f"3. Cite sources for each major claim using [Source X] notation, where X corresponds to the URL order in the references.\n"
                f"4. EXCLUDE speculation, opinions, and promotional content unless clearly labeled as such.\n"
                f"5. Use comparative data when available (e.g., \"increased by X% from previous period\").\n"
                f"6. Prioritize information from reputable sources like established crypto news sites, official documentation, academic papers.\n"
                f"7. Organize information by factual categories: technical specifications, market data, governance structure, etc.\n"
                f"8. Include limitations or caveats about the data when relevant.\n\n"
                f"RESEARCH CONTENT:\n{content}\n\n"
                f"Provide a concise, fact-focused summary answering the query. Include relevant numerical data and proper citations."
            )
            
            self.logger.debug(f"Sending prompt to LLM for summarization, query: {query}")
            response = self.llm.invoke(prompt)
            self.logger.debug(f"Received response from LLM, length: {len(response.content) if response.content else 0}")
            return response.content
        except Exception as e:
            self.logger.error(f"Summarization error: {str(e)}", exc_info=True)
            return f"Summarization failed: {str(e)}"

class TechnicalAgent(ResearchAgent):
    """Agent specialized in researching technical aspects of crypto projects."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["github.com", "docs.uniswap.org", "ethereum.org", "medium.com", "vitalik.ca"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"TechnicalAgent researching: {node.query}")
        try:
            enhanced_query = f"{node.query} cryptocurrency blockchain technical architecture"
            self.logger.debug(f"Enhanced query: {enhanced_query}")
            
            results = self._search_web(enhanced_query)
            if results:
                self.logger.debug(f"Processing {len(results)} search results")
                node.content = "\n\n".join([r['body'] for r in results])
                node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in results]
                node.summary = self._summarize_content(node.content, node.query)
                self.logger.debug(f"Node summary length: {len(node.summary)}")
            else:
                self.logger.warning("No search results found, setting default summary")
                node.summary = "No technical information found."
            
            self.logger.info(f"TechnicalAgent completed research for: {node.query}")
            return node
        except Exception as e:
            self.logger.error(f"Error in TechnicalAgent.research: {str(e)}", exc_info=True)
            # Make sure we still return the node even if we encounter an error
            node.summary = f"Research failed: {str(e)}"
            return node

class TokenomicsAgent(ResearchAgent):
    """Agent specialized in researching tokenomics and distribution."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["coingecko.com", "coinmarketcap.com", "messari.io", "etherscan.io", "blockchain.com", "defillama.com"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"TokenomicsAgent researching: {node.query}")
        try:
            # Create a more targeted and comprehensive query
            enhanced_query = self._create_enhanced_query(node.query)
            self.logger.debug(f"Enhanced query for tokenomics: {enhanced_query}")
            results = self._search_web(enhanced_query, max_results=7)  # Increased result count for more comprehensive data
            
            if results:
                self.logger.debug(f"Processing {len(results)} tokenomics search results")
                # Sort results to prioritize authoritative sources
                prioritized_results = self._prioritize_authoritative_sources(results)
                self.logger.debug(f"Prioritized results - first URL: {prioritized_results[0]['href'] if prioritized_results else 'None'}")
                
                # Extract and normalize tokenomics data
                tokenomics_data = self._extract_tokenomics_data(prioritized_results, node.query)
                self.logger.debug(f"Extracted tokenomics data: {json.dumps(tokenomics_data, indent=2)}")
                
                # Store the structured data and raw content
                node.structured_data = tokenomics_data
                node.content = "\n\n".join([r['body'] for r in prioritized_results])
                node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in prioritized_results]
                
                # Generate a fact-focused summary
                self.logger.debug(f"Generating summary for tokenomics data")
                node.summary = self._summarize_content(node.content, node.query)
                self.logger.debug(f"Generated summary length: {len(node.summary) if node.summary else 0}")
            else:
                self.logger.warning(f"No search results found for tokenomics query: {enhanced_query}")
                node.summary = "No tokenomics information found."
                # Add minimal structured data for fallback
                node.structured_data = {
                    "total_supply": None,
                    "circulating_supply": None,
                    "max_supply": None,
                    "token_allocations": {}
                }
            
            self.logger.info(f"TokenomicsAgent completed research for: {node.query}")
            return node
        except Exception as e:
            self.logger.error(f"Error in TokenomicsAgent.research: {str(e)}", exc_info=True)
            # Make sure we still return the node even if we encounter an error
            node.summary = f"Tokenomics research failed: {str(e)}"
            # Ensure we have at least an empty structured_data
            node.structured_data = {
                "total_supply": None,
                "circulating_supply": None,
                "max_supply": None,
                "token_allocations": {},
                "error": str(e)
            }
            # Ensure we have references (empty array)
            node.references = []
            return node
    
    def _create_enhanced_query(self, base_query: str) -> str:
        """Create an enhanced query that targets specific tokenomics metrics."""
        # Extract the cryptocurrency name from the query
        crypto_name = base_query.split()[0] if base_query.split() else ""
        
        # Create a targeted query focusing on specific tokenomics metrics
        query_components = [
            f"{crypto_name} tokenomics official",
            f"{crypto_name} total supply circulating supply max supply",
            f"{crypto_name} token distribution allocation",
            f"{crypto_name} vesting schedule unlock",
            f"{crypto_name} token utility mechanism economic model",
            f"{crypto_name} staking rewards inflation"
        ]
        
        # Use a random component to get diverse results on subsequent calls
        import random
        enhanced_query = random.choice(query_components)
        
        self.logger.info(f"Enhanced tokenomics query: {enhanced_query}")
        return enhanced_query
    
    def _prioritize_authoritative_sources(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Sort results to prioritize authoritative sources."""
        # Define authoritative domains for tokenomics data
        authoritative_domains = [
            "coingecko.com", "coinmarketcap.com", "messari.io", "defillama.com",
            "etherscan.io", "bscscan.com", "solscan.io", 
            ".medium.com", ".github.io", "docs.", "whitepaper", "tokenomics"
        ]
        
        # Function to score a result based on domain and content
        def score_result(result):
            url = result.get('href', '').lower()
            title = result.get('title', '').lower()
            body = result.get('body', '').lower()
            
            score = 0
            
            # Score based on authoritative domain
            for domain in authoritative_domains:
                if domain in url:
                    score += 10
                    break
            
            # Score based on relevant content
            token_terms = ["token", "supply", "distribution", "allocation", "vesting", "tokenomics"]
            for term in token_terms:
                if term in title:
                    score += 3
                if term in body[:200]:  # Check just beginning of body for efficiency
                    score += 1
            
            # Prioritize data-rich content
            data_indicators = ["total supply", "circulating supply", "max supply", "%", "allocation"]
            for indicator in data_indicators:
                if indicator in body:
                    score += 5
            
            # Penalize forum posts and non-authoritative sources
            if any(forum in url for forum in ["reddit.com", "bitcointalk.org", "forum"]):
                score -= 5
                
            return score
        
        # Sort results by score in descending order
        return sorted(results, key=score_result, reverse=True)
    
    def _extract_tokenomics_data(self, results: List[Dict[str, str]], query: str) -> Dict[str, Any]:
        """Extract structured tokenomics data from search results."""
        import re
        
        # Initialize structured data
        data = {
            "total_supply": None,
            "circulating_supply": None,
            "max_supply": None,
            "token_allocations": {},
            "vesting_info": {},
            "token_utility": []
        }
        
        # Combine all text for analysis
        all_text = " ".join([r.get('body', '') for r in results])
        
        # Extract total supply
        total_supply_patterns = [
            r"total supply\D*(\d[\d,.]* ?[kmbt]?)",
            r"total token supply\D*(\d[\d,.]* ?[kmbt]?)"
        ]
        for pattern in total_supply_patterns:
            matches = re.search(pattern, all_text, re.IGNORECASE)
            if matches:
                data["total_supply"] = matches.group(1)
                break
        
        # Extract circulating supply
        circ_supply_patterns = [
            r"circulating supply\D*(\d[\d,.]* ?[kmbt]?)",
            r"current supply\D*(\d[\d,.]* ?[kmbt]?)"
        ]
        for pattern in circ_supply_patterns:
            matches = re.search(pattern, all_text, re.IGNORECASE)
            if matches:
                data["circulating_supply"] = matches.group(1)
                break
        
        # Extract max supply
        max_supply_patterns = [
            r"max(imum)? supply\D*(\d[\d,.]* ?[kmbt]?)",
            r"hard cap\D*(\d[\d,.]* ?[kmbt]?)"
        ]
        for pattern in max_supply_patterns:
            matches = re.search(pattern, all_text, re.IGNORECASE)
            if matches:
                data["max_supply"] = matches.group(2 if "maximum" in pattern else 1)
                break
        
        # Extract allocation percentages
        allocation_pattern = r"(\d+(?:\.\d+)?)%\s*(?:allocated|goes|for|to)?\s*(team|foundation|community|ecosystem|treasury|investors|private sale|public sale|marketing|advisors|partners|development)"
        for match in re.finditer(allocation_pattern, all_text, re.IGNORECASE):
            percentage = float(match.group(1))
            category = match.group(2).lower()
            data["token_allocations"][category] = percentage
        
        # Log extracted data
        self.logger.info(f"Extracted tokenomics data: {data}")
        
        return data

class MarketAgent(ResearchAgent):
    """Agent specialized in researching market position and competition."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["coindesk.com", "cointelegraph.com", "theblock.co", "decrypt.co", "cryptobriefing.com", 
                            "tradingview.com", "coinglass.com", "glassnode.com"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"MarketAgent researching: {node.query}")
        try:
            # Create more targeted query based on the specific market aspect we want to research
            enhanced_query = self._create_enhanced_market_query(node.query)
            self.logger.debug(f"Enhanced market query: {enhanced_query}")
            results = self._search_web(enhanced_query, max_results=8)  # Increased for more comprehensive data
            
            if results:
                self.logger.debug(f"Processing {len(results)} market search results")
                # Prioritize and score results for market research
                prioritized_results = self._prioritize_market_sources(results)
                self.logger.debug(f"Prioritized market results - first URL: {prioritized_results[0]['href'] if prioritized_results else 'None'}")
                
                # Extract structured market data
                market_data = self._extract_market_data(prioritized_results, node.query)
                self.logger.debug(f"Extracted market data: {json.dumps(market_data, indent=2)}")
                
                # Store structured data and raw content
                node.structured_data = market_data
                node.content = "\n\n".join([r['body'] for r in prioritized_results])
                node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in prioritized_results]
                
                # Generate fact-focused summary
                self.logger.debug(f"Generating summary for market data")
                node.summary = self._summarize_content(node.content, node.query)
                self.logger.debug(f"Generated market summary length: {len(node.summary) if node.summary else 0}")
            else:
                self.logger.warning(f"No search results found for market query: {enhanced_query}")
                node.summary = "No market information found."
                # Add minimal structured data for fallback
                node.structured_data = {
                    "price_metrics": {},
                    "market_cap_metrics": {},
                    "volume_metrics": {},
                    "competitors": []
                }
                
            self.logger.info(f"MarketAgent completed research for: {node.query}")
            return node
        except Exception as e:
            self.logger.error(f"Error in MarketAgent.research: {str(e)}", exc_info=True)
            # Make sure we still return the node even if we encounter an error
            node.summary = f"Market research failed: {str(e)}"
            # Ensure we have at least empty structured_data
            node.structured_data = {
                "price_metrics": {},
                "market_cap_metrics": {},
                "volume_metrics": {},
                "competitors": [],
                "error": str(e)
            }
            # Ensure we have references (empty array)
            node.references = []
            return node
    
    def _create_enhanced_market_query(self, base_query: str) -> str:
        """Create targeted market research queries based on the research focus."""
        # Extract cryptocurrency name from query
        crypto_words = base_query.split()
        crypto_name = crypto_words[0] if crypto_words else ""
        
        # Detect the specific market aspect to research
        query_focus = "general"  # default focus
        if any(word in base_query.lower() for word in ["price", "trend", "prediction", "forecast"]):
            query_focus = "price"
        elif any(word in base_query.lower() for word in ["volume", "liquidity", "trading"]):
            query_focus = "volume"
        elif any(word in base_query.lower() for word in ["competitor", "comparison", "vs", "versus"]):
            query_focus = "competitors"
        elif any(word in base_query.lower() for word in ["market cap", "marketcap", "dominance"]):
            query_focus = "marketcap"
        
        # Specialized query components based on focus
        query_templates = {
            "price": [
                f"{crypto_name} price analysis historical performance",
                f"{crypto_name} price correlation with bitcoin ethereum",
                f"{crypto_name} price support resistance levels"
            ],
            "volume": [
                f"{crypto_name} trading volume exchanges statistics",
                f"{crypto_name} liquidity depth analysis",
                f"{crypto_name} volume profile distribution"
            ],
            "competitors": [
                f"{crypto_name} competitors market comparison",
                f"{crypto_name} vs similar cryptocurrencies metrics",
                f"{crypto_name} market position relative competitors"
            ],
            "marketcap": [
                f"{crypto_name} market cap historical growth",
                f"{crypto_name} market share in cryptocurrency ecosystem",
                f"{crypto_name} market valuation metrics"
            ],
            "general": [
                f"{crypto_name} comprehensive market analysis",
                f"{crypto_name} market performance metrics statistics",
                f"{crypto_name} trading indicators technical analysis"
            ]
        }
        
        # Get templates for the focus area
        focus_templates = query_templates.get(query_focus, query_templates["general"])
        
        # Select a template randomly to get diverse results
        import random
        enhanced_query = random.choice(focus_templates)
        
        self.logger.info(f"Enhanced market query ({query_focus} focus): {enhanced_query}")
        return enhanced_query
    
    def _prioritize_market_sources(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Prioritize results based on their relevance to market analysis."""
        # Define authoritative market data sources
        authoritative_domains = [
            "coingecko.com", "coinmarketcap.com", "tradingview.com", "coindesk.com", 
            "cointelegraph.com", "theblock.co", "messari.io", "glassnode.com", 
            "santiment.net", "intotheblock.com", "defipulse.com"
        ]
        
        # Define relevant market data terms
        market_terms = [
            "price", "volume", "market cap", "dominance", "liquidity", "volatility",
            "correlation", "indicator", "technical analysis", "chart", "trend",
            "support", "resistance", "order book", "trading", "exchange"
        ]
        
        # Score function for market results
        def score_market_result(result):
            url = result.get('href', '').lower()
            title = result.get('title', '').lower()
            body = result.get('body', '').lower()
            
            score = 0
            
            # Boost score for authoritative domains
            for domain in authoritative_domains:
                if domain in url:
                    score += 10
                    break
            
            # Boost for recent content (if date available in title or first part of body)
            date_indicators = ["2023", "2024", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
            for indicator in date_indicators:
                if indicator in title.lower() or indicator in body[:100].lower():
                    score += 5
                    break
            
            # Boost for market-specific terms
            for term in market_terms:
                if term in title.lower():
                    score += 3
                if term in body[:300].lower():
                    score += 1
            
            # Boost for data-rich content
            data_indicators = ["$", "%", "+", "-", "increase", "decrease", "grew", "fell", "million", "billion", "ratio"]
            for indicator in data_indicators:
                # Count occurrences and boost score accordingly (capped)
                occurrences = body.count(indicator)
                score += min(occurrences, 10)
            
            # Penalize low-value content
            if any(term in url.lower() for term in ["forum", "reddit", "twitter", "youtube"]):
                score -= 5
                
            return score
        
        # Sort by score
        return sorted(results, key=score_market_result, reverse=True)
    
    def _extract_market_data(self, results: List[Dict[str, str]], query: str) -> Dict[str, Any]:
        """Extract structured market data from search results."""
        import re
        from datetime import datetime
        
        # Initialize structured data
        data = {
            "price_metrics": {},
            "volume_metrics": {},
            "market_cap_metrics": {},
            "competitors": [],
            "technical_indicators": {},
            "analyst_sentiment": {},
            "recent_price_movements": [],
            "data_timestamp": datetime.now().isoformat()
        }
        
        # Combine all text for analysis
        all_text = " ".join([r.get('body', '') for r in results])
        
        # Extract current price
        price_pattern = r"(?:current|latest|trading)\s+price.*?[$€£¥](\d+(?:,\d+)*(?:\.\d+)?)"
        price_match = re.search(price_pattern, all_text, re.IGNORECASE)
        if price_match:
            data["price_metrics"]["current_price"] = price_match.group(1)
        
        # Extract price changes
        price_change_pattern = r"(?:increased|decreased|rose|fell|gained|lost)\s+by\s+(\d+(?:\.\d+)?)%"
        for match in re.finditer(price_change_pattern, all_text, re.IGNORECASE):
            movement = {
                "percentage": match.group(1),
                "context": all_text[max(0, match.start()-50):min(len(all_text), match.end()+50)]
            }
            data["recent_price_movements"].append(movement)
        
        # Extract market cap
        market_cap_pattern = r"market\s+cap(?:italization)?\s+of\s+[$€£¥]?(\d+(?:\.\d+)?)\s*(million|billion|trillion|B|M|T)"
        market_cap_match = re.search(market_cap_pattern, all_text, re.IGNORECASE)
        if market_cap_match:
            value = market_cap_match.group(1)
            unit = market_cap_match.group(2).lower()
            data["market_cap_metrics"]["market_cap"] = f"{value} {unit}"
        
        # Extract volume
        volume_pattern = r"(?:24h|daily|trading)\s+volume.*?[$€£¥]?(\d+(?:\.\d+)?)\s*(million|billion|trillion|B|M|T)"
        volume_match = re.search(volume_pattern, all_text, re.IGNORECASE)
        if volume_match:
            value = volume_match.group(1)
            unit = volume_match.group(2).lower()
            data["volume_metrics"]["daily_volume"] = f"{value} {unit}"
        
        # Extract competitors
        competitor_pattern = r"(?:competitors?|rivals?|similar\s+to|alternatives?)(?:\s+include|\s+are|\s+is|:)?\s+([A-Za-z0-9 ,]+(?:and|&)\s+[A-Za-z0-9 ]+)"
        competitor_match = re.search(competitor_pattern, all_text, re.IGNORECASE)
        if competitor_match:
            competitor_text = competitor_match.group(1)
            competitors = re.split(r',|\band\b|&', competitor_text)
            data["competitors"] = [comp.strip() for comp in competitors if comp.strip()]
        
        # Extract technical indicators
        indicator_patterns = [
            (r"RSI.*?(?:at|of|is)\s+(\d+(?:\.\d+)?)", "RSI"),
            (r"MACD.*?(?:shows|indicates|is)\s+(\w+)", "MACD"),
            (r"moving average(?:s)?.*?(\w+\s+\w+)", "MA")
        ]
        
        for pattern, indicator_name in indicator_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                data["technical_indicators"][indicator_name] = match.group(1)
        
        self.logger.info(f"Extracted market data with {len(data['recent_price_movements'])} price movements and {len(data['competitors'])} competitors")
        return data

class EcosystemAgent(ResearchAgent):
    """Agent specialized in researching ecosystem, partnerships and integrations."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["medium.com", "blog.ethereum.org", "defillama.com", "dappradar.com", "consensys.net"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"EcosystemAgent researching: {node.query}")
        enhanced_query = f"{node.query} cryptocurrency ecosystem partnerships integrations defi protocol"
        results = self._search_web(enhanced_query)
        if results:
            node.content = "\n\n".join([r['body'] for r in results])
            node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in results]
            node.summary = self._summarize_content(node.content, node.query)
        else:
            node.summary = "No ecosystem information found."
        return node

class GovernanceAgent(ResearchAgent):
    """Agent specialized in researching governance aspects of crypto projects."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["docs.uniswap.org", "forum.arbitrum.foundation", "gov.curve.fi", "medium.com", "github.com"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"GovernanceAgent researching: {node.query}")
        enhanced_query = f"{node.query} cryptocurrency governance DAO voting mechanism"
        results = self._search_web(enhanced_query)
        if results:
            node.content = "\n\n".join([r['body'] for r in results])
            node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in results]
            node.summary = self._summarize_content(node.content, node.query)
        else:
            node.summary = "No governance information found."
        return node

class TeamAgent(ResearchAgent):
    """Agent specialized in researching team and development aspects of crypto projects."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["linkedin.com", "github.com", "medium.com", "twitter.com", "sui.io"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"TeamAgent researching: {node.query}")
        enhanced_query = f"{node.query} cryptocurrency team founders developers roadmap"
        results = self._search_web(enhanced_query)
        if results:
            node.content = "\n\n".join([r['body'] for r in results])
            node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in results]
            node.summary = self._summarize_content(node.content, node.query)
        else:
            node.summary = "No team or development information found."
        return node

def get_agent_for_research_type(research_type: str, llm: ChatOpenAI, logger: logging.Logger) -> ResearchAgent:
    try:
        agents = {
            ResearchType.TECHNICAL: TechnicalAgent(llm, logger),
            ResearchType.TOKENOMICS: TokenomicsAgent(llm, logger),
            ResearchType.MARKET: MarketAgent(llm, logger),
            ResearchType.ECOSYSTEM: EcosystemAgent(llm, logger),
            ResearchType.GOVERNANCE: GovernanceAgent(llm, logger),
            ResearchType.TEAM: TeamAgent(llm, logger),
        }
        agent = agents.get(research_type, TechnicalAgent(llm, logger))
        logger.debug(f"Selected agent for research type {research_type}: {agent.__class__.__name__}")
        return agent
    except Exception as e:
        logger.error(f"Error creating agent for research type {research_type}: {str(e)}", exc_info=True)
        # Default to TechnicalAgent as fallback
        return TechnicalAgent(llm, logger)