# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from collections import Counter
from typing import List

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult


class AgentToAgentInteractions(BaseMetric):
    """
    Collects the Agent to Agent Interactions counts throughout a trace.
    """

    def __init__(self, jury=None, dataset=None):
        super().__init__(jury=jury, dataset=dataset)
        self.name = "AgentToAgentInteractions"
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return ["EventsAttributes"]

    def validate_config(self) -> bool:
        return True

    async def compute(self, data):
        try:
            agent_events = [
                span.raw_span_data["Events.Attributes"][0]["agent_name"]
                for span in data
                if len(span.raw_span_data["Events.Attributes"]) > 0
                and "agent_name" in span.raw_span_data["Events.Attributes"][0].keys()
            ]

            transitions = []
            for i in range(len(agent_events) - 1):
                if agent_events[i] != agent_events[i + 1]:
                    transition = f"{agent_events[i]} -> {agent_events[i + 1]}"
                    transitions.append(transition)

            transition_counts = Counter(transitions)

            return MetricResult(
                metric_name=self.name,
                description="",
                value=transition_counts,
                unit="",
                reasoning="",
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

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                unit="",
                reasoning="",
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
