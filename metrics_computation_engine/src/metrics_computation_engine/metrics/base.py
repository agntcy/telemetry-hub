# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.llm_judge.jury import Jury
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.types import AggregationLevel


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
        reasoning: str = "",
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
            span_id=span_ids or [],
            session_id=session_ids or [],
            source="native",
            entities_involved=[],
            edges_involved=[],
            success=True,
            metadata={"metric_type": "llm-as-a-judge"},
            error_message=None,
            reasoning=reasoning,
        )

    def _create_error_result(
        self,
        error_message: str = "Computation failed",
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
            span_id=span_ids or [],
            session_id=session_ids or [],
            source="native",
            entities_involved=[],
            edges_involved=[],
            success=False,
            metadata={"metric_type": "llm-as-a-judge"},
            error_message=error_message,
        )

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
