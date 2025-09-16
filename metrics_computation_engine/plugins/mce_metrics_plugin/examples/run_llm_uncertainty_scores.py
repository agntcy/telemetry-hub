import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from mce_metrics_plugin.session.llm_uncertainty_scores import (
    LLMAverageConfidence,
    LLMMaximumConfidence,
    LLMMinimumConfidence,
)

from metrics_computation_engine.core.data_parser import parse_raw_spans
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict
from metrics_computation_engine.logger import setup_logger
from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry

logger = setup_logger(__name__)


RAW_TRACES_PATH = Path("examples/llm_metrics_single_session_traces.json")


async def compute():
    traces_by_session = json.loads(RAW_TRACES_PATH.read_text())

    for session_id, raw_spans in traces_by_session.items():
        span_entities = parse_raw_spans(raw_spans=raw_spans)
        traces_by_session[session_id] = span_entities

    addon = "" if len(traces_by_session) == 1 else "s"
    logger.info(f"Calculating metrics for {len(traces_by_session)} session{addon}.")

    session_entities = build_session_entities_from_dict(sessions_data=traces_by_session)
    sessions_data = {entity.session_id: entity for entity in session_entities}

    registry = MetricRegistry()

    for metric_class in [
        LLMAverageConfidence,
        LLMMinimumConfidence,
        LLMMaximumConfidence,
    ]:
        registry.register_metric(
            metric_class=metric_class, metric_name=metric_class.__name__
        )

    registered_metrics = registry.list_metrics()
    logger.info(
        f"Following {len(registered_metrics)} metrics"
        f" are registered: {registered_metrics}"
    )
    llm_config = LLMJudgeConfig()
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
