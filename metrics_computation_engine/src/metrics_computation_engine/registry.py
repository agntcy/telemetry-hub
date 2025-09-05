# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict, Optional

from metrics_computation_engine.metrics.base import BaseMetric


class MetricRegistry:
    """Enhanced registry that can handle both native and DeepEval metrics"""

    def __init__(self, config=None):
        self._metrics: Dict[str, Any] = {}

    def register_metric(self, metric_class, metric_name: Optional[str] = None):
        """Register either a native metric class or DeepEval metric instance"""

        if not issubclass(metric_class, BaseMetric):
            raise ValueError(f"Metric {metric_name} must inherit from BaseMetric")
        if metric_name is None:
            metric_name = metric_class.__name__
        self._metrics[metric_name] = metric_class

    def get_metric(self, name: str):
        """Get a metric by name"""
        return self._metrics.get(name)

    def list_metrics(self):
        """List all registered metrics"""
        return list(self._metrics.keys())
