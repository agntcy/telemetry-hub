# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity

from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


class CyclesCount(BaseMetric):
    """
    Counts contiguous cycles in agent and tool interactions.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return ["Events.Attributes"]

    def validate_config(self) -> bool:
        return True

    def create_model(self, llm_config):
        return self.create_no_model()

    def get_model_provider(self):
        return self.get_provider_no_model_needed()

    def init_with_model(self, model) -> bool:
        return True

    def count_contiguous_cycles(self, seq, min_cycle_len=2):
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

    async def compute(self, session: SessionEntity):
        try:
            # Get agent and tool spans, extract entity names
            # agent_tool_spans = []
            # if session.agent_spans:
            #     agent_tool_spans.extend(session.agent_spans)
            # if session.tool_spans:
            #     agent_tool_spans.extend(session.tool_spans)
            # Sort by timestamp to maintain order
            # agent_tool_spans.sort(key=lambda x: x.timestamp or "")

            agent_tool_spans = [
                span for span in session.spans if span.entity_type in ["agent", "tool"]
            ]
            events = [span.entity_name for span in agent_tool_spans]
            cycle_count = self.count_contiguous_cycles(events)

            span_ids = [span.span_id for span in agent_tool_spans]

            return MetricResult(
                metric_name=self.name,
                value=cycle_count,
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name,
                description="Count of contiguous cycles in agent and tool interactions",
                unit="cycles",
                reasoning="Count of contiguous cycles in agent and tool interactions",
                span_id="",
                session_id=[session.session_id],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={
                    "span_ids": span_ids,
                    "event_sequence": events,
                    "total_events": len(events),
                },
                error_message=None,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                value=-1,
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name
                if hasattr(session, "app_name")
                else "unknown",
                description="",
                unit="",
                reasoning="Count of contiguous cycles in agent and tool interactions",
                span_id="",
                session_id=[session.session_id]
                if hasattr(session, "session_id")
                else [],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=str(e),
            )
