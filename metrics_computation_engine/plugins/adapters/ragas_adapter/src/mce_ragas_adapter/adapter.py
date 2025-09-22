# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Tuple, Dict
import importlib

# These imports will be available in the runtime environment
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.types import AggregationLevel
from metrics_computation_engine.models.requests import LLMJudgeConfig

# Import logger from MCE following the standard pattern
from metrics_computation_engine.logger import setup_logger

from .model_loader import (
    MODEL_PROVIDER_NAME,
    load_model,
)
from .metric_configuration import MetricConfiguration, build_metric_configuration_map

# Set up logger using MCE's standard pattern
logger = setup_logger(__name__)


class RagasAdapter(BaseMetric):
    """
    Adapter to integrate RAGAS metrics as 3rd party plugins into the MCE.
    """

    def __init__(self, ragas_metric_name: str, mode: str = "precision"):
        super().__init__()
        
        metric_configuration_map: Dict[str, MetricConfiguration] = (
            build_metric_configuration_map()
        )

        metric_configuration_map: Dict[str, MetricConfiguration] = (
            build_metric_configuration_map()
        )

        # Handle extended naming convention where the full dotted name might be passed
        if "." in ragas_metric_name and ragas_metric_name.count(".") >= 2:
            # Parse "ragas.TopicAdherenceScore.f1" format
            parts = ragas_metric_name.split(".")
            if len(parts) >= 3 and parts[0].lower() == "ragas":
                actual_metric_name = parts[1]  # TopicAdherenceScore
                extracted_mode = parts[2]  # f1

                # Validate extracted mode
                valid_modes = ["precision", "recall", "f1"]
                if extracted_mode in valid_modes:
                    self.ragas_metric_name = actual_metric_name
                    self.mode = (
                        extracted_mode  # Use extracted mode instead of parameter
                    )
                    logger.info(
                        f"RagasAdapter: Extracted mode '{extracted_mode}' from metric name '{ragas_metric_name}'"
                    )
                else:
                    # Invalid mode in name, use the base name and parameter mode
                    self.ragas_metric_name = actual_metric_name
                    self.mode = mode
                    logger.warning(
                        f"RagasAdapter: Invalid mode '{extracted_mode}' in name, using parameter mode '{mode}'"
                    )
            else:
                # Not RAGAS format, use as-is
                self.ragas_metric_name = ragas_metric_name
                self.mode = mode
        else:
            # Standard case: just the metric name
            self.ragas_metric_name = ragas_metric_name
            self.mode = mode

        # Get metric configuration from centralized system
        if self.ragas_metric_name not in metric_configuration_map:
            supported_metrics = sorted(metric_configuration_map.keys())
            raise ValueError(
                f"Supported metrics are {supported_metrics},"
                f" but `{self.ragas_metric_name}` was given."
            )

        self.metric_configuration: MetricConfiguration = metric_configuration_map[
            self.ragas_metric_name
        ]

        # Validate mode support if specified in configuration
        if self.metric_configuration.mode_support:
            if self.mode not in self.metric_configuration.mode_support:
                raise ValueError(
                    f"Invalid mode '{self.mode}' for metric '{self.ragas_metric_name}'. "
                    f"Must be one of: {self.metric_configuration.mode_support}"
                )

        self.name = (
            f"{self.ragas_metric_name}_{self.mode}"
            if self.mode != "precision"
            else self.ragas_metric_name
        )
        self.ragas_metric = None
        self.model = None

        # Use configuration from centralized system
        self.aggregation_level: AggregationLevel = (
            self.metric_configuration.requirements.aggregation_level
        )
        self.required = {"entity_type": self.metric_configuration.requirements.entity_type}

        # Debug: Log final configuration
        logger.info(
            f"RagasAdapter final config: metric='{self.ragas_metric_name}', mode='{self.mode}', name='{self.name}'"
        )

    def get_model_provider(self):
        return MODEL_PROVIDER_NAME

    def init_with_model(self, model: Any) -> bool:
        """
        Initialize RAGAS metric with the provided model.

        Args:
            model: Should be a LangchainLLMWrapper instance from model_loader

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Verify we have a real LangchainLLMWrapper, not a fallback
            if "BasicRagasModel" in str(type(model)):
                logger.error(
                    f"Received fallback model instead of real RAGAS model for {self.ragas_metric_name}"
                )
                return False

            self.model = model

            # Load the RAGAS metric class dynamically
            module = importlib.import_module("ragas.metrics")
            ragas_metric_cls = getattr(module, self.ragas_metric_name, None)

            if ragas_metric_cls is None:
                logger.error(
                    f"RAGAS metric class '{self.ragas_metric_name}' not found in ragas.metrics module"
                )
                return False

            # Create RAGAS metric instance with model
            if self.ragas_metric_name == "TopicAdherenceScore":
                self.ragas_metric = ragas_metric_cls(llm=model, mode=self.mode)
                logger.info(
                    f"RAGAS TopicAdherenceScore initialized with mode: {self.mode}"
                )
            else:
                self.ragas_metric = ragas_metric_cls(llm=model)

            logger.info(
                f"Successfully initialized RAGAS metric: {self.ragas_metric_name}"
            )
            return True

        except Exception as exc:
            logger.error(
                f"Failed to initialize RAGAS metric '{self.ragas_metric_name}': {exc}"
            )
            return False

    def create_model(self, llm_config: LLMJudgeConfig) -> Any:
        return load_model(llm_config)

    @property
    def required_parameters(self):
        """Map RAGAS required params to your framework's format"""
        return getattr(self.ragas_metric, "_required_params", [])

    def validate_config(self) -> bool:
        """Validate the RAGAS metric configuration"""
        try:
            # Basic validation - check if metric has required attributes
            return hasattr(self.ragas_metric, "multi_turn_ascore") or hasattr(
                self.ragas_metric, "single_turn_ascore"
            )
        except Exception:
            return False

    async def _assess_input_data(
        self, data: SpanEntity | list[SpanEntity] | Any
    ) -> Tuple[bool, str, str, str]:
        data_is_appropriate: bool = True
        error_message: str = ""
        app_name: str = ""
        entities_involved: list = []
        category = "application"
        span_id: str = ""
        session_id: str = ""

        # Handle SessionEntity (session-level metrics)
        if self.aggregation_level == "session":
            # Check if it's a SessionEntity
            if hasattr(data, "spans") and hasattr(data, "session_id"):
                # This is a SessionEntity, extract spans for processing
                spans = data.spans
                session_id = data.session_id
                app_name = data.app_name
                entities_involved = [span.entity_name for span in data.agent_spans]

                if not spans:
                    data_is_appropriate = False
                    error_message = "Session contains no spans"
                elif not any(
                    span.entity_type in self.required["entity_type"] for span in spans
                ):
                    data_is_appropriate = False
                    error_message = f"Session must contain at least one entity of type: {self.required['entity_type']}"
                else:
                    # Use first span for span_id
                    span_id = spans[0].span_id
            else:
                data_is_appropriate = False
                error_message = (
                    f"Expected SessionEntity for {self.aggregation_level}-level metric"
                )
        else:
            # For non-session level metrics
            data_is_appropriate = False
            error_message = f"Unexpected aggregation level: {self.aggregation_level}"

        return (
            data_is_appropriate,
            error_message,
            category,
            app_name,
            entities_involved,
            span_id,
            session_id,
        )

    async def compute(self, data: SpanEntity | list[SpanEntity]) -> MetricResult:
        """
        Compute the metric using RAGAS's interface and return in the framework's format
        """
        # Log data validation info
        if isinstance(data, list):
            logger.debug(
                f"Processing {len(data)} span entities for {self.ragas_metric_name}"
            )
        else:
            logger.debug(f"Processing single span entity for {self.ragas_metric_name}")

        (
            data_is_appropriate,
            error_message,
            category,
            app_name,
            entities_involved,
            span_id,
            session_id,
        ) = await self._assess_input_data(data=data)

        if not data_is_appropriate:
            logger.warning(
                f"Data assessment failed for {self.ragas_metric_name}: {error_message}"
            )
            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                category=category,
                app_name=app_name,
                span_id=[span_id],
                session_id=[session_id],
                source="",
                entities_involved=entities_involved,
                edges_involved=[],
                success=False,
                metadata={},
                error_message=error_message,
            )

        try:
            # Convert data to RAGAS format using the centralized test case calculator
            test_case_calculator = self.metric_configuration.test_case_calculator
            sample = test_case_calculator.calculate_test_case(data=data)

            # DEBUG: RAGAS metric inspection
            logger.info(f"DEBUG: RAGAS metric type: {type(self.ragas_metric)}")
            logger.info(
                f"DEBUG: RAGAS metric attributes: {[attr for attr in dir(self.ragas_metric) if not attr.startswith('_')]}"
            )

            # Use RAGAS async evaluation method
            if hasattr(self.ragas_metric, "multi_turn_ascore"):
                try:
                    score = await self.ragas_metric.multi_turn_ascore(sample)
                except Exception as inner_exc:
                    logger.error(
                        f"RAGAS computation failed for {self.name}: {inner_exc}"
                    )
                    logger.error(f"DEBUG: Exception type: {type(inner_exc).__name__}")
                    import traceback

                    logger.error(f"DEBUG: Full traceback:\n{traceback.format_exc()}")
                    raise inner_exc
            elif hasattr(self.ragas_metric, "single_turn_ascore"):
                try:
                    score = await self.ragas_metric.single_turn_ascore(sample)
                except Exception as inner_exc:
                    logger.error(
                        f"RAGAS computation failed for {self.name}: {inner_exc}"
                    )
                    logger.error(f"DEBUG: Exception type: {type(inner_exc).__name__}")
                    import traceback

                    logger.error(f"DEBUG: Full traceback:\n{traceback.format_exc()}")
                    raise inner_exc
            else:
                raise AttributeError(
                    f"RAGAS metric {self.name} does not have expected async score methods"
                )

            logger.info(f"RAGAS {self.name} computed successfully: {score}")

            # Extract additional metadata from the metric
            metadata = {
                "mode": self.mode,  # Use our adapter's mode, not the RAGAS metric's mode
                "ragas_metric_mode": getattr(
                    self.ragas_metric, "mode", None
                ),  # Also include RAGAS's reported mode for debugging
                "reference_topics": getattr(sample, "reference_topics", None),
            }

            # Filter out None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            return MetricResult(
                metric_name=self.name,
                description=f"RAGAS {self.name} metric",
                value=score,
                reasoning=f"RAGAS {self.name} evaluation completed",
                unit="score",
                aggregation_level=self.aggregation_level,
                category=category,
                app_name=app_name,
                span_id=[span_id],
                session_id=[session_id],
                source="ragas",
                entities_involved=entities_involved,
                edges_involved=[],
                metadata=metadata,
                success=score is not None,
                error_message=None,
            )

        except Exception as exc:
            logger.error(f"RAGAS computation failed for {self.name}: {exc}")
            # Add full traceback for debugging
            import traceback

            logger.error(f"DEBUG: Exception type: {type(exc).__name__}")
            logger.error(f"DEBUG: Full traceback:\n{traceback.format_exc()}")

            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                reasoning="",
                unit="",
                aggregation_level=self.aggregation_level,
                category=category,
                app_name=app_name,
                span_id=[span_id],
                session_id=[session_id],
                source="ragas",
                entities_involved=entities_involved,
                edges_involved=[],
                metadata={},
                success=False,
                error_message=str(exc),
            )
