from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from typing import List


class ToolErrorRate(BaseMetric):
    """
    Calculates the percentage of tool spans that resulted in an error.
    """

    def __init__(self, jury=None, dataset=None):
        super().__init__(jury=jury, dataset=dataset)
        self.name = "ToolErrorRate"
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return []

    def validate_config(self) -> bool:
        return True

    async def compute(self, data):
        try:
            tool_spans = [span for span in data if span.entity_type == "tool"]
            total_tool_calls = len(tool_spans)
            total_tool_errors = sum(1 for span in tool_spans if span.contains_error)

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
                span_id="",
                session_id="",
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={
                    "total_tool_calls": total_tool_calls,
                    "total_tool_errors": total_tool_errors,
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
                session_id="",
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=str(e),
            )
