# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult


class ToolError(BaseMetric):
    """
    Collects the Agent to Agent Interactions counts throughout a trace.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "span"

        self.required = {"entity_type": ["tool"]}

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

    async def compute(self, data):
        # TODO: Should not be responsible for this here.
        def find(d, search="status"):
            """Recursively search for all <search> fields in a nested dict."""
            if isinstance(d, dict):
                for key, value in d.items():
                    if key == search:
                        yield value
                    else:
                        yield from find(value, search)
            elif isinstance(d, list):
                for item in d:
                    yield from find(item, search)

        if data.entity_type not in self.required["entity_type"]:
            return MetricResult(
                metric_name=self.name,
                description="",
                reasoning="",
                value=-1,
                unit="",
                aggregation_level="",
                span_id="",
                session_id="",
                source="",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message="",
            )

        results = list(find(dict(data), "status"))

        if len(results) > 0:
            return MetricResult(
                metric_name=self.name,
                description="",
                value=results[0],
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

        return MetricResult(
            metric_name=self.name,
            description="",
            value=-1,
            reasoning="",
            unit="",
            aggregation_level=self.aggregation_level,
            span_id="",
            session_id="",
            source="native",
            entities_involved=[],
            edges_involved=[],
            success=False,
            metadata={},
            error_message="",
        )
