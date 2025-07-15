# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult


class CyclesCount(BaseMetric):
    """
    Collects the Agent to Agent Interactions counts throughout a trace.
    """

    def __init__(self, jury=None, dataset=None):
        super().__init__(jury=jury, dataset=dataset)
        self.name = "CyclesCount"
        self.aggregation_level = "session"

        self.required = {"entity_type": ["agent", "tool"]}

    @property
    def required_parameters(self) -> List[str]:
        return ["Events.Attributes"]

    def validate_config(self) -> bool:
        return True

    async def compute(self, data):
        def count_contiguous_cycles(seq, min_cycle_len=2):
            n = len(seq)
            cycle_count = 0
            i = 0
            while i < n:
                found_cycle = False
                for k in range(min_cycle_len, (n - i) // 2 + 1):
                    if seq[i : i + k] == seq[i + k : i + 2 * k]:
                        cycle_count += 1
                        found_cycle = True
                        i += k
                        break
                if not found_cycle:
                    i += 1
            return cycle_count

        try:
            events = [
                d.entity_name
                for d in data
                if d.entity_type in self.required["entity_type"]
            ]
            cycle_count = count_contiguous_cycles(events)

            return MetricResult(
                metric_name=self.name,
                description="",
                value=cycle_count,
                unit="",
                reasoning="Count of contiguous cycles in agent and tool interactions",
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
                reasoning="Count of contiguous cycles in agent and tool interactions",
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
