from typing import List, Dict, Optional, Literal
import logging
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
import uuid

class ResearchNode:
    """Represents a node in the research tree."""
    
    def __init__(
        self, 
        id: str = None, 
        query: str = "", 
        parent_id: str = None,
        depth: int = 0,
        research_type: str = None,
        data_field: str = None,
        source: str = None
    ):
        self.id = id or str(uuid.uuid4())
        self.query = query
        self.parent_id = parent_id
        self.depth = depth
        self.research_type = research_type
        self.data_field = data_field  # Field name this node is researching
        self.source = source  # Source this node should use (e.g., "coingecko")
        
        # Results
        self.content = ""  # Raw research content
        self.summary = ""  # LLM-generated summary
        self.references = []  # List of reference objects {title, url}
        self.structured_data = {}  # Extracted structured data (key-value pairs)
        self.image_path = ""  # Path to any visualization
        
        # Relationships
        self.children = []
        
        # For backward compatibility with the older ResearchNode implementation
        self.node_id = self.id
    
    def add_child(self, query: str, research_type: str = None, data_field: str = None, source: str = None) -> 'ResearchNode':
        """Add a child node and return it."""
        child = ResearchNode(
            query=query,
            parent_id=self.id,
            depth=self.depth + 1,
            research_type=research_type,
            data_field=data_field,
            source=source
        )
        self.children.append(child)
        return child
    
    def to_dict(self) -> Dict:
        """Convert the node to a dictionary for serialization."""
        node_dict = {
            "id": self.id,
            "node_id": self.id,  # For backward compatibility
            "query": self.query,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "research_type": self.research_type,
            "data_field": self.data_field,
            "source": self.source,
            "content": self.content,
            "summary": self.summary,
            "references": self.references,
            "structured_data": self.structured_data,
            "image_path": self.image_path,
            "children": [child.to_dict() for child in self.children]
        }
        return node_dict
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ResearchNode':
        """Create a node from a dictionary."""
        node_id = data.get("id") or data.get("node_id")  # Support both new and old format
        
        node = cls(
            id=node_id,
            query=data.get("query", ""),
            parent_id=data.get("parent_id"),
            depth=data.get("depth", 0),
            research_type=data.get("research_type"),
            data_field=data.get("data_field"),
            source=data.get("source")
        )
        node.content = data.get("content", "")
        node.summary = data.get("summary", "")
        node.references = data.get("references", [])
        node.structured_data = data.get("structured_data", {})
        node.image_path = data.get("image_path", "")
        node.node_id = node_id  # For backward compatibility
        
        # Recursively build children
        for child_data in data.get("children", []):
            child = cls.from_dict(child_data)
            node.children.append(child)
            
        return node

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