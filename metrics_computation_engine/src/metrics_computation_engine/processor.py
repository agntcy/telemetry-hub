# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import asyncio
import inspect
from typing import Any, Dict, List, Optional, Union

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
    ):
        self.registry = registry
        self._metric_instances: Dict[str, BaseMetric] = {}
        self._jury = None
        self.dataset = dataset
        self.llm_config = llm_config
        self.model_handler = model_handler
        # Cache for introspection results
        self._context_support_cache: Dict[str, bool] = {}

    def _metric_supports_context(self, metric: BaseMetric) -> bool:
        """Check if metric's compute method accepts context parameter (cached)"""
        metric_class_name = metric.__class__.__name__

        if metric_class_name not in self._context_support_cache:
            signature = inspect.signature(metric.compute)
            self._context_support_cache[metric_class_name] = (
                "context" in signature.parameters
            )

        return self._context_support_cache[metric_class_name]

    def _metric_supports_agent_computation(self, metric: BaseMetric) -> bool:
        """Check if metric supports agent-level computation"""
        return (
            hasattr(metric, "supports_agent_computation")
            and metric.supports_agent_computation()
        )

    async def _handle_agent_cache_and_compute(
        self, metric: BaseMetric, data: Any, context: Dict[str, Any]
    ) -> List[MetricResult]:
        """Handle caching and computation for agent-level metrics"""

        # Discover agents first - ensure execution_tree is available
        if not hasattr(data, "execution_tree") or data.execution_tree is None:
            from metrics_computation_engine.entities.models.execution_tree import (
                ExecutionTree,
            )

            data.execution_tree = ExecutionTree()

        agent_ids = list(data.agent_stats.keys()) if data.agent_stats else []

        if not agent_ids:
            logger.debug(
                f"No agents found for {metric.name} in session {data.session_id}"
            )
            return []  # No agents found

        logger.debug(f"Found {len(agent_ids)} agents for {metric.name}: {agent_ids}")

        # Try to get all agent results from cache at once
        cached_results = await metric.check_cache_metric(
            metric_name=metric.name,
            session_id=data.session_id,
            context=context,  # This will trigger _check_all_agents_cache
        )

        # Filter cached results to only include agents from current session
        if cached_results is not None:
            filtered_results = [
                result
                for result in cached_results
                if result.metadata.get("agent_id") in agent_ids
            ]

            if len(filtered_results) == len(agent_ids):
                # All agents cached
                logger.debug(
                    f"Cache hit for all {len(agent_ids)} agents of {metric.name}"
                )
                return filtered_results
            else:
                logger.debug(
                    f"Partial cache hit: {len(filtered_results)}/{len(agent_ids)} agents cached"
                )
                # For now, recompute all if not all cached (simpler logic)
                pass

        # Some or all agents missing from cache - compute all
        logger.debug(f"Cache miss for {metric.name} agents, computing...")

        if self._metric_supports_context(metric):
            new_results = await metric.compute_with_dispatch(data, **context)
        else:
            new_results = await metric.compute_with_dispatch(data)

        # Ensure we return a list
        if isinstance(new_results, list):
            return new_results
        else:
            return [new_results] if new_results else []

    async def _safe_compute(
        self, metric: BaseMetric, data: Any, context: Optional[Dict[str, Any]] = None
    ) -> Union[MetricResult, List[MetricResult]]:
        """Safely compute metric with error handling and cache checking"""
        try:
            # Check if this is agent computation
            is_agent_computation = context and context.get("agent_computation", False)

            if is_agent_computation and hasattr(data, "agent_stats"):
                # Agent computation - use agent-aware caching
                return await self._handle_agent_cache_and_compute(metric, data, context)

            # Regular session/span computation - existing logic
            cached_result = None

            if metric.aggregation_level in ["span", "session"]:
                cached_result = await metric.check_cache_metric(
                    metric_name=metric.name, session_id=data.session_id, context=context
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
                result = await metric.compute(data, **context)
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
            logger.warning(
                f"metric {metric_name} encountered an issue when initiating."
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

    def _classify_metrics_by_aggregation_level(self) -> Dict[str, List[tuple]]:
        """
        Pre-classify metrics by aggregation level to avoid repeated filtering.

        Returns:
            Dict mapping aggregation levels to list of (metric_name, metric_class) tuples
        """
        classified_metrics = {
            "span": [],
            "session": [],
            "agent": [],  # Session-level metrics that support agent computation
            "population": [],
        }

        for metric_name in self.registry.list_metrics():
            metric_class = self.registry.get_metric(metric_name)

            # Determine aggregation level
            if hasattr(metric_class, "aggregation_level"):
                agg_level = metric_class.aggregation_level
            else:
                # Need to instantiate to get aggregation level
                temp_instance = metric_class(metric_name)
                agg_level = temp_instance.aggregation_level

            # Add to appropriate category
            if agg_level == "span":
                classified_metrics["span"].append((metric_name, metric_class))
            elif agg_level == "session":
                classified_metrics["session"].append((metric_name, metric_class))

                # Also check if it supports agent computation
                temp_instance = metric_class(metric_name)
                if self._metric_supports_agent_computation(temp_instance):
                    classified_metrics["agent"].append((metric_name, metric_class))
            elif agg_level == "population":
                classified_metrics["population"].append((metric_name, metric_class))

        return classified_metrics

    async def compute_metrics(
        self, sessions_set: SessionSet, computation_levels: Optional[List[str]] = None
    ) -> Dict[str, List[MetricResult]]:
        """
        Compute multiple metrics concurrently using SessionEntity objects.

        Args:
            sessions_set: SessionSet containing SessionEntity objects
            computation_levels: List of computation levels to process (defaults to ["session"])
        """
        # Set default computation levels for backward compatibility
        if computation_levels is None:
            computation_levels = ["session"]

        # Pre-classify metrics by aggregation level for efficiency
        classified_metrics = self._classify_metrics_by_aggregation_level()
        logger.info(
            f"Classified metrics: {[(level, len(metrics)) for level, metrics in classified_metrics.items()]}"
        )

        tasks = []
        metric_results = {
            "span_metrics": [],
            "session_metrics": [],
            "agent_metrics": [],
            "population_metrics": [],
        }

        for session_index, session_entity in enumerate(
            sessions_set.sessions
        ):  # browse by SessionEntity
            # Span-level metrics: iterate through spans in the session
            for span in session_entity.spans:
                for metric_name, metric_class in classified_metrics["span"]:
                    # For entity filtering, we need a temp instance to check requirements
                    temp_instance = metric_class(metric_name)
                    if not self._should_compute_metric_for_span(temp_instance, span):
                        continue

                    # Only initialize if we're going to compute it
                    metric_instance = await self._initialize_metric(
                        metric_name, metric_class
                    )

                    if metric_instance is not None:
                        tasks.append(self._safe_compute(metric_instance, span))

            # Session-level metrics: pass the SessionEntity directly
            if "session" in computation_levels:
                for metric_name, metric_class in classified_metrics["session"]:
                    logger.info(f"METRIC NAME (session level): {metric_name}")
                    required_params = self._get_metric_requirements(
                        metric_class, metric_name
                    )
                    logger.info(f"REQUIRED PARAMS: {required_params}")

                    if not self._check_session_requirements(
                        metric_name, session_entity, required_params
                    ):
                        continue

                    metric_instance = await self._initialize_metric(
                        metric_name, metric_class
                    )

                    if metric_instance is not None:
                        # Prepare context for metrics that need it
                        context = None
                        if sessions_set is not None:
                            context = {
                                "session_set_stats": sessions_set.stats,
                                "session_index": session_index,
                                "session_set": sessions_set,
                            }
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug(
                                    f"Prepared context with keys: {list(context.keys())}"
                                )
                        # Pass the SessionEntity directly to session-level metrics
                        tasks.append(
                            self._safe_compute(
                                metric_instance, session_entity, context=context
                            )
                        )

            # Agent-level metrics: process session-level metrics that support agent computation
            if "agent" in computation_levels:
                logger.info(
                    f"Processing agent-level metrics for session {session_entity.session_id}"
                )

                for metric_name, metric_class in classified_metrics["agent"]:
                    logger.info(f"METRIC NAME (agent level): {metric_name}")
                    # Check requirements for the session
                    required_params = self._get_metric_requirements(
                        metric_class, metric_name
                    )
                    if not self._check_session_requirements(
                        metric_name, session_entity, required_params
                    ):
                        logger.debug(
                            f"Session doesn't meet requirements for {metric_name}"
                        )
                        continue
                    logger.info(f"REQUIRED PARAMS: {required_params}")
                    # Initialize the metric
                    metric_instance = await self._initialize_metric(
                        metric_name, metric_class
                    )

                    if metric_instance is not None:
                        # Prepare context with agent computation flag
                        context = None
                        if sessions_set is not None:
                            context = {
                                "session_set_stats": sessions_set.stats,
                                "session_index": session_index,
                                "session_set": sessions_set,
                                "agent_computation": True,
                            }
                            logger.debug(
                                f"Prepared context with agent computation flag for {metric_name}"
                            )

                        # Compute the metric with agent option
                        tasks.append(
                            self._safe_compute(
                                metric=metric_instance,
                                data=session_entity,
                                context=context,
                            )
                        )

        # Population-level metrics: pass all sessions data
        for metric_name, metric_class in classified_metrics["population"]:
            metric_instance = await self._initialize_metric(metric_name, metric_class)

            if metric_instance is not None:
                # Pass the entire sessions_data dict for population metrics
                tasks.append(self._safe_compute(metric_instance, sessions_set))

        # Execute all tasks concurrently
        if tasks:
            raw_results: List[
                Union[MetricResult, List[MetricResult]]
            ] = await asyncio.gather(*tasks)

            # mapping of session ids / app name
            sessions_appname_dict = {
                k: v for k, v in sessions_set.stats.meta.session_ids
            }
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"sessions_appname_dict: {sessions_appname_dict}")

            # Flatten results - handle both single results and lists of results
            flattened_results: List[MetricResult] = []
            for raw_result in raw_results:
                if raw_result is None:
                    logger.error("Got None result from metric computation - skipping")
                    continue

                # Handle both single results and lists of results
                if isinstance(raw_result, list):
                    # Multiple results (e.g., from agent-level computation)
                    flattened_results.extend(raw_result)
                else:
                    # Single result
                    flattened_results.append(raw_result)

            # Organize results by aggregation level
            for result in flattened_results:
                if result is None:
                    logger.error("Got None result from flattened results - skipping")
                    continue
                if (result.value == -1 or result.value == {}) and not result.success:
                    continue
                aggregation_level = result.aggregation_level
                if aggregation_level in ["span", "session", "agent"]:
                    result.app_name = sessions_appname_dict.get(
                        result.session_id[0], result.app_name
                    )

                metric_results[f"{aggregation_level}_metrics"].append(result)

        return metric_results
