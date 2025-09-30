# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

# Workflow Efficiency
from typing import List, Optional

from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.session import SessionEntity


class WorkflowEfficiency(BaseMetric):
    """
    Measures workflow efficiency using agent transition data.
    """

    REQUIRED_PARAMETERS = {
        "WorkflowEfficiency": ["agent_transitions", "agent_transition_counts"]
    }

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return self.REQUIRED_PARAMETERS

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
            # Calculate efficiency metrics from pre-computed agent transitions
            total_transitions = (
                len(session.agent_transitions) if session.agent_transitions else 0
            )
            unique_transitions = (
                len(session.agent_transition_counts)
                if session.agent_transition_counts
                else 0
            )

            # Simple efficiency score: fewer unique transition types = more efficient
            # You can implement more sophisticated logic here
            efficiency_score = (
                1.0
                if unique_transitions <= 2
                else max(0.0, 1.0 - (unique_transitions - 2) * 0.2)
            )

            agent_span_ids = (
                [span.span_id for span in session.agent_spans]
                if session.agent_spans
                else []
            )

            entities_involved = (
                [span.entity_name for span in session.agent_spans]
                if session.agent_spans
                else []
            )
            return MetricResult(
                metric_name=self.name,
                description="Workflow efficiency based on agent transitions",
                value=efficiency_score,
                reasoning="",
                unit="efficiency_score",
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name,
                span_id="",
                session_id=session.session_id,
                source="native",
                entities_involved=list(set(entities_involved)),
                edges_involved=[],
                success=True,
                metadata={
                    "total_transitions": total_transitions,
                    "unique_transitions": unique_transitions,
                    "transition_counts": dict(session.agent_transition_counts)
                    if session.agent_transition_counts
                    else {},
                    "span_ids": agent_span_ids,
                },
                error_message=None,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="",
                reasoning="",
                value=-1,
                unit="",
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name,
                span_id="",
                session_id=session.session_id if hasattr(session, "session_id") else "",
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=str(e),
            )
