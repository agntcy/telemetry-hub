# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict

from metrics_computation_engine.metrics.base import BaseMetric


class MetricRegistry:
    """Enhanced registry handles native metrics"""

    def __init__(self, config=None):
        self._metrics: Dict[str, Any] = {}

    def register_metric(self, metric_class_or_instance):
        """Register a native metric class"""

        metric_name = metric_class_or_instance.__name__
        if not issubclass(metric_class_or_instance, BaseMetric):
            raise ValueError(f"Metric {metric_name} must inherit from BaseMetric")
        self._metrics[metric_name] = metric_class_or_instance

    def get_metric(self, name: str):
        """Get a metric by name"""
        return self._metrics.get(name)

    def list_metrics(self):
        """List all registered metrics"""
        return list(self._metrics.keys())
