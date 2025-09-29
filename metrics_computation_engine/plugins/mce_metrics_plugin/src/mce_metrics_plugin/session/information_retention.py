from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.entities.models.session import SessionEntity

INFORMATION_RETENTION_PROMPT = """
    You are an evaluator of Information Retention.

    You will be given multiple RESPONSES from different interactions. Evaluate how well the Assistant retains and recalls relevant information over time.

    Here is the evaluation criteria to follow: (1) Does the Assistant correctly remember and reference previously provided information? (2) Does the Assistant avoid forgetting key details or introducing inconsistencies in recalled information? (3) Is the recalled information applied appropriately in the responses?

    Scoring Rubric:
        1: The Assistant consistently retains and recalls information accurately across all interactions.
        0: The Assistant fails to retain or recall relevant information, leading to inaccuracies or contradictions.

    RESPONSES to evaluate: {responses}
"""


class InformationRetention(BaseMetric):
    """
    Measures how well information is retained across multiple interactions.
    """

    REQUIRED_PARAMETERS = {"InformationRetention": ["conversation_data"]}

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
        responses = ""

        if session.conversation_data:
            responses = session.conversation_data.get("conversation", "")

        entities_involved = (
            [span.entity_name for span in session.agent_spans]
            if session.agent_spans
            else []
        )

        prompt = INFORMATION_RETENTION_PROMPT.format(responses=responses)

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score=score,
                category="application",
                app_name=session.app_name,
                reasoning=reasoning,
                entities_involved=entities_involved,
                span_ids=[span.span_id for span in session.agent_spans],
                session_ids=[session.session_id],
            )

        return self._create_error_result(
            error_message="No model available",
            category="application",
            app_name=session.app_name,
            entities_involved=entities_involved,
            span_ids=[span.span_id for span in session.agent_spans],
            session_ids=[session.session_id],
        )
