from typing import List, Dict, Optional, Literal
import logging
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI

@dataclass
class ResearchNode:
    """Represents a single node in the research tree hierarchy."""
    query: str
    depth: int = 0
    parent_id: Optional[str] = None
    node_id: str = field(default_factory=lambda: str(id(object())))
    children: List["ResearchNode"] = field(default_factory=list)
    content: str = ""
    summary: str = ""
    references: List[Dict[str, str]] = field(default_factory=list)
    
    def add_child(self, query: str) -> "ResearchNode":
        """Add a child research node to this node."""
        child = ResearchNode(
            query=query, 
            depth=self.depth + 1,
            parent_id=self.node_id
        )
        self.children.append(child)
        return child
    
    def to_dict(self) -> Dict:
        """Convert the node to a dictionary for serialization."""
        return {
            "query": self.query,
            "depth": self.depth,
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "content": self.content,
            "summary": self.summary,
            "references": self.references,
            "children": [child.to_dict() for child in self.children]
        }

class ResearchType:
    """Enum-like class for research types."""
    TECHNICAL = "technical"
    TOKENOMICS = "tokenomics"
    MARKET = "market"
    ECOSYSTEM = "ecosystem"
    GOVERNANCE = "governance"
    TEAM = "team"
    RISKS = "risks"
    OPPORTUNITIES = "opportunities"

class ResearchManager:
    """Manages the entire research process across multiple agents and resources."""
    
    def __init__(
        self, 
        query: str,
        llm: ChatOpenAI,
        logger: logging.Logger,
        max_depth: int = 2,
        max_breadth: int = 3,
        research_types: List[str] = None
    ):
        self.query = query
        self.llm = llm
        self.logger = logger
        self.max_depth = max_depth
        self.max_breadth = max_breadth
        self.research_types = research_types or [
            ResearchType.TECHNICAL,
            ResearchType.TOKENOMICS,
            ResearchType.MARKET,
            ResearchType.ECOSYSTEM
        ]
        self.root_node = ResearchNode(query=query)
        self.all_references = []
    
    def generate_research_tree(self) -> ResearchNode:
        """Generate the full research tree based on the main query."""
        self.logger.info(f"Generating research tree for: {self.query}")
        self._expand_node(self.root_node)
        return self.root_node
    
    def _expand_node(self, node: ResearchNode) -> None:
        """Recursively expand a node with child research questions."""
        # Stop if we've reached max depth
        if node.depth >= self.max_depth:
            return
        
        # Generate sub-questions based on research types for root node
        if node.depth == 0:
            self._generate_strategic_questions(node)
        else:
            self._generate_tactical_questions(node)
    
    def _generate_strategic_questions(self, node: ResearchNode) -> None:
        """Generate strategic research questions for the root node based on research types."""
        for research_type in self.research_types:
            prompt = self._get_strategic_question_prompt(node.query, research_type)
            try:
                response = self.llm.invoke(prompt).content
                question = response.strip()
                if question:
                    child = node.add_child(question)
                    self.logger.info(f"Added strategic question: {question}")
                    self._expand_node(child)
            except Exception as e:
                self.logger.error(f"Error generating strategic question for {research_type}: {str(e)}")
    
    def _generate_tactical_questions(self, node: ResearchNode) -> None:
        """Generate tactical sub-questions for a strategic question node."""
        prompt = (
            f"To research '{node.query}' effectively, I need to break this down into "
            f"{self.max_breadth} specific sub-questions that will help gather comprehensive information.\n"
            f"These questions should be specific, focused, and diverse in their approach.\n"
            f"Generate exactly {self.max_breadth} questions, each on a new line."
        )
        
        try:
            response = self.llm.invoke(prompt).content
            sub_questions = [q.strip() for q in response.strip().split('\n') if q.strip()][:self.max_breadth]
            
            for sub_q in sub_questions:
                # Remove numbering if present
                clean_q = sub_q
                if len(sub_q) > 3 and sub_q[0].isdigit() and sub_q[1:3] in ['. ', ') ']:
                    clean_q = sub_q.split(' ', 1)[1]
                    
                child = node.add_child(clean_q)
                self.logger.info(f"Added tactical question: {clean_q}")
                # We don't expand tactical questions further
        except Exception as e:
            self.logger.error(f"Error generating tactical questions: {str(e)}")
    
    def _get_strategic_question_prompt(self, main_query: str, research_type: str) -> str:
        """Generate a prompt to create a strategic question for a specific research type."""
        prompts = {
            ResearchType.TECHNICAL: f"Generate one comprehensive research question about the technical architecture, features, and innovation of {main_query}.",
            ResearchType.TOKENOMICS: f"Generate one comprehensive research question about the tokenomics, supply, distribution, and utility of {main_query}.",
            ResearchType.MARKET: f"Generate one comprehensive research question about the market position, competitors, and adoption metrics of {main_query}.",
            ResearchType.ECOSYSTEM: f"Generate one comprehensive research question about the ecosystem, partnerships, and integrations of {main_query}.",
            ResearchType.GOVERNANCE: f"Generate one comprehensive research question about the governance model, voting mechanisms, and decision-making process of {main_query}.",
            ResearchType.TEAM: f"Generate one comprehensive research question about the team, founders, and key contributors behind {main_query}.",
            ResearchType.RISKS: f"Generate one comprehensive research question about the risks, challenges, and potential vulnerabilities of {main_query}.",
            ResearchType.OPPORTUNITIES: f"Generate one comprehensive research question about the future opportunities, growth potential, and upcoming developments for {main_query}."
        }
        return prompts.get(research_type, f"Generate one comprehensive research question about {main_query} related to {research_type}.") 