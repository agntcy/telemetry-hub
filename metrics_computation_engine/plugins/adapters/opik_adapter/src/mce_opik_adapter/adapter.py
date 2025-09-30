from typing import Tuple, Any, Dict, List
import importlib

from opik.evaluation.metrics import score_result

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.types import AggregationLevel
from metrics_computation_engine.models.requests import LLMJudgeConfig

from .model_loader import (
    MODEL_PROVIDER_NAME,
    load_model,
)
from .metric_configuration import MetricConfiguration, build_metric_configuration_map


class OpikMetricAdapter(BaseMetric):
    """
    Adapter to integrate Opik metrics as 3rd party plugins into the MCE.
    """

    def __init__(self, opik_metric_name: str):
        super().__init__()

        metric_configuration_map: Dict[str, MetricConfiguration] = (
            build_metric_configuration_map()
        )

        if opik_metric_name not in metric_configuration_map:
            supported_metrics = sorted(metric_configuration_map.keys())
            raise ValueError(
                f"Supported metrics are {supported_metrics},"
                f" but `{opik_metric_name}` was given."
            )

        self.opik_metric_name = opik_metric_name
        self.name = opik_metric_name
        self.opik_metric = None
        self.model = None

        # Use configuration from centralized system
        self.metric_configuration: MetricConfiguration = metric_configuration_map[
            opik_metric_name
        ]
        self.aggregation_level: AggregationLevel = (
            self.metric_configuration.requirements.aggregation_level
        )
        self.required = {
            "entity_type": self.metric_configuration.requirements.entity_type
        }

    def get_model_provider(self):
        return MODEL_PROVIDER_NAME

    @classmethod
    def get_requirements(cls, metric_name: str) -> List[str]:
        """Get required parameters from centralized configuration"""
        from .metric_configuration import build_metric_configuration_map

        try:
            config_map = build_metric_configuration_map()
            if metric_name in config_map:
                return config_map[metric_name].requirements.required_input_parameters
            return []
        except Exception:
            return []

    def init_with_model(self, model: Any) -> bool:
        self.model = model
        # Load the opik metric with model
        try:
            module = importlib.import_module("opik.evaluation.metrics")
            opik_metric_cls = getattr(module, self.opik_metric_name, None)
            if opik_metric_cls is None:
                return False
            if "heuristics" in str(opik_metric_cls):
                self.type = "heuristics"
                self.opik_metric = opik_metric_cls()
            else:
                self.opik_metric = opik_metric_cls(model=model)
            return True
        except Exception:
            return False

    def create_model(self, llm_config: LLMJudgeConfig) -> Any:
        return load_model(llm_config)

    @property
    def required_parameters(self):
        """Map Opik required params to your framework's format"""
        # Opik metrics don't typically expose required params the same way
        # Return empty list or implement based on specific metric needs
        return getattr(self.opik_metric, "_required_params", [])

    def validate_config(self) -> bool:
        """Validate the Opik metric configuration"""
        try:
            # Basic validation - check if metric has required methods
            return hasattr(self.opik_metric, "score") or hasattr(
                self.opik_metric, "ascore"
            )
        except Exception:
            return False

    async def _assess_input_data(self, data: SpanEntity) -> Tuple[bool, str, str, str]:
        data_is_appropriate: bool = True
        error_message: str = ""
        span_id: str = ""
        session_id: str = ""

        if isinstance(data, SpanEntity):
            span_id = data.span_id
            session_id = data.session_id
            if data.entity_type not in self.required["entity_type"]:
                data_is_appropriate = False
                error_message = "Entity type must be one of " + ", ".join(
                    self.required["entity_type"]
                )
            elif not (data.input_payload and data.output_payload and data.entity_name):
                data_is_appropriate = False
                error_message = (
                    "Entity must have all following attributes :"
                    " 'input_payload', 'output_payload' and 'entity_name'"
                )
        else:
            data_is_appropriate = False
            error_message = "data must be of type 'SpanEntity'"

        return data_is_appropriate, error_message, span_id, session_id

    async def compute(self, data) -> MetricResult:
        """
        Compute the metric using Opik's interface and return in your framework's format
        """
        (
            data_is_appropriate,
            error_message,
            span_id,
            session_id,
        ) = await self._assess_input_data(data=data)

        if not data_is_appropriate:
            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                category="agent",
                app_name=data.app_name,
                span_id=[span_id],
                session_id=[session_id],
                source="opik",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=error_message,
            )

        try:
            # Extract parameters for Opik metric using centralized test case calculator
            test_case_calculator = self.metric_configuration.test_case_calculator
            opik_params = test_case_calculator.calculate_test_case(data)

            # Use async version if available, otherwise fallback to sync
            if hasattr(self.opik_metric, "ascore"):
                result: score_result.ScoreResult = await self.opik_metric.ascore(
                    **opik_params
                )
            else:
                if self.type == "heuristics":
                    result: score_result.ScoreResult = self.opik_metric.score(
                        output=opik_params["output"]
                    )
                else:
                    result: score_result.ScoreResult = self.opik_metric.score(
                        **opik_params
                    )

            # Extract metadata from the result
            metadata = {
                "opik_name": getattr(self.opik_metric, "name", None),
                "opik_tracking": getattr(self.opik_metric, "_track", None),
                "opik_project": getattr(self.opik_metric, "_project_name", None),
                "threshold": getattr(self.opik_metric, "threshold", None),
            }

            # Add any additional metadata from the result
            if hasattr(result, "metadata") and result.metadata:
                metadata.update(result.metadata)

            # Filter out None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            return MetricResult(
                metric_name=self.name,
                description="",
                value=result.value,
                reasoning=getattr(result, "reason", ""),
                unit="",
                aggregation_level="span",
                category="agent",
                app_name=data.app_name,
                span_id=[span_id],
                session_id=[session_id],
                source="opik",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata=metadata,
                error_message=None,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                category="agent",
                app_name=data.app_name,
                span_id=[span_id],
                session_id=[session_id],
                source="opik",
                entities_involved=[],
                edges_involved=[],
                metadata={},
                success=False,
                error_message=str(e),
            )
