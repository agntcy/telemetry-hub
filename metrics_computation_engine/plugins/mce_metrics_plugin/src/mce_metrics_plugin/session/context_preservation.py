from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.entities.models.session import SessionEntity

# Context Preservation
CONTEXT_PRESERVATION_PROMPT = """
    You are an evaluator of Context Preservation.

    Evaluate the given response based on its ability to understand and address the provided input. You will be given a CONVERSATION.

    Here is the evaluation criteria to follow: (1) Does the response accurately understand and address the given input? (2) Is the response relevant and logically structured? (3) Does the response provide useful or insightful information?

    Scoring Rubric:
        1: The response is highly relevant, well-structured, and insightful.
        0: The response is irrelevant, unclear, or fails to address the input effectively.

    CONVERSATION to evaluate: {conversation}
"""


class ContextPreservation(BaseMetric):
    REQUIRED_PARAMETERS = {"ContextPreservation": ["conversation_data"]}

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

        entities_involved = (
            [span.entity_name for span in session.agent_spans]
            if session.agent_spans
            else []
        )
        prompt = CONTEXT_PRESERVATION_PROMPT.format(conversation=conversation)

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score=score,
                category="application",
                app_name=session.app_name,
                reasoning=reasoning,
                entities_involved=entities_involved,
                span_ids=agent_span_ids,
                session_ids=[session.session_id],
            )

        return self._create_error_result(
            error_message="No model available",
            category="application",
            app_name=session.app_name,
            entities_involved=entities_involved,
            span_ids=agent_span_ids,
            session_ids=[session.session_id],
        )
