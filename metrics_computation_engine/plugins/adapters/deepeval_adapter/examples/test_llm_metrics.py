# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from mce_deepeval_adapter.adapter import DeepEvalMetricAdapter

from metrics_computation_engine.core.data_parser import parse_raw_spans
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict
from metrics_computation_engine.logger import setup_logger
from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry

RAW_TRACES_PATH: Path = (
    Path(__file__).parent / "data" / "llm_metrics_single_session_traces.json"
)
ENV_FILE_PATH: Path = Path(__file__).parent / ".env"

logger = setup_logger(name=__name__)


def build_llm_metrics() -> List[str]:
    return [
        "AnswerRelevancyMetric",
        "CoherenceMetric",
        "ToxicityMetric",
        "BiasMetric",
        "TonalityMetric",
        "GroundednessMetric",
        "AnswerCorrectnessMetric",
        "GeneralStructureAndStyleMetric",
    ]


async def compute():
    load_dotenv(ENV_FILE_PATH)
    traces_by_session = json.loads(RAW_TRACES_PATH.read_text())

    for session_id, raw_spans in traces_by_session.items():
        span_entities = parse_raw_spans(raw_spans=raw_spans)
        traces_by_session[session_id] = span_entities

    addon = "" if len(traces_by_session) == 1 else "s"
    logger.info(f"Calculating metrics for {len(traces_by_session)} session{addon}.")

    session_entities = build_session_entities_from_dict(sessions_data=traces_by_session)
    sessions_data = {entity.session_id: entity for entity in session_entities}

    registry = MetricRegistry()
    metrics = build_llm_metrics()

    for metric_name in metrics:
        registry.register_metric(
            metric_class=DeepEvalMetricAdapter, metric_name=metric_name
        )

    registered_metrics = registry.list_metrics()
    logger.info(
        f"Following {len(registered_metrics)} metrics are registered:"
        f" {registered_metrics}"
    )
    llm_config = LLMJudgeConfig(
        LLM_BASE_MODEL_URL=os.environ["MCE_LLM_BASE_MODEL_URL"],
        LLM_MODEL_NAME=os.environ["MCE_LLM_MODEL_NAME"],
        LLM_API_KEY=os.environ["MCE_LLM_API_KEY"],
    )
    model_handler = ModelHandler()
    processor = MetricsProcessor(
        registry=registry, model_handler=model_handler, llm_config=llm_config
    )

    logger.info("Metrics calculation processor  started")
    results = await processor.compute_metrics(sessions_data=sessions_data)

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
