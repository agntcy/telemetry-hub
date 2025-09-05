from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.models.session import SessionEntity

# Consistency
CONSISTENCY_PROMPT = """
    You are an evaluator of Consistency.

    You will be given multiple RESPONSES from different interactions. Evaluate the consistency in the RESPONSES.

    Here is the evaluation criteria to follow: (1) Are the responses consistent in the information they provide? (2) Do the responses avoid contradictions or conflicting statements? (3) Is the overall tone and style of the responses consistent?

    Scoring Rubric:
        1: the responses are fully consistent across all interactions.
        0: the responses are not consistent.

    RESPONSES to evaluate: {conversation}
"""


class Consistency(BaseMetric):
    REQUIRED_PARAMETERS = {"Consistency": ["conversation_data"]}

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

        prompt = CONSISTENCY_PROMPT.format(conversation=conversation)

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
