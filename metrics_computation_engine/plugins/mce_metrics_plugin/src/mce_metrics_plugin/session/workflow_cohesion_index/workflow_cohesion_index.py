# Workflow Cohesion Index
from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.models.session import SessionEntity

WORKFLOW_COHESION_INDEX_PROMPT = """
    You are an evaluator of Workflow Cohesion.

    You will be given multiple RESPONSES describing different components of a workflow. Evaluate how well these components integrate and function cohesively as a unified system.

    Here is the evaluation criteria to follow: (1) Do the components interact smoothly without unnecessary friction or gaps? (2) Is there a logical flow between different parts of the workflow? (3) Does the workflow maintain consistency and efficiency across all stages?

    Scoring Rubric:
        1: the workflow is highly cohesive, with seamless integration among components and a logical, efficient flow.
        0: the workflow lacks cohesion, with poor integration, inconsistencies, or significant inefficiencies.

    RESPONSES to evaluate: {conversation}
"""


class WorkflowCohesionIndex(BaseMetric):
    """
    Measures how well different components work together as a cohesive workflow.
    """

    REQUIRED_PARAMETERS = {"WorkflowCohesionIndex": ["conversation_data"]}

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return self.REQUIRED_PARAMETERS

    def validate_config(self) -> bool:
        return True

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    async def compute(self, session: SessionEntity):
        conversation = (
            session.conversation_data.get("conversation", "")
            if session.conversation_data
            else ""
        )
        agent_span_ids = (
            [span.span_id for span in session.agent_spans]
            if session.agent_spans
            else []
        )

        prompt = WORKFLOW_COHESION_INDEX_PROMPT.format(conversation=conversation)

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score=score,
                reasoning=reasoning,
                span_ids=agent_span_ids,
                session_ids=[session.session_id],
            )

        return self._create_error_result(
            error_message="No model available",
            span_ids=agent_span_ids,
            session_ids=[session.session_id],
        )
