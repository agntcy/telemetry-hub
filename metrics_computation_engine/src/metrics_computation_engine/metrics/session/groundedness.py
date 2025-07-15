# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List

from metrics_computation_engine.llm_judge.prompts import groundedness_prompt
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading, MetricResult


class Groundedness(BaseMetric):
    """
    Determines if the tool usage was accurate with respect to the input.
    """

    def __init__(self, jury=None, dataset=None):
        super().__init__(jury=jury, dataset=dataset)
        self.name = "Groundedness"
        self.aggregation_level = "session"

        self.required = {"entity_type": ["agent"]}

    @property
    def required_parameters(self) -> List[str]:
        pass

    def validate_config(self) -> bool:
        pass

    def extract_data(self, data) -> bool:
        return "Hello, world!"

    async def compute(self, data):
        try:
            if self.jury:
                conversation = [
                    f"INPUT: {d.input_payload}\n OUTPUT: {d.output_payload}"
                    for d in data
                    if d.entity_type in ["agent", "tool"]
                ]
                prompt = groundedness_prompt.format(
                    conversation="\n\n".join(conversation)
                )

                score, reasoning = self.jury.judge(prompt, BinaryGrading)

                return MetricResult(
                    metric_name=self.name,
                    description="",
                    value=score,
                    reasoning=reasoning,
                    unit="",
                    aggregation_level=self.aggregation_level,
                    span_id="",
                    session_id="",
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
                span_id="",
                session_id="",
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message="Please configure your LLM credentials",
            )
        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                span_id="",
                session_id="",
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=e,
            )
