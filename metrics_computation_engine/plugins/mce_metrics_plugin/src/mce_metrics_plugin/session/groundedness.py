# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.entities.models.session import SessionEntity

import json

# Co-located prompt for better readability and maintainability
GROUNDEDNESS_PROMPT = """
    You are an evaluator of Groundedness Evaluate how well each response is grounded in verifiable data and avoids speculation or hallucinations.

    Here is the evaluation criteria to follow: (1) Is the response based on verifiable information from the provided data, knowledge bases, or tool outputs? (2) Does the response avoid speculation, hallucinations, or misleading statements? (3) Is the factual accuracy of the response maintained throughout the conversation?

    Scoring Rubric:
        1: Response by the system is fully grounded by the context available through the tools and conversation.
        0: There are details in the response that are not grounded by the context available through tools and conversation.

    CONVERSATION: {conversation}
"""


class Groundedness(BaseMetric):
    REQUIRED_PARAMETERS = {"Groundedness": ["conversation_data"]}

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
        Compute groundedness using pre-populated SessionEntity data.

        Args:
            session: SessionEntity with pre-computed conversation data
        """
        try:
            if self.jury:
                # Use pre-computed conversation data from SessionEntity
                conversation = (
                    session.conversation_data.get("elements", "")
                    if session.conversation_data
                    else ""
                )

                conversation_str = (
                    json.dumps(conversation, indent=2)
                    if isinstance(conversation, list)
                    else conversation
                )
                prompt = GROUNDEDNESS_PROMPT.format(conversation=conversation_str)
                score, reasoning = self.jury.judge(prompt, BinaryGrading)

                # Get relevant span IDs for metadata
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

                return self._create_success_result(
                    score=score,
                    reasoning=reasoning,
                    category="application",
                    app_name=session.app_name,
                    entities_involved=entities_involved,
                    span_ids=[agent_span_ids],
                    session_ids=[session.session_id],
                )

            return self._create_error_result(
                error_message="Please configure your LLM credentials",
                category="application",
                app_name=session.app_name,
                entities_involved=entities_involved,
                span_ids=[agent_span_ids],
                session_ids=[session.session_id],
            )

        except Exception as e:
            return self._create_error_result(
                error_message=str(e),
                category="application",
                app_name=session.app_name,
                entities_involved=entities_involved,
                span_ids=[agent_span_ids],
                session_ids=[session.session_id],
            )