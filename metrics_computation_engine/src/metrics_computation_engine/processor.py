# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import Any, Dict

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.session import SessionEntity
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
        self.semaphore = asyncio.Semaphore(10)

    async def _safe_compute(self, metric: BaseMetric, data: Any) -> MetricResult:
        """Safely compute metric with error handling"""
        async with self.semaphore:
            try:
                result = await metric.compute(data)
                return result
            except Exception as e:
                # Return error result instead of crashing
                return MetricResult(
                    metric_name=metric.name,
                    value=-1,
                    error_message=str(e),
                    aggregation_level=metric.aggregation_level,
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
                conversation_text = attr_value.get("conversation", "")
                if not conversation_text or len(conversation_text) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `conversation` is empty"
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
            elif param == "user_input":
                if not attr_value or len(str(attr_value)) == 0:
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `user_input` is empty"
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
                if not isinstance(attr_value, list):
                    logger.info(
                        f"{metric_name} invalid for session {session_entity.session_id}! `agent_transition_counts` is empty"
                    )
                    return False
                if len(attr_value) == 0:
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
        self, sessions_data: Dict[str, SessionEntity]
    ) -> Dict[str, Any]:
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

        for session_id, session_entity in sessions_data.items():
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
                        tasks.append(self._safe_compute(metric_instance, span))

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
                    # Pass the SessionEntity directly to session-level metrics
                    tasks.append(self._safe_compute(metric_instance, session_entity))

        # Population-level metrics: pass all sessions data
        for metric_name in self.registry.list_metrics():
            metric_class = self.registry.get_metric(metric_name)
            metric_instance = await self._initialize_metric(metric_name, metric_class)

            if (
                metric_instance is not None
                and metric_instance.aggregation_level == "population"
            ):
                # Pass the entire sessions_data dict for population metrics
                tasks.append(self._safe_compute(metric_instance, sessions_data))

        # Execute all tasks concurrently
        if tasks:
            results = await asyncio.gather(*tasks)

            # Organize results by aggregation level
            for result in results:
                if result.value == -1 and not result.success:
                    continue

                aggregation_level = result.aggregation_level
                metric_results[f"{aggregation_level}_metrics"].append(result)

        return metric_results
