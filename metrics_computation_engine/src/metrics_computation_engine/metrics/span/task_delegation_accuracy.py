# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading


class TaskDelegationAccuracy(BaseMetric):
    """
    Determines if the task delegation was accurate with respect to the input.
    """

    TASK_DELEGATION_ACCURACY_PROMPT = """
    # TODO: Define the task delegation accuracy evaluation prompt

    Agent Input: {agent_input}
    Agent Output: {agent_output}

    Evaluation Task: Assess the task delegation accuracy.

    Scoring Rubric:
    1: Task delegation was accurate
    0: Task delegation was not accurate
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "span"

        self.required = {"entity_type": ["agent"]}

    @property
    def required_parameters(self) -> List[str]:
        pass

    def validate_config(self) -> bool:
        pass

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    async def compute(self, data):
        if data.entity_type not in self.required["entity_type"] or not (
            data.input_payload and data.output_payload and data.entity_name
        ):
            return self._create_error_result(
                category="agent",
                error_message="Missing required data for task delegation accuracy computation",
            )

        if self.jury:
            prompt = self.TASK_DELEGATION_ACCURACY_PROMPT.format(
                agent_input=data.input_payload, agent_output=data.output_payload
            )

            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score,
                category="agent",
                reasoning=reasoning,
                span_ids=[data.span_id],
                session_ids=data.session_id,
            )

        return self._create_error_result(
            category="agent", error_message="Please configure your LLM credentials"
        )
