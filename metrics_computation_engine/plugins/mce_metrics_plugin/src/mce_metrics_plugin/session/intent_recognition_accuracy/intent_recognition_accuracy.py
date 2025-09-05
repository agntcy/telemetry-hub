from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.models.session import SessionEntity

# Co-located prompt for better readability and maintainability
INTENT_RECOGNITION_ACCURACY_PROMPT = """
    You are an evaluator of Intent Recognition Accuracy.

    You will be given a QUERY and a RESPONSE, and (optionally) a Reference Answer that gets a score of 3. Evaluate how well the RESPONSE demonstrates intent recognition accuracy.

    Here is the evaluation criteria to follow: (1) Does the response correctly identify the user's intent? (2) Does the response address the identified intent accurately? (3) Is the response appropriate for the identified intent?

    Scoring Rubric:
        1: the Assistant accurately identifies the user's intent and responds appropriately.
        0: the Assistant fails to identify the user's intent correctly.

    QUERY: {query} Optional Reference Answer (Score 3): {ground_truth} RESPONSE to evaluate: {response}
"""


class IntentRecognitionAccuracy(BaseMetric):
    """
    Measures how well the assistant recognizes and responds to user intents.
    """

    REQUIRED_PARAMETERS = {"IntentRecognitionAccuracy": ["workflow_data"]}

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
        """
        Compute intent recognition accuracy using pre-populated SessionEntity data.

        Args:
            session: SessionEntity with pre-computed workflow data
        """
        # Extract data directly from the session entity - much cleaner now
        query = session.workflow_data.get("query", "") if session.workflow_data else ""
        response = (
            session.workflow_data.get("response", "") if session.workflow_data else ""
        )

        # Get workflow span IDs for metadata
        workflow_span_ids = (
            [span.span_id for span in session.workflow_spans]
            if session.workflow_spans
            else []
        )

        # TODO: Add ground truth lookup once dataset is available
        ground_truth = "No ground truth available"

        # Format the prompt
        prompt = INTENT_RECOGNITION_ACCURACY_PROMPT.format(
            query=query, response=response, ground_truth=ground_truth
        )

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score=score,
                reasoning=reasoning,
                span_ids=workflow_span_ids,
                session_ids=[session.session_id],
            )

        return self._create_error_result(
            error_message="No model available",
            span_ids=workflow_span_ids,
            session_ids=[session.session_id],
        )
