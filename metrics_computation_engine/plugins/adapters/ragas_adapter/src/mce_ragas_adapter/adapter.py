# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Tuple
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

# Set up logger using MCE's standard pattern
logger = setup_logger(__name__)


class RagasAdapter(BaseMetric):
    """
    Adapter to integrate RAGAS metrics as 3rd party plugins into the MCE.
    """

    def __init__(self, ragas_metric_name: str, mode: str = "precision"):
        super().__init__()

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

        # Validate final mode
        valid_modes = ["precision", "recall", "f1"]
        if self.mode not in valid_modes:
            raise ValueError(
                f"Invalid mode '{self.mode}'. Must be one of: {valid_modes}"
            )

        self.name = (
            f"{self.ragas_metric_name}_{self.mode}"
            if self.mode != "precision"
            else self.ragas_metric_name
        )
        self.ragas_metric = None
        self.model = None

        # Debug: Log final configuration
        logger.info(
            f"RagasAdapter final config: metric='{self.ragas_metric_name}', mode='{self.mode}', name='{self.name}'"
        )

        # Mapping of RAGAS metrics to their data conversion methods
        self.RAGAS_METRIC_MAP = {
            "TopicAdherenceScore": self.create_ragas_multi_turn_sample,
        }

        # For TopicAdherenceScore, we need session-level data (conversation flow)
        if self.ragas_metric_name == "TopicAdherenceScore":
            self.aggregation_level: AggregationLevel = "session"
            self.required = {"entity_type": ["llm"]}

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

    def create_ragas_multi_turn_sample(self, data: list[SpanEntity]):
        """
        Convert SpanEntity list to RAGAS MultiTurnSample format.
        Enhanced with NumPy compatibility fixes for RAGAS v0.3.2.
        """
        try:
            from ragas.dataset_schema import MultiTurnSample
            from ragas.messages import HumanMessage, AIMessage
        #            from ragas.messages import HumanMessage, AIMessage, ToolMessage, ToolCall
        except ImportError:
            raise ImportError(
                "RAGAS library not installed. Please install with: pip install ragas"
            )

        # Sort spans by timestamp to maintain conversation order
        sorted_spans = sorted(data, key=lambda span: span.timestamp)
        llm_spans = [span for span in sorted_spans if span.entity_type == "llm"]

        logger.info(
            f"RAGAS DEBUG: Total spans: {len(data)}, LLM spans: {len(llm_spans)}"
        )

        # Debug: Show all entity types present
        entity_types = [span.entity_type for span in sorted_spans]
        logger.info(f"RAGAS DEBUG: Entity types found: {set(entity_types)}")

        if not llm_spans:
            logger.warning("RAGAS DEBUG: No LLM spans found in the data")
            # Let's also check what spans we do have
            for i, span in enumerate(sorted_spans[:3]):
                logger.warning(
                    f"RAGAS DEBUG: Span {i} - type: {span.entity_type}, has input: {bool(span.input_payload)}, has output: {bool(span.output_payload)}"
                )
            raise ValueError("No LLM spans found in the data")

        # Extract conversation flow from LLM spans
        conversation_messages = []
        reference_topics = []

        for i, span in enumerate(llm_spans):
            input_payload = span.input_payload
            output_payload = span.output_payload

            logger.info(f"RAGAS DEBUG: === Span {i} Analysis ===")
            logger.info(
                f"RAGAS DEBUG: Span {i} input_keys: {list(input_payload.keys()) if input_payload else 'None'}"
            )
            logger.info(
                f"RAGAS DEBUG: Span {i} output_keys: {list(output_payload.keys()) if output_payload else 'None'}"
            )

            # Show sample input payload content
            if input_payload:
                logger.info(f"RAGAS DEBUG: Span {i} input payload sample:")
                for key, value in list(input_payload.items())[:10]:  # First 10 items
                    value_preview = (
                        str(value)[:100] + "..."
                        if len(str(value)) > 100
                        else str(value)
                    )
                    logger.info(f"RAGAS DEBUG:   {key}: {value_preview}")

            # Show sample output payload content
            if output_payload:
                logger.info(f"RAGAS DEBUG: Span {i} output payload sample:")
                for key, value in list(output_payload.items())[:10]:  # First 10 items
                    value_preview = (
                        str(value)[:100] + "..."
                        if len(str(value)) > 100
                        else str(value)
                    )
                    logger.info(f"RAGAS DEBUG:   {key}: {value_preview}")

            if not input_payload or not output_payload:
                logger.info(f"RAGAS DEBUG: Span {i} skipped - missing payload")
                continue

            # Extract number of turns in the conversation
            try:
                prompt_keys = [
                    key
                    for key in input_payload.keys()
                    if key.startswith("gen_ai.prompt")
                ]
                logger.info(f"RAGAS DEBUG: Span {i} found prompt keys: {prompt_keys}")

                num_turns = len(
                    set([message_key.split(".")[2] for message_key in prompt_keys])
                )
                logger.info(f"RAGAS DEBUG: Span {i} extracted num_turns: {num_turns}")
            except Exception as e:
                logger.info(f"RAGAS DEBUG: Span {i} failed to extract turns: {e}")
                num_turns = 1

            # Build conversation from input payload
            messages_found_this_span = 0
            logger.info(
                f"RAGAS DEBUG: Span {i} building conversation for {num_turns} turns"
            )

            for n in range(num_turns):
                role_key = f"gen_ai.prompt.{n}.role"
                content_key = f"gen_ai.prompt.{n}.content"

                logger.info(
                    f"RAGAS DEBUG: Span {i} turn {n} - looking for keys: {role_key}, {content_key}"
                )

                has_role = role_key in input_payload
                has_content = content_key in input_payload
                logger.info(
                    f"RAGAS DEBUG: Span {i} turn {n} - has_role: {has_role}, has_content: {has_content}"
                )

                if has_role and has_content:
                    role = input_payload[role_key]
                    content = input_payload[content_key]

                    if role == "user":
                        conversation_messages.append(HumanMessage(content=content))
                        messages_found_this_span += 1
                        logger.info(
                            f"RAGAS DEBUG: Span {i} turn {n} - added HumanMessage"
                        )
                    elif role == "assistant":
                        conversation_messages.append(AIMessage(content=content))
                        messages_found_this_span += 1
                        logger.info(f"RAGAS DEBUG: Span {i} turn {n} - added AIMessage")
                    else:
                        logger.info(
                            f"RAGAS DEBUG: Span {i} turn {n} - unknown role '{role}', skipped"
                        )

            # Add AI response from output payload
            completion_key = "gen_ai.completion.0.content"
            logger.info(
                f"RAGAS DEBUG: Span {i} looking for completion key: {completion_key}"
            )
            logger.info(
                f"RAGAS DEBUG: Span {i} has completion: {completion_key in output_payload}"
            )

            if completion_key in output_payload:
                ai_response = output_payload[completion_key]
                logger.info(
                    f"RAGAS DEBUG: Span {i} found completion: '{str(ai_response)[:50]}...'"
                )
                conversation_messages.append(AIMessage(content=ai_response))
                messages_found_this_span += 1
                logger.info(f"RAGAS DEBUG: Span {i} - added completion AIMessage")

            logger.info(
                f"RAGAS DEBUG: Span {i} extracted {messages_found_this_span} messages total"
            )

        # For TopicAdherenceScore, we need reference topics
        # These could be extracted from metadata or configured
        # For now, using a default set - in real implementation, this should be configurable
        reference_topics = ["technology", "science", "business", "math"]

        # Validate conversation messages to prevent NumPy type errors
        if not conversation_messages:
            raise ValueError("No conversation messages found in the data")

        # Ensure all message content is properly typed as strings
        validated_messages = []
        for msg in conversation_messages:
            if hasattr(msg, "content") and msg.content:
                # Ensure content is a proper string type
                validated_content = str(msg.content).strip()
                if validated_content:
                    if isinstance(msg, HumanMessage):
                        validated_messages.append(
                            HumanMessage(content=validated_content)
                        )
                    elif isinstance(msg, AIMessage):
                        validated_messages.append(AIMessage(content=validated_content))

        if not validated_messages:
            raise ValueError("No valid messages found after validation")

        # Ensure reference topics are proper string types
        validated_reference_topics = [
            str(topic).strip() for topic in reference_topics if topic
        ]

        logger.info(
            f"RAGAS DEBUG: Final - Original messages: {len(conversation_messages)}, Validated messages: {len(validated_messages)}"
        )
        for i, msg in enumerate(validated_messages[:3]):  # Show first 3 messages
            logger.info(
                f"RAGAS DEBUG: Message {i}: {type(msg).__name__} - {str(msg.content)[:100]}..."
            )

        logger.debug(
            f"Creating MultiTurnSample with {len(validated_messages)} messages and {len(validated_reference_topics)} topics"
        )

        return MultiTurnSample(
            user_input=validated_messages, reference_topics=validated_reference_topics
        )

    async def _assess_input_data(
        self, data: SpanEntity | list[SpanEntity] | Any
    ) -> Tuple[bool, str, str, str]:
        data_is_appropriate: bool = True
        error_message: str = ""
        span_id: str = ""
        session_id: str = ""

        # Handle SessionEntity (session-level metrics)
        if self.aggregation_level == "session":
            # Check if it's a SessionEntity
            if hasattr(data, "spans") and hasattr(data, "session_id"):
                # This is a SessionEntity, extract spans for processing
                spans = data.spans
                session_id = data.session_id

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

        return data_is_appropriate, error_message, span_id, session_id

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
                span_id=[span_id],
                session_id=[session_id],
                source="",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=error_message,
            )

        try:
            # Extract spans from SessionEntity
            spans_data = data.spans

            # Convert data to RAGAS format using the correct method from RAGAS_METRIC_MAP
            conversion_method = self.RAGAS_METRIC_MAP[self.ragas_metric_name]
            sample = conversion_method(data=spans_data)

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
                span_id=[span_id],
                session_id=[session_id],
                source="ragas",
                entities_involved=[],
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
                span_id=[span_id],
                session_id=[session_id],
                source="ragas",
                entities_involved=[],
                edges_involved=[],
                metadata={},
                success=False,
                error_message=str(exc),
            )
