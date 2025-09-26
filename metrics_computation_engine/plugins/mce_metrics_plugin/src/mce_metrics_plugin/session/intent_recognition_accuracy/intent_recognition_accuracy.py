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

    REQUIRED_PARAMETERS = {
        "IntentRecognitionAccuracy": ["input_query", "final_response"]
    }

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
        query = session.input_query
        response = session.final_response
        ground_truth = session.ground_truth

        entities_involved = (
            [span.entity_name for span in session.agent_spans]
            if session.agent_spans
            else []
        )
        # TODO: Add ground truth lookup once dataset is available
        

        # Format the prompt
        prompt = INTENT_RECOGNITION_ACCURACY_PROMPT.format(
            query=query, response=response, ground_truth=ground_truth
        )

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
