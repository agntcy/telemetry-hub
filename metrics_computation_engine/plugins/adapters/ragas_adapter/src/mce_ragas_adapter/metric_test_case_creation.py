from abc import ABCMeta, abstractmethod
from typing import Union

from metrics_computation_engine.models.session import SessionEntity
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


class AbstractTestCaseCalculator(metaclass=ABCMeta):
    @abstractmethod
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> any:
        """abstract method for calculating test cases"""


class RagasMultiTurnTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> any:
        """
        Convert SessionEntity data to RAGAS MultiTurnSample format.
        """
        try:
            from ragas.dataset_schema import MultiTurnSample
            from ragas.messages import HumanMessage, AIMessage
        except ImportError:
            raise ImportError(
                "RAGAS library not installed. Please install with: pip install ragas"
            )

        # Ensure we have SessionEntity data
        data = _make_sure_input_is_session_entity(data=data)

        # Extract spans data
        spans_data = data.spans

        # Sort spans by timestamp to maintain conversation order
        sorted_spans = sorted(spans_data, key=lambda span: span.timestamp)
        llm_spans = [span for span in sorted_spans if span.entity_type == "llm"]

        logger.info(
            f"RAGAS DEBUG: Total spans: {len(spans_data)}, LLM spans: {len(llm_spans)}"
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


def _make_sure_input_is_session_entity(
    data: Union[SpanEntity, SessionEntity],
) -> SessionEntity:
    if not isinstance(data, SessionEntity):
        raise TypeError("data must be an instance of SessionEntity")
    return data
