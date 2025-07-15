# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from collections import Counter
from typing import List

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult


class AgentToToolInteractions(BaseMetric):
    """
    Collects the Agent to Agent Interactions counts throughout a trace.
    """

    def __init__(self, jury=None, dataset=None):
        super().__init__(jury=jury, dataset=dataset)
        self.name = "AgentToToolInteractions"
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return ["Events.Attributes"]

    def validate_config(self) -> bool:
        return True

    async def compute(self, data):
        try:
            tool_events = [
                span.raw_span_data["SpanAttributes"]
                for span in data
                if span.entity_type == "tool"
            ]

            transitions = []
            for span in tool_events:
                transition = f"(Agent: {span['ioa_observe.workflow.name']}) -> (Tool: {span['traceloop.entity.name']})"
                transitions.append(transition)

            transition_counts = Counter(transitions)

            return MetricResult(
                metric_name=self.name,
                description="",
                value=transition_counts,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                span_id=[span.span_id for span in data] if data else [],
                session_id=[data[0].session_id] if data else [],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={},
                error_message=None,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                span_id=[span.span_id for span in data] if data else [],
                session_id=[data[0].session_id] if data else [],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=e,
            )
