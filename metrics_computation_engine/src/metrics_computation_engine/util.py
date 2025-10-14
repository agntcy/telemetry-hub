# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
from functools import lru_cache
from importlib.metadata import entry_points
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Tuple, Optional
from fastapi import HTTPException

from metrics_computation_engine.dal.api_client import (
    get_all_session_ids,
    get_traces_by_session,
    get_traces_by_session_ids,
)

from metrics_computation_engine.metrics.population import (
    GraphDeterminismScore,
)

from metrics_computation_engine.metrics.span import (
    ToolUtilizationAccuracy,
)

from metrics_computation_engine.metrics.session import (
    AgentToAgentInteractions,
    AgentToToolInteractions,
    CyclesCount,
    ToolErrorRate,
    PassiveEvalApp,
    PassiveEvalAgents,
)

from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.models.requests import (
    DataFetchingConfig,
    MetricsConfigRequest,
)

from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

NATIVE_METRICS = {
    "AgentToAgentInteractions": AgentToAgentInteractions,
    "AgentToToolInteractions": AgentToToolInteractions,
    "Cycles": CyclesCount,
    "ToolErrorRate": ToolErrorRate,
    "ToolUtilizationAccuracy": ToolUtilizationAccuracy,
    "GraphDeterminismScore": GraphDeterminismScore,
    "PassiveEvalApp": PassiveEvalApp,
    "PassiveEvalAgents": PassiveEvalAgents,
}

# Cache for all available metrics (native + plugins)
_ALL_METRICS_CACHE = None

# Cache for metric adapters (for dynamically created metrics)
_METRIC_ADAPTERS_CACHE = None


@lru_cache(maxsize=1)
def get_metric_adapters():
    """
    Get all available metric adapters from plugins.
    These are special adapters that can create metrics dynamically.
    """
    global _METRIC_ADAPTERS_CACHE

    if _METRIC_ADAPTERS_CACHE is None:
        _METRIC_ADAPTERS_CACHE = {}

        # Get entry points for metric adapters
        try:
            eps = entry_points(group="metrics_computation_engine.adapters")
        except TypeError:
            # Fallback for older Python versions
            eps = entry_points().get("metrics_computation_engine.adapters", [])

        for entry_point in eps:
            try:
                adapter_class = entry_point.load()
                _METRIC_ADAPTERS_CACHE[entry_point.name] = adapter_class
                print(f"Loaded metric adapter: {entry_point.name}")
            except Exception as e:
                import traceback

                print(traceback.format_exc())
                print(f"Warning: Failed to load adapter '{entry_point.name}': {e}")

    return _METRIC_ADAPTERS_CACHE


@lru_cache(maxsize=1)
def get_all_metric_classes():
    """
    Get all available metric classes including native and plugin metrics.
    This function caches the result to avoid repeated entry point discovery.
    """
    global _ALL_METRICS_CACHE

    if _ALL_METRICS_CACHE is None:
        # Start with native metrics
        _ALL_METRICS_CACHE = NATIVE_METRICS.copy()

        # Get entry points for our plugin group
        try:
            eps = entry_points(group="metrics_computation_engine.plugins")
        except TypeError:
            # Fallback for older Python versions
            eps = entry_points().get("metrics_computation_engine.plugins", [])

        for entry_point in eps:
            try:
                plugin_metric_class = entry_point.load()
                _ALL_METRICS_CACHE[entry_point.name] = plugin_metric_class
            except Exception as e:
                # Skip failed plugins but log the error
                import traceback

                print(traceback.format_exc())
                print(f"Warning: Failed to load '{entry_point.name}': {e}")

    return _ALL_METRICS_CACHE


def get_metric_class(metric_name: str) -> Tuple[Any, str]:
    """
    Dynamically import a class from a string.
    Include both native and plugin metrics, as well as adapter-based metrics.

    Args:
        metric_name: Either a simple name or a dotted path like 'deepeval.metrics.AnswerRelevancyMetric'

    Returns:
        Tuple of (metric_class, processed_metric_name)
    """
    # First, try to get from direct plugin/native metrics
    all_metrics = get_all_metric_classes()
    metric_key = metric_name.split(".")[-1]

    # Check if it's a direct match in our registered metrics
    if metric_key in all_metrics:
        return (all_metrics[metric_key], metric_key)

    # If not found and it's a dotted name, try to find an appropriate adapter
    if "." in metric_name:
        adapter_info = find_metric_adapter(metric_name)
        if adapter_info:
            return adapter_info

    # If still not found, raise an error
    available_metrics = list(all_metrics.keys())
    available_adapters = list(get_metric_adapters().keys())

    raise ValueError(
        f"Metric '{metric_key}' not found. "
        f"Available native/plugin metrics: {available_metrics}. "
        f"Available adapters: {available_adapters}. "
        f"For adapter metrics, use format like 'deepeval.metrics.AnswerRelevancyMetric'"
    )


def find_metric_adapter(metric_name: str) -> Optional[Tuple[Any, str]]:
    """
    Find an appropriate adapter for a dotted metric name.

    Args:
        metric_name: Dotted metric name like 'deepeval.metrics.AnswerRelevancyMetric'

    Returns:
        Tuple of (adapter_class, metric_name) or None if no adapter found
    """
    adapters = get_metric_adapters()

    # Check if any adapter can handle this metric
    for adapter_name, adapter_class in adapters.items():
        if can_adapter_handle_metric(adapter_name, metric_name):
            # For RAGAS, handle different naming formats
            if adapter_name.lower() == "ragas":
                parts = metric_name.split(".")
                if len(parts) >= 3:
                    # Check if it's ragas.metrics.MetricName or ragas.MetricName.mode format
                    if parts[1] == "metrics":
                        # Format: ragas.metrics.TopicAdherenceScore -> pass TopicAdherenceScore
                        return (adapter_class, parts[2])
                    else:
                        # Format: ragas.TopicAdherenceScore.mode -> pass full name for mode extraction
                        return (adapter_class, metric_name)
                else:
                    # Format: ragas.MetricName -> pass MetricName
                    return (adapter_class, parts[1])
            else:
                # Standard behavior for other adapters
                return (adapter_class, metric_name.split(".")[-1])

    return None


def can_adapter_handle_metric(adapter_name: str, metric_name: str) -> bool:
    """
    Check if an adapter can handle a specific metric name.

    Args:
        adapter_name: Name of the adapter (e.g., 'deepeval')
        metric_name: Full metric name (e.g., 'deepeval.metrics.AnswerRelevancyMetric')

    Returns:
        True if the adapter can handle this metric
    """
    # Simple heuristic: check if adapter name is in the metric path
    return adapter_name.lower() in metric_name.lower()


def create_adapted_metric(adapter_class: Any, metric_name: str) -> Any:
    """
    Create a metric instance using an adapter.

    Args:
        adapter_class: The adapter class (e.g., DeepEvalMetricAdapter)
        metric_name: The original metric name

    Returns:
        Configured metric instance
    """
    logger.info(
        f"create_adapted_metric called with metric_name: '{metric_name}', adapter_class: {adapter_class}"
    )

    parts = metric_name.split(".")
    logger.info(f"Metric name parts: {parts}")

    # Handle RAGAS extended naming convention: "ragas.TopicAdherenceScore.mode"
    if len(parts) >= 3 and parts[0].lower() == "ragas":
        provider, base_metric_name, mode = parts[0], parts[1], parts[2]
        logger.info(
            f"RAGAS extended naming detected: provider={provider}, base={base_metric_name}, mode={mode}"
        )

        # Validate RAGAS mode
        valid_ragas_modes = ["precision", "recall", "f1"]
        if mode in valid_ragas_modes:
            # Check if this is RagasAdapter by checking class name
            if (
                hasattr(adapter_class, "__name__")
                and "RagasAdapter" in adapter_class.__name__
            ):
                logger.info(
                    f"Creating RAGAS adapter with mode: {mode} for metric: {base_metric_name}"
                )
                return adapter_class(base_metric_name, mode=mode)
            else:
                logger.info(
                    f"Not a RagasAdapter, using fallback for {base_metric_name}"
                )
                # Fallback for non-RAGAS adapters
                return adapter_class(base_metric_name)
        else:
            logger.info(f"Invalid RAGAS mode '{mode}', treating as standard metric")
            # Invalid mode, treat the last part as part of metric name
            actual_metric_name = metric_name.split(".")[-1]
            return adapter_class(actual_metric_name)
    else:
        logger.info(
            f"Standard naming convention, using last part: {parts[-1] if parts else 'unknown'}"
        )
        # Standard behavior for other adapters
        actual_metric_name = metric_name.split(".")[-1]
        return adapter_class(actual_metric_name)


def stringify_keys(obj):
    if isinstance(obj, dict):
        return {str(k): stringify_keys(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_keys(i) for i in obj]
    else:
        return obj


def format_return(results):
    formatted_results = {}

    for metric_category, metric_results in results.items():
        formatted_results[metric_category] = [
            asdict(r) if is_dataclass(r) else r for r in metric_results
        ]

    return stringify_keys(formatted_results)


def clear_metrics_cache():
    """
    Clear the metrics cache.
    Useful for testing or when plugins are added/removed.
    """
    global _ALL_METRICS_CACHE, _METRIC_ADAPTERS_CACHE
    _ALL_METRICS_CACHE = None
    _METRIC_ADAPTERS_CACHE = None


def get_all_available_metrics():
    """
    Get all available metrics including native, plugin metrics, and supported adapter metrics
    """
    metrics = {}

    # Add native metrics
    for name, metric_class in NATIVE_METRICS.items():
        try:
            # Create instance to get metadata
            instance = metric_class()
            # Check if metric supports agent computation
            supports_agent = False
            if hasattr(instance, "supports_agent_computation"):
                try:
                    supports_agent = instance.supports_agent_computation()
                except Exception:
                    supports_agent = False

            metrics[name] = {
                "name": name,
                "class": metric_class.__name__,
                "module": metric_class.__module__,
                "aggregation_level": getattr(instance, "aggregation_level", "unknown"),
                "supports_agent_computation": supports_agent,
                "description": (
                    getattr(instance, "description", None)
                    or getattr(instance, "__doc__", None)
                    or getattr(metric_class, "__doc__", None)
                    or "No description available"
                ),
                "required_parameters": getattr(instance, "required_parameters", []),
                "source": "native",
            }
        except Exception as e:
            logger.error(f"{name=} {metric_class=} {e}")
            # Fallback if instance creation fails
            metrics[name] = {
                "name": name,
                "class": metric_class.__name__,
                "module": metric_class.__module__,
                "description": (metric_class.__doc__ or "No description available"),
                "source": "native",
                "error": str(e),
            }

    # Get entry points for plugin metrics
    try:
        eps = entry_points(group="metrics_computation_engine.plugins")
    except TypeError:
        # Fallback for older Python versions
        eps = entry_points().get("metrics_computation_engine.plugins", [])

    for entry_point in eps:
        try:
            plugin_metric = entry_point.load()
            instance = plugin_metric()
            # Check if metric supports agent computation
            supports_agent = False
            if hasattr(instance, "supports_agent_computation"):
                try:
                    supports_agent = instance.supports_agent_computation()
                except Exception:
                    supports_agent = False

            metrics[entry_point.name] = {
                "name": entry_point.name,
                "class": plugin_metric.__name__,
                "module": plugin_metric.__module__,
                "aggregation_level": getattr(instance, "aggregation_level", "unknown"),
                "supports_agent_computation": supports_agent,
                "description": (
                    getattr(instance, "description", None)
                    or instance.__doc__
                    or plugin_metric.__doc__
                    or "No description available"
                ),
                "required_parameters": getattr(instance, "required_parameters", []),
                "source": "plugin",
            }
        except Exception as e:
            print(f"Warning: Failed to load plugin '{entry_point}': {e}")
            metrics[entry_point.name] = {
                "name": entry_point.name,
                "source": "plugin",
                "error": f"Failed to load plugin: {str(e)}",
            }

    # Add adapter information and enumerate their specific metrics
    adapters = get_metric_adapters()
    for adapter_name, adapter_class in adapters.items():
        # Add the adapter info with correct usage examples
        usage_examples = {
            "opik": "opik.Hallucination",
            "deepeval": "deepeval.AnswerRelevancyMetric",
            "ragas": "ragas.ContextPrecision",
        }
        example_usage = usage_examples.get(
            adapter_name.lower(), f"{adapter_name}.MetricName"
        )

        metrics[f"{adapter_name}_adapter"] = {
            "name": f"{adapter_name}_adapter",
            "class": adapter_class.__name__,
            "module": adapter_class.__module__,
            "description": f"Adapter for {adapter_name} metrics. Use dotted notation like '{example_usage}'",
            "source": "adapter",
            "adapter_for": adapter_name,
        }

        # Try to enumerate specific metrics provided by this adapter
        try:
            if adapter_name.lower() == "opik":
                # Special handling for Opik adapter
                try:
                    from mce_opik_adapter.metric_configuration import (
                        build_metric_configuration_map,
                    )

                    config_map = build_metric_configuration_map()
                    for metric_name, config in config_map.items():
                        full_metric_name = f"opik.{metric_name}"
                        metrics[full_metric_name] = {
                            "name": full_metric_name,
                            "class": f"OpikMetricAdapter({metric_name})",
                            "module": adapter_class.__module__,
                            "aggregation_level": config.requirements.aggregation_level,
                            "supports_agent_computation": False,  # Opik metrics typically don't support agent level
                            "description": f"Opik {metric_name} metric - Use as 'opik.{metric_name}'",
                            "required_parameters": config.requirements.required_input_parameters,
                            "source": "adapter_metric",
                            "adapter_name": adapter_name,
                            "entity_types": config.requirements.entity_type,
                        }
                except ImportError:
                    logger.warning("Could not import Opik adapter configuration")
                except Exception as opik_error:
                    logger.error(f"Error enumerating Opik metrics: {opik_error}")
            elif adapter_name.lower() == "deepeval":
                # Add common DeepEval metrics
                common_deepeval_metrics = [
                    "AnswerRelevancyMetric",
                    "FaithfulnessMetric",
                    "ContextualPrecisionMetric",
                    "ContextualRecallMetric",
                    "ContextualRelevancyMetric",
                    "HallucinationMetric",
                    "BiasMetric",
                    "ToxicityMetric",
                ]
                for metric_name in common_deepeval_metrics:
                    full_metric_name = f"deepeval.{metric_name}"
                    metrics[full_metric_name] = {
                        "name": full_metric_name,
                        "class": f"DeepEvalMetricAdapter({metric_name})",
                        "module": adapter_class.__module__,
                        "aggregation_level": "span",
                        "supports_agent_computation": False,
                        "description": f"DeepEval {metric_name} - Use as 'deepeval.{metric_name}'",
                        "source": "adapter_metric",
                        "adapter_name": adapter_name,
                    }
            elif adapter_name.lower() == "ragas":
                # Add common RAGAS metrics
                common_ragas_metrics = [
                    "ContextPrecision",
                    "ContextRecall",
                    "Faithfulness",
                    "AnswerRelevancy",
                    "AnswerSimilarity",
                    "AnswerCorrectness",
                ]
                for metric_name in common_ragas_metrics:
                    full_metric_name = f"ragas.{metric_name}"
                    metrics[full_metric_name] = {
                        "name": full_metric_name,
                        "class": f"RagasMetricAdapter({metric_name})",
                        "module": adapter_class.__module__,
                        "aggregation_level": "span",
                        "supports_agent_computation": False,
                        "description": f"RAGAS {metric_name} - Use as 'ragas.{metric_name}'",
                        "source": "adapter_metric",
                        "adapter_name": adapter_name,
                    }
        except Exception as e:
            logger.error(f"Failed to enumerate metrics for adapter {adapter_name}: {e}")

    return metrics


async def compute(
    metrics,  # List of metric CLASSES, e.g. [MetricA, MetricB]
    llm_judge_config,  # Dict with LLM judge config
    data_fetching_config: DataFetchingConfig,  # DataFetchingConfig model with validation
):
    """
    Compute metrics for sessions based on the provided data fetching configuration.

    Args:
        metrics: List of metric classes to compute
        llm_judge_config: Configuration for LLM judge
        data_fetching_config: DataFetchingConfig instance containing session selection criteria
    """
    traces_by_session = {}

    # Validate the data fetching config
    if not data_fetching_config.validate():
        raise HTTPException(
            status_code=400, detail="Invalid data fetching configuration"
        )

    # Get session IDs based on the configuration type
    if data_fetching_config.is_batch():
        # Use batch configuration to get session IDs
        batch_config = data_fetching_config.get_batch_config()
        session_ids = get_all_session_ids(batch_config)

        if not session_ids:
            logger.warning("No sessions found matching the batch configuration")
            return {"metrics": [], "results": {}}

        # Load traces for each session individually
        for session_id in session_ids:
            traces_by_session[session_id] = get_traces_by_session(session_id)
    else:
        # Use specific session IDs
        session_ids = data_fetching_config.get_session_ids()

        if not session_ids:
            logger.warning("No session IDs provided")
            return {"metrics": [], "results": {}}

        # Load traces for multiple sessions at once (more efficient)
        traces_by_session, notfound_session_ids = get_traces_by_session_ids(session_ids)

        if notfound_session_ids:
            logger.warning(f"Sessions not found: {notfound_session_ids}")

        if not traces_by_session:
            logger.warning("No traces found for the provided session IDs")
            return {"metrics": [], "results": {}}

    # Set up metrics registry
    from metrics_computation_engine.model_handler import ModelHandler

    registry = MetricRegistry()
    model_handler = ModelHandler()

    for metric in metrics:
        if "." not in metric.__module__:
            registry.register_metric(metric)
            continue
        metric_path = metric.__module__ + "." + metric.__name__
        metric_class, processed_name = get_metric_class(metric_path)

        # If it's an adapter, create the metric instance with the processed name
        if hasattr(metric_class, "__name__") and "Adapter" in metric_class.__name__:
            metric_instance = create_adapted_metric(metric_class, metric_path)
            registry.register_metric(metric_instance.__class__)
        else:
            registry.register_metric(metric_class)

    # Process metrics
    processor = MetricsProcessor(registry, model_handler, llm_config=llm_judge_config)
    results = await processor.compute_metrics(traces_by_session)

    return {"metrics": registry.list_metrics(), "results": format_return(results)}


async def compute_from_request(config_request: MetricsConfigRequest):
    """
    Convenience function to compute metrics directly from a MetricsConfigRequest.

    Args:
        config_request: MetricsConfigRequest containing all configuration
    """
    if not config_request.validate():
        raise HTTPException(
            status_code=400, detail="Invalid metrics configuration request"
        )

    # Convert metric names to metric classes
    metric_classes = []
    for metric_name in config_request.metrics:
        try:
            metric_class, processed_name = get_metric_class(metric_name)

            # If it's an adapter, create the adapted metric
            if hasattr(metric_class, "__name__") and "Adapter" in metric_class.__name__:
                metric_instance = create_adapted_metric(metric_class, metric_name)
                metric_classes.append(metric_instance.__class__)
            else:
                metric_classes.append(metric_class)

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return await compute(
        metrics=metric_classes,
        llm_judge_config=config_request.llm_judge_config,
        data_fetching_config=config_request.data_fetching_infos,
    )


# Rest of your utility functions remain the same...
def get_tool_definitions_from_span_attributes(
    span_attributes: Dict[str, Any],
) -> List[Dict[str, Any]]:
    tool_definition_mapping = dict()
    for k, v in span_attributes.items():
        key_prefix = "llm.request.functions."
        if k.startswith(key_prefix):
            number, attribute = k[len(key_prefix) :].split(".")
            if number not in tool_definition_mapping:
                tool_definition_mapping[number] = dict()
            tool_definition_mapping[number][attribute] = (
                json.loads(v) if attribute == "parameters" else v
            )
    sorted_keys = sorted(tool_definition_mapping.keys())
    res = [tool_definition_mapping[number] for number in sorted_keys]
    del sorted_keys, tool_definition_mapping
    return res


def build_chat_history_from_payload(
    payload: Dict[str, Any], prefix: str
) -> List[Dict[str, Any]]:
    # Example 1: payload = span_entity.input_payload, prefix = "gen_ai.prompt."
    # Example 1: payload = span_entity.output_payload, prefix = "gen_ai.completion."
    chat_entry_dicts = dict()
    for k, v in payload.items():
        if k.startswith(prefix):
            number, raw_key = k[len(prefix) :].split(sep=".", maxsplit=1)
            if number not in chat_entry_dicts:
                chat_entry_dicts[number] = dict()
            chat_entry_dicts[number][raw_key] = v
    chat_history = [chat_entry_dicts[str(i)] for i in range(len(chat_entry_dicts))]
    del chat_entry_dicts
    for i, message in enumerate(chat_history):
        if message["role"] != "assistant":
            continue
        message_copy = _unflatten_tool_calls_in_message(message=message)
        chat_history[i] = message_copy
    return chat_history


def _unflatten_tool_calls_in_message(message: Dict[str, Any]) -> Dict[str, Any]:
    tool_calls_dict = dict()
    message_copy = message.copy()
    for k, v in message.items():
        tool_calls_prefix = "tool_calls."
        if k.startswith(tool_calls_prefix):
            num, raw_key = k[len(tool_calls_prefix) :].split(sep=".", maxsplit=1)
            if num not in tool_calls_dict:
                tool_calls_dict[num] = dict()
            tool_calls_dict[num][raw_key] = (
                json.loads(v) if raw_key == "arguments" else v
            )
            del message_copy[k]
    tool_calls = [tool_calls_dict[str(i)] for i in range(len(tool_calls_dict))]
    message_copy["tool_calls"] = tool_calls
    message_content = message_copy.get("content", "")
    if tool_calls and (message_content in ('""', "''")):
        message_content = ""
    message_copy["content"] = message_content
    return message_copy
