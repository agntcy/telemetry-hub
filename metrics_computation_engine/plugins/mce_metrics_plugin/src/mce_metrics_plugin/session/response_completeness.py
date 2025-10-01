# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

# Information Retention
from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.entities.models.session import SessionEntity

# Response Completeness
RESPONSE_COMPLETENESS_PROMPT = """
    You are an evaluator of Completeness.

    You will be given a CONVERSATION. Evaluate how well the RESPONSES demonstrates completeness.

    Here is the evaluation criteria to follow: (1) Does the response cover all relevant aspects of the query? (2) Does the response provide sufficient detail and explanation? (3) Does the response leave out any critical information needed to fully address the query?

    Scoring Rubric:
        1: Each intent/objective required by the user has been addressed by the system.
        0: The system had missed a detail or was not able to fully address the needs of the user.

    CONVERSATION to evaluate: {conversation}
"""


class ResponseCompleteness(BaseMetric):
    """
    Evaluates how complete the responses are in addressing user queries.
    """

    REQUIRED_PARAMETERS = {"ResponseCompleteness": ["conversation_data"]}

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
        prompt = RESPONSE_COMPLETENESS_PROMPT.format(conversation=conversation)

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
