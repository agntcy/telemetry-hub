# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.session import SessionEntity


class ToolErrorRate(BaseMetric):
    """
    Calculates the percentage of tool spans that resulted in an error.
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
            total_tool_calls = len(tool_spans)

            error_spans = [span for span in tool_spans if span.contains_error]
            total_tool_errors = len(error_spans)
            error_span_ids = [span.span_id for span in error_spans]

            tool_error_rate = (
                (total_tool_errors / total_tool_calls) * 100 if total_tool_calls else 0
            )

            return MetricResult(
                metric_name=self.name,
                description="Percentage of tool spans that encountered errors",
                value=tool_error_rate,
                reasoning="",
                unit="%",
                aggregation_level=self.aggregation_level,
                span_id=error_span_ids,
                session_id=[session.session_id],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={
                    "total_tool_calls": total_tool_calls,
                    "total_tool_errors": total_tool_errors,
                    "all_tool_span_ids": [span.span_id for span in tool_spans],
                },
                error_message=None,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="Failed to calculate tool error rate",
                value=-1,
                reasoning="",
                unit="%",
                aggregation_level=self.aggregation_level,
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
