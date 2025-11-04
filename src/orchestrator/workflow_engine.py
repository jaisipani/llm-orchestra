from typing import Any, Optional
from dataclasses import dataclass

from pydantic import BaseModel, Field

from src.llm.client import LLMClient
from src.llm.prompts import MULTI_SERVICE_PROMPT
from src.utils.logger import logger

@dataclass
class WorkflowStep:
    service: str
    intent: str
    parameters: dict
    depends_on: Optional[int] = None
    result: Optional[Any] = None
    status: str = 'pending'  # pending, running, completed, failed

class MultiServiceIntent(BaseModel):
    multi_service: bool = Field(..., description="Whether this requires multiple services")
    services: list[str] = Field(default_factory=list, description="List of services involved")
    operations: list[dict] = Field(default_factory=list, description="List of operations to perform")
    reasoning: str = Field(..., description="Explanation of the workflow")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")

class WorkflowEngine:
    def __init__(self):
        self.llm = LLMClient()
    def detect_multi_service(self, user_message: str) -> Optional[MultiServiceIntent]:
        intent = self.llm.parse_intent(
            user_message=user_message,
            system_prompt=MULTI_SERVICE_PROMPT,
            response_model=MultiServiceIntent
        )
        if intent and intent.multi_service:
            logger.info(f"Multi-service workflow detected: {len(intent.operations)} operations")
            return intent
        
        return None
    
    def create_workflow(self, multi_intent: MultiServiceIntent) -> list[WorkflowStep]:
        steps = []
        for i, op in enumerate(multi_intent.operations):
            step = WorkflowStep(
                service=op.get('service', ''),
                intent=op.get('intent', ''),
                parameters=op.get('parameters', {}),
                depends_on=op.get('depends_on')
            )
            steps.append(step)
        
        logger.debug(f"Created workflow with {len(steps)} steps")
        return steps
    
    def can_execute_step(self, step: WorkflowStep, completed_steps: list[int]) -> bool:
        if step.depends_on is None:
            return True
        return step.depends_on in completed_steps
    
    def inject_context(
        self,
        step: WorkflowStep,
        previous_results: dict[int, Any]
    ) -> WorkflowStep:
        if step.depends_on is not None and step.depends_on in previous_results:
            dependency_result = previous_results[step.depends_on]
            if isinstance(dependency_result, dict):
                if 'id' in dependency_result and 'id' not in step.parameters:
                    step.parameters['id'] = dependency_result['id']
                
                if 'attendees' in dependency_result and 'emails' not in step.parameters:
                    if isinstance(dependency_result['attendees'], list):
                        emails = [a.get('email') for a in dependency_result['attendees'] if 'email' in a]
                        step.parameters['emails'] = emails
            
            elif isinstance(dependency_result, list):
                if 'ids' not in step.parameters:
                    step.parameters['items'] = dependency_result
        
        return step

class WorkflowContext:
    def __init__(self):
        self.results: dict[int, Any] = {}
        self.completed_steps: list[int] = []
        self.failed_steps: list[int] = []
    def add_result(self, step_index: int, result: Any) -> None:
        self.results[step_index] = result
        self.completed_steps.append(step_index)
        logger.debug(f"Step {step_index} completed, result stored")
    def mark_failed(self, step_index: int) -> None:
        self.failed_steps.append(step_index)
        logger.warning(f"Step {step_index} marked as failed")
    def get_result(self, step_index: int) -> Optional[Any]:
        return self.results.get(step_index)
