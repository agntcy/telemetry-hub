# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from collections import Counter
from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.session import SessionEntity


class AgentToAgentInteractions(BaseMetric):
    """
    Collects the Agent to Agent Interactions counts throughout a trace.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return ["Events.Attributes", "EventsAttributes"]

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
            # Use pre-computed agent transitions from SessionEntity
            transition_counts = (
                session.agent_transition_counts
                if session.agent_transition_counts
                else Counter()
            )
            transitions = session.agent_transitions if session.agent_transitions else []

            # Get span IDs from agent spans
            span_ids = (
                [span.span_id for span in session.agent_spans]
                if session.agent_spans
                else []
            )
            entities_involved = (
                list(set([span.entity_name for span in session.agent_spans]))
                if session.agent_spans
                else []
            )
            
            return MetricResult(
                metric_name=self.name,
                description="Agent to agent interaction transition counts",
                value=dict(transition_counts),
                unit="transitions",
                reasoning="",
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name,
                span_id=span_ids,
                session_id=[session.session_id],
                source="native",
                entities_involved=entities_involved,
                edges_involved=[],
                success=True,
                metadata={
                    "total_transitions": len(transitions),
                    "unique_transitions": len(transition_counts),
                    "all_transitions": transitions,
                },
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
                category="application",
                app_name=session.app_name,
                span_id=[],
                session_id=[session.session_id]
                if hasattr(session, "session_id")
                else [],
                source="native",
                entities_involved=entities_involved,
                edges_involved=[],
                success=False,
                metadata={},
                error_message=str(e),
            )
