import logging
import json
import os
import time
from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, END
from backend.state import ResearchState
from backend.services.reporting.progress_tracker import ProgressTracker
from backend.services.reporting.error_reporter import ErrorReporter
from langchain_openai import ChatOpenAI
from copy import deepcopy

class WorkflowManager:
    """Manages LangGraph workflow execution and state management."""
    
    def __init__(self, logger: logging.Logger, 
                 progress_tracker: Optional[ProgressTracker] = None,
                 error_reporter: Optional[ErrorReporter] = None,
                 config_path: str = "backend/config/report_config.json"):
        self.logger = logger
        self.progress_tracker = progress_tracker
        self.error_reporter = error_reporter
        self.config_path = config_path
        self.report_config = self._load_report_config()
        self.active_workflows = {}
        self.completed_workflows = {}
        
        # Will be set when LLM is initialized
        self.llm = None
        
        # Will be set when graph is compiled
        self.graph = None
    
    def _load_report_config(self) -> Dict[str, Any]:
        """Load report configuration from file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                self.logger.info(f"Loaded report configuration from {self.config_path} with {len(config.get('sections', []))} sections")
                return config
            else:
                self.logger.error(f"Report configuration file not found at {self.config_path}")
                if self.error_reporter:
                    self.error_reporter.report_error(
                        FileNotFoundError(f"Report config not found at {self.config_path}"),
                        category="system_error",
                        component="workflow_manager"
                    )
                return {}
        except Exception as e:
            self.logger.error(f"Error loading report configuration: {str(e)}")
            if self.error_reporter:
                self.error_reporter.report_error(
                    e, category="system_error", component="workflow_manager",
                    context={"config_path": self.config_path}
                )
            return {}
    
    def initialize_llm(self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """Initialize the language model."""
        try:
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable not set")
                    
            self.llm = ChatOpenAI(model=model_name, api_key=api_key)
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
    
    def create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow."""
        try:
            from backend.agents.enhanced_researcher import enhanced_researcher
            from backend.agents.writer import writer
            from backend.agents.visualization_agent import visualization_agent
            from backend.agents.reviewer import reviewer
            from backend.agents.editor import editor
            from backend.agents.publisher import publisher
            
            # Initialize the workflow using dict as the state type, not ResearchState
            workflow = StateGraph(Dict)
            
            # Define workflow nodes using dynamic wrappers to include logging and progress tracking
            workflow.add_node("enhanced_researcher", self._create_node_wrapper(enhanced_researcher, "Research"))
            workflow.add_node("writer", self._create_node_wrapper(writer, "Writing"))
            workflow.add_node("visualization_agent", self._create_node_wrapper(visualization_agent, "Visualization"))
            workflow.add_node("reviewer", self._create_node_wrapper(reviewer, "Review"))
            workflow.add_node("editor", self._create_node_wrapper(editor, "Editing"))
            workflow.add_node("publisher", self._create_node_wrapper(publisher, "Publishing"))
            
            # Set entry point
            workflow.set_entry_point("enhanced_researcher")
            
            # Add edges to create sequential flow
            workflow.add_edge("enhanced_researcher", "writer")
            workflow.add_edge("writer", "visualization_agent")
            workflow.add_edge("visualization_agent", "reviewer")
            workflow.add_edge("reviewer", "editor")
            workflow.add_edge("editor", "publisher")
            workflow.add_edge("publisher", END)
            
            # Compile the graph
            self.graph = workflow.compile()
            self.logger.info("Successfully created and compiled workflow graph")
            return workflow
        except Exception as e:
            self.logger.error(f"Error creating workflow: {str(e)}")
            if self.error_reporter:
                self.error_reporter.report_error(
                    e, category="system_error", component="workflow_manager"
                )
            return None
    
    def _create_node_wrapper(self, agent_function, step_name: str):
        """Create a wrapper for an agent node that includes progress tracking and error handling."""
        llm = self.llm
        logger = self.logger
        progress_tracker = self.progress_tracker
        error_reporter = self.error_reporter
        
        async def wrapped_agent(state, config=None):
            try:
                # Deep copy state to avoid modifying the original if there's an error
                working_state = deepcopy(state)
                
                # Get project name safely - use actual value or empty string, never "Unknown Project"
                project_name = working_state.get("project_name", "")
                if not project_name:
                    logger.warning("Project name missing in state - check workflow setup")
                    if isinstance(state, dict):
                        # Use the workflow_id if available as a fallback
                        for workflow_id, workflow in self.active_workflows.items():
                            if workflow.get("state") == state:
                                project_name = workflow.get("project_name", "")
                                logger.info(f"Recovered project name '{project_name}' from active workflows")
                                working_state["project_name"] = project_name
                                break
                    
                    # Final fallback - but should never reach here if things are working properly
                    if not project_name:
                        project_name = "Unknown Project"
                
                # Store original project name for verification after agent call
                original_project_name = project_name
                
                # Track progress start
                if progress_tracker:
                    progress_tracker.update_progress(
                        step=step_name, 
                        percentage=0, 
                        message=f"Starting {step_name.lower()} for {project_name}",
                        job_id=project_name  # Add job_id to ensure tracking is associated with the right project
                    )
                
                # Set start time for metrics
                start_time = time.time()
                
                # Run the agent - log the actual values for debugging
                logger.info(f"Starting agent: {step_name} for '{project_name}'")
                
                # Run the agent with explicit injected parameters
                updated_state = await agent_function(working_state, llm, logger, config)
                
                # Calculate metrics
                duration = time.time() - start_time
                
                # Ensure project_name is preserved in the updated state
                if isinstance(updated_state, dict):
                    if "project_name" not in updated_state:
                        logger.warning(f"Project name missing in updated state - restoring '{original_project_name}'")
                        updated_state["project_name"] = original_project_name
                    elif updated_state["project_name"] != original_project_name and original_project_name != "Unknown Project":
                        logger.warning(f"Project name changed from '{original_project_name}' to '{updated_state['project_name']}' - restoring original")
                        updated_state["project_name"] = original_project_name
                
                # Track progress completion
                if progress_tracker:
                    progress_tracker.update_progress(
                        step=step_name, 
                        percentage=100, 
                        message=f"Completed {step_name.lower()} for {project_name} in {duration:.2f}s",
                        job_id=project_name  # Add job_id to ensure tracking is associated with the right project
                    )
                
                logger.info(f"Completed agent: {step_name} for '{project_name}' in {duration:.2f}s")
                return updated_state
            except Exception as e:
                logger.error(f"Error in {step_name}: {str(e)}", exc_info=True)
                
                # Get project name for error reporting
                error_project_name = "Unknown Project"
                if isinstance(state, dict) and "project_name" in state:
                    error_project_name = state["project_name"]
                
                # Report error
                if error_reporter:
                    error_id = error_reporter.report_error(
                        e, 
                        category="processing_error", 
                        component=f"agent.{step_name.lower()}", 
                        context={
                            "project_name": error_project_name,
                            "step": step_name
                        }
                    )
                
                # Update progress to show error
                if progress_tracker:
                    progress_tracker.update_progress(
                        step=step_name, 
                        percentage=100,  # Mark as complete even though it failed
                        message=f"Error in {step_name.lower()}: {str(e)}",
                        job_id=error_project_name  # Add job_id with project name
                    )
                
                # Return a state with the error information and preserved project name
                if isinstance(state, dict):
                    # Add error to the state as dict
                    errors = state.get("errors", [])
                    state["errors"] = errors + [str(e)]
                    
                    # Update progress in state as dict
                    state["progress"] = f"Error in {step_name}: {str(e)}"
                    
                    # Preserve project name if it's missing
                    if "project_name" not in state and error_project_name != "Unknown Project":
                        state["project_name"] = error_project_name
                
                return state
        
        return wrapped_agent
    
    async def execute_workflow(self, project_name: str, fast_mode: bool = False) -> Dict[str, Any]:
        """Execute the workflow for a given project."""
        # Ensure LLM is initialized
        if not self.llm:
            success = self.initialize_llm()
            if not success:
                return {"error": "Failed to initialize language model"}
        
        # Ensure graph is created
        if not self.graph:
            workflow = self.create_workflow()
            if not workflow:
                return {"error": "Failed to create workflow"}
        
        try:
            # Print the actual project name for debugging
            self.logger.info(f"Creating initial state with project_name: '{project_name}'")
            
            # CRITICAL: Ensure project_name is a string and not None or empty
            if not project_name or not isinstance(project_name, str):
                self.logger.error(f"Invalid project name: {project_name}")
                return {"error": "Invalid project name"}
            
            # Create initial state as a simple dictionary
            state = {
                "project_name": project_name,  # Explicitly set the project name
                "report_config": deepcopy(self.report_config),
                "fast_mode": fast_mode,
                "errors": []
            }
            
            # Generate workflow key
            workflow_id = f"{project_name}_{int(time.time())}"
            
            # Start progress tracking
            if self.progress_tracker:
                self.progress_tracker.start_tracking(project_name, 6)  # 6 total steps
            
            # Store active workflow
            self.active_workflows[workflow_id] = {
                "project_name": project_name,
                "start_time": time.time(),
                "state": state,  # Use a reference to the state so we can look it up later
                "status": "running"
            }
            
            # Execute workflow - use the dictionary state directly
            self.logger.info(f"Starting workflow execution for {project_name} (fast_mode: {fast_mode})")
            
            # Debug: Log the state before passing to LangGraph
            self.logger.info(f"Executing with state keys: {list(state.keys())}")
            self.logger.info(f"State project_name: '{state.get('project_name')}'")
            
            # Pass the state directly to the graph
            result = await self.graph.ainvoke(state)
            
            # Calculate metrics
            duration = time.time() - self.active_workflows[workflow_id]["start_time"]
            
            # Store completed workflow
            self.completed_workflows[workflow_id] = {
                "project_name": project_name,
                "start_time": self.active_workflows[workflow_id]["start_time"],
                "end_time": time.time(),
                "duration": duration,
                "result": result
            }
            
            # Remove from active workflows
            self.active_workflows.pop(workflow_id, None)
            
            # Complete progress tracking
            if self.progress_tracker:
                self.progress_tracker.complete()
            
            self.logger.info(f"Completed workflow execution for {project_name} in {duration:.2f}s")
            
            # Access result data, handling None result
            if result is None:
                self.logger.error("Workflow returned None result")
                return {
                    "workflow_id": workflow_id,
                    "project_name": project_name,
                    "duration": duration,
                    "error": "Workflow execution failed with None result",
                    "report_path": None,
                    "errors": ["Workflow execution failed with None result"]
                }
                
            return {
                "workflow_id": workflow_id,
                "project_name": project_name,
                "duration": duration,
                "result": result,
                "report_path": result.get("final_report"),
                "errors": result.get("errors", [])
            }
            
        except Exception as e:
            self.logger.error(f"Error executing workflow: {str(e)}", exc_info=True)
            
            # Report error
            if self.error_reporter:
                error_id = self.error_reporter.report_error(
                    e, 
                    category="system_error", 
                    component="workflow_manager",
                    context={"project_name": project_name, "fast_mode": fast_mode}
                )
            
            return {
                "error": str(e),
                "project_name": project_name
            }
    
    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get information about active workflows."""
        active_list = []
        current_time = time.time()
        
        for workflow_id, workflow in self.active_workflows.items():
            active_list.append({
                "workflow_id": workflow_id,
                "project_name": workflow["project_name"],
                "running_time": current_time - workflow["start_time"],
                "status": workflow["status"]
            })
            
        return active_list
    
    def get_completed_workflows(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get information about completed workflows."""
        completed_list = []
        
        # Sort by completion time (most recent first)
        sorted_workflows = sorted(
            self.completed_workflows.items(),
            key=lambda x: x[1]["end_time"],
            reverse=True
        )
        
        for workflow_id, workflow in sorted_workflows[:limit]:
            completed_list.append({
                "workflow_id": workflow_id,
                "project_name": workflow["project_name"],
                "duration": workflow["duration"],
                "completed_at": workflow["end_time"]
            })
            
        return completed_list 