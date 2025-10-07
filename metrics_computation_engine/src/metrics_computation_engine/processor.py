# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import asyncio
import inspect
import os
from typing import Any, Dict, List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.session_set import SessionSet
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


class MetricsProcessor:
    """Main processor for computing metrics"""

    def __init__(
        self,
        registry: MetricRegistry,
        model_handler: ModelHandler,
        llm_config=None,
        dataset=None,  # TODO: remove dataset
        max_concurrent_tasks: Optional[int] = None,
    ):
        self.registry = registry
        self._metric_instances: Dict[str, BaseMetric] = {}
        self._jury = None
        self.dataset = dataset
        self.llm_config = llm_config
        self.model_handler = model_handler
        # Cache for introspection results
        self._context_support_cache: Dict[str, bool] = {}

        if max_concurrent_tasks is None:
            env_limit = os.getenv("METRICS_MAX_CONCURRENCY")
            if env_limit:
                try:
                    max_concurrent_tasks = int(env_limit)
                except ValueError:
                    logger.warning(
                        "Invalid METRICS_MAX_CONCURRENCY value '%s', ignoring.",
                        env_limit,
                    )

        if max_concurrent_tasks is not None and max_concurrent_tasks <= 0:
            logger.warning(
                "max_concurrent_tasks=%s is not positive; proceeding without throttling.",
                max_concurrent_tasks,
            )
            max_concurrent_tasks = None

        self._max_concurrency = max_concurrent_tasks
        self._semaphore = (
            asyncio.Semaphore(self._max_concurrency)
            if self._max_concurrency is not None
            else None
        )

    def _metric_supports_context(self, metric: BaseMetric) -> bool:
        """Check if metric's compute method accepts context parameter (cached)"""
        metric_class_name = metric.__class__.__name__

        if metric_class_name not in self._context_support_cache:
            signature = inspect.signature(metric.compute)
            self._context_support_cache[metric_class_name] = (
                "context" in signature.parameters
            )

        return self._context_support_cache[metric_class_name]

    async def _safe_compute(
        self, metric: BaseMetric, data: Any, context: Optional[Dict[str, Any]] = None
    ) -> MetricResult:
        """Safely compute metric with error handling and cache checking"""
        try:
            # Check cache first
            cached_result = None

            if metric.aggregation_level in ["span", "session"]:
                cached_result = await metric.check_cache_metric(
                    metric_name=metric.name, session_id=data.session_id
                )
            if cached_result is not None:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Cache hit for {metric.name} {cached_result=}")
                # build back the MetricResult object from cached data
                return cached_result

            # Cache miss - compute normally
            logger.debug(f"Cache miss for {metric.name}, computing...")

            if self._metric_supports_context(metric) and context is not None:
                logger.debug(
                    f"Calling {metric.name} with context: {list(context.keys()) if context else 'None'}"
                )
                result = await metric.compute(data, context=context)
            else:
                logger.debug(
                    f"Calling {metric.name} without context (supports_context: {self._metric_supports_context(metric)}, context is None: {context is None})"
                )
                result = await metric.compute(data)
            return result
        except Exception as e:
            # logger.error(traceback.format_exc())
            logger.exception(f"Error computing metric {metric.name}: {e}")
            # Return error result instead of crashing
            # Extract basic info from data for error reporting
            app_name = "unknown-app"
            if hasattr(data, "app_name"):
                app_name = data.app_name
            elif (
                hasattr(data, "spans")
                and data.spans
                and hasattr(data.spans[0], "app_name")
            ):
                app_name = data.spans[0].app_name

            return MetricResult(
                metric_name=metric.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=metric.aggregation_level,
                category="application",
                app_name=app_name,
                span_id=[],
                session_id=[],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=str(e),
            )

    async def _bounded_safe_compute(
        self, metric: BaseMetric, data: Any, context: Optional[Dict[str, Any]] = None
    ) -> MetricResult:
        """Run metric computation while respecting concurrency limits."""

        if self._semaphore is None:
            return await self._safe_compute(metric, data, context=context)

        async with self._semaphore:
            return await self._safe_compute(metric, data, context=context)

    async def _initialize_metric(self, metric_name: str, metric_class) -> BaseMetric:
        """Initialize a metric with its required model"""
        metric_instance = metric_class(metric_name)

        model_provider = metric_instance.get_model_provider()
        model = None

        # If model_provider is None, this metric doesn't need an LLM model
        if model_provider is not None:
            # Use the enhanced model handler to get or create the model
            model = await self.model_handler.get_or_create_model(
                provider=model_provider, llm_config=self.llm_config
            )

            # Fallback: if model handler couldn't create it, try the metric's method
            if model is None:
                # Check if the metric has its own model creation method
                if hasattr(metric_instance, "create_model"):
                    model = metric_instance.create_model(self.llm_config)
                    if model is not None:
                        # Store the model in the handler for future use
                        await self.model_handler.set_model(
                            provider=model_provider,
                            llm_config=self.llm_config,
                            model=model,
                        )

        # Initialize the metric with the model
        ok = metric_instance.init_with_model(model)
        if not ok:
            print(
                f"Warning: metric {metric_name} encountered an issue when initiating."
            )
            return None

        return metric_instance

    def _check_session_requirements(
        self, metric_name: str, session_entity: SessionEntity, required_params: list
    ) -> bool:
        """
        Check if session entity has all required parameters for a metric.

        Args:
            session_entity: The SessionEntity to check
            required_params: List of required parameter names

        Returns:
            bool: True if all requirements are met, False otherwise
        """
        for param in required_params:
            # Check if the attribute exists on the session entity
            if not hasattr(session_entity, param):
                return False

            # Check for null attribute values
            attr_value = getattr(session_entity, param, None)
            if attr_value is None:
                return False

            # Specific validation for known attributes
            if param == "conversation_data":
                if not isinstance(attr_value, dict):
                    return False
                # Check if conversation_data has elements (the actual structure)
                elements = attr_value.get("elements", [])
                if not elements or len(elements) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `conversation_data.elements` is empty"
                    )
                    return False
            elif param == "conversation_elements":
                if not isinstance(attr_value, list):
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `conversation_elements` is empty"
                    )
                    return False
                if len(attr_value) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `conversation_elements` is empty"
                    )
                    return False
            elif param == "tool_calls":
                if not isinstance(attr_value, list):
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `tool_calls` is empty"
                    )
                    return False
                if len(attr_value) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `conversation_elements` is empty"
                    )
                    return False
            elif param == "input_query":
                if not attr_value or len(str(attr_value)) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `input_query` is empty"
                    )
                    return False
            elif param == "final_response":
                if not attr_value or len(str(attr_value)) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! final_response` is empty"
                    )
                    return False
            elif param == "workflow_data":
                if not isinstance(attr_value, dict):
                    return False
                query = attr_value.get("query", "")
                response = attr_value.get("response", "")
                if not query or len(query) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `query` is empty"
                    )
                    return False
                if not response or len(response) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `response` is empty"
                    )
                    return False
            elif param == "agent_transitions":
                if not isinstance(attr_value, list):
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `agent_transitions` is empty"
                    )
                    return False
                if len(attr_value) == 0:
                    return False
            elif param == "agent_transition_counts":
                # agent_transition_counts should be a Counter (which is a dict-like object)
                from collections import Counter

                if not isinstance(attr_value, (Counter, dict)):
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `agent_transition_counts` should be a Counter object"
                    )
                    return False
                if len(attr_value) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `agent_transition_counts` is empty"
                    )
                    return False
            elif isinstance(attr_value, (str, list, dict)):
                if not attr_value:  # Empty string, list, or dict
                    return False

        return True

    def _get_metric_requirements(self, metric_class, metric_name: str) -> list:
        """Get required parameters from class without instantiation"""
        required_params_dict = getattr(metric_class, "REQUIRED_PARAMETERS", {})

        if isinstance(required_params_dict, dict):
            return required_params_dict.get(metric_name, [])

        return []

    def _should_compute_metric_for_span(
        self, metric_instance: BaseMetric, span: Any
    ) -> bool:
        """Check if metric should be computed for this span based on entity type filtering"""
        # Check if metric has entity type requirements
        if (
            not hasattr(metric_instance, "required")
            or "entity_type" not in metric_instance.required
        ):
            return True  # No requirements = apply to all spans

        # Check if span has entity type
        if not hasattr(span, "entity_type") or not span.entity_type:
            return True  # No entity type info = apply (fallback to original behavior)

        # Check if span's entity type matches metric requirements
        required_types = metric_instance.required["entity_type"]
        return span.entity_type in required_types

    async def compute_metrics(
        self, sessions_set: SessionSet
    ) -> Dict[str, List[MetricResult]]:
        """
        Compute multiple metrics concurrently using SessionEntity objects.

        Args:
            sessions_data: Dictionary mapping session_id to SessionEntity
        """
        tasks = []
        metric_results = {
            "span_metrics": [],
            "session_metrics": [],
            "population_metrics": [],
        }

        for session_index, session_entity in enumerate(
            sessions_set.sessions
        ):  # browse by SessionEntity
            # Span-level metrics: iterate through spans in the session
            for span in session_entity.spans:
                for metric_name in self.registry.list_metrics():
                    metric_class = self.registry.get_metric(metric_name)

                    # Check aggregation level without instantiation
                    if hasattr(metric_class, "aggregation_level"):
                        # Get aggregation_level
                        if metric_class.aggregation_level != "span":
                            continue

                        # For entity filtering, we still need a temp instance to check requirements
                        temp_instance = metric_class(metric_name)
                        if not self._should_compute_metric_for_span(
                            temp_instance, span
                        ):
                            continue
                    else:
                        # If it needs an instance to get aggregation_level
                        temp_instance = metric_class(metric_name)
                        if temp_instance.aggregation_level != "span":
                            continue
                        if not self._should_compute_metric_for_span(
                            temp_instance, span
                        ):
                            continue

                    # Only initialize if we're going to compute it
                    metric_instance = await self._initialize_metric(
                        metric_name, metric_class
                    )

                    if metric_instance is not None:
                        tasks.append(
                            self._bounded_safe_compute(metric_instance, span)
                        )

            # Session-level metrics: pass the SessionEntity directly
            for metric_name in self.registry.list_metrics():
                metric_class = self.registry.get_metric(metric_name)

                required_params = self._get_metric_requirements(
                    metric_class, metric_name
                )
                logger.info(f"METRIC NAME: {metric_name}")
                logger.info(f"REQUIRED PARAMS: {required_params}")

                if not self._check_session_requirements(
                    metric_name, session_entity, required_params
                ):
                    continue

                metric_instance = await self._initialize_metric(
                    metric_name, metric_class
                )

                if (
                    metric_instance is not None
                    and metric_instance.aggregation_level == "session"
                ):
                    # Prepare context for metrics that need it
                    context = None
                    if sessions_set is not None:
                        context = {
                            "session_set_stats": sessions_set.stats,
                            "session_index": session_index,
                            "session_set": sessions_set,
                        }
                        logger.debug(
                            f"Prepared context with keys: {list(context.keys())}"
                        )
                    # Pass the SessionEntity directly to session-level metrics
                    tasks.append(
                        self._bounded_safe_compute(
                            metric_instance, session_entity, context=context
                        )
                    )

        # Population-level metrics: pass all sessions data
        for metric_name in self.registry.list_metrics():
            metric_class = self.registry.get_metric(metric_name)
            metric_instance = await self._initialize_metric(metric_name, metric_class)

            if (
                metric_instance is not None
                and metric_instance.aggregation_level == "population"
            ):
                # Pass the entire sessions_data dict for population metrics
                tasks.append(
                    self._bounded_safe_compute(metric_instance, sessions_set)
                )

        # Execute all tasks concurrently
        if tasks:
            results: List[MetricResult] = await asyncio.gather(*tasks)

            # mapping of session ids / app name
            sessions_appname_dict = {
                k: v for k, v in sessions_set.stats.meta.session_ids
            }
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"sessions_appname_dict: {sessions_appname_dict}")

            # Organize results by aggregation level
            for result in results:
                if (result.value == -1 or result.value == {}) and not result.success:
                    continue
                aggregation_level = result.aggregation_level
                if aggregation_level in ["span", "session"]:
                    result.app_name = sessions_appname_dict.get(
                        result.session_id[0], result.app_name
                    )

                metric_results[f"{aggregation_level}_metrics"].append(result)

        return metric_results
