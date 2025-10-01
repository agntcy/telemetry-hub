# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.llm_judge.jury import Jury
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.types import AggregationLevel
from metrics_computation_engine.dal.api_client import get_api_client
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

DEFAULT_PROVIDER = "NATIVE"


class BaseMetric(ABC):
    """Base class for generic metric"""

    def __init__(self, jury: Optional[Jury] = None, dataset: Optional[Dict] = None):
        self.jury = jury
        self.dataset = dataset
        self.name: str = ""  # Set by concrete implementations
        self.aggregation_level: AggregationLevel  # Set by concrete implementations

    @abstractmethod
    async def compute(self, data: Any):
        """Compute the metric for given data"""
        pass

    @abstractmethod
    def init_with_model(self, model: Any) -> bool:
        """Set the model that will be used by the metric"""
        pass

    @abstractmethod
    def get_model_provider(self) -> Optional[str]:
        """Return the model provider, if a model is needed by the metric"""
        pass

    @abstractmethod
    def create_model(self, llm_config: LLMJudgeConfig) -> Any:
        """Create the LLM model handler for the metric, using the config passed"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the plugin configuration"""
        pass

    @property
    @abstractmethod
    def required_parameters(self) -> List[str]:
        """Return list of required parameters for this metric"""
        pass

    def _create_success_result(
        self,
        score: float,
        category: str,
        app_name: str,
        reasoning: str = "",
        entities_involved: Optional[List[str]] = None,
        span_ids: Optional[List[str]] = None,
        session_ids: Optional[List[str]] = None,
    ) -> MetricResult:
        """
        Create a successful MetricResult for LLM-as-a-judge metrics.

        Args:
            score: Computed score
            reasoning: LLM reasoning for the score
            span_ids: List of span IDs involved in the computation
            session_ids: List of session IDs involved in the computation

        Returns:
            MetricResult object for success case
        """
        return MetricResult(
            metric_name=self.name,
            description="",
            value=score,
            unit="",
            aggregation_level=self.aggregation_level,
            category=category,
            app_name=app_name,
            span_id=span_ids or [],
            session_id=session_ids or [],
            source="native",
            entities_involved=entities_involved,
            edges_involved=[],
            success=True,
            metadata={"metric_type": "llm-as-a-judge"},
            error_message=None,
            reasoning=reasoning,
        )

    def _create_error_result(
        self,
        category: str,
        app_name: str,
        error_message: str = "Computation failed",
        entities_involved: Optional[List[str]] = None,
        span_ids: Optional[List[str]] = None,
        session_ids: Optional[List[str]] = None,
    ) -> MetricResult:
        """
        Create an error MetricResult for when computation fails.

        Args:
            error_message: Descriptive error message
            span_ids: List of span IDs involved in the computation
            session_ids: List of session IDs involved in the computation

        Returns:
            MetricResult object for error case
        """
        return MetricResult(
            metric_name=self.name,
            description="",
            value=-1.0,
            reasoning="",
            unit="",
            aggregation_level=self.aggregation_level,
            category=category,
            app_name=app_name,
            span_id=span_ids or [],
            session_id=session_ids or [],
            source="native",
            entities_involved=entities_involved,
            edges_involved=[],
            success=False,
            metadata={"metric_type": "llm-as-a-judge"},
            error_message=error_message,
        )

    def get_cache_metric(
        self, data: Any, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a cache key for this metric computation.

        Override this method in concrete metrics if you need custom cache key logic.
        Default implementation uses metric name + data hash.

        Args:
            data: The data being processed by the metric
            context: Optional context data

        Returns:
            A unique cache key string for this computation
        """
        import hashlib

        data_str = str(data) if data else ""
        context_str = str(context) if context else ""
        combined = f"{self.name}:{data_str}:{context_str}"
        return hashlib.md5(combined.encode()).hexdigest()

    async def check_cache_metric(
        self, metric_name: str, session_id: str
    ) -> Optional[MetricResult]:
        """Check if this metric result exists in cache/database.

        Returns the cached result if found, None otherwise.
        Only checks cache if METRICS_CACHE_ENABLED is True.

        Args:
            data: The data being processed by the metric
            context: Optional context data

        Returns:
            Cached MetricResult if found, None otherwise
        """

        def _check_metrics_conditions(
            list_of_json_objects: list, metric_name: str
        ) -> bool:
            """
            Analyzes a list of JSON objects to check if any object's 'metrics' attribute
            matches specific conditions.

            Used conditionally to decide whether to skip writing metrics for a session.
            Returns True if:
            - 'metrics.aggregation_level' is set AND
            - 'metrics.category' is set AND
            - 'metrics.name' is set

            Otherwise, returns False.

            Args:
                list_of_json_objects (list): A list of dictionaries (representing JSON objects).

            Returns:
                bool: True if any object meets the conditions, False otherwise.
                Dict: the metric read from db as a db dict
            """
            for obj in list_of_json_objects:
                if isinstance(obj, dict) and "metrics" in obj:
                    metrics = obj["metrics"]
                    # Parse JSON string if metrics is stored as string
                    if isinstance(metrics, str):
                        try:
                            import json

                            metrics = json.loads(metrics)
                        except (json.JSONDecodeError, TypeError):
                            continue

                    if isinstance(metrics, dict):
                        read_metric_name = metrics.get("metric_name", "")

                        # Condition
                        if metric_name == read_metric_name:
                            return True, obj
            return False, None

        # Check if caching is enabled
        if not os.getenv("METRICS_CACHE_ENABLED", "false").lower() == "true":
            return None

        # database retrieval here
        metrics = get_api_client().get_session_metrics(session_id=session_id)

        # cached metric
        is_cached_metric, metric = _check_metrics_conditions(metrics, metric_name)

        if is_cached_metric:
            metric_data = metric.get("metrics", {})

            # Parse JSON string if metrics is stored as string
            if isinstance(metric_data, str):
                try:
                    import json

                    metric_data = json.loads(metric_data)
                except (json.JSONDecodeError, TypeError):
                    return None

            metric_data["from_cache"] = True

            # Ensure required fields are present for backward compatibility with cached data
            if "category" not in metric_data:
                metric_data["category"] = "application"  # Default category
            if "app_name" not in metric_data:
                metric_data["app_name"] = "unknown"  # Default app_name

            return MetricResult(**metric_data)
        return None

    def get_default_provider(self) -> str:
        return DEFAULT_PROVIDER

    def get_provider_no_model_needed(self):
        return None

    def create_no_model(self, llm_config: LLMJudgeConfig):
        return None

    def create_native_model(self, llm_config: LLMJudgeConfig) -> Any:
        jury = Jury(llm_config.model_dump())
        return jury


class CustomBaseMetric(BaseMetric, ABC):
    """
    Simplified metric base: User only sets 'aggregation_level' as a class variable and implements 'compute'.
    """

    name: Optional[str] = None  # User must set this in the class definition
    aggregation_level: Optional[AggregationLevel] = (
        None  # User must set this in the class definition
    )

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        # Optionally check that subclass has defined aggregation_level
        if self.aggregation_level is None:
            raise ValueError(
                "aggregation_level must be set as a class variable in your metric subclass."
            )

    @property
    def required_parameters(self) -> List[str]:
        return []

    def validate_config(self) -> bool:
        return True

    @abstractmethod
    async def compute(self, data: Any):
        pass
