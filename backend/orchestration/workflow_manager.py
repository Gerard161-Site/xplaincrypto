import logging
import json
import os
import time
import asyncio
from typing import Dict, Any, Optional, List, TypedDict
from copy import deepcopy

class WorkflowState(TypedDict):
    project_name: str
    report_config: Dict[str, Any]
    fast_mode: bool
    mode: str
    visualization_request: List[Dict[str, Any]]
    errors: Dict[str, Any]
    review_status: Dict[str, Any]
    writer_output: Dict[str, Any]
    visualizer_output: Dict[str, Any]
    merged_output: Dict[str, Any]
    final_report: str
    report_path: str
    visualization_list: List[Dict[str, Any]]

class WorkflowManager:
    def __init__(
        self,
        logger: logging.Logger,
        config_path: str = "backend/config/report_config.json",
        progress_tracker=None,
        error_reporter=None
    ):
        self.logger = logger
        self.config_path = config_path
        self.report_config = self._load_report_config()
        self.llm = None
        self.llm_model = None
        self.progress_tracker = progress_tracker
        self.error_reporter = error_reporter
        if progress_tracker:
            self.logger.info("ProgressTracker initialized in WorkflowManager")
        if error_reporter:
            self.logger.info("ErrorReporter initialized in WorkflowManager")

    def _load_report_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                if "sections" not in config or not isinstance(config["sections"], list):
                    self.logger.error("Invalid report_config.json: 'sections' must be a list")
                    return {}
                self.logger.info(f"Loaded report configuration with {len(config.get('sections', []))} sections")
                return config
        except Exception as e:
            self.logger.error(f"Error loading report_config: {str(e)}")
            if self.error_reporter:
                self.error_reporter.report_error(
                    e, category="system_error", component="workflow_manager",
                    context={"config_path": self.config_path}
                )
            return {}

    def initialize_llm(self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None):
        from langchain_openai import ChatOpenAI
        try:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.llm = ChatOpenAI(model=model_name, api_key=api_key)
            self.llm_model = model_name
            self.logger.info(f"Initialized LLM with model {model_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing LLM: {str(e)}")
            if self.error_reporter:
                self.error_reporter.report_error(
                    e, category="system_error", component="workflow_manager",
                    context={"model_name": model_name}
                )
            return False

    async def initialize(self):
        """Asynchronously initialize the WorkflowManager components."""
        self.logger.info("Starting asynchronous initialization of WorkflowManager")
        try:
            if not self.llm:
                success = self.initialize_llm()
                if not success:
                    self.logger.error("Failed to initialize LLM in WorkflowManager")
                    if self.error_reporter:
                        self.error_reporter.report_error(
                            Exception("LLM initialization failed"),
                            category="system_error",
                            component="workflow_manager",
                            context={"feature": "llm_initialization"}
                        )
                    return False
            self.logger.info("WorkflowManager initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error during WorkflowManager initialization: {str(e)}")
            if self.error_reporter:
                self.error_reporter.report_error(
                    e, category="system_error", component="workflow_manager",
                    context={"feature": "async_initialization"}
                )
            return False

    async def execute_workflow(self, project_name: str, fast_mode: bool = False, mode: str = "report", visualization_request: Optional[Dict] = None) -> Dict[str, Any]:
        from backend.agents.researcher import researcher
        from backend.agents.writer import writer
        from backend.agents.visualizer import visualizer_async
        from backend.agents.reviewer import reviewer
        from backend.agents.editor import editor
        from backend.agents.publisher import publisher

        self.logger.info(f"Starting asynchronous workflow execution for {project_name}")
        start_time = time.time()

        if not self.llm:
            success = self.initialize_llm()
            if not success:
                return {"error": "Failed to initialize language model"}

        state = {
            "project_name": project_name,
            "report_config": deepcopy(self.report_config),
            "fast_mode": fast_mode,
            "mode": mode,
            "visualization_request": [visualization_request] if visualization_request else [],
            "errors": {},
            "review_status": {},
            "writer_output": {},
            "visualizer_output": {},
            "merged_output": {},
            "final_report": "",
            "report_path": "",
            "visualization_list": []
        }
        
        try:
            # Run each agent asynchronously with longer timeout for researcher
            self.logger.info("Running Researcher")
            # Give researcher more time to complete all sections
            state = await asyncio.wait_for(
                researcher(state, llm=self.llm, logger=self.logger),
                timeout=600  # 10 minutes timeout for researcher
            )
            self.logger.info("Researcher completed")
            
            if mode != "query":
                self.logger.info("Running Writer")
                state = await writer(state, llm=self.llm, logger=self.logger)
                self.logger.info("Writer completed")
            
            self.logger.info("Running Visualizer")
            state = await visualizer_async(state, llm=self.llm, logger=self.logger)
            self.logger.info("Visualizer completed")
            
            self.logger.info("Merging results")
            state = self._merge_results(state)
            self.logger.info("Merge completed")
            
            self.logger.info("Running Reviewer")
            state = await reviewer(state, llm=self.llm, logger=self.logger)
            self.logger.info("Reviewer completed")
            
            self.logger.info("Running Editor")
            state = await editor(state, llm=self.llm, logger=self.logger)
            self.logger.info("Editor completed")
            
            self.logger.info("Running Publisher")
            state = await publisher(state, llm=self.llm, logger=self.logger)
            self.logger.info("Publisher completed")
            
            duration = time.time() - start_time
            self.logger.info(f"Completed workflow execution for {project_name} in {duration:.2f}s")
            return {
                "project_name": project_name,
                "result": state,
                "report_path": state.get("report_path"),
                "visualization_list": state.get("visualization_list", []),
                "mode": mode,
                "errors": state.get("errors", {})
            }
        except Exception as e:
            self.logger.error(f"Error executing workflow: {str(e)}")
            if self.error_reporter:
                self.error_reporter.report_error(
                    e, category="system_error", component="workflow_manager",
                    context={"project_name": project_name, "mode": mode}
                )
            return {
                "error": str(e),
                "project_name": project_name,
                "mode": mode
            }
        
    def _merge_results(self, state: WorkflowState) -> Dict[str, Any]:
        self.logger.info(f"Merging results for project: {state.get('project_name', 'Unknown Project')}")
        writer_output = state.get('writer_output', {})
        visualizer_output = state.get('visualizer_output', {})
        merged_output = {
            "draft": writer_output.get('draft', ''),
            "sections": writer_output.get('sections', {}),
            "visualizations": visualizer_output.get('visualizations', {}),
            "visualization_list": visualizer_output.get('visualization_list', []),
            "visualization_data_sources": visualizer_output.get('visualization_data_sources', {}),
            "errors": {
                **writer_output.get('errors', {}),
                **visualizer_output.get('errors', {})
            }
        }
        updated_state = state.copy()
        updated_state['merged_output'] = merged_output
        self.logger.info(f"Merged state keys: {list(updated_state.keys())}")
        return updated_state