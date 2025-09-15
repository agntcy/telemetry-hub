# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric

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
            return self._create_error_result(
                category="agent", error_message="Entity is not a tool!"
            )

        results = list(find(dict(data), "status"))

        if len(results) > 0:
            return self._create_success_result(
                results[0],
                category="agent",
                span_ids=[data.span_id],
                session_ids=data.session_id,
            )

        return self._create_error_result(
            category="agent", error_message="Failed to retrieve tool status."
        )
