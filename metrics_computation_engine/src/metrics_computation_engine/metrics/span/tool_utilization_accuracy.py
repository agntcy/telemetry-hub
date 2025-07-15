# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List

from metrics_computation_engine.llm_judge.prompts import (
    tool_utilization_accuracy_prompt,
)
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading, MetricResult


class ToolUtilizationAccuracy(BaseMetric):
    """
    Determines if the tool usage was accurate with respect to the input.
    """

    def __init__(self, jury=None, dataset=None):
        super().__init__(jury=jury, dataset=dataset)
        self.name = "ToolUtilizationAccuracy"
        self.aggregation_level = "span"

        self.required = {"entity_type": ["tool"]}

    @property
    def required_parameters(self) -> List[str]:
        pass

    def validate_config(self) -> bool:
        pass

    def extract_data(self, data) -> bool:
        return "Hello, world!"

    async def compute(self, data):
        if data.entity_type not in self.required["entity_type"] or not (
            data.input_payload and data.output_payload and data.entity_name
        ):
            return MetricResult(
                metric_name="",
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level="",
                span_id=[data.span_id],
                session_id=[data.session_id],
                source="",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message="",
            )

        if self.jury:
            prompt = tool_utilization_accuracy_prompt.format(
                tool_input=data.input_payload,
                tool_output=data.output_payload,
                tool_name=data.entity_name,
                tool_definition=data.tool_definition,
            )

            score, reasoning = self.jury.judge(prompt, BinaryGrading)

            return MetricResult(
                metric_name=self.name,
                description="",
                value=score,
                reasoning=reasoning,
                unit="",
                aggregation_level=self.aggregation_level,
                span_id=[data.span_id],
                session_id=[data.session_id],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={},
                error_message=None,
            )

        return MetricResult(
            metric_name=self.name,
            description="",
            value=-1,
            reasoning="",
            unit="",
            aggregation_level=self.aggregation_level,
            span_id=[data.span_id],
            session_id=[data.session_id],
            source="native",
            entities_involved=[],
            edges_involved=[],
            success=False,
            metadata={},
            error_message="Please configure your LLM credentials",
        )
