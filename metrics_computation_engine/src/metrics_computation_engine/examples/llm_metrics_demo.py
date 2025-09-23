# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from metrics_computation_engine.core.data_parser import parse_raw_spans

# Import 3rd party adapters
from mce_deepeval_adapter.adapter import DeepEvalMetricAdapter
from mce_opik_adapter.adapter import OpikMetricAdapter

from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.logger import setup_logger
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.model_handler import ModelHandler

# Use the new trace data file
RAW_TRACES_PATH: Path = Path(__file__).parent / "data" / "8efde096af0e9d89e59b19905e487fa6.json"
ENV_FILE_PATH: Path = Path(__file__).parent.parent.parent.parent / ".env"

print("ENV", ENV_FILE_PATH)
logger = setup_logger(name=__name__)


async def compute():
    # Load from the new trace data file
    raw_spans = json.loads(RAW_TRACES_PATH.read_text())

    # Convert the list to a single session
    span_entities = parse_raw_spans(raw_spans=raw_spans)
    traces_by_session = build_session_entities_from_dict({"session_1": span_entities})
    traces_by_session = {
        session.session_id: session for session in traces_by_session
    }
    addon = "" if len(traces_by_session) == 1 else "s"

    logger.info(f"Calculating metrics for {len(traces_by_session)} session{addon}.")

    registry = MetricRegistry()

    # Register only the 4 requested LLM metrics
    
    # 1. Relevance - AnswerRelevancyMetric from DeepEval
    registry.register_metric(DeepEvalMetricAdapter, "AnswerRelevancyMetric")
    logger.info("Registered AnswerRelevancyMetric from DeepEval")
    
    # 2. Hallucination from Opik
    registry.register_metric(OpikMetricAdapter, "Hallucination")
    logger.info("Registered Hallucination from Opik")
    
    # 3. Bias - BiasMetric from DeepEval
    registry.register_metric(DeepEvalMetricAdapter, "BiasMetric")
    logger.info("Registered BiasMetric from DeepEval")
    
    # 4. Toxicity - ToxicityMetric from DeepEval
    registry.register_metric(DeepEvalMetricAdapter, "ToxicityMetric")
    logger.info("Registered ToxicityMetric from DeepEval")

    registered_metrics = registry.list_metrics()
    logger.info(
        f"Following {len(registered_metrics)} LLM metrics are registered:"
        f" {registered_metrics}"
    )

    # Configure LLM for the metrics that require LLM judge
    llm_config = LLMJudgeConfig(
        LLM_BASE_MODEL_URL=os.environ["LLM_BASE_MODEL_URL"],
        LLM_MODEL_NAME=os.environ["LLM_MODEL_NAME"],
        LLM_API_KEY=os.environ["LLM_API_KEY"],
    )

    model_handler = ModelHandler()

    processor = MetricsProcessor(
        model_handler=model_handler, registry=registry, llm_config=llm_config
    )

    logger.info("LLM metrics calculation processor started")
    results = await processor.compute_metrics(traces_by_session)

    logger.info("LLM metrics calculation processor finished")

    results_dicts = _format_results(results=results)
    return_dict = {"metrics": registered_metrics, "results": results_dicts}
    logger.info(json.dumps(return_dict, indent=4))

    # Additional summary for the specific metrics
    logger.info("\n=== LLM METRICS SUMMARY ===")
    for session_id, session_results in results_dicts.items():
        logger.info(f"\nSession: {session_id}")
        for result in session_results:
            metric_name = result.get('metric_name', 'Unknown')
            value = result.get('value', 'N/A')
            success = result.get('success', False)
            source = result.get('source', 'Unknown')
            logger.info(f"  {metric_name} ({source}): {value} [Success: {success}]")


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
