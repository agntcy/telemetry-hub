# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading


class ToolUtilizationAccuracy(BaseMetric):
    """
    Determines if the tool usage was accurate with respect to the input.
    """

    REQUIRED_PARAMETERS = [
        "input_payload",
        "output_payload",
        "entity_name",
        "tool_definition",
    ]
    TOOL_UTILIZATION_ACCURACY_PROMPT = """
    You are an evaluator tasked with assessing the Tool Utilization Accuracy made by an AI agent for a given query.

    Input: {tool_input}

    Tool Called: {tool_name}

    Tool Definition: {tool_definition}

    Output: {tool_output}

    Evaluation Task - Determine if the tool called was reasonable in response to the input. Further determine if the tool was able to provide output to address the needs in the input.

    Scoring Rubric:
    1: The tool call was completeley reasonable addressed the input.
    0: It is unclear why this tool was called and/or it failed to provide useful output.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "span"

        self.required = {"entity_type": ["tool"]}

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
                "Missing required data for tool utilization accuracy computation"
            )

        if self.jury:
            prompt = self.TOOL_UTILIZATION_ACCURACY_PROMPT.format(
                tool_input=data.input_payload,
                tool_output=data.output_payload,
                tool_name=data.entity_name,
                tool_definition=data.tool_definition,
            )

            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(score, reasoning, span_ids=[data.span_id], session_ids=[data.session_id])

        return self._create_error_result("Please configure your LLM credentials")
