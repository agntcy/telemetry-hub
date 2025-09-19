from typing import Tuple, Any
import importlib

from opik.evaluation.metrics import score_result

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.types import AggregationLevel
from metrics_computation_engine.models.requests import LLMJudgeConfig

from .model_loader import (
    MODEL_PROVIDER_NAME,
    load_model,
)


class OpikMetricAdapter(BaseMetric):
    """
    Adapter to integrate Opik metrics as 3rd party plugins into the MCE.
    """

    REQUIRED_PARAMETERS = {
        "Hallucination": ["input_payload", "output_payload"],
        "Sentiment": ["output_payload"],
    }

    def __init__(self, opik_metric_name: str):
        super().__init__()
        self.opik_metric_name = opik_metric_name
        self.name = opik_metric_name
        self.opik_metric = None
        self.aggregation_level: AggregationLevel = "span"
        self.model = None
        self.required = {"entity_type": ["llm"]}
        self.type = "judge"

    def get_model_provider(self):
        return MODEL_PROVIDER_NAME

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

    def extract_opik_parameters(self, data: SpanEntity) -> dict:
        """
        Extract parameters from SpanEntity and map them to Opik metric requirements.
        This method should be customized based on your data structure and the specific
        Opik metric being used.
        """
        # Basic extraction - you may need to customize this based on your data format
        params = {}

        # Most Opik metrics expect these basic parameters
        if hasattr(data, "input_payload") and data.input_payload:
            if isinstance(data.input_payload, str):
                params["input"] = data.input_payload
            elif isinstance(data.input_payload, dict):
                # Try to extract input from common keys
                params["input"] = str(data.input_payload)
            else:
                params["input"] = str(data.input_payload)

        if hasattr(data, "output_payload") and data.output_payload:
            if isinstance(data.output_payload, str):
                params["output"] = data.output_payload
            elif isinstance(data.output_payload, dict):
                # Try to extract output from common keys
                params["output"] = str(data.output_payload)
            else:
                params["output"] = str(data.output_payload)

        # For metrics that need context (like Hallucination)
        if hasattr(data, "context") and data.context:
            params["context"] = (
                data.context if isinstance(data.context, list) else [str(data.context)]
            )

        # For metrics that need expected output
        if hasattr(data, "expected_output") and data.expected_output:
            params["expected_output"] = str(data.expected_output)

        return params

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
            # Extract parameters for Opik metric
            opik_params = self.extract_opik_parameters(data)

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
