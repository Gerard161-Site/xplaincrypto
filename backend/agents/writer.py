# backend/agents/writer.py
import logging
import json
import os
import math
from typing import Dict, Any, Optional, List, Set, Tuple
from langchain_openai import ChatOpenAI
from backend.state import ResearchState
from datetime import datetime
from backend.utils.inference import infer_missing_data
from backend.retriever.huggingface_search import HuggingFaceSearch
from transformers import pipeline
import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.utils.number_formatter import NumberFormatter
from backend.utils.inference import openai_retry_decorator
from backend.utils.cache_utils import CacheManager
import time

class WriterAgent:
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger, hf_api_token: Optional[str] = None):
        """
        Initialize the WriterAgent with language model and HuggingFace capabilities.
        
        Args:
            llm: Language model for content generation
            logger: Logger instance for tracking operations
            hf_api_token: Optional HuggingFace API token for external inference
        """
        self.llm = llm
        self.logger = logger
        self.hf_api_token = hf_api_token or os.getenv("HUGGINGFACE_API_KEY")
        self.use_local = not self.hf_api_token
        
        # Initialize with a lightweight model for better performance
        try:
            if self.use_local:
                # Use a lighter model (distilbart instead of pegasus-xsum) for better performance
                self.summary_model = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
                self.logger.info("Using local sshleifer/distilbart-cnn-12-6 for summaries")
            else:
                self.hf_search = HuggingFaceSearch(api_token=self.hf_api_token)
                self.logger.info("Using Hugging Face API with summarization models")
        except Exception as e:
            self.logger.error(f"Failed to initialize summary model: {str(e)}", exc_info=True)
            self.use_local = False
            self.hf_search = None if not self.hf_api_token else HuggingFaceSearch(api_token=self.hf_api_token)
    
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
            
        # Get problem sections information
        problem_sections = []
        if isinstance(state, dict):
            problem_sections = state.get("problem_sections", [])
        else:
            problem_sections = getattr(state, "problem_sections", []) if hasattr(state, "problem_sections") else []
            
        # Track problem section titles for easier lookups
        problem_section_titles = {ps["title"] for ps in problem_sections if "title" in ps}
        self.logger.info(f"Problem section titles: {problem_section_titles}")
        
        # Get report configuration
        report_config = None
        if isinstance(state, dict):
            report_config = state.get("report_config", {})
        else:
            report_config = getattr(state, "report_config", {})
        
        if not report_config:
            self.logger.error("No report configuration found")
            return "Error: No report configuration found"
        
        # Get sections from report config
        sections = report_config.get("sections", [])
        if not sections:
            self.logger.error("No sections found in report configuration")
            return "Error: No sections found in report configuration"
        
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
                # For problem sections, use HuggingFace immediately for better performance
                if is_problem_section:
                    self.logger.info(f"Using HuggingFace fallback for problem section: {section_title}")
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
                cache_mgr.save_to_cache(
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
    async def _infer_section_content(self, section_title: str, description: str, data_sources: Dict, project_name: str) -> str:
        """
        Infer content for a section using available data sources and HuggingFace.
        
        Args:
            section_title: Section title
            description: Section description/prompt
            data_sources: Available data sources
            project_name: Name of the project
            
        Returns:
            Inferred content for the section
        """
        # Check cache first
        normalized_section = section_title.lower().replace(" ", "_")
        cache_mgr = CacheManager(project_name=project_name, logger=self.logger)
        cached_content = cache_mgr.load("writer_infer", "section", normalized_section)
        
        if cached_content and "content" in cached_content:
            self.logger.info(f"Using cached inferred content for {section_title}")
            return cached_content["content"]
            
        # Try to find content in web research data
        content = ""
        for source, data in data_sources.items():
            if source == "web_research" and isinstance(data, dict):
                for query, summary in data.items():
                    if section_title.lower() in query.lower() and isinstance(summary, str) and summary.strip():
                        content = summary
                        self.logger.info(f"Used web research content for '{section_title}' from query '{query}'")
                        break
            if content:
                break
        
        # If no content found in web research, use HuggingFace or local summarization
        if not content and (self.hf_search or self.use_local):
            # Extract relevant data for this section
            available_data = {k: v for k, v in data_sources.items() if k != "web_research"}
            relevant_data = {}
            
            # Look for data across all sources
            for source, source_data in available_data.items():
                if isinstance(source_data, dict):
                    for file_name, file_data in source_data.items():
                        # Look for section name in file name as a heuristic
                        if section_title.lower().replace(" ", "") in file_name.lower().replace("_", ""):
                            if isinstance(file_data, dict):
                                relevant_data[file_name] = file_data
            
            # If no section-specific data, use multi-source data if available
            if not relevant_data and "multi" in data_sources:
                relevant_data = {"multi": data_sources["multi"]}
                
            if not relevant_data:
                self.logger.warning(f"No data sources available for {section_title}")
                content = f"Data unavailable for {section_title}."
            else:
                try:
                    # Create a more focused prompt
                    prompt = (
                        f"Create a factual 400-word summary for the '{section_title}' section "
                        f"of a report on {project_name}. {description} "
                        f"Use ONLY these verified data points: {json.dumps(relevant_data)[:2000]}... "
                        f"Do NOT include any information not supported by the data."
                    )
                    
                    if self.use_local:
                        # Use local model with controlled parameters
                        inference_result = self.summary_model(
                            prompt, 
                            max_length=500,  
                            min_length=300,
                            do_sample=False
                        )
                        content = inference_result[0]["summary_text"] if inference_result else ""
                    else:
                        # Use HuggingFace API
                        result = self.hf_search.query(
                            "sshleifer/distilbart-cnn-12-6", 
                            prompt, 
                            {"max_length": 500}
                        )
                        content = result[0].get("generated_text", "") if result and len(result) > 0 else ""
                        
                    self.logger.info(f"Inferred content for '{section_title}' via HF/local model")
                except Exception as e:
                    self.logger.error(f"Failed to infer content for '{section_title}': {str(e)}")
                    content = f"Data unavailable for {section_title}."
        
        # Cache successful inference
        if content and content != f"Data unavailable for {section_title}.":
            cache_mgr.save_to_cache(
                {"content": content, "section_title": section_title},
                "writer_infer",
                "section",
                normalized_section,
                ttl_hours=24
            )
        
        return content

    def _get_required_fields(self, section: Dict, report_config: Dict) -> list[str]:
        fields = set()
        if "data_fields" in section:
            fields.update(section["data_fields"])
        for vis in section.get("visualizations", []):
            vis_config = report_config.get("visualization_types", {}).get(vis, {})
            if "data_field" in vis_config:
                fields.add(vis_config["data_field"])
            if "data_fields" in vis_config:
                fields.update(vis_config["data_fields"])
        if "fallback_fields" in section:
            fields.update(section["fallback_fields"])
        return list(fields)
    
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
            # Return a placeholder message instead of trying to call another method that might require parameters we don't have
            return f"Content generation failed for {section_name}. Error: {str(e)}"

    @openai_retry_decorator
    async def _generate_section_content(self, section: Dict, research_summary: str, key_metrics: Dict, data_sources: Dict, project_name: str, is_problem_section: bool = False) -> str:
        """
        Generate content for a section using optimized LLM parameters.
        Prioritizes using existing research data and enforces minimum word counts.
        
        Args:
            section: Section configuration
            research_summary: Existing content for the section if available
            key_metrics: Preprocessed key metrics from all data sources
            data_sources: All available data sources
            project_name: Name of the project
            is_problem_section: Whether this section has explicitly marked data issues
            
        Returns:
            Generated content for the section
        """
        section_title = section["title"]
        description = section.get("prompt", "")
        min_words = section.get("min_words", 400)
        max_words = section.get("max_words", 700)
        
        # Check if we have existing content that meets minimum requirements
        if research_summary.strip() and len(research_summary.split()) >= min_words:
            self.logger.info(f"Using existing research content for {section_title} ({len(research_summary.split())} words)")
            return research_summary
            
        # If not enough existing content, try to generate from research data
        # First check if we have any web_research data for this section
        section_research = ""
        if "web_research" in data_sources:
            for query, content in data_sources["web_research"].items():
                # Check if the query is relevant to this section
                query_lower = query.lower()
                if (section_title.lower() in query_lower or 
                    any(keyword in query_lower for keyword in section_title.lower().split())):
                    section_research += f"{content}\n\n"
        
        # Gather other relevant data for this section
        data_for_section = {}
        if "data_sources" in section:
            for source_name in section["data_sources"]:
                if source_name in data_sources:
                    data_for_section[source_name] = data_sources[source_name]
        
        # If we have good research data, use it even if this section is in problem_sections
        has_research_data = len(section_research.strip().split()) >= 100
        
        # Only use fallback if this is explicitly a problem section AND we don't have research data
        if is_problem_section and not has_research_data:
            self.logger.info(f"Using HuggingFace fallback for problem section: {section_title}")
            return await self._generate_content_for_problem_section(
                project_name=project_name,
                section=section,
                data_sources=data_sources,
                key_metrics=key_metrics
            )
        
        # Use either the research summary or the compiled section research
        context = research_summary.strip() if research_summary.strip() else section_research
        
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
    async def _generate_problem_section(self, section_config: Dict, data_sources: Dict, key_metrics: Dict, project_name: str) -> str:
        """Special method to generate content for problematic sections using a more specialized approach."""
        section_title = section_config["title"]
        description = section_config.get("prompt", "")
        min_words = section_config.get("min_words", 400)
        max_words = section_config.get("max_words", 700)
        
        # Build a generic prompt based on the section's own description
        prompt_text = (
            f"Create a comprehensive section on {section_title} for {project_name}.\n\n"
            f"CRITICAL REQUIREMENTS:\n"
            f"1. This section MUST contain AT LEAST {min_words} words of detailed content\n"
            f"2. Create thorough, specific content even if direct data is limited\n"
            f"3. Use professional investment-focused language\n\n"
            f"Focus on: {description}\n\n"
            f"When creating this section:\n"
            f"- Draw on general knowledge of crypto/blockchain projects\n"
            f"- Include industry standards and best practices\n"
            f"- Provide specific examples and detailed analysis\n"
            f"- Cover all aspects mentioned in the section description\n\n"
            f"If specific {project_name} data is unavailable, extrapolate from general project patterns "
            f"and similar blockchain projects in the same category.\n\n"
            f"THIS SECTION REQUIRES A MINIMUM OF {min_words} WORDS."
        )
        
        # Use GPT-4 with reduced token limit for these sections
        section_llm = ChatOpenAI(
            model="gpt-4", 
            temperature=0.7,
            max_tokens=3500  # Reduced to avoid context limit exceeded errors
        )
        
        prompt = ChatPromptTemplate.from_template(prompt_text)
        chain = prompt | section_llm | StrOutputParser()
        
        try:
            self.logger.info(f"Generating specialized content for section: {section_title}")
            content = await chain.ainvoke({
                "section_title": section_title,
                "project_name": project_name,
                "min_words": min_words,
                "max_words": max_words,
                "description": description,
                "key_metrics": json.dumps(key_metrics, indent=2),
                "data_sources": json.dumps(data_sources["multi"], indent=2)
            })
            
            word_count = len(content.split())
            self.logger.info(f"Generated {word_count} words for section '{section_title}'")
            
            # If still insufficient, try one more time with even stronger emphasis
            if word_count < min_words:
                self.logger.warning(f"Still insufficient content ({word_count}/{min_words}) for '{section_title}'. Retrying...")
                
                retry_prompt = ChatPromptTemplate.from_template(
                    f"The content you generated for {section_title} is only {word_count} words, but we need AT LEAST {min_words}.\n\n"
                    f"COMPLETELY REWRITE and EXPAND this section to contain AT MINIMUM {min_words} words.\n\n"
                    f"Original content:\n{content}\n\n"
                    f"Add more depth, examples, context, and analysis. THIS IS CRITICAL."
                )
                
                retry_chain = retry_prompt | section_llm | StrOutputParser()
                content = await retry_chain.ainvoke({})
                
                final_word_count = len(content.split())
                self.logger.info(f"After final retry for '{section_title}': {word_count} → {final_word_count} words")
            
            return content
            
        except Exception as e:
            self.logger.error(f"Error in _generate_problem_section for '{section_title}': {str(e)}")
            return f"Data unavailable for {section_title}. This section requires {min_words} words of content about {description}."

    def _generate_fallback_content(self, project_name: str, section_title: str) -> str:
        """
        Generate basic fallback content when all other content generation methods fail.
        This is the last resort when nothing else works.
        
        Args:
            project_name: Name of the project
            section_title: Section title
            
        Returns:
            Basic fallback content
        """
        self.logger.warning(f"Using basic fallback content for {section_title}")
        
        base_content = (
            f"# {section_title}\n\n"
            f"This section would typically cover {section_title.lower()} aspects of {project_name}. "
            f"However, sufficient verified data is currently unavailable for a comprehensive analysis.\n\n"
            f"Data limitations prevent us from providing detailed insights in this area. "
            f"For a thorough assessment, we recommend consulting official project documentation "
            f"and verified primary sources.\n\n"
            f"## Data Status\n\n"
            f"- **Status**: Data unavailable or insufficient\n"
            f"- **Next steps**: Consult primary sources\n"
            f"- **Last checked**: {datetime.now().strftime('%Y-%m-%d')}\n"
        )
        
        # Add section-specific fallback content
        if "executive summary" in section_title.lower():
            base_content += (
                f"\n## Project Overview\n\n"
                f"{project_name} is a cryptocurrency project in the blockchain ecosystem. "
                f"A detailed executive summary requires comprehensive verified data, which is currently unavailable."
            )
        elif "tokenomics" in section_title.lower():
            base_content += (
                f"\n## Token Economics\n\n"
                f"The token economics of {project_name} would typically include supply mechanisms, "
                f"distribution model, and utility within its ecosystem. "
                f"Verified tokenomics data is required for detailed analysis."
            )
        elif "market" in section_title.lower():
            base_content += (
                f"\n## Market Considerations\n\n"
                f"A proper market analysis would cover price trends, trading volume, market capitalization, "
                f"and competitive positioning of {project_name}. "
                f"This analysis requires verified market data from reliable sources."
            )
        elif "technical" in section_title.lower():
            base_content += (
                f"\n## Technical Assessment\n\n"
                f"A technical assessment would analyze the blockchain architecture, "
                f"consensus mechanism, and technical innovations of {project_name}. "
                f"Reliable technical documentation is necessary for a proper evaluation."
            )
            
        return base_content

    def _extract_key_metrics(self, data_sources: Dict) -> Dict:
        """
        Extract key metrics from various data sources.
        
        Args:
            data_sources: Dictionary of data from different sources
            
        Returns:
            Dictionary of key metrics consolidated from all sources
        """
        key_metrics = {}
        
        # Extract from coinmarketcap data
        if "coinmarketcap" in data_sources:
            coinmarketcap_data = data_sources["coinmarketcap"]
            if isinstance(coinmarketcap_data, dict):
                for file_name, file_data in coinmarketcap_data.items():
                    if isinstance(file_data, dict):
                        for metric in ["current_price", "market_cap", "volume_24h", "circulating_supply", "total_supply", "max_supply"]:
                            if metric in file_data and metric not in key_metrics:
                                key_metrics[metric] = file_data[metric]
        
        # Extract from defillama data
        if "defillama" in data_sources:
            defillama_data = data_sources["defillama"]
            if isinstance(defillama_data, dict):
                for file_name, file_data in defillama_data.items():
                    if isinstance(file_data, dict):
                        for metric in ["tvl", "tvl_history"]:
                            if metric in file_data and metric not in key_metrics:
                                key_metrics[metric] = file_data[metric]
        
        # Extract from tokenomics data
        if "tokenomics" in data_sources:
            tokenomics_data = data_sources["tokenomics"]
            if isinstance(tokenomics_data, dict):
                for file_name, file_data in tokenomics_data.items():
                    if isinstance(file_data, dict):
                        for metric in ["token_allocation", "token_distribution"]:
                            if metric in file_data and metric not in key_metrics:
                                key_metrics[metric] = file_data[metric]
        
        return key_metrics

    def _get_focused_data(self, section: Dict, available_data: Dict) -> Dict:
        """
        Extract only the data relevant to a specific section to reduce prompt size.
        
        Args:
            section: Section configuration
            available_data: All available data
            
        Returns:
            Dictionary of data focused on section needs
        """
        focused_data = {}
        
        # Extract data source names from section config
        data_sources = section.get("data_sources", [])
        
        # Extract fallback fields from section config
        fallback_fields = section.get("fallback_fields", [])
        
        # Copy only the required data sources
        for source in data_sources:
            if source in available_data:
                focused_data[source] = available_data[source]
                
        # For multi-source data, extract only the relevant fields
        if "multi" in available_data and fallback_fields:
            if "multi" not in focused_data:
                focused_data["multi"] = {}
                
            for field in fallback_fields:
                if field in available_data.get("multi", {}):
                    focused_data["multi"][field] = available_data["multi"][field]
                    
        return focused_data

    async def _generate_content_for_problem_section(self, project_name: str, section: Dict, 
                                        data_sources: Dict, key_metrics: Dict) -> str:
        """
        Generate content for sections with data problems using HuggingFace or fallback methods.
        For sections identified in problem_sections, we use this more conservative approach
        that avoids speculative content generation but still aims to meet word count requirements.
        
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
        cached_content = cache_mgr.load("writer_hf", "section", normalized_section)
        
        if cached_content and "content" in cached_content:
            content = cached_content["content"]
            word_count = len(content.split())
            
            # Only use cached content if it meets minimum word count
            if word_count >= min_words:
                self.logger.info(f"Using cached HF content for problem section: {section_title} ({word_count} words)")
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
                    1. This section MUST contain AT LEAST {min_words} words
                    2. Focus on: {description}
                    3. Use only verified data - DO NOT fabricate information
                    
                    Available verified data:
                    {relevant_data_json}
                    
                    Key metrics:
                    {key_metrics_json}
                    
                    INSTRUCTIONS:
                    - Start with the verified data points above
                    - Expand with general educational content about this topic area
                    - Include relevant industry standards and best practices
                    - Clearly mark when moving from verified data to general information
                    - GENERATE AT LEAST {min_words} WORDS TOTAL
                    
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
                1. This section MUST contain AT LEAST {min_words} words of detailed content
                2. Focus on: {description}
                3. Clearly indicate that specific project data is limited
                
                INSTRUCTIONS:
                - Begin by acknowledging data limitations for {project_name} in this area
                - Provide educational content about this topic in cryptocurrency/blockchain projects
                - Discuss industry standards, methodologies, and best practices
                - Include general information investors should know about this aspect
                - Maintain a professional, educational tone
                - GENERATE AT LEAST {min_words} WORDS TOTAL
                
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
                
                expanded_content = llm.invoke(expansion_prompt).content
                
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
        cache_mgr.save_to_cache(
            {"content": content, "section_title": section_title, "word_count": word_count},
            "writer_hf",
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
        Generate content with limited verified data points while still meeting word count requirements.
        
        Args:
            project_name: Name of the project
            section_title: Title of the section
            description: Description of the section
            relevant_data: Dictionary of relevant data points
            min_words: Minimum word count required
            
        Returns:
            Generated section content
        """
        self.logger.info(f"Generating limited content for {section_title} with {len(relevant_data)} data points")
        
        # First try with gpt-3.5-turbo for better performance
        try:
            llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=0.7,
                max_tokens=2000
            )
            
            prompt = ChatPromptTemplate.from_template(
                """
                Create a detailed section on {section_title} for {project_name}.
                
                CRITICAL REQUIREMENTS:
                1. This section MUST contain AT LEAST {min_words} words
                2. Focus on: {description}
                3. Use only verified data - DO NOT fabricate information about {project_name}
                
                Available verified data:
                {relevant_data_json}
                
                INSTRUCTIONS:
                - Start with the limited verified data above
                - Expand with educational content about this topic area in cryptocurrency
                - Include industry standards and best practices
                - Clearly mark where you transition from verified project data to general information
                - GENERATE AT LEAST {min_words} WORDS TOTAL
                
                If verified data is limited, address this transparently while still providing valuable 
                general information about similar aspects in other crypto projects.
                """
            )
            
            chain = prompt | llm | StrOutputParser()
            
            content = await chain.ainvoke({
                "section_title": section_title,
                "project_name": project_name,
                "min_words": min_words,
                "description": description,
                "relevant_data_json": json.dumps(relevant_data, indent=2)
            })
            
            word_count = len(content.split())
            self.logger.info(f"Generated limited content for {section_title}: {word_count} words")
            
            # If not enough words, try once more with explicit instructions
            if word_count < min_words:
                self.logger.warning(f"Limited content too short ({word_count}/{min_words}). Using GPT-4.")
                
                gpt4_llm = ChatOpenAI(
                    model="gpt-4", 
                    temperature=0.7,
                    max_tokens=3000
                )
                
                retry_prompt = ChatPromptTemplate.from_template(
                    """
                    Create a COMPREHENSIVE educational section on {section_title} for {project_name}.
                    
                    CRITICAL REQUIREMENTS:
                    1. This section MUST contain AT LEAST {min_words} words of detailed content
                    2. Focus on: {description}
                    3. Be intellectually honest and accurate
                    
                    Available verified data:
                    {relevant_data_json}
                    
                    INSTRUCTIONS:
                    - Begin with available verified data (if any)
                    - Clearly acknowledge data limitations for {project_name}
                    - Provide detailed educational content about this aspect in cryptocurrency projects
                    - Discuss industry standards, methodologies, and best practices
                    - Include implications for investors
                    - Maintain a professional, educational tone
                    - YOUR RESPONSE MUST BE AT LEAST {min_words} WORDS
                    
                    You must produce a substantive, educational section even with limited project-specific data.
                    """
                )
                
                retry_chain = retry_prompt | gpt4_llm | StrOutputParser()
                
                retry_content = await retry_chain.ainvoke({
                    "section_title": section_title,
                    "project_name": project_name,
                    "min_words": min_words,
                    "description": description,
                    "relevant_data_json": json.dumps(relevant_data, indent=2)
                })
                
                retry_word_count = len(retry_content.split())
                
                # Use the better content (prefer higher word count but must meet minimum)
                if retry_word_count >= min_words or retry_word_count > word_count:
                    self.logger.info(f"Using GPT-4 content for {section_title}: {retry_word_count} words")
                    return retry_content
            
            # Return original content if it's good enough
            if word_count >= min_words:
                return content
                
            # If we got here, the content is still too short, create a hybrid with fallback
            fallback = self._generate_fallback_content(project_name, section_title)
            hybrid_content = f"{content}\n\n{fallback}"
            
            self.logger.info(f"Using hybrid content for {section_title}: {len(hybrid_content.split())} words")
            return hybrid_content
            
        except Exception as e:
            self.logger.error(f"Error generating limited content: {str(e)}")
            return self._generate_fallback_content(project_name, section_title)

@openai_retry_decorator
async def writer(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> Dict:
    """
    Asynchronous writer function for generating research reports from state data.
    
    Args:
        state: Dictionary containing research state
        llm: Language model instance to use for generation
        logger: Logger instance
        config: Optional configuration dictionary
        
    Returns:
        Updated state dictionary with draft content
    """
    # Performance tracking
    start_time = time.time()
    
    # Create a copy of the state to avoid modifying the original
    updated_state = state.copy() if isinstance(state, dict) else state
    
    try:
        # Get project name
        project_name = state.get('project_name', 'Unknown Project') if isinstance(state, dict) else getattr(state, 'project_name', 'Unknown Project')
        logger.info(f"Async writer creating draft for {project_name}")
        
        # Create writer agent
        writer_agent = WriterAgent(
            llm=llm,
            logger=logger,
            hf_api_token=os.getenv("HUGGINGFACE_API_KEY")
        )
        
        # Generate draft
        draft_content = await writer_agent.write_draft(state)
        
        # Update state with draft
        if isinstance(updated_state, dict):
            updated_state['draft'] = draft_content
        else:
            updated_state.draft = draft_content
            
        elapsed_time = time.time() - start_time
        logger.info(f"Successfully created draft with {len(draft_content.split())} words in {elapsed_time:.2f} seconds")
        return updated_state
        
    except Exception as e:
        logger.error(f"Error in async writer: {str(e)}", exc_info=True)
        
        # Record error in state
        if isinstance(updated_state, dict):
            if "errors" not in updated_state:
                updated_state["errors"] = {}
            updated_state["errors"]["writer"] = f"Failed to create draft: {str(e)}"
        
        return updated_state

async def writer_sync(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> Dict:
    """
    Synchronous version of the writer function for compatibility with workflow_manager.
    This wraps the asynchronous WriterAgent functionality in a synchronous interface.
    """
    # Performance tracking
    start_time = time.time()
    
    # Return a copy of the state to avoid modifying the original
    updated_state = state.copy() if isinstance(state, dict) else state
    
    # Ensure errors is a dictionary
    if isinstance(updated_state, dict):
        if "errors" not in updated_state:
            updated_state["errors"] = {}
        elif not isinstance(updated_state["errors"], dict):
            updated_state["errors"] = {}
    
    try:
        project_name = state.get("project_name", "Unknown Project") if isinstance(state, dict) else getattr(state, "project_name", "Unknown Project")
        logger.info(f"Writer sync creating draft for {project_name}")
        
        # Create writer agent instance with optimized parameters
        writer_agent = WriterAgent(
            llm=llm,
            logger=logger,
            hf_api_token=os.getenv("HUGGINGFACE_API_KEY")
        )
        
        try:
            # Run the async agent directly
            draft_content = await writer_agent.write_draft(state)
            
            # Update state with draft content
            if isinstance(updated_state, dict):
                updated_state["draft"] = draft_content
                updated_state["progress"] = f"Draft created for {project_name}"
            else:
                updated_state.draft = draft_content
                if hasattr(updated_state, 'update_progress'):
                    updated_state.update_progress(f"Draft created for {project_name}")
                else:
                    updated_state.progress = f"Draft created for {project_name}"
                    
            elapsed_time = time.time() - start_time
            logger.info(f"Successfully created draft with {len(draft_content.split())} words in {elapsed_time:.2f} seconds")
            return updated_state
            
        except Exception as e:
            logger.error(f"Error in writer_sync async execution: {str(e)}", exc_info=True)
            if isinstance(updated_state, dict):
                updated_state["errors"]["writer"] = str(e)
            return updated_state
            
    except Exception as e:
        logger.error(f"Error in writer_sync setup: {str(e)}", exc_info=True)
        if isinstance(updated_state, dict):
            updated_state["errors"]["writer_setup"] = str(e)
        return updated_state