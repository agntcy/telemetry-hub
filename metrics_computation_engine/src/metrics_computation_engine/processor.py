# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import asyncio
import inspect
import json
import traceback
from typing import Any, Dict, List, Optional, Union

from metrics_computation_engine.constants import BINARY_GRADING_LABELS, DEEPEVAL_METRICS
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
        include_stack_trace: bool = False,
        include_unmatched_spans: bool = False,
        reorg_by_entity: bool = False,
    ):
        self.registry = registry
        self._metric_instances: Dict[str, BaseMetric] = {}
        self._jury = None
        self.dataset = dataset
        self.llm_config = llm_config
        self.model_handler = model_handler
        self.include_stack_trace = include_stack_trace
        self.include_unmatched_spans = include_unmatched_spans
        self.reorg_by_entity = reorg_by_entity
        # Cache for introspection results
        self._context_support_cache: Dict[str, bool] = {}
        # Track unmatched spans per metric
        self._unmatched_spans: List[Dict[str, Any]] = []

    def _format_error_message(self, exception: Exception) -> str:
        """Format error message, optionally including stack trace."""
        error_msg = str(exception)
        if self.include_stack_trace:
            full_traceback = traceback.format_exc()
            return f"{error_msg}\n\nStack trace:\n{full_traceback}"
        return error_msg

    def _record_unmatched_span(
        self,
        metric_name: str,
        aggregation_level: str,
        entity_id: str,
        entity_type: str,
        session_id: str,
        skip_reason: str,
        skip_category: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an unmatched span for tracking purposes."""
        if not self.include_unmatched_spans:
            return

        self._unmatched_spans.append(
            {
                "metric_name": metric_name,
                "aggregation_level": aggregation_level,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "session_id": session_id,
                "skip_reason": skip_reason,
                "skip_category": skip_category,  # "entity_type_mismatch", "requirement_not_met", "computation_failed"
                "details": details or {},
            }
        )

    def _metric_supports_context(self, metric: BaseMetric) -> bool:
        """Check if metric's compute method accepts **kwargs (cached)"""
        metric_class_name = metric.__class__.__name__

        if metric_class_name not in self._context_support_cache:
            signature = inspect.signature(metric.compute)

            self._context_support_cache[metric_class_name] = any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in signature.parameters.values()
            )

        return self._context_support_cache[metric_class_name]

    def _metric_supports_agent_computation(self, metric: BaseMetric) -> bool:
        """Check if metric supports agent-level computation"""
        return (
            hasattr(metric, "supports_agent_computation")
            and metric.supports_agent_computation()
        )

    def _assign_metric_label(self, result: MetricResult) -> None:
        """Assign a human-readable label to BinaryGrading metric results."""

        if not result:
            return

        metric_name = (result.metric_name or "").strip()

        print(f"Metric name: {metric_name}")
        metadata = result.metadata or {}
        if not isinstance(metadata, dict):
            metadata = {}

        if metric_name == "Sentiment":
            sentiment_keys = {k: metadata.get(k) for k in ("neg", "neu", "pos")}
            numeric_scores = {
                key: float(value)
                for key, value in sentiment_keys.items()
                if isinstance(value, (int, float))
            }

            if not numeric_scores:
                return

            max_score = max(numeric_scores.values())
            top_keys = [
                key for key, score in numeric_scores.items() if score == max_score
            ]
            label_key = top_keys[0]
            result.label = label_key
            return

        label_map = BINARY_GRADING_LABELS.get(metric_name)
        if label_map is None:
            logger.warning(f"No label map found for metric {metric_name}")
            return

        eval_value = result.value
        if metric_name in DEEPEVAL_METRICS:
            threshold_value = metadata.get("threshold")
            if threshold_value is not None:
                value_key = 1 if float(eval_value) >= float(threshold_value) else 0
        else:
            value_key = 1 if float(eval_value) >= 0.5 else 0

        label = label_map.get(value_key)
        if label:
            result.label = label

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
                error_message=self._format_error_message(e),
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
    ) -> tuple[bool, Optional[str]]:
        """
        Check if session entity has all required parameters for a metric.

        Returns:
            tuple: (is_valid, skip_reason)
        """
        missing = []
        present = {}

        for param in required_params:
            value = getattr(session_entity, param, None)

            # Special case: conversation_data needs to check nested elements
            if param == "conversation_data" and isinstance(value, dict):
                if not value.get("elements"):
                    missing.append(f"{param}.elements")
                    continue

            if not value:
                missing.append(param)
            else:
                present[param] = value

        if missing:
            present_str = ", ".join(present.keys()) if present else "none"
            reason = f"Missing/empty required params: [{', '.join(missing)}]. Present: [{present_str}]"
            logger.info(
                f"{metric_name} invalid for session {session_entity.session_id}: {reason}"
            )
            return (False, reason)

        return (True, None)

    def _get_metric_requirements(self, metric_class, metric_name: str) -> list:
        """Get required parameters from class without instantiation"""
        required_params_dict = getattr(metric_class, "REQUIRED_PARAMETERS", {})

        if isinstance(required_params_dict, dict):
            return required_params_dict.get(metric_name, [])

        return []

    def _deduplicate_failures(self, failures):
        seen = set()
        deduplicated = []

        for failure in failures:
            try:
                key = json.dumps(failure, sort_keys=True, default=str)
            except TypeError:
                key = str(failure)

            if key not in seen:
                seen.add(key)
                deduplicated.append(failure)

        return deduplicated

    def _reorganize_results_by_entity(
        self, metric_results: Dict[str, List], unmatched_spans: List[Dict]
    ) -> Dict[str, List]:
        """
        Reorganize results to group by entity (span_id, session_id, agent_id, population_id).

        Each entity will have:
        - evaluated_metrics: List of successful metric results
        - failed_metrics: List of metrics that failed during evaluation
        - skipped_metrics: List of metrics that were skipped
        """
        from collections import defaultdict

        # Group span metrics by span_id
        span_groups = defaultdict(
            lambda: {
                "span_id": None,
                "session_id": None,
                "app_name": None,
                "evaluated_metrics": [],
                "failed_metrics": [],
                "skipped_metrics": [],
            }
        )

        for result in metric_results.get("span_metrics", []):
            span_id = result.span_id[0] if result.span_id else "unknown"
            span_groups[span_id]["span_id"] = span_id
            span_groups[span_id]["session_id"] = (
                result.session_id[0] if result.session_id else None
            )
            span_groups[span_id]["app_name"] = result.app_name
            span_groups[span_id]["evaluated_metrics"].append(result)

        # Group session metrics by session_id
        session_groups = defaultdict(
            lambda: {
                "session_id": None,
                "app_name": None,
                "evaluated_metrics": [],
                "failed_metrics": [],
                "skipped_metrics": [],
            }
        )

        for result in metric_results.get("session_metrics", []):
            session_id = result.session_id[0] if result.session_id else "unknown"
            session_groups[session_id]["session_id"] = session_id
            session_groups[session_id]["app_name"] = result.app_name
            session_groups[session_id]["evaluated_metrics"].append(result)

        # Group agent metrics by agent_id
        agent_groups = defaultdict(
            lambda: {
                "agent_id": None,
                "session_id": None,
                "app_name": None,
                "evaluated_metrics": [],
                "failed_metrics": [],
                "skipped_metrics": [],
            }
        )

        for result in metric_results.get("agent_metrics", []):
            agent_id = (
                result.metadata.get("agent_id", "unknown")
                if result.metadata
                else "unknown"
            )
            agent_groups[agent_id]["agent_id"] = agent_id
            agent_groups[agent_id]["session_id"] = (
                result.session_id[0] if result.session_id else None
            )
            agent_groups[agent_id]["app_name"] = result.app_name
            agent_groups[agent_id]["evaluated_metrics"].append(result)

        # Group population metrics (typically one group)
        population_groups = defaultdict(
            lambda: {
                "population_id": "all",
                "evaluated_metrics": [],
                "failed_metrics": [],
                "skipped_metrics": [],
            }
        )

        for result in metric_results.get("population_metrics", []):
            population_groups["all"]["evaluated_metrics"].append(result)

        # Distribute failed_metrics to their respective entities
        for failure in metric_results.get("failed_metrics", []):
            agg_level = failure.get("aggregation_level", "unknown")

            if agg_level == "span":
                # span_id can be a string or list
                raw_span_id = failure.get("span_id", "unknown")
                span_id = (
                    raw_span_id[0] if isinstance(raw_span_id, list) else raw_span_id
                )
                if span_id not in span_groups:
                    span_groups[span_id]["span_id"] = span_id
                    raw_session = failure.get("session_id")
                    span_groups[span_id]["session_id"] = (
                        raw_session[0]
                        if isinstance(raw_session, list) and raw_session
                        else raw_session
                    )
                    raw_app = failure.get("app_name")
                    span_groups[span_id]["app_name"] = (
                        raw_app[0]
                        if isinstance(raw_app, list) and raw_app
                        else (raw_app or "unknown")
                    )
                span_groups[span_id]["failed_metrics"].append(failure)

            elif agg_level == "session":
                raw_session_id = failure.get("session_id", "unknown")
                session_id = (
                    raw_session_id[0]
                    if isinstance(raw_session_id, list) and raw_session_id
                    else raw_session_id
                )
                if session_id not in session_groups:
                    session_groups[session_id]["session_id"] = session_id
                    raw_app = failure.get("app_name")
                    session_groups[session_id]["app_name"] = (
                        raw_app[0]
                        if isinstance(raw_app, list) and raw_app
                        else (raw_app or "unknown")
                    )
                session_groups[session_id]["failed_metrics"].append(failure)

            elif agg_level == "agent":
                agent_id = failure.get("metadata", {}).get("agent_id", "unknown")
                if agent_id not in agent_groups:
                    agent_groups[agent_id]["agent_id"] = agent_id
                agent_groups[agent_id]["failed_metrics"].append(failure)

            else:
                population_groups["all"]["failed_metrics"].append(failure)

        # Distribute skipped/unmatched spans to their respective entities
        for skipped in unmatched_spans:
            agg_level = skipped.get("aggregation_level", "unknown")

            if agg_level == "span":
                span_id = skipped.get("entity_id", "unknown")
                if span_id not in span_groups:
                    span_groups[span_id]["span_id"] = span_id
                    span_groups[span_id]["session_id"] = skipped.get("session_id")
                    span_groups[span_id]["app_name"] = skipped.get("details", {}).get(
                        "app_name", "unknown"
                    )
                span_groups[span_id]["skipped_metrics"].append(skipped)

            elif agg_level == "session":
                session_id = skipped.get("session_id", "unknown")
                if session_id not in session_groups:
                    session_groups[session_id]["session_id"] = session_id
                    session_groups[session_id]["app_name"] = skipped.get(
                        "details", {}
                    ).get("app_name", "unknown")
                session_groups[session_id]["skipped_metrics"].append(skipped)

            elif agg_level == "agent":
                session_id = skipped.get("session_id", "unknown")
                if session_id not in agent_groups:
                    agent_groups[session_id]["agent_id"] = session_id
                agent_groups[session_id]["skipped_metrics"].append(skipped)

        return {
            "span_metrics": list(span_groups.values()),
            "session_metrics": list(session_groups.values()),
            "agent_metrics": list(agent_groups.values()),
            "population_metrics": list(population_groups.values())
            if population_groups["all"]["evaluated_metrics"]
            or population_groups["all"]["failed_metrics"]
            else [],
        }

    def _is_span_valid(self, span: Any) -> tuple[bool, Optional[str]]:
        """
        Check if span has required basic attributes.

        Returns:
            tuple: (is_valid, reason) - reason is set if invalid
        """
        if not getattr(span, "span_id", None):
            return False, "Missing span_id"
        # Note: session_id is Optional in SpanEntity, so we don't require it here
        if not getattr(span, "entity_type", None):
            return False, "Missing entity_type"
        return True, None

    def _get_matching_metrics_for_span(
        self, span: Any, span_metrics: List[tuple]
    ) -> List[tuple]:
        """
        Get list of metrics that match this span's entity type.

        Returns:
            List of (metric_name, metric_class) tuples that match the span
        """
        matching = []
        span_entity_type = getattr(span, "entity_type", None)

        for metric_name, metric_class in span_metrics:
            # Get required entity types for this metric
            required_types = []
            if hasattr(metric_class, "required"):
                required_types = metric_class.required.get("entity_type", [])
            else:
                # Need to instantiate to check
                temp_instance = metric_class(metric_name)
                if hasattr(temp_instance, "required"):
                    required_types = temp_instance.required.get("entity_type", [])

            if span_entity_type in required_types:
                matching.append((metric_name, metric_class))

        return matching

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
            "failed_metrics": [],
        }

        # Clear unmatched spans tracking for this computation
        self._unmatched_spans = []

        for session_index, session_entity in enumerate(
            sessions_set.sessions
        ):  # browse by SessionEntity
            # Span-level metrics: iterate through spans in the session
            for span in session_entity.spans:
                # 1. Check if span is valid (has required basic fields)
                is_valid, invalid_reason = self._is_span_valid(span)
                if not is_valid:
                    self._record_unmatched_span(
                        metric_name="ALL",
                        aggregation_level="span",
                        entity_id=getattr(span, "span_id", "unknown"),
                        entity_type=getattr(span, "entity_type", "unknown"),
                        session_id=session_entity.session_id,
                        skip_reason=invalid_reason,
                        skip_category="invalid_span",
                        details={"app_name": getattr(span, "app_name", "unknown")},
                    )
                    continue

                # 2. Find which metrics match this span
                matching_metrics = self._get_matching_metrics_for_span(
                    span, classified_metrics["span"]
                )

                # 3. If no metrics match, record as no_matching_metrics
                if not matching_metrics:
                    all_required_types = []
                    for _, mc in classified_metrics["span"]:
                        if hasattr(mc, "required"):
                            all_required_types.extend(
                                mc.required.get("entity_type", [])
                            )

                    self._record_unmatched_span(
                        metric_name="ALL",
                        aggregation_level="span",
                        entity_id=span.span_id,
                        entity_type=span.entity_type,
                        session_id=session_entity.session_id,
                        skip_reason=f"Span entity type '{span.entity_type}' does not match any requested metric",
                        skip_category="no_matching_metrics",
                        details={
                            "app_name": span.app_name,
                            "requested_metrics_require": list(set(all_required_types)),
                        },
                    )
                    continue

                # 4. Process matching metrics
                for metric_name, metric_class in matching_metrics:
                    try:
                        metric_instance = await self._initialize_metric(
                            metric_name, metric_class
                        )

                        if metric_instance is not None:
                            span_context = {
                                "include_stack_trace": self.include_stack_trace,
                            }
                            tasks.append(
                                self._safe_compute(
                                    metric_instance, span, context=span_context
                                )
                            )

                    except Exception as e:
                        metric_results["failed_metrics"].append(
                            {
                                "metric_name": metric_name,
                                "aggregation_level": "span",
                                "session_id": [session_entity.session_id],
                                "span_id": span.span_id,
                                "app_name": [span.app_name],
                                "error_message": self._format_error_message(e),
                                "metadata": {},
                            }
                        )
                        continue

            # Session-level metrics: pass the SessionEntity directly
            if "session" in computation_levels:
                for metric_name, metric_class in classified_metrics["session"]:
                    logger.info(f"METRIC NAME (session level): {metric_name}")
                    required_params = self._get_metric_requirements(
                        metric_class, metric_name
                    )
                    logger.info(f"REQUIRED PARAMS: {required_params}")

                    is_valid, skip_reason = self._check_session_requirements(
                        metric_name, session_entity, required_params
                    )
                    if not is_valid:
                        self._record_unmatched_span(
                            metric_name=metric_name,
                            aggregation_level="session",
                            entity_id=session_entity.session_id,
                            entity_type="session",
                            session_id=session_entity.session_id,
                            skip_reason=skip_reason,
                            skip_category="requirement_not_met",
                            details={
                                "app_name": session_entity.app_name,
                                "required_params": required_params,
                            },
                        )
                        continue

                    try:
                        metric_instance = await self._initialize_metric(
                            metric_name, metric_class
                        )
                    except Exception as e:
                        metric_results["failed_metrics"].append(
                            {
                                "metric_name": metric_name,
                                "aggregation_level": "session",
                                "session_id": [session_entity.session_id],
                                "span_id": None,
                                "app_name": [session_entity.app_name],
                                "error_message": self._format_error_message(e),
                                "metadata": {},
                            }
                        )
                        continue

                    if metric_instance is not None:
                        # Prepare context for metrics that need it
                        context = {
                            "include_stack_trace": self.include_stack_trace,
                        }
                        if sessions_set is not None:
                            context.update(
                                {
                                    "session_set_stats": sessions_set.stats,
                                    "session_index": session_index,
                                    "session_set": sessions_set,
                                }
                            )
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
                    is_valid, skip_reason = self._check_session_requirements(
                        metric_name, session_entity, required_params
                    )
                    if not is_valid:
                        logger.debug(
                            f"Session doesn't meet requirements for {metric_name}"
                        )
                        self._record_unmatched_span(
                            metric_name=metric_name,
                            aggregation_level="agent",
                            entity_id=session_entity.session_id,
                            entity_type="session",
                            session_id=session_entity.session_id,
                            skip_reason=skip_reason,
                            skip_category="requirement_not_met",
                            details={
                                "app_name": session_entity.app_name,
                                "required_params": required_params,
                            },
                        )
                        continue
                    logger.info(f"REQUIRED PARAMS: {required_params}")
                    # Initialize the metric
                    metric_instance = await self._initialize_metric(
                        metric_name, metric_class
                    )

                    if metric_instance is not None:
                        # Prepare context with agent computation flag
                        context = {
                            "include_stack_trace": self.include_stack_trace,
                            "agent_computation": True,
                        }
                        if sessions_set is not None:
                            context.update(
                                {
                                    "session_set_stats": sessions_set.stats,
                                    "session_index": session_index,
                                    "session_set": sessions_set,
                                }
                            )
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
            try:
                metric_instance = await self._initialize_metric(
                    metric_name, metric_class
                )
            except Exception as e:
                metric_results["failed_metrics"].append(
                    {
                        "metric_name": metric_name,
                        "aggregation_level": "unknown",
                        "session_id": [
                            session_entity.session_id
                            for session_entity in sessions_set.sessions
                        ],
                        "span_id": None,
                        "app_name": list(
                            set(
                                [
                                    session_entity.app_name
                                    for session_entity in sessions_set.sessions
                                ]
                            )
                        ),
                        "error_message": self._format_error_message(e),
                        "metadata": {},
                    }
                )
                continue

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
                    metric_results["failed_metrics"].append(
                        {
                            "metric_name": raw_result.metric_name,
                            "aggregation_level": raw_result.aggregation_level,
                            "error_message": raw_result.error_message
                            or "Metric returned none value.",
                            "metadata": raw_result.metadata,
                            "session_id": raw_result.session_id,
                            "span_id": raw_result.span_id,
                            "app_name": raw_result.app_name,
                        }
                    )
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
                    metric_results["failed_metrics"].append(
                        {
                            "metric_name": result.metric_name,
                            "aggregation_level": result.aggregation_level,
                            "error_message": result.error_message
                            or "Metric returned none value.",
                            "session_id": result.session_id,
                            "span_id": result.span_id,
                            "app_name": result.app_name,
                            "metadata": result.metadata,
                        }
                    )
                    continue
                if (result.value == -1 or result.value == {}) and not result.success:
                    metric_results["failed_metrics"].append(
                        {
                            "metric_name": result.metric_name,
                            "aggregation_level": result.aggregation_level,
                            "error_message": result.error_message
                            or "Metric returned unsuccessful result",
                            "session_id": result.session_id,
                            "span_id": result.span_id,
                            "app_name": result.app_name,
                            "metadata": result.metadata,
                        }
                    )
                    continue
                self._assign_metric_label(result)
                aggregation_level = result.aggregation_level
                if aggregation_level in ["span", "session", "agent"]:
                    result.app_name = sessions_appname_dict.get(
                        result.session_id[0], result.app_name
                    )

                metric_results[f"{aggregation_level}_metrics"].append(result)

        metric_results["failed_metrics"] = self._deduplicate_failures(
            metric_results["failed_metrics"]
        )

        # Optionally reorganize results to group by entity
        if self.reorg_by_entity:
            return self._reorganize_results_by_entity(
                metric_results,
                self._unmatched_spans if self.include_unmatched_spans else [],
            )

        # Default: return flat structure with optional unmatched_spans
        if self.include_unmatched_spans:
            metric_results["unmatched_spans"] = self._unmatched_spans

        return metric_results
