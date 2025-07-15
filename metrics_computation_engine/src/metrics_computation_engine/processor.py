# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Any, Dict

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.registry import MetricRegistry


class MetricsProcessor:
    """Main processor for computing metrics"""

    def __init__(self, registry: MetricRegistry, llm_config=None, dataset=None):
        self.registry = registry
        self._metric_instances: Dict[str, BaseMetric] = {}
        self._jury = None
        self.dataset = dataset
        if llm_config:
            from metrics_computation_engine.llm_judge.jury import Jury

            self._jury = Jury(llm_config)

    async def _safe_compute(self, metric: BaseMetric, data: Any) -> MetricResult:
        """Safely compute metric with error handling"""
        result = await metric.compute(data)
        return result

    async def compute_metrics(self, data: Any) -> Dict[str, Any]:
        """Compute multiple metrics concurrently"""
        tasks = []
        metric_names = []

        metric_results = {
            "span_metrics": {},
            "session_metrics": {},
            "population_metrics": {},
        }

        # TODO: There may be future metrics where session metrics are dependent
        # on derived span_metrics. For now, we will just replicate the
        # dependent calculation, but eventually we may want to pass a sort of
        # span_level_derived_metrics for session metrics.

        for metric_name in self.registry.list_metrics():
            metric_class = self.registry._metrics[metric_name]
            metric_instance = metric_class(self._jury, self.dataset)

            # TODO: HIGHLY INEFFICIENT
            if metric_instance.aggregation_level in ["span", "session"]:
                for session, session_spans in data.items():
                    if metric_instance.aggregation_level == "span":
                        for span in session_spans:
                            tasks.append(self._safe_compute(metric_instance, span))
                    elif metric_instance.aggregation_level == "session":
                        tasks.append(self._safe_compute(metric_instance, session_spans))

            if metric_instance.aggregation_level == "population":
                tasks.append(self._safe_compute(metric_instance, data))

            metric_names.append(metric_name)

        results = await asyncio.gather(*tasks)

        metric_results = {
            "span_metrics": [],
            "session_metrics": [],
            "population_metrics": [],
        }

        for result in results:
            mc = result.aggregation_level
            if result.value == -1 and result.error_message == "":
                continue
            metric_results[f"{mc}_metrics"].append(result)

        return metric_results
