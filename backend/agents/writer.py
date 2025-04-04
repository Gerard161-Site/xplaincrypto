# backend/agents/writer.py
import logging
import json
import os
from typing import Dict, Any, Optional
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

class WriterAgent:
    def __init__(self, llm: ChatOpenAI, logger: logging.Logger, hf_api_token: Optional[str] = None):
        self.llm = llm
        self.logger = logger
        self.hf_api_token = hf_api_token or os.getenv("HUGGINGFACE_API_KEY")
        self.use_local = not self.hf_api_token
        try:
            if self.use_local:
                self.summary_model = pipeline("summarization", model="google/pegasus-xsum")
                self.logger.info("Using local google/pegasus-xsum for summaries")
            else:
                self.hf_search = HuggingFaceSearch(api_token=self.hf_api_token)
                self.logger.info("Using Hugging Face API with google/pegasus-xsum")
        except Exception as e:
            self.logger.error(f"Failed to initialize summary model: {str(e)}", exc_info=True)
            self.use_local = False
            self.hf_search = None if not self.hf_api_token else HuggingFaceSearch(api_token=self.hf_api_token)
    
    async def write_draft(self, state: ResearchState) -> str:
        self.logger.info(f"Writing draft for {state.project_name}")
        report_config = state.report_config or {}
        if "sections" not in report_config:
            self.logger.error("No sections in report_config")
            raise ValueError("Report config missing 'sections' key")
        
        data_sources = {
            "coingecko": state.coingecko_data,
            "coinmarketcap": state.coinmarketcap_data,
            "defillama": state.defillama_data,
            "web_research": state.research_data,
            "structured_data": state.structured_data
        }
        data_sources["multi"] = {}
        for source in ["structured_data", "web_research", "coingecko", "coinmarketcap", "defillama"]:
            if data_sources[source]:
                data_sources["multi"].update({k: v for k, v in data_sources[source].items() if k not in data_sources["multi"]})
        
        key_metrics = self._format_key_metrics(data_sources["multi"])
        
        draft = state.draft or f"# {state.project_name} Research Report\n\n*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\nThis report is generated with AI assistance and should not be considered financial advice.\n\n"
        
        # Process sections in parallel (keeping original approach)
        tasks = []
        
        # Identify potential problem sections based on configuration and available data
        problem_sections = []
        for section in report_config.get("sections", []):
            section_title = section["title"]
            
            # Check if section requires data that we're missing
            required_fields = self._get_required_fields(section, report_config)
            missing_fields = [f for f in required_fields if f not in data_sources["multi"] or data_sources["multi"][f] is None]
            
            # Identify problem sections by:
            # 1. High minimum word requirements (400+)
            # 2. Many missing data fields
            # 3. Required sections with little research data
            is_problem = (
                (section.get("min_words", 0) >= 400 and len(missing_fields) > 2) or
                (section.get("required", False) and len(missing_fields) > len(required_fields) / 2) or
                (section.get("min_words", 0) >= 500)
            )
            
            if is_problem:
                problem_sections.append(section_title)
                self.logger.info(f"Identified potential problem section '{section_title}' with {len(missing_fields)} missing fields")
        
        for section in report_config.get("sections", []):
            section_title = section["title"]
            if "min_words" not in section or "max_words" not in section:
                self.logger.error(f"Section '{section_title}' missing min_words or max_words")
                raise ValueError(f"Section '{section_title}' must specify min_words and max_words")
            
            required_fields = self._get_required_fields(section, report_config)
            missing_fields = [f for f in required_fields if f not in data_sources["multi"] or data_sources["multi"][f] is None]
            if missing_fields and (self.hf_search or self.use_local):
                inferred_data = infer_missing_data(self.hf_search, data_sources["multi"], missing_fields, state.project_name, self.logger, 
                                                  model="distilbert-base-uncased-distilled-squad")
                data_sources["multi"].update(inferred_data)
                self.logger.info(f"Inferred {len(missing_fields)} fields for {section_title}: {missing_fields}")
            
            existing_content = ""
            if f"# {section_title}" in draft:
                start_idx = draft.index(f"# {section_title}") + len(f"# {section_title}\n\n")
                end_idx = draft.find("\n\n#", start_idx) if "\n\n#" in draft[start_idx:] else len(draft)
                existing_content = draft[start_idx:end_idx].strip()
            
            # Flag as problem section if it's in our dynamically identified list
            is_problem_section = section_title in problem_sections
            
            task = self._generate_section_content(section, existing_content, key_metrics, data_sources, state.project_name, is_problem_section)
            tasks.append((section_title, task))
        
        sections_content_list = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
        sections_content = {t[0]: c for t, c in zip(tasks, sections_content_list)}
        
        # For sections with exceptions or insufficient content, retry individually
        for section_title, content in sections_content.items():
            # Check if we got an exception or insufficient content
            if isinstance(content, Exception) or len(str(content).split()) < 100:
                self.logger.warning(f"Section '{section_title}' needs retry: {str(content) if isinstance(content, Exception) else 'insufficient content'}")
                section_config = next((s for s in report_config.get("sections", []) if s["title"] == section_title), None)
                if section_config:
                    try:
                        # Enhanced retry with more specific instructions
                        retry_content = await self._generate_problem_section(section_config, data_sources, key_metrics, state.project_name)
                        if not isinstance(retry_content, Exception) and len(retry_content.split()) > 100:
                            sections_content[section_title] = retry_content
                            self.logger.info(f"Successfully regenerated content for '{section_title}' with {len(retry_content.split())} words")
                    except Exception as e:
                        self.logger.error(f"Error in retry for '{section_title}': {str(e)}")
        
        # Build the final draft
        updated_draft = []
        for line in draft.split("\n"):
            if line.startswith("# ") and line[2:] in sections_content:
                section_title = line[2:]
                content = sections_content.get(section_title, "")
                if isinstance(content, Exception):
                    self.logger.error(f"Failed to generate content for {section_title}: {str(content)}")
                    content = await self._infer_section_content(section_title, section.get("prompt", ""), data_sources, state.project_name)
                updated_draft.append(f"# {section_title}\n\n{content}\n\n")
            else:
                updated_draft.append(line)
        
        for section in report_config.get("sections", []):
            section_title = section["title"]
            if f"# {section_title}" not in draft and section_title in sections_content:
                content = sections_content[section_title]
                if isinstance(content, Exception):
                    content = await self._infer_section_content(section_title, section.get("prompt", ""), data_sources, state.project_name)
                updated_draft.append(f"# {section_title}\n\n{content}\n\n")
        
        final_draft = "\n".join(updated_draft)
        self.logger.info(f"Draft generated: {len(final_draft.split())} words")
        
        # Verify each section meets minimum word requirements
        section_content = {}
        current_section = None
        for line in final_draft.split('\n'):
            if line.startswith('# '):
                current_section = line[2:].strip()
                section_content[current_section] = []
            elif current_section:
                section_content[current_section].append(line)
        
        # Check word counts against report_config requirements
        for section in report_config.get("sections", []):
            section_title = section["title"]
            min_words = section.get("min_words", 0)
            max_words = section.get("max_words", 0)
            
            if section_title in section_content:
                content_text = " ".join(section_content[section_title])
                word_count = len(content_text.split())
                
                if word_count < min_words:
                    self.logger.warning(f"Section '{section_title}' has only {word_count} words, below minimum {min_words} words")
                elif max_words > 0 and word_count > max_words:
                    self.logger.warning(f"Section '{section_title}' has {word_count} words, exceeding maximum {max_words} words")
                else:
                    self.logger.info(f"Section '{section_title}' has {word_count} words, within requirements ({min_words}-{max_words})")
            else:
                self.logger.warning(f"Section '{section_title}' is missing from draft")
        
        draft_headers = [line for line in final_draft.split('\n') if line.startswith('#')][:10]
        self.logger.info(f"Draft section headers: {draft_headers}")
        
        return final_draft
    
    @openai_retry_decorator
    async def _infer_section_content(self, section_title: str, description: str, data_sources: Dict, project_name: str) -> str:
        content = ""
        for source, data in data_sources.items():
            if source == "web_research":
                for query, summary in data.items():
                    if section_title.lower() in query.lower() and isinstance(summary, str) and summary.strip():
                        content = summary
                        self.logger.info(f"Used web research content for '{section_title}' from query '{query}'")
                        break
            if content:
                break
        
        if not content and (self.hf_search or self.use_local):
            prompt = f"Generate a 400-500 word summary for '{section_title}' of {project_name}: {description} based on available data: {json.dumps(data_sources['multi'])}"
            try:
                if self.use_local:
                    content = self.summary_model(prompt, max_length=500, min_length=400, do_sample=False)[0]["summary_text"]
                else:
                    result = self.hf_search.query("google/pegasus-xsum", prompt, {"max_length": 500})
                    content = result[0].get("generated_text", "") if result else ""
                self.logger.info(f"Inferred content for '{section_title}' via HF/local model")
            except Exception as e:
                self.logger.error(f"Failed to infer content for '{section_title}': {str(e)}")
        
        return content if content else f"Data unavailable for {section_title}."

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
    async def _generate_section_content(self, section: Dict, research_summary: str, key_metrics: Dict, data_sources: Dict, project_name: str, is_problem_section: bool = False) -> str:
        section_title = section["title"]
        description = section.get("prompt", "")
        min_words = section["min_words"]
        max_words = section["max_words"]
        
        if not research_summary.strip():
            research_summary = await self._infer_section_content(section_title, description, data_sources, project_name)
        
        # Determine section importance based on config properties
        # - Higher min_words requirement suggests more important section
        # - Required sections are more important
        is_key_section = section.get("required", False) and min_words >= 300
        
        # Enhanced template with exact section titles to ensure matching with report_config.json
        template = (
            "Write a professional, fact-focused section for a {project_name} cryptocurrency research report.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "1. Use EXACTLY this section title: '{section_title}'\n"
            "2. Word count: MUST be between {min_words}-{max_words} words\n"
            "3. Use factual data from the provided sources\n"
            "4. Include specific dates, numbers, and percentages where available\n"
            "5. Use a professional tone suitable for crypto investors\n"
            "6. Generate DETAILED, COMPREHENSIVE content\n"
            "7. Focus on: {description}\n"
            "8. If you include subsections, use double hashtag (##) for subsection titles\n"
            "9. If source data is limited, use general industry knowledge about cryptocurrency projects\n\n"
            "Research Summary:\n{research_summary}\n\n"
            "Key Metrics:\n{key_metrics}\n\n"
            "Data Sources:\n{data_sources}"
        )
        
        # For important sections, use a more specialized prompt
        if is_key_section or is_problem_section:
            template = (
                "Create a COMPREHENSIVE section for a {project_name} cryptocurrency research report focusing on '{section_title}'.\n\n"
                "CRITICAL REQUIREMENTS:\n"
                "1. Section title: EXACTLY '{section_title}' (do not change or modify this title)\n"
                "2. Length: MINIMUM {min_words} words - REQUIRED\n"
                "3. Create detailed content even if source data is limited\n"
                "4. Use a professional tone suitable for crypto investors\n"
                "5. Focus on: {description}\n\n"
                "If data is limited:\n"
                "- Draw on general knowledge about crypto projects\n"
                "- Include relevant industry standards, trends, and best practices\n"
                "- Create thoughtful, balanced analysis with proper disclaimers\n\n"
                "Research Summary:\n{research_summary}\n\n"
                "Available Data:\n{data_sources}\n\n"
                "Remember: This section MUST have {min_words}+ words of substantive content"
            )
        
        # Select the model based on section importance
        if is_key_section or is_problem_section or min_words > 400:
            # Use GPT-4 with high token limit for important sections
            section_llm = ChatOpenAI(
                model="gpt-4", 
                temperature=0.7,
                max_tokens=8000
            )
            self.logger.info(f"Using GPT-4 with 8000 tokens for important section: {section_title}")
        else:
            # Use main model for other sections
            section_llm = self.llm
            self.logger.info(f"Using standard LLM for section: {section_title}")
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | section_llm | StrOutputParser()
            
        try:
            content = await chain.ainvoke({
                "section_title": section_title,
                "project_name": project_name,
                "min_words": min_words,
                "max_words": max_words,
                "description": description,
                "research_summary": research_summary,
                "key_metrics": json.dumps(key_metrics, indent=2),
                "data_sources": json.dumps(data_sources["multi"], indent=2)
            })
            
            word_count = len(content.split())
            if word_count < min_words:
                self.logger.warning(f"Section {section_title} word count {word_count} below minimum {min_words}")
                
                # For insufficient content, retry with a different prompt emphasizing length
                retry_template = (
                    "You generated {word_count} words for the '{section_title}' section, but we need AT LEAST {min_words} words.\n\n"
                    "REWRITE this section to contain AT MINIMUM {min_words} words. Add more detailed analysis, examples, context, and industry insights.\n\n"
                    "Original content:\n{content}\n\n"
                    "ENSURE your new version meets the minimum word count of {min_words} words. This is CRITICAL."
                )
                retry_prompt = ChatPromptTemplate.from_template(retry_template)
                retry_chain = retry_prompt | section_llm | StrOutputParser()
                content = await retry_chain.ainvoke({
                    "section_title": section_title,
                    "min_words": min_words,
                    "word_count": word_count,
                    "content": content
                })
                
                # Final check after retry
                new_word_count = len(content.split())
                self.logger.info(f"After retry for {section_title}: {word_count} → {new_word_count} words")
            
            return content
        except Exception as e:
            self.logger.error(f"Error generating content for {section_title}: {str(e)}")
            return await self._infer_section_content(section_title, description, data_sources, project_name)

    def _format_key_metrics(self, combined_data: Dict) -> Dict:
        formatter = NumberFormatter()
        key_metrics = {}
        for key, value in combined_data.items():
            if key in ["current_price", "market_cap", "24h_volume", "total_supply", "circulating_supply", "tvl"]:
                if isinstance(value, (int, float)):
                    if key == "current_price":
                        key_metrics[key] = formatter.format_currency(value, precision=2)
                    elif key in ["market_cap", "24h_volume", "tvl"]:
                        key_metrics[key] = formatter.format_currency(value, precision=2)
                    elif key in ["total_supply", "circulating_supply"]:
                        key_metrics[key] = formatter.format_number(value, precision=2) + " tokens"
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
        
        # Use GPT-4 with high token limit for these sections
        section_llm = ChatOpenAI(
            model="gpt-4", 
            temperature=0.7,
            max_tokens=8000  # Increased to match main settings
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

    def _generate_content_for_section(self, project_name: str, section_title: str, section_data: Dict, 
                                max_tokens: int = 1500, use_gpt4: bool = False) -> str:
        """Generate content for a specific section with context control."""
        # Use focused prompt that doesn't include full data context
        prompt = (
            f"Write an informative and professional section on '{section_title}' for a cryptocurrency "
            f"research report about {project_name}. Focus on making this section detailed and "
            f"investment-grade quality, with at least 500 words of content.\n\n"
        )
        
        # Add relevant context based on section title
        if "executive summary" in section_title.lower():
            prompt += (
                f"This should provide a concise overview of {project_name}, highlighting its key features, "
                f"recent performance, market position, and investment thesis in about 400 words.\n\n"
            )
        elif "introduction" in section_title.lower():
            prompt += (
                f"This should cover {project_name}'s background, mission, core features, "
                f"and unique value proposition in the cryptocurrency landscape in about 500 words.\n\n"
            )
        elif "tokenomics" in section_title.lower():
            prompt += (
                f"This should detail {project_name}'s token supply, distribution, utility, economics model, "
                f"and any staking/rewards mechanisms in about 600 words. Include specific numbers and percentages.\n\n"
            )
        elif "market" in section_title.lower():
            prompt += (
                f"This should analyze {project_name}'s market position, competitors, trading volume, "
                f"liquidity, and price action. Include market cap and trading metrics in about 600 words.\n\n"
            )
        elif "technical" in section_title.lower():
            prompt += (
                f"This should explain {project_name}'s underlying technology, blockchain architecture, "
                f"consensus mechanism, and technical innovations in about 500 words.\n\n"
            )
        elif "developer" in section_title.lower():
            prompt += (
                f"This should cover {project_name}'s developer ecosystem, tools, documentation, "
                f"and user interface/experience design in about 500 words.\n\n"
            )
        elif "security" in section_title.lower():
            prompt += (
                f"This should assess {project_name}'s security measures, audit history, "
                f"vulnerabilities, and security practices in about 400 words.\n\n"
            )
        elif "liquidity" in section_title.lower():
            prompt += (
                f"This should analyze {project_name}'s liquidity metrics, trading volumes, "
                f"user adoption, and on-chain activity metrics in about 500 words.\n\n"
            )
        elif "governance" in section_title.lower():
            prompt += (
                f"This should detail {project_name}'s governance model, voting mechanisms, "
                f"community participation, and decentralization approach in about 400 words.\n\n"
            )
        elif "ecosystem" in section_title.lower():
            prompt += (
                f"This should explore {project_name}'s partnerships, integrations, and position "
                f"within the broader blockchain ecosystem in about 400 words.\n\n"
            )
        elif "risk" in section_title.lower():
            prompt += (
                f"This should identify key risks and potential opportunities associated with {project_name}, "
                f"including regulatory concerns, technological risks, and growth potential in about 450 words.\n\n"
            )
        elif "team" in section_title.lower():
            prompt += (
                f"This should profile {project_name}'s leadership team, development activity, "
                f"and organizational structure in about 400 words.\n\n"
            )
        elif "conclusion" in section_title.lower():
            prompt += (
                f"This should summarize the key findings about {project_name} and provide "
                f"a balanced investment perspective in about 300 words.\n\n"
            )
        
        # Add just the most relevant pieces of data rather than everything
        relevant_data = {}
        
        # Extract only section-relevant data points
        if "tokenomics" in section_title.lower():
            keys_to_extract = ['total_supply', 'circulating_supply', 'max_supply']
            for key in keys_to_extract:
                if key in section_data:
                    relevant_data[key] = section_data[key]
        elif "market" in section_title.lower():
            keys_to_extract = ['current_price', 'market_cap', '24h_volume', 'price_change_percentage_24h']
            for key in keys_to_extract:
                if key in section_data:
                    relevant_data[key] = section_data[key]
        
        if relevant_data:
            prompt += f"Incorporate these data points: {json.dumps(relevant_data)}\n\n"
            
        # Add final instructions
        prompt += (
            f"Write in a professional, analytical style suitable for sophisticated investors. "
            f"Be objective, balanced, and evidence-based. Format the response in clean markdown."
        )
        
        try:
            # Select appropriate model
            if use_gpt4:
                # Use GPT-4 for important sections, but with controlled max_tokens
                content = self.llm.invoke(prompt, max_tokens=max_tokens).content
            else:
                # Use standard model for other sections
                content = self.llm.invoke(prompt, max_tokens=max_tokens).content
                
            # Basic validation and fallback
            if len(content.split()) < 100:
                self.logger.warning(f"Generated content for {section_title} is suspiciously short. Using fallback.")
                return self._generate_fallback_content(project_name, section_title)
                
            return content
        except Exception as e:
            self.logger.error(f"Error generating content for {section_title}: {str(e)}")
            return self._generate_fallback_content(project_name, section_title)
            
    def _generate_fallback_content(self, project_name: str, section_title: str) -> str:
        """Generate fallback content when the primary content generation fails."""
        base_content = (
            f"## {section_title}\n\n"
            f"This section covers {section_title.lower()} aspects of {project_name}. "
            f"{project_name} demonstrates several important characteristics in this area that warrant investor attention. "
            f"Further analysis with more specific data is recommended for a complete understanding."
        )
        
        # Add section-specific fallback content
        if "executive summary" in section_title.lower():
            base_content += (
                f" {project_name} is a cryptocurrency project with distinctive features in the blockchain ecosystem. "
                f"This report examines its fundamental aspects, market performance, technical architecture, and investment potential."
            )
        elif "tokenomics" in section_title.lower():
            base_content += (
                f" The token economics of {project_name} include its supply mechanisms, distribution model, and utility within its ecosystem. "
                f"The token plays a central role in the project's functionality and value proposition."
            )
            
        return base_content

@openai_retry_decorator
async def writer(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> Dict:
    # Get project name from state
    project_name = state.get("project_name", "Unknown Project")
    logger.info(f"Writer agent processing for {project_name}")
    
    # Update progress
    if hasattr(state, 'update_progress'):
        state.update_progress(f"Writing draft report for {project_name}...")
    else:
        state["progress"] = f"Writing draft report for {project_name}..."
    
    try:
        hf_api_token = config.get("hf_api_token") if config else os.getenv("HUGGINGFACE_API_KEY")
        writer_agent = WriterAgent(llm, logger, hf_api_token)
        
        # Create a temporary ResearchState object for backward compatibility
        temp_state = ResearchState(project_name=project_name)
        for key, value in state.items():
            if hasattr(temp_state, key):
                setattr(temp_state, key, value)
                
        # Call the writer agent with the temp state
        draft = await writer_agent.write_draft(temp_state)
        
        # Set the draft in the dictionary state
        state["draft"] = draft
        
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Draft report written for {project_name}")
        else:
            state["progress"] = f"Draft report written for {project_name}"
    except Exception as e:
        logger.error(f"Error in writer: {str(e)}", exc_info=True)
        state["draft"] = f"# {project_name} Research Report\n\n*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\nThis report is generated with AI assistance and should not be considered financial advice.\n\n" + \
                     f"Error: {str(e)}. Insufficient data from API, web search, or inference."
        
        # Update progress
        if hasattr(state, 'update_progress'):
            state.update_progress(f"Created minimal draft due to error: {str(e)}")
        else:
            state["progress"] = f"Created minimal draft due to error: {str(e)}"
    
    return state

def writer_sync(state: Dict, llm: ChatOpenAI, logger: logging.Logger, config: Optional[Dict[str, Any]] = None) -> Dict:
    return asyncio.run(writer(state, llm, logger, config))