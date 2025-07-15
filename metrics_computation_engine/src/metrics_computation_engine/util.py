# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import asdict

from metrics_computation_engine.metrics.span import (
    ToolUtilizationAccuracy,
    ToolError,
)

from metrics_computation_engine.metrics.session import (
    AgentToAgentInteractions,
    AgentToToolInteractions,
    ToolErrorRate,
    Groundedness,
    CyclesCount,
)

NATIVE_METRICS = {
    "AgentToAgentInteractions": AgentToAgentInteractions,
    "AgentToToolInteractions": AgentToToolInteractions,
    "ToolErrorRate": ToolErrorRate,
    "ToolUtilizationAccuracy": ToolUtilizationAccuracy,
    "Groundedness": Groundedness,
    "CyclesCount": CyclesCount,
    "ToolError": ToolError,
}


def get_metric_class(metric_name):
    """
    Dynamically import a class from a string
    """
    return NATIVE_METRICS[metric_name.split(".")[-1]]


def stringify_keys(obj):
    if isinstance(obj, dict):
        return {str(k): stringify_keys(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_keys(i) for i in obj]
    else:
        return obj


def format_return(results):
    for metric_category, metric_results in results.items():
        results[metric_category] = [asdict(r) for r in metric_results]

    return stringify_keys(results)
