import json
from abc import ABCMeta, abstractmethod
from typing import Optional, Union

from deepeval.test_case import ConversationalTestCase, LLMTestCase, ToolCall, Turn

from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.util import (
    build_chat_history_from_payload,
    get_tool_definitions_from_span_attributes,
)


class AbstractTestCaseCalculator(metaclass=ABCMeta):
    @abstractmethod
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        """abstract method for calculating test cases"""


class DeepEvalTestCaseLLM(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        """
        Convert your framework's data format to DeepEval's LLMTestCase format.
        You'll need to customize this based on your data structure.
        """
        # TODO: maybe need to constrain support of different 3rd party metrics,
        # input, actual_output, expected_output, retrieval_context would need to be extracted automatically to align with
        # the current data processing strategy.
        data = _make_sure_input_is_span_entity(data=data)
        return LLMTestCase(
            input=json.dumps(data.input_payload, indent=2),
            actual_output=json.dumps(data.output_payload, indent=2),
            expected_output="",
            retrieval_context=[],
        )


class DeepEvalTestCaseLLMWithTools(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        """
        Create test case with tools from SessionEntity data.
        """
        data: SessionEntity = _make_sure_input_is_session_entity(data=data)
        user_input = data.input_query or ""
        final_response = data.final_response or ""

        if not user_input or not final_response:
            raise ValueError("No user input or final response found in session")

        tools_called = []
        for tool_call in data.tool_calls or []:
            tools_called.append(
                ToolCall(
                    name=tool_call.name,
                    description=tool_call.description,
                    input_parameters=tool_call.input_parameters,
                    output=tool_call.output,
                )
            )

        return LLMTestCase(
            input=user_input, actual_output=final_response, tools_called=tools_called
        )


class DeepEvalTestCaseConversational(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        """
        Create conversational test case from SessionEntity data.
        """
        data: SessionEntity = _make_sure_input_is_session_entity(data=data)
        # TODO: Since developers can control this role, there's no guarantee it will always be assistant. How can this be autonomously detected?
        chatbot_role = "assistant"
        if not data.conversation_elements:
            raise ValueError("No conversation elements found in session")

        # Convert SessionEntity conversation elements to DeepEval Turn format
        turns = []
        for element in data.conversation_elements:
            role = element.role
            if role not in ["user", "assistant"]:
                role = "assistant"
            turns.append(Turn(role=role, content=element.content))

        return ConversationalTestCase(chatbot_role=chatbot_role, turns=turns)


class LLMAnswerRelevancyTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        data = _make_sure_input_is_span_entity(data=data)
        chat_payload = data.input_payload
        raw_span_data = data.raw_span_data
        span_attributes = raw_span_data["SpanAttributes"]
        tool_definitions = get_tool_definitions_from_span_attributes(
            span_attributes=span_attributes
        )
        full_input_dict = {
            "tool_definitions": tool_definitions,
            "chat_payload": chat_payload,
        }
        test_case = LLMTestCase(
            input=json.dumps(full_input_dict, indent=2),
            actual_output=json.dumps(data.output_payload, indent=2),
        )
        return test_case


class SessionAnswerRelevancyTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        """
        Create test case for session-level answer relevancy using enriched session data.
        Uses the input_query and final_response fields from the SessionEntity.
        Falls back to extracting from available spans if enriched data is not available.
        """
        data: SessionEntity = _make_sure_input_is_session_entity(data=data)

        user_input = data.input_query or ""
        final_response = data.final_response or ""

        # If enriched data is not available, don't try to extract from raw spans
        # because that's where the problematic analysis content comes from.
        # The enriched data should be the authoritative source.
        if not user_input or not final_response:
            # Only try conversation_elements as a fallback, but with filtering
            if data.conversation_elements and (not user_input or not final_response):
                # Find first user input with filtering
                if not user_input:
                    for element in data.conversation_elements:
                        if element.get("role", "").lower() == "user":
                            content = element.get("content", "")
                            # Apply same filtering as our transformer
                            if content and not self._is_system_content(content):
                                user_input = content
                                break

                # Find last meaningful assistant response with filtering
                if not final_response:
                    for element in reversed(data.conversation_elements):
                        if element.get("role", "").lower() == "assistant":
                            content = element.get("content", "")
                            # Apply filtering to avoid analysis content
                            if content and not self._is_system_content(content):
                                final_response = content
                                break

        # Provide fallback values if still empty
        if not user_input:
            user_input = "[FALLBACK] No meaningful user input found in session data"
        if not final_response:
            final_response = (
                "[FALLBACK] No meaningful final response found in session data"
            )

        test_case = LLMTestCase(
            input=user_input,
            actual_output=final_response,
        )
        return test_case

    def _is_system_content(self, content: str) -> bool:
        """Check if content looks like system control or analysis messages."""
        if not content:
            return True

        content_lower = content.lower().strip()

        # Filter out obvious system control messages
        system_patterns = [
            content.strip().startswith('{"next":'),
            content.strip() == '{"next": "FINISH"}',
            content.strip().startswith('{"next": "'),
            len(content.strip()) < 10,  # Very short responses
            "text contains" in content_lower,
            content_lower.startswith("the word "),
            "mentioned" in content_lower
            and ("next" in content_lower or "finish" in content_lower),
            content_lower == "next",
            content_lower == "finish",
        ]

        return any(system_patterns)


class LLMAnswerCorrectnessTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        data: SpanEntity = _make_sure_input_is_span_entity(data=data)
        raw_span_data = data.raw_span_data
        span_attributes = raw_span_data["SpanAttributes"]
        tool_definitions = get_tool_definitions_from_span_attributes(
            span_attributes=span_attributes
        )
        chat_payload = build_chat_history_from_payload(
            payload=data.input_payload, prefix="gen_ai.prompt."
        )
        full_input_dict = {
            "tool_definitions": tool_definitions,
            "chat_payload": chat_payload,
        }
        actual_output = build_chat_history_from_payload(
            payload=data.output_payload, prefix="gen_ai.completion."
        )
        expected_output: Optional[str] = ""
        if data.expected_output:
            expected_output = json.dumps(data.expected_output, indent=2)
        test_case = LLMTestCase(
            input=json.dumps(full_input_dict, indent=2),
            actual_output=json.dumps(actual_output, indent=2),
            expected_output=expected_output,
        )
        return test_case


class LLMGeneralStructureAndStyleTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Union[ConversationalTestCase, LLMTestCase]:
        data: SpanEntity = _make_sure_input_is_span_entity(data=data)
        span_attributes = data.raw_span_data["SpanAttributes"]
        tool_definitions = get_tool_definitions_from_span_attributes(
            span_attributes=span_attributes
        )
        chat_payload = build_chat_history_from_payload(
            payload=data.input_payload, prefix="gen_ai.prompt."
        )
        full_input_dict = {
            "tool_definitions": tool_definitions,
            "chat_payload": chat_payload,
        }
        actual_output = build_chat_history_from_payload(
            payload=data.output_payload, prefix="gen_ai.completion."
        )

        test_case = LLMTestCase(
            input=json.dumps(full_input_dict, indent=2),
            actual_output=json.dumps(actual_output, indent=2),
        )
        return test_case


def _make_sure_input_is_session_entity(
    data: Union[SpanEntity, SessionEntity],
) -> SessionEntity:
    if not isinstance(data, SessionEntity):
        raise TypeError("data must be an instance of SessionEntity")
    return data


def _make_sure_input_is_span_entity(
    data: Union[SpanEntity, SessionEntity],
) -> SpanEntity:
    if not isinstance(data, SpanEntity):
        raise TypeError("data must be an instance of SpanEntity")
    return data
