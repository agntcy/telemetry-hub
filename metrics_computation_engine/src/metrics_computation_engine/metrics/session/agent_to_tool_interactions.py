# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from collections import Counter
from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity


class AgentToToolInteractions(BaseMetric):
    """
    Collects the Agent to Tool Interactions counts throughout a trace.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return []

    def validate_config(self) -> bool:
        return True

    def create_model(self, llm_config):
        return self.create_no_model()

    def get_model_provider(self):
        return self.get_provider_no_model_needed()

    def init_with_model(self, model) -> bool:
        return True

    async def compute(self, session: SessionEntity):
        try:
            tool_spans = session.tool_spans if session.tool_spans else []

            transitions = []
            for span in tool_spans:
                span_attrs = span.raw_span_data.get("SpanAttributes", {})
                workflow_name = span_attrs["ioa_observe.workflow.name"]
                tool_name = span_attrs.get("traceloop.entity.name", span.entity_name)

                transition = f"(Agent: {workflow_name}) -> (Tool: {tool_name})"
                transitions.append(transition)

            transition_counts = Counter(transitions)

            return MetricResult(
                metric_name=self.name,
                value=dict(transition_counts),
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name,
                description="Agent to tool interaction counts",
                reasoning="",
                unit="interactions",
                span_id=[span.span_id for span in tool_spans],
                session_id=[session.session_id],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={
                    "total_tool_calls": len(tool_spans),
                    "unique_interactions": len(transition_counts),
                },
                error_message=None,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                value=-1,
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name if hasattr(session, "app_name") else "unknown",
                description="",
                reasoning="",
                unit="",
                span_id=[],
                session_id=[session.session_id]
                if hasattr(session, "session_id")
                else [],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=e,
            )
