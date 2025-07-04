# backend/agents/writer.py
import logging
import json
import os
import math
import asyncio
from typing import Dict, Any, Optional, List, Set, Tuple
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from datetime import datetime
from backend.utils.number_formatter import NumberFormatter
from backend.utils.cache_utils import CacheManager
import time
from backend.utils.state_manager import StateManager
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Define openai_retry_decorator directly in writer.py
def openai_retry_decorator(func):
    """
    Decorator to retry OpenAI API calls with exponential backoff.
    Retries up to 3 times with a wait time of 1-5 seconds between attempts.
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying {func.__name__} (attempt {retry_state.attempt_number}/3) due to {retry_state.outcome.exception()}"
        )
    )
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

class WriterAgent:
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger):
        """
        Initialize the WriterAgent with language model.
        
        Args:
            llm: Language model for content generation
            logger: Logger instance for tracking operations
        """
        self.llm = llm
        self.logger = logger

    async def write_draft(self, state: ResearchState) -> str:
        """
        Generate a draft research report using data from ResearchState.
        Handles content generation for all sections in parallel for improved performance.
        
        Args:
            state: Research state containing project data and configuration
            
        Returns:
            Complete draft text with all sections
        """
        # Get project name from state, handling both dict and object formats
        project_name = None
        if isinstance(state, dict):
            project_name = state.get("project_name", "Unknown Project")
        else:
            project_name = getattr(state, "project_name", "Unknown Project")
        
        start_time = time.time()
        self.logger.info(f"Writing draft for {project_name}")
        
        # Initialize CacheManager for standardized caching
        cache_mgr = CacheManager(project_name=project_name, logger=self.logger)
        
        # Get data from state instead of reloading from disk
        data_sources = {}
        if isinstance(state, dict):
            data_sources = state.get("data", {})
        else:
            data_sources = getattr(state, "data", {})
            
        # Validate data_sources format
        if not isinstance(data_sources, dict):
            self.logger.warning("Invalid data_sources format in state, treating as empty")
            data_sources = {}
        
        # Log data source sizes to help debug context window issues
        self._log_data_source_sizes(data_sources)
            
        # Get problem sections information
        problem_sections = []
        if isinstance(state, dict):
            problem_sections = state.get("problem_sections", [])
        else:
            problem_sections = getattr(state, "problem_sections", []) if hasattr(state, "problem_sections") else []
            
        # Track problem section titles for easier lookups
        problem_section_titles = {ps["title"] for ps in problem_sections if "title" in ps}
        self.logger.info(f"Problem section titles: {problem_section_titles}")
        
        # Initialize StateManager for this operation
        state_manager = StateManager(logger=self.logger)
        
        # Get report configuration
        report_config = state_manager.get_report_config(state)
        
        self.logger.info(f"Writer agent starting for project: {project_name}")
        self.logger.info(f"Using report config version: {report_config.get('version', 'unknown')}")
        
        # Update progress using StateManager
        state = state_manager.update_progress(state, f"Writing draft report for {project_name}...")
        
        if not report_config:
            self.logger.error("No report_config found in state")
            return state_manager.add_error(state, "writer", "No report_config found in state")
        
        # Get sections from report config
        sections = report_config.get("sections", [])
        if not sections:
            self.logger.error("No sections found in report_config")
            return state_manager.add_error(state, "writer", "No sections found in report_config")
        
        # Preprocess key metrics once - improves performance vs. doing in each section
        key_metrics = self._format_key_metrics(self._extract_key_metrics(data_sources))
        
        # Define async function for parallel section generation
        async def generate_section_content(section: Dict) -> Tuple[str, str]:
            """Generate content for a single section."""
            section_title = section.get("title", "")
            if not section_title:
                return section_title, ""
                
            # Skip if section title is clearly invalid
            if not isinstance(section_title, str):
                self.logger.warning(f"Invalid section title format: {section_title}")
                return str(section_title), ""
                
            # Create standardized cache key
            normalized_section = section_title.lower().replace(" ", "_")
            
            # Check if section content is already cached
            cached_content = cache_mgr.load("writer", "section", normalized_section)
            if cached_content and "content" in cached_content:
                self.logger.info(f"Using cached content for section: {section_title}")
                return section_title, cached_content["content"]
                
            # Get existing content if available in state
            existing_content = ""
            if isinstance(state, dict):
                if "sections" in state and section_title in state["sections"]:
                    existing_content = state["sections"][section_title].get("content", "")
            else:
                if hasattr(state, "sections") and hasattr(state.sections, section_title):
                    existing_content = state.sections[section_title].get("content", "")
            
            # Check if this is a problem section
            is_problem_section = self.check_for_problem_section(section_title, problem_section_titles)
            
            try:
                # For problem sections, use a lightweight approach
                if is_problem_section:
                    self.logger.info(f"Using lightweight approach for problem section: {section_title}")
                    content = await self._generate_content_for_problem_section(
                        project_name=project_name,
                        section=section,
                        data_sources=data_sources,
                        key_metrics=key_metrics
                    )
                else:
                    # For standard sections, use LLM with optimized parameters
                    self.logger.info(f"Using standard content generation for section: {section_title}")
                    content = await self._generate_section_content(
                        section=section,
                        research_summary=existing_content,
                        key_metrics=key_metrics,
                        data_sources=data_sources,
                        project_name=project_name,
                        is_problem_section=False
                    )
                    
                # Cache successful generation
                cache_mgr.save(
                    {"content": content, "section_title": section_title},
                    "writer", 
                    "section",
                    normalized_section,
                    ttl_hours=24
                )
                
                return section_title, content
                
            except Exception as e:
                self.logger.error(f"Error generating content for {section_title}: {str(e)}")
                return section_title, self._generate_fallback_content(project_name, section_title)
        
        # Generate content for all sections in parallel with batching
        batch_size = 3  # Process 3 sections at a time to avoid overwhelming LLM API
        sections_content = {}
        num_batches = math.ceil(len(sections) / batch_size)
        
        self.logger.info(f"Processing {len(sections)} sections in {num_batches} batches of {batch_size}")
        
        for batch_idx in range(num_batches):
            batch_start = batch_idx * batch_size
            batch_end = min((batch_idx + 1) * batch_size, len(sections))
            batch_sections = sections[batch_start:batch_end]
            
            self.logger.info(f"Processing batch {batch_idx+1}/{num_batches} with {len(batch_sections)} sections")
            
            # Process batch in parallel
            results = await asyncio.gather(
                *(generate_section_content(section) for section in batch_sections),
                return_exceptions=True
            )
            
            # Extract results, handling exceptions
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Batch processing error: {str(result)}")
                    continue
                
                section_title, content = result
                if section_title and content:
                    sections_content[section_title] = content
        
        # Combine all sections in the original order from report_config
        draft = []
        
        # Add sections in the order defined in report_config
        for section in sections:
            section_title = section.get("title", "")
            if section_title in sections_content:
                draft.append(f"# {section_title}\n\n{sections_content[section_title]}\n")
        
        # Add Data Limitations section if problem sections exist
        if problem_sections:
            limitations = ["## Data Limitations\n\nThe following sections had missing or incomplete data:\n"]
            for ps in problem_sections:
                if "title" in ps and "missing_fields" in ps:
                    limitations.append(f"- **{ps['title']}**: Missing fields: {', '.join(ps['missing_fields'])}")
            draft.append("\n".join(limitations))
        
        # Add references if available
        references = []
        if isinstance(state, dict):
            if "references" in state:
                references = state["references"]
        else:
            if hasattr(state, "references"):
                references = state.references
        
        if references:
            draft.append("\n## References\n")
            for ref in references:
                draft.append(f"- {ref['title']}: [{ref['url']}]({ref['url']})")
        
        # Log time taken for performance analysis
        elapsed_time = time.time() - start_time
        self.logger.info(f"Draft generated in {elapsed_time:.2f} seconds")
        
        return "\n".join(draft)
    
    @openai_retry_decorator
    async def _chunk_content_generation(self, section_name, prompt, max_chunk_tokens=3000):
        """
        Generate content in chunks to avoid context length exceeded errors.
        
        Args:
            section_name: Name of the section
            prompt: Prompt for content generation
            max_chunk_tokens: Maximum tokens per chunk
            
        Returns:
            Generated content
        """
        try:
            self.logger.info(f"Generating content for {section_name} in chunks")
            
            # Initialize content
            full_content = ""
            
            # Generate first chunk
            response = self.llm.invoke(
                prompt,
                max_tokens=max_chunk_tokens
            )
            
            # Extract content
            if hasattr(response, 'content'):
                chunk = response.content
            else:
                chunk = str(response)
                
            full_content += chunk
            
            # Check if content seems complete
            if len(chunk) < max_chunk_tokens * 2:  # Rough estimate
                return full_content
                
            # Generate additional chunks if needed
            for i in range(1, 3):  # Maximum 3 chunks
                # Create continuation prompt
                continuation_prompt = f"{prompt}\n\nContinue from where you left off:\n{chunk[-200:]}"
                
                # Generate next chunk
                response = self.llm.invoke(
                    continuation_prompt,
                    max_tokens=max_chunk_tokens
                )
                
                # Extract content
                if hasattr(response, 'content'):
                    chunk = response.content
                else:
                    chunk = str(response)
                    
                full_content += "\n" + chunk
                
                # Check if content seems complete
                if len(chunk) < max_chunk_tokens * 2:  # Rough estimate
                    break
                    
            return full_content
            
        except Exception as e:
            self.logger.error(f"Error generating chunked content for {section_name}: {str(e)}")
            return f"Content generation failed for {section_name}. Error: {str(e)}"

    @openai_retry_decorator
    async def _generate_section_content(self, section: Dict, research_summary: str, key_metrics: Dict, data_sources: Dict, project_name: str, is_problem_section: bool = False) -> str:
        """
        Generate content for a single section using available data and the LLM.
        
        Args:
            section: Section configuration
            research_summary: Existing research summary if available
            key_metrics: Preprocessed key metrics
            data_sources: All available data sources
            project_name: Name of the project
            is_problem_section: Whether this is a problem section with limited data
            
        Returns:
            Generated content for the section
        """
        section_title = section.get("title", "")
        description = section.get("prompt", "")
        min_words = section.get("min_words", 400)
        max_words = section.get("max_words", 700)
        
        self.logger.info(f"Generating content for section: {section_title} (target: {min_words}-{max_words} words)")
        
        # Check for cached content first
        normalized_section_title = section_title.lower().replace(' ', '_')
        cache_mgr = CacheManager(project_name=project_name, logger=self.logger)
        cached_content = cache_mgr.load("writer", "section", normalized_section_title)
        
        if cached_content and "content" in cached_content:
            self.logger.info(f"Using cached content for section: {section_title}")
            return cached_content["content"]
        
        # Check for existing research summary
        if research_summary and len(research_summary.strip()) > 0:
            self.logger.info(f"Found existing research summary for {section_title}: {len(research_summary.split())} words")
        
        # Use focused data chunk for this section to avoid context window limits
        chunked_data = self._chunk_data_for_section(section_title, data_sources)
        
        # Create a context dictionary with relevant information
        context = {}
        
        # Add section-specific data
        data_fields = section.get("data_fields", [])
        fallback_fields = section.get("fallback_fields", [])
        
        # Add data fields if available
        for field in data_fields:
            # Check for field in key metrics first (most concise)
            if field in key_metrics:
                context[field] = key_metrics[field]
                continue
                
            # Then look in all data sources
            for source, source_data in chunked_data.items():
                if isinstance(source_data, dict):
                    for key, value in source_data.items():
                        if isinstance(value, dict) and field in value:
                            context[f"{source}.{key}.{field}"] = value[field]
                            break
        
        # Add fallback fields if available
        for field in fallback_fields:
            if field in key_metrics and field not in context:
                context[field] = key_metrics[field]
        
        # Add web research if available
        if "web_research" in chunked_data:
            context["research"] = chunked_data["web_research"]
        
        # Count available context data to determine strategy
        context_items = len(context)
        
        self.logger.info(f"Content generation context for '{section_title}': {context_items} items with strategy: {'problem-section' if is_problem_section else 'standard'}")
        
        # For very limited data, use a lightweight approach
        if context_items < 3 and not is_problem_section:
            self.logger.info(f"Limited data for section '{section_title}', using lightweight approach")
            content = await self._generate_limited_content(
                project_name=project_name,
                section_title=section_title,
                description=description,
                relevant_data=context,
                min_words=min_words
            )
            
            # Cache the generated content
            cache_mgr.save(
                {"content": content, "section_title": section_title, "word_count": len(content.split())},
                "writer",
                "section",
                normalized_section_title,
                ttl_hours=24
            )
            
            return content
        
        # Use gpt-3.5-turbo for all sections to improve performance
        section_llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=2000
        )
        
        # First try with standard instructions
        prompt = ChatPromptTemplate.from_template(
            """
            Create a detailed section on {section_title} for {project_name}.
            
            REQUIREMENTS:
            - Write at least {min_words} and at most {max_words} words
            - Section focus: {description}
            - Include specific facts and analysis
            
            Available data:
            {context}
            
            Key metrics:
            {key_metrics_json}
            
            GENERATE COMPREHENSIVE CONTENT WITH AT LEAST {min_words} WORDS based on the available data.
            Acknowledge data limitations if necessary, but provide general educational context when specific data is unavailable.
            """
        )
        
        chain = prompt | section_llm | StrOutputParser()
        
        try:
            # Get multi-source data if available
            multi_data = data_sources.get("multi", {}) if isinstance(data_sources, dict) and "multi" in data_sources else {}
            
            # Limit data scope to improve performance
            focused_data = self._get_focused_data(section, data_sources)
            
            content = await chain.ainvoke({
                "section_title": section_title,
                "project_name": project_name,
                "min_words": min_words,
                "max_words": max_words,
                "description": description,
                "context": context if context else "Limited research data available. Focus on general knowledge about this topic.",
                "key_metrics_json": json.dumps(key_metrics, indent=2)
            })
            
            word_count = len(content.split())
            self.logger.info(f"Generated initial content for {section_title}: {word_count} words")
            
            # If content doesn't meet minimum word count, try again with more explicit instructions
            if word_count < min_words:
                self.logger.warning(f"Content for {section_title} too short ({word_count}/{min_words}). Retrying with explicit instructions.")
                
                # More explicit prompting to get longer content
                retry_prompt = ChatPromptTemplate.from_template(
                    """
                    Create a COMPREHENSIVE section on {section_title} for {project_name}.
                    
                    CRITICAL REQUIREMENTS:
                    - The content MUST be AT LEAST {min_words} words in length
                    - Focus on: {description}
                    - Include specific facts, analysis, and educational context
                    
                    Available data:
                    {context}
                    
                    Key metrics:
                    {key_metrics_json}
                    
                    I NEED AT LEAST {min_words} WORDS OF CONTENT. If specific data is limited, supplement with:
                    1. General educational information about this topic area
                    2. Industry standards and best practices
                    3. Methodological explanations relevant to the section
                    4. Implications for investors
                    
                    YOU MUST PRODUCE AT LEAST {min_words} WORDS OF HIGH-QUALITY CONTENT.
                    """
                )
                
                retry_chain = retry_prompt | section_llm | StrOutputParser()
                
                retry_content = await retry_chain.ainvoke({
                    "section_title": section_title,
                    "project_name": project_name,
                    "min_words": min_words,
                    "max_words": max_words,
                    "description": description,
                    "context": context if context else "Limited research data available. Focus on general knowledge about this topic.",
                    "key_metrics_json": json.dumps(key_metrics, indent=2)
                })
                
                retry_word_count = len(retry_content.split())
                self.logger.info(f"Retry generated content for {section_title}: {retry_word_count} words")
                
                # If retry is better, use that
                if retry_word_count > word_count:
                    content = retry_content
                    word_count = retry_word_count
                
                # If still below minimum, use GPT-4 for more comprehensive content
                if word_count < min_words:
                    self.logger.warning(f"Retry content still too short ({word_count}/{min_words}). Using GPT-4.")
                    
                    gpt4_llm = ChatOpenAI(
                        model="gpt-4", 
                        temperature=0.7,
                        max_tokens=3000
                    )
                    
                    final_chain = retry_prompt | gpt4_llm | StrOutputParser()
                    
                    final_content = await final_chain.ainvoke({
                        "section_title": section_title,
                        "project_name": project_name,
                        "min_words": min_words,
                        "max_words": max_words,
                        "description": description,
                        "context": context if context else "Limited research data available. Focus on general knowledge about this topic.",
                        "key_metrics_json": json.dumps(key_metrics, indent=2)
                    })
                    
                    final_word_count = len(final_content.split())
                    self.logger.info(f"GPT-4 generated content for {section_title}: {final_word_count} words")
                    
                    if final_word_count > word_count:
                        content = final_content
                        word_count = final_word_count
            
            # Cache the generated content
            cache_mgr.save(
                {"content": content, "section_title": section_title, "word_count": word_count},
                "writer",
                "section",
                normalized_section_title,
                ttl_hours=24
            )
            
            return content
            
        except Exception as e:
            self.logger.error(f"Error generating section content: {str(e)}")
            # If we have some context, fall back to a more basic approach
            if context:
                return f"# {section_title}\n\n{context}"
            # If all else fails, use totally generic content
            return self._generate_fallback_content(project_name, section_title)

    def _format_key_metrics(self, combined_data: Dict) -> Dict:
        """
        Format key metrics for better readability in generated content.
        
        Args:
            combined_data: Dictionary of key metrics from all sources
            
        Returns:
            Dictionary of formatted metrics
        """
        formatter = NumberFormatter()
        key_metrics = {}
        
        # List of metrics we want to format
        currency_metrics = ["current_price", "market_cap", "24h_volume", "volume_24h", "tvl"]
        token_metrics = ["total_supply", "circulating_supply", "max_supply"]
        percentage_metrics = ["price_change_percentage_24h", "price_change_7d", "price_change_30d"]
        
        for key, value in combined_data.items():
            # Skip None values and non-numeric values for numeric fields
            if value is None:
                continue
                
            if key in currency_metrics and isinstance(value, (int, float)):
                key_metrics[key] = formatter.format_currency(value, precision=2)
            elif key in token_metrics and isinstance(value, (int, float)):
                key_metrics[key] = formatter.format_number(value, precision=2) + " tokens"
            elif key in percentage_metrics and isinstance(value, (int, float)):
                key_metrics[key] = f"{value:.2f}%"
            elif isinstance(value, (dict, list)):
                # Preserve structured data but don't format
                key_metrics[key] = value
            elif isinstance(value, (int, float)):
                # Format any other numeric values
                key_metrics[key] = formatter.format_number(value, precision=2)
            else:
                # Keep other values as is
                key_metrics[key] = value
                
        return key_metrics

    @openai_retry_decorator
    async def _generate_content_for_problem_section(self, project_name: str, section: Dict, 
                                        data_sources: Dict, key_metrics: Dict) -> str:
        """
        Generate content for sections with data problems using a conservative approach.
        Relies on available data and LLM to generate educational content.
        
        Args:
            project_name: Name of the project
            section: Section configuration
            data_sources: Available data sources
            key_metrics: Preprocessed key metrics
            
        Returns:
            Generated content with clear indication of data limitations
        """
        section_title = section.get("title", "")
        description = section.get("prompt", "")
        min_words = section.get("min_words", 400)
        max_words = section.get("max_words", 700)
        
        # Create normalized section name for caching
        normalized_section = section_title.lower().replace(" ", "_")
        
        # Check if we have cached content first
        cache_mgr = CacheManager(project_name=project_name, logger=self.logger)
        cached_content = cache_mgr.load("writer", "section", normalized_section)
        
        if cached_content and "content" in cached_content:
            content = cached_content["content"]
            word_count = len(content.split())
            
            # Only use cached content if it meets minimum word count
            if word_count >= min_words:
                self.logger.info(f"Using cached content for problem section: {section_title} ({word_count} words)")
                return content
            else:
                self.logger.info(f"Cached content too short ({word_count}/{min_words}), regenerating: {section_title}")
            
        # Extract relevant data specific to this section
        relevant_data = {}
        
        # Add section-specific fields from fallback_fields
        if "fallback_fields" in section:
            for field in section["fallback_fields"]:
                # Look in key_metrics first
                if field in key_metrics:
                    relevant_data[field] = key_metrics[field]
                    continue
                    
                # Then try each data source
                for source, source_data in data_sources.items():
                    if isinstance(source_data, dict):
                        for key, file_data in source_data.items():
                            if isinstance(file_data, dict) and field in file_data:
                                relevant_data[field] = file_data[field]
                                break
        
        # Step 1: Generate base content using available data
        content = ""
        
        # If we have relevant data, use it
        if relevant_data:
            try:
                # Use direct LLM approach for better quality and control
                self.logger.info(f"Generating problem section content with limited data: {section_title}")
                
                llm = ChatOpenAI(
                    model="gpt-3.5-turbo",
                    temperature=0.7,
                    max_tokens=2000
                )
                
                prompt = ChatPromptTemplate.from_template(
                    """
                    Create a detailed section on {section_title} for {project_name}.
                    
                    CRITICAL REQUIREMENTS:
                    - Write at least {min_words} and at most {max_words} words
                    - Focus on: {description}
                    - Use only verified data - DO NOT fabricate information
                    
                    Available verified data:
                    {relevant_data_json}
                    
                    Key metrics:
                    {key_metrics_json}
                    
                    INSTRUCTIONS:
                    - Start with the verified data points above
                    - Expand with general educational content about this topic in cryptocurrency/blockchain projects
                    - Discuss industry standards, methodologies, and best practices
                    - Clearly mark when moving from verified data to general information
                    - Format in Markdown with clear organization
                    
                    If data is limited, acknowledge this limitation transparently while providing valuable 
                    general information about this aspect of cryptocurrency projects.
                    """
                )
                
                chain = prompt | llm | StrOutputParser()
                
                content = await chain.ainvoke({
                    "section_title": section_title,
                    "project_name": project_name,
                    "min_words": min_words,
                    "max_words": max_words,
                    "description": description,
                    "relevant_data_json": json.dumps(relevant_data, indent=2),
                    "key_metrics_json": json.dumps(key_metrics, indent=2)
                })
                
            except Exception as e:
                self.logger.error(f"Error in problem section generation for {section_title}: {str(e)}")
                content = await self._generate_limited_content(project_name, section_title, description, relevant_data, min_words)
        else:
            # No relevant data available, generate educational content
            self.logger.warning(f"No relevant data for problem section: {section_title}")
            
            # Use a more focused template for data-limited sections
            llm = ChatOpenAI(
                model="gpt-4",  # Use GPT-4 for better quality when data is limited
                temperature=0.7,
                max_tokens=3000
            )
            
            prompt = ChatPromptTemplate.from_template(
                """
                Create a detailed educational section on {section_title} for {project_name}.
                
                CRITICAL REQUIREMENTS:
                - Write at least {min_words} and at most {max_words} words
                - Focus on: {description}
                - Clearly indicate that specific project data is limited
                
                INSTRUCTIONS:
                - Begin by acknowledging data limitations for {project_name} in this area
                - Provide educational content about this topic in cryptocurrency/blockchain projects
                - Discuss industry standards, methodologies, and best practices
                - Include general information investors should know about this aspect
                - Maintain a professional, educational tone
                - Format in Markdown with clear organization
                
                The goal is to provide valuable information to readers even when project-specific 
                data is limited or unavailable.
                """
            )
            
            try:
                chain = prompt | llm | StrOutputParser()
                
                content = await chain.ainvoke({
                    "section_title": section_title,
                    "project_name": project_name,
                    "min_words": min_words,
                    "max_words": max_words,
                    "description": description
                })
            except Exception as e:
                self.logger.error(f"Error generating educational content for {section_title}: {str(e)}")
                content = self._generate_fallback_content(project_name, section_title)
        
        # Step 2: Ensure content meets minimum word count
        word_count = len(content.split())
        
        # If content is too short, expand it with general knowledge while maintaining data integrity
        if word_count < min_words:
            self.logger.warning(f"Problem section content too short: {section_title} ({word_count}/{min_words} words)")
            
            # Try using GPT-4 to expand the content while maintaining data integrity
            try:
                llm = ChatOpenAI(
                    model="gpt-4", 
                    temperature=0.7,
                    max_tokens=3000
                )
                
                expansion_prompt = (
                    f"I need to expand this section to AT LEAST {min_words} words while maintaining factual accuracy.\n\n"
                    f"SECTION: {section_title} for {project_name}\n\n"
                    f"CURRENT CONTENT ({word_count} words):\n{content}\n\n"
                    f"Please rewrite and expand this content to a MINIMUM of {min_words} words by:\n"
                    f"1. Adding general context about this type of cryptocurrency topic\n"
                    f"2. Discussing standard industry practices and benchmarks\n"
                    f"3. Adding educational content about this area for investors\n"
                    f"4. Clearly acknowledging data limitations where appropriate\n\n"
                    f"IMPORTANT: Do NOT add speculative or fabricated information about {project_name} specifically. "
                    f"If specific data is unavailable, acknowledge this limitation and provide general educational "
                    f"content about similar projects or the industry segment instead.\n\n"
                    f"THE EXPANDED SECTION MUST HAVE AT LEAST {min_words} WORDS and maintain data integrity."
                )
                
                expanded_content = await llm.ainvoke(expansion_prompt)
                expanded_content = expanded_content.content if hasattr(expanded_content, 'content') else str(expanded_content)
                
                expanded_word_count = len(expanded_content.split())
                self.logger.info(f"Expanded problem section from {word_count} to {expanded_word_count} words")
                
                if expanded_word_count >= min_words:
                    content = expanded_content
                    word_count = expanded_word_count
                elif expanded_word_count > word_count:
                    # Still use the expansion if it's better than what we had
                    content = expanded_content
                    word_count = expanded_word_count
            except Exception as e:
                self.logger.error(f"Error expanding problem section: {str(e)}")
        
        # Cache the final content
        cache_mgr.save(
            {"content": content, "section_title": section_title, "word_count": word_count},
            "writer",
            "section",
            normalized_section,
            ttl_hours=24
        )
        
        return content

    def check_for_problem_section(self, section_title: str, problem_section_titles: Set[str]) -> bool:
        """
        Check if a section is a problem section.
        
        Args:
            section_title: Title of the section
            problem_section_titles: Set of problem section titles from state.problem_sections
            
        Returns:
            True if this is a problem section with explicitly missing required data, False otherwise
        """
        # Log the check to help with debugging
        is_problem = section_title in problem_section_titles
        
        if is_problem:
            self.logger.info(f"Section '{section_title}' IS in problem_section_titles: {problem_section_titles}")
        else:
            self.logger.info(f"Section '{section_title}' is NOT in problem_section_titles: {problem_section_titles}")
            
        # Only classify sections as problem sections if they're explicitly listed in problem_section_titles
        # This ensures we don't default to fallbacks unless we know data is missing
        return is_problem

    @openai_retry_decorator
    async def _generate_limited_content(self, project_name: str, section_title: str, description: str, 
                                      relevant_data: Dict, min_words: int) -> str:
        """
        Generate section content with very limited data, optimizing for model context window.
        Used for sections with minimal data to avoid overwhelming the model with irrelevant information.
        
        Args:
            project_name: Name of the project
            section_title: Section title
            description: Section description
            relevant_data: Limited relevant data for this section
            min_words: Minimum word count target
            
        Returns:
            Generated content
        """
        self.logger.info(f"Using limited content generation for section '{section_title}' with {len(relevant_data)} data points")
        
        # Create a specific, highly focused prompt
        prompt = f"""
Write a detailed analysis for the '{section_title}' section of a report on the {project_name} cryptocurrency project.

SECTION PURPOSE:
{description}

AVAILABLE DATA:
{json.dumps(relevant_data, indent=2) if relevant_data else "Limited data available for this section."}

INSTRUCTIONS:
1. Write a comprehensive section of at least {min_words} words
2. Include all relevant information from the provided data
3. Use a formal, analytical tone suitable for investors
4. Organize with logical subheadings as needed
5. IMPORTANT: If data is limited, acknowledge this explicitly rather than inventing facts
6. Focus on what can be reasonably inferred from available information
7. Format in Markdown

OUTPUT:
"""
        
        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip() if hasattr(response, 'content') else str(response)
            
            word_count = len(content.split())
            self.logger.info(f"Generated content for '{section_title}' using limited approach: {word_count} words")
            
            # If content is too short, note the limitation in content
            if word_count < min_words:
                self.logger.warning(f"Generated content for '{section_title}' is below target length ({word_count}/{min_words})")
                content += f"\n\n*Note: Limited data was available for a comprehensive analysis of {section_title}.*"
            
            return content
        except Exception as e:
            self.logger.error(f"Error generating limited content for '{section_title}': {str(e)}")
            return self._generate_fallback_content(project_name, section_title)

    def _log_data_source_sizes(self, data_sources: Dict) -> None:
        """
        Log the size of each data source to help identify context window issues.
        
        Args:
            data_sources: Dictionary of all data sources
        """
        try:
            self.logger.info("Data source size analysis:")
            total_size = 0
            
            for source_name, source_data in data_sources.items():
                source_json = json.dumps(source_data)
                source_size = len(source_json)
                total_size += source_size
                token_estimate = source_size / 4  # Rough estimate of token count
                
                self.logger.info(f"  - {source_name}: {source_size} bytes (~{int(token_estimate)} tokens)")
                
                # Flag large sources that could cause context window issues
                if token_estimate > 30000:
                    self.logger.warning(f"  - Source {source_name} may exceed context window limits")
            
            self.logger.info(f"Total data size: {total_size} bytes (~{int(total_size/4)} tokens)")
            
            # Warn if total size approaches context window
            if total_size/4 > 100000:
                self.logger.warning(f"Total data exceeds 100k tokens, will use data chunking for context window management")
        except Exception as e:
            self.logger.error(f"Error analyzing data source sizes: {e}")

    def _chunk_data_for_section(self, section_title: str, data_sources: Dict, max_tokens: int = 60000) -> Dict:
        """
        Create a smaller, focused version of data sources for a specific section to avoid context window limits.
        
        Args:
            section_title: Title of section being processed
            data_sources: Complete data sources dictionary
            max_tokens: Maximum approximate token limit
            
        Returns:
            Reduced data sources focused on the current section
        """
        try:
            # Make a clean copy to preserve original
            chunked_data = {}
            
            # Get normalized section name for better matching
            normalized_section = section_title.lower().replace(" ", "_")
            
            # First pass: Include only section-specific data
            bytes_used = 0
            
            # 1. Include web research specifically for this section
            if "web_research" in data_sources and isinstance(data_sources["web_research"], dict):
                chunked_data["web_research"] = {}
                for query, content in data_sources["web_research"].items():
                    # Only include research relevant to this section
                    if normalized_section in query.lower().replace(" ", "_"):
                        chunked_data["web_research"][query] = content
                        bytes_used += len(json.dumps(content))
            
            # 2. Include data whose keys match the section name
            for source, source_data in data_sources.items():
                if source != "web_research" and isinstance(source_data, dict):
                    for key, value in source_data.items():
                        # Check if key is relevant to this section
                        if normalized_section in key.lower().replace(" ", "_"):
                            if source not in chunked_data:
                                chunked_data[source] = {}
                            chunked_data[source][key] = value
                            bytes_used += len(json.dumps(value))
            
            # 3. Include key metrics for all sections
            if "coinmarketcap" in data_sources:
                for key in ["market_cap", "current_price", "volume_24h"]:
                    for file_name, file_data in data_sources["coinmarketcap"].items():
                        if isinstance(file_data, dict) and key in file_data:
                            if "coinmarketcap" not in chunked_data:
                                chunked_data["coinmarketcap"] = {}
                            if file_name not in chunked_data["coinmarketcap"]:
                                chunked_data["coinmarketcap"][file_name] = {}
                            chunked_data["coinmarketcap"][file_name][key] = file_data[key]
                            bytes_used += len(json.dumps(file_data[key]))
            
            # Validate we have reasonable data size
            token_estimate = bytes_used / 4
            self.logger.info(f"Chunked data for section '{section_title}': ~{int(token_estimate)} tokens")
            
            if token_estimate < 100:
                self.logger.warning(f"Very little data found for section '{section_title}', will use fallbacks")
            
            return chunked_data
            
        except Exception as e:
            self.logger.error(f"Error chunking data for section '{section_title}': {e}")
            return {}

@openai_retry_decorator
async def writer(state: Dict[str, Any], llm: ChatOpenAI, logger: logging.Logger, config=None) -> Dict[str, Any]:
    """
    Generate a research report draft based on collected data.
    Uses StateManager for consistent state access.
    """
    try:
        # Initialize StateManager for consistent state access
        state_manager = StateManager(logger=logger)
        
        # Get project name and report config using StateManager
        project_name = state_manager.get_project_name(state)
        report_config = state_manager.get_report_config(state)
        
        logger.info(f"Writer agent starting for project: {project_name}")
        logger.info(f"Using report config version: {report_config.get('version', 'unknown')}")
        
        # Update progress using StateManager
        state = state_manager.update_progress(state, f"Writing draft report for {project_name}...")
        
        if not report_config:
            logger.error("No report_config found in state")
            return state_manager.add_error(state, "writer", "No report_config found in state")
        
        sections = report_config.get("sections", [])
        if not sections:
            logger.error("No sections found in report_config")
            return state_manager.add_error(state, "writer", "No sections found in report_config")
        
        # Get all state data to analyze size
        all_data = state_manager.get_data(state)
        
        # Log data sizes to identify potential context window issues
        logger.info("Analyzing data sizes for writer context window management")
        total_size = 0
        large_sources = []
        
        for source_name, source_data in all_data.items():
            try:
                source_json = json.dumps(source_data)
                source_size = len(source_json)
                total_size += source_size
                token_estimate = source_size / 4  # Rough estimate of token count
                
                logger.info(f"Data source {source_name}: ~{int(token_estimate)} tokens")
                
                # Flag large sources for potential splitting
                if token_estimate > 30000:
                    logger.warning(f"Large data source detected: {source_name} (~{int(token_estimate)} tokens)")
                    large_sources.append(source_name)
            except Exception as e:
                logger.error(f"Error analyzing data source {source_name}: {str(e)}")
        
        logger.info(f"Total data size: ~{int(total_size/4)} tokens")
        
        # Get key metrics using StateManager
        key_metrics = state_manager.get_key_metrics(state)
        
        # Create a draft report structure
        draft = f"# {project_name} Research Report\n\n"
        
        # Initialize CacheManager for writer content
        cache_manager = CacheManager(project_name=project_name, logger=logger)
        
        # Initialize WriterAgent
        writer_agent = WriterAgent(llm=llm, logger=logger)
        
        # Generate draft using WriterAgent
        draft_content = await writer_agent.write_draft(state)
        draft += draft_content
        
        # Add disclaimer
        draft += "## Disclaimer\n\n"
        draft += "This research report is for informational purposes only. It does not constitute investment advice, "
        draft += "nor is it an offer to buy or sell any cryptocurrency or financial product. "
        draft += "The information contained in this report has been compiled from sources believed to be reliable, "
        draft += "but no representation or warranty, express or implied, is made as to its accuracy, completeness or correctness. "
        draft += "All opinions and estimates are given as of the date hereof and are subject to change without notice.\n\n"
        draft += f"*Generated on {datetime.now().strftime('%Y-%m-%d')}*\n\n"
        
        # Save draft to state using StateManager
        state = state_manager.update_draft(state, draft)
        
        # Update progress using StateManager
        state = state_manager.update_progress(state, f"Draft report completed for {project_name}")
        
        return state
        
    except Exception as e:
        logger.error(f"Error in writer agent: {str(e)}", exc_info=True)
        
        # Initialize StateManager if not done already
        if 'state_manager' not in locals():
            state_manager = StateManager(logger=logger)
            
        # Add error to state using StateManager
        return state_manager.add_error(state, "writer", str(e))

def _create_focused_data_for_section(all_data: Dict, section_title: str, logger: logging.Logger) -> Dict:
    """
    Create a smaller, focused version of data sources for a specific section to avoid context window limits.
    
    Args:
        all_data: Complete data sources dictionary
        section_title: Title of section being processed
        logger: Logger instance
        
    Returns:
        Reduced data sources focused on the current section
    """
    try:
        # Make a clean copy to preserve original
        focused_data = {}
        
        # Get normalized section name for better matching
        normalized_section = section_title.lower().replace(" ", "_")
        
        # First pass: Include only section-specific data
        
        # 1. Include web research specifically for this section
        if "web_research" in all_data and isinstance(all_data["web_research"], dict):
            focused_data["web_research"] = {}
            for query, content in all_data["web_research"].items():
                # Only include research relevant to this section
                if normalized_section in query.lower().replace(" ", "_"):
                    focused_data["web_research"][query] = content
        
        # 2. Include data whose keys match the section name
        for source, source_data in all_data.items():
            if source != "web_research" and isinstance(source_data, dict):
                for key, value in source_data.items():
                    # Check if key is relevant to this section
                    if normalized_section in key.lower().replace(" ", "_"):
                        if source not in focused_data:
                            focused_data[source] = {}
                        focused_data[source][key] = value
        
        # 3. Include key metrics for all sections
        if "coinmarketcap" in all_data:
            for key in ["market_cap", "current_price", "volume_24h"]:
                for file_name, file_data in all_data["coinmarketcap"].items():
                    if isinstance(file_data, dict) and key in file_data:
                        if "coinmarketcap" not in focused_data:
                            focused_data["coinmarketcap"] = {}
                        if file_name not in focused_data["coinmarketcap"]:
                            focused_data["coinmarketcap"][file_name] = {}
                        focused_data["coinmarketcap"][file_name][key] = file_data[key]
        
        # Log what we found
        sources_included = list(focused_data.keys())
        logger.info(f"Focused data for section '{section_title}' includes sources: {sources_included}")
        
        return focused_data
        
    except Exception as e:
        logger.error(f"Error creating focused data for section '{section_title}': {str(e)}")
        # Return empty dict on error to avoid breaking the flow
        return {}