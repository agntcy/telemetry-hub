# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.session import SessionEntity
from metrics_computation_engine.models.eval import MetricResult


class SpanCounter(BaseMetric):
    """
    Calculates the number of spans.
    This is a demo sample for implementing a metric.
    """

    REQUIRED_PARAMETERS = []

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
        total_spans = len(session.spans)
        all_span_ids = [span.span_id for span in session.spans]

        return MetricResult(
            metric_name=self.name,
            description="Number of spans in the session",
            value=total_spans,
            reasoning="",
            unit="count",
            aggregation_level=self.aggregation_level,
            span_id="",
            session_id=session.session_id,
            source="native",
            entities_involved=[],
            edges_involved=[],
            success=True,
            error_message=None,
            metadata={
                "computed_by": "SpanCounter plugin",
                "data_count": total_spans,
                "span_ids": all_span_ids,
                "agent_spans": len(session.agent_spans) if session.agent_spans else 0,
                "workflow_spans": len(session.workflow_spans)
                if session.workflow_spans
                else 0,
            },
        )
