from typing import List, Dict
import logging
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from backend.research.core import ResearchNode, ResearchType
from backend.retriever.tavily_search import TavilySearch

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
            results = tavily.search(max_results=max_results)
            self.logger.info(f"Web search returned {len(results)} results")
            return results
        except Exception as e:
            self.logger.error(f"Web search error: {str(e)}")
            return []
    
    def _summarize_content(self, content: str, query: str) -> str:
        """Summarize the collected content using LLM."""
        if not content:
            return "No information found for this query."
        
        summary_prompt = (
            f"Based on this information about \"{query}\":\n\n"
            f"{content[:6000]}\n\n"
            f"Provide a concise, factual summary addressing the query directly. "
            f"Include specific details, numbers, and technical information where available. "
            f"Be comprehensive but concise (2-3 paragraphs)."
        )
        
        try:
            summary = self.llm.invoke(summary_prompt).content
            return summary
        except Exception as e:
            self.logger.error(f"Summarization error: {str(e)}")
            return "Error generating summary: " + str(e)

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
        enhanced_query = f"{node.query} cryptocurrency blockchain technical architecture"
        results = self._search_web(enhanced_query)
        if results:
            node.content = "\n\n".join([r['body'] for r in results])
            node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in results]
            node.summary = self._summarize_content(node.content, node.query)
        else:
            node.summary = "No technical information found."
        return node

class TokenomicsAgent(ResearchAgent):
    """Agent specialized in researching tokenomics and economics."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["coingecko.com", "coinmarketcap.com", "defillama.com", "messari.io", "tokenterminal.com"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"TokenomicsAgent researching: {node.query}")
        enhanced_query = f"{node.query} cryptocurrency token tokenomics supply distribution economics"
        results = self._search_web(enhanced_query)
        if results:
            node.content = "\n\n".join([r['body'] for r in results])
            node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in results]
            node.summary = self._summarize_content(node.content, node.query)
        else:
            node.summary = "No tokenomics information found."
        return node

class MarketAgent(ResearchAgent):
    """Agent specialized in researching market position and competition."""
    
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        super().__init__(
            llm=llm,
            logger=logger,
            include_domains=["coindesk.com", "cointelegraph.com", "theblock.co", "decrypt.co", "cryptobriefing.com"]
        )
    
    def research(self, node: ResearchNode) -> ResearchNode:
        self.logger.info(f"MarketAgent researching: {node.query}")
        enhanced_query = f"{node.query} cryptocurrency market position competitors trading volume price"
        results = self._search_web(enhanced_query)
        if results:
            node.content = "\n\n".join([r['body'] for r in results])
            node.references = [{'title': r['body'][:50] + "...", 'url': r['href']} for r in results]
            node.summary = self._summarize_content(node.content, node.query)
        else:
            node.summary = "No market information found."
        return node

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
    agents = {
        ResearchType.TECHNICAL: TechnicalAgent(llm, logger),
        ResearchType.TOKENOMICS: TokenomicsAgent(llm, logger),
        ResearchType.MARKET: MarketAgent(llm, logger),
        ResearchType.ECOSYSTEM: EcosystemAgent(llm, logger),
        ResearchType.GOVERNANCE: GovernanceAgent(llm, logger),
        ResearchType.TEAM: TeamAgent(llm, logger),
    }
    return agents.get(research_type, TechnicalAgent(llm, logger))