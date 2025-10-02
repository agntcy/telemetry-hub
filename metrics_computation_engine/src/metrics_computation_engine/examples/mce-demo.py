# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv

# Import MCE Native Metrics
from metrics_computation_engine.metrics.session import (
    AgentToAgentInteractions,
    AgentToToolInteractions,
    CyclesCount,
)

# Import MCE Plugin Metrics
from mce_metrics_plugin.session import (
    GoalSuccessRate,
    ContextPreservation,
    WorkflowCohesionIndex,
    ComponentConflictRate,
    ResponseCompleteness,
    InformationRetention,
    IntentRecognitionAccuracy,
)

# Import 3rd party adapters
from mce_deepeval_adapter.adapter import DeepEvalMetricAdapter
from mce_opik_adapter.adapter import OpikMetricAdapter

from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.logger import setup_logger
from metrics_computation_engine.util import get_metric_class
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.entities.core.trace_processor import TraceProcessor

RAW_TRACES_PATH: Path = Path(__file__).parent / "data" / "sample_data.json"
ENV_FILE_PATH: Path = Path(__file__).parent.parent.parent.parent / ".env"

print("ENV", ENV_FILE_PATH)

# Load environment variables from .env file
load_dotenv(ENV_FILE_PATH)

logger = setup_logger(name=__name__)


async def compute():
    # Option1: load from local file
    raw_spans = json.loads(RAW_TRACES_PATH.read_text())

    # Convert the list to a single session
    trace_processor = TraceProcessor()
    sessions_set = trace_processor.process_raw_traces(raw_spans)

    logger.info(f"Calculating metrics for {len(sessions_set.sessions)} session.")

    registry = MetricRegistry()

    # Register metrics directly by class
    session_metrics = [
        GoalSuccessRate,
        ContextPreservation,
        WorkflowCohesionIndex,
        ComponentConflictRate,
        ResponseCompleteness,
        InformationRetention,
        IntentRecognitionAccuracy,
        AgentToAgentInteractions,
        AgentToToolInteractions,
        CyclesCount,
    ]

    for metric in session_metrics:
        logger.info(f"Registered {metric.__name__} via direct class.")
        registry.register_metric(metric)

    # If developing a service you can use MCE's get_metric_class() helper to translate string requests to their respective classes
    service_request_metrics = [
        "ToolErrorRate",
        "ToolUtilizationAccuracy",
        "Groundedness",
        "Consistency",
    ]
    for metric in service_request_metrics:
        metric, metric_name = get_metric_class(metric)
        registry.register_metric(metric, metric_name)
        logger.info(f"Registered {metric_name} via get_metric_class() helper.")

    # For third party metrics you will need to use the adapters as the metric class, and then use the metric names as defined by that respective library
    registry.register_metric(DeepEvalMetricAdapter, "AnswerRelevancyMetric")
    registry.register_metric(OpikMetricAdapter, "Hallucination")
    # Again you can use the get_metric_class() helper while structuring your metric as '<third_party_libary>.<third_party_metric>'
    for metric in ["deepeval.RoleAdherenceMetric"]:
        metric, metric_name = get_metric_class(metric)
        registry.register_metric(metric, metric_name)
    logger.info(
        "Registered DeepEval's AnswerRelevancy, Hallucination, RoleAdherence Metrics from 3rd parties."
    )

    registered_metrics = registry.list_metrics()
    logger.info(
        f"Following {len(registered_metrics)} metrics are registered:"
        f" {registered_metrics}"
    )

    llm_config = LLMJudgeConfig(
        LLM_BASE_MODEL_URL=os.environ["LLM_BASE_MODEL_URL"],
        LLM_MODEL_NAME=os.environ["LLM_MODEL_NAME"],
        LLM_API_KEY=os.environ["LLM_API_KEY"],
    )

    model_handler = ModelHandler()

    processor = MetricsProcessor(
        model_handler=model_handler, registry=registry, llm_config=llm_config
    )

    logger.info("Metrics calculation processor started")
    results = await processor.compute_metrics(sessions_set)

    logger.info("Metrics calculation processor finished")

    results_dicts = _format_results(results=results)
    return_dict = {"metrics": registered_metrics, "results": results_dicts}
    logger.info(json.dumps(return_dict, indent=4))


def _format_results(
    results: Dict[str, List[MetricResult]],
) -> Dict[str, List[Dict[str, Any]]]:
    results_dicts = dict()
    for k, v in results.items():
        new_v = [asdict(metric_result) for metric_result in v]
        results_dicts[k] = new_v
    return results_dicts


if __name__ == "__main__":
    asyncio.run(compute())
