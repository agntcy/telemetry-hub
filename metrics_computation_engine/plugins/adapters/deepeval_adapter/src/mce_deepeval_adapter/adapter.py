# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict, List, Tuple, Union

from metrics_computation_engine.logger import setup_logger
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.types import AggregationLevel

from .metric_configuration import MetricConfiguration, build_metric_configuration_map
from .model_loader import MODEL_PROVIDER_NAME, load_model

import os

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"

logger = setup_logger(__name__)


class DeepEvalMetricAdapter(BaseMetric):
    """
    Adapter to integrate DeepEval metrics as 3rd party plugins into the MCE.
    """

    def __init__(self, deepeval_metric_name: str):
        super().__init__()
        metric_configuration_map: Dict[str, MetricConfiguration] = (
            build_metric_configuration_map()
        )
        if deepeval_metric_name not in metric_configuration_map:
            supported_metrics = sorted(metric_configuration_map.keys())
            raise ValueError(
                f"Supported metrics are {supported_metrics},"
                f" but `{deepeval_metric_name}` was given."
            )
        self.name = deepeval_metric_name
        self.deepeval_metric = None
        self.model = None
        metric_configuration: MetricConfiguration = metric_configuration_map[
            deepeval_metric_name
        ]
        self.metric_configuration: MetricConfiguration = metric_configuration
        self.aggregation_level: AggregationLevel = (
            metric_configuration.requirements.aggregation_level
        )
        self.required = {"entity_type": metric_configuration.requirements.entity_type}

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
        try:
            self.model = model
            deepeval_metric_cls = self.metric_configuration.metric_class
            kwargs = dict()
            if self.metric_configuration.metric_class_arguments:
                kwargs.update(self.metric_configuration.metric_class_arguments)
            kwargs["model"] = model
            self.deepeval_metric = deepeval_metric_cls(**kwargs)
            return True
        except Exception as e:
            logger.warning(
                f"Error while calling init_with_model for metric {self.name}."
                f" Error: {e}"
            )
            return False

    def create_model(self, llm_config: LLMJudgeConfig) -> Any:
        return load_model(llm_config)

    @property
    def required_parameters(self):
        """Map DeepEval required params to your framework's format"""
        return getattr(self.deepeval_metric, "_required_params", [])

    def validate_config(self) -> bool:
        """Validate the DeepEval metric configuration"""
        try:
            # Basic validation - check if metric has required attributes
            return hasattr(self.deepeval_metric, "measure") or hasattr(
                self.deepeval_metric, "a_measure"
            )
        except Exception as e:
            logger.warning(
                f"Error while calling validate_config for metric {self.name}"
                f". Error: {e}"
            )
            return False

    def _check_span_required_params(self, data: SpanEntity) -> Tuple[bool, str]:
        """Check required span parameters and return (is_valid, error_message)."""
        missing = []
        present = {}

        # Check standard span attributes
        for param in ["input_payload", "output_payload", "entity_name"]:
            value = getattr(data, param, None)
            if not value:
                missing.append(param)
            else:
                present[param] = value

        if missing:
            present_str = (
                ", ".join(f"{k}={v}" for k, v in present.items()) if present else "none"
            )
            error_message = (
                f"Missing required attributes: [{', '.join(missing)}]. "
                f"Present: [{present_str}]"
            )
            return False, error_message

        return True, ""

    def _check_session_required_params(
        self, data: SessionEntity
    ) -> Tuple[bool, str]:
        """Check required session parameters and return (is_valid, error_message)."""
        # Check if session has at least one span with matching entity type
        required_types = self.required["entity_type"]
        has_matching_type = any(
            span.entity_type in required_types for span in data.spans
        )
        if not has_matching_type:
            return (
                False,
                f"Session must contain at least one entity of type {required_types}",
            )

        return True, ""

    async def _assess_input_data(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Tuple[bool, str, str, str]:
        span_id: str = ""
        session_id: str = ""

        # Handle single SpanEntity (span-level metrics)
        if isinstance(data, SpanEntity):
            span_id = data.span_id
            session_id = data.session_id

            # Check entity type
            if data.entity_type not in self.required["entity_type"]:
                return (
                    False,
                    f"Entity type must be one of {self.required['entity_type']}, got '{data.entity_type}'",
                    span_id,
                    session_id,
                )

            # Check required parameters
            is_valid, error_message = self._check_span_required_params(data)
            if not is_valid:
                return (
                    False,
                    f"{error_message} Entity type: '{data.entity_type}'",
                    span_id,
                    session_id,
                )

            return True, "", span_id, session_id

        # Handle SessionEntity (session-level metrics)
        if isinstance(data, SessionEntity) and self.aggregation_level == "session":
            session_id = data.session_id

            if not data.spans:
                return (
                    False,
                    f"Session '{session_id}' spans cannot be empty",
                    "",
                    session_id,
                )

            span_id = data.spans[0].span_id

            # Check required parameters
            is_valid, error_message = self._check_session_required_params(data)
            if not is_valid:
                return False, error_message, span_id, session_id

            return True, "", span_id, session_id

        # Fallback for unexpected data types or aggregation level mismatch
        return (
            False,
            f"Unsupported data type '{type(data).__name__}' or aggregation level mismatch",
            "",
            "",
        )

    async def _get_source_data(self, data: Union[SpanEntity, SessionEntity]):
        # Handle single SpanEntity (span-level metrics)
        if isinstance(data, SpanEntity):
            span_id = [data.span_id]
            session_id = [data.session_id]
            entities_involved = [data.entity_name]
            app_name = data.app_name
            category = "agent"

        # Handle SessionEntity (session-level metrics)
        elif isinstance(data, SessionEntity) and self.aggregation_level == "session":
            session_id = [data.session_id]
            span_id = [s.span_id for s in data.spans]
            entities_involved = [span.entity_name for span in data.agent_spans]
            app_name = data.spans[0].app_name
            category = "application"

        return category, app_name, entities_involved, span_id, session_id

    async def compute(
        self, data: SpanEntity | SessionEntity, **context
    ) -> MetricResult:
        """
        Compute the metric using DeepEval's interface and return in your framework's format
        """

        # Initialize variables before try block to avoid UnboundLocalError
        (
            category,
            app_name,
            entities_involved,
            span_id,
            session_id,
        ) = await self._get_source_data(data=data)

        try:
            test_case_calculator = self.metric_configuration.test_case_calculator
            test_case = test_case_calculator.calculate_test_case(data=data)

            # Use async version if available, otherwise fallback to sync
            if hasattr(self.deepeval_metric, "a_measure"):
                score = await self.deepeval_metric.a_measure(test_case)
            else:
                score = self.deepeval_metric.measure(test_case)

            # Extract additional metadata from the metric
            metadata = {
                "threshold": getattr(self.deepeval_metric, "threshold", None),
                "success": getattr(self.deepeval_metric, "success", None),
                "reason": getattr(self.deepeval_metric, "reason", None),
                "evaluation_cost": getattr(
                    self.deepeval_metric, "evaluation_cost", None
                ),
                "verbose_logs": getattr(self.deepeval_metric, "verbose_logs", None),
            }

            logger.info(f"metadata: {metadata}")
            # Filter out None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            logger.info(f"aggregation level: {self.aggregation_level}")
            return MetricResult(
                metric_name=self.name,
                description="",
                value=score,
                reasoning=metadata["reason"],
                unit="",
                aggregation_level=self.aggregation_level,
                category=category,
                app_name=app_name,
                agent_id=data.agent_id,
                span_id=span_id,
                session_id=session_id,
                source="deepeval",
                entities_involved=entities_involved,
                edges_involved=[],
                success=getattr(self.deepeval_metric, "success", score is not None),
                metadata=metadata,
                error_message=None,
            )

        except Exception as e:
            # Format error message with optional stack trace
            import traceback

            error_msg = str(e)
            if context.get("include_stack_trace", False):
                error_msg = f"{error_msg}\n\nStack trace:\n{traceback.format_exc()}"

            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=app_name,
                agent_id=data.agent_id,
                span_id=span_id,
                session_id=session_id,
                source="deepeval",
                entities_involved=entities_involved,
                edges_involved=[],
                metadata={},
                success=False,
                error_message=error_msg,
            )
