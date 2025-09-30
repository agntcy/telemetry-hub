from abc import ABCMeta, abstractmethod
from typing import Union, Dict, Any

from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


class AbstractTestCaseCalculator(metaclass=ABCMeta):
    @abstractmethod
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Dict[str, Any]:
        """abstract method for calculating test cases"""


class OpikSpanTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Dict[str, Any]:
        """
        Extract parameters from SpanEntity and map them to Opik metric requirements.
        This method extracts data from SpanEntity based on Opik metric needs.
        """
        # Ensure we have SpanEntity data
        data = _make_sure_input_is_span_entity(data=data)

        # Basic extraction for Opik metrics
        params = {}

        # Most Opik metrics expect these basic parameters
        if hasattr(data, "input_payload") and data.input_payload:
            if isinstance(data.input_payload, str):
                params["input"] = data.input_payload
            elif isinstance(data.input_payload, dict):
                # Try to extract input from common keys
                params["input"] = (
                    data.input_payload.get("input")
                    or data.input_payload.get("question")
                    or data.input_payload.get("query")
                    or str(data.input_payload)
                )
            else:
                params["input"] = str(data.input_payload)

        if hasattr(data, "output_payload") and data.output_payload:
            if isinstance(data.output_payload, str):
                params["output"] = data.output_payload
            elif isinstance(data.output_payload, dict):
                # Try to extract output from common keys
                params["output"] = (
                    data.output_payload.get("output")
                    or data.output_payload.get("answer")
                    or data.output_payload.get("response")
                    or str(data.output_payload)
                )
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

        logger.info(f"Opik test case parameters extracted: {list(params.keys())}")
        return params


class OpikSessionTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Dict[str, Any]:
        """
        Extract parameters from SessionEntity for session-level Opik metrics.
        This is for future session-level metrics support.
        """
        # Ensure we have SessionEntity data
        data = _make_sure_input_is_session_entity(data=data)

        # Session-level parameter extraction
        params = {}

        # Extract conversation-level information
        if hasattr(data, "conversation_elements") and data.conversation_elements:
            # Convert conversation elements to a suitable format
            conversation = []
            for element in data.conversation_elements:
                conversation.append({"role": element.role, "content": element.content})
            params["conversation"] = conversation

        # Extract session-level metrics
        if hasattr(data, "input_query") and data.input_query:
            params["user_input"] = data.input_query

        if hasattr(data, "final_response") and data.final_response:
            params["final_response"] = data.final_response

        # Extract tool calls if available
        if hasattr(data, "tool_calls") and data.tool_calls:
            tools_used = []
            for tool_call in data.tool_calls:
                tools_used.append(
                    {
                        "name": tool_call.name,
                        "description": tool_call.description,
                        "input_parameters": tool_call.input_parameters,
                        "output": tool_call.output,
                    }
                )
            params["tools_used"] = tools_used

        logger.info(
            f"Opik session test case parameters extracted: {list(params.keys())}"
        )
        return params


class OpikHallucinationTestCase(AbstractTestCaseCalculator):
    def calculate_test_case(
        self, data: Union[SpanEntity, SessionEntity]
    ) -> Dict[str, Any]:
        """
        Specialized test case calculator for Hallucination metric.
        Extracts specific parameters needed for hallucination detection.
        """
        # Ensure we have SpanEntity data
        data = _make_sure_input_is_span_entity(data=data)

        params = {}

        # Extract input (user query/question)
        if hasattr(data, "input_payload") and data.input_payload:
            if isinstance(data.input_payload, dict):
                # Look for various input keys
                params["input"] = (
                    data.input_payload.get("input")
                    or data.input_payload.get("question")
                    or data.input_payload.get("query")
                    or data.input_payload.get("prompt")
                    or str(data.input_payload)
                )
            else:
                params["input"] = str(data.input_payload)

        # Extract output (AI response)
        if hasattr(data, "output_payload") and data.output_payload:
            if isinstance(data.output_payload, dict):
                # Look for various output keys
                params["output"] = (
                    data.output_payload.get("output")
                    or data.output_payload.get("answer")
                    or data.output_payload.get("response")
                    or data.output_payload.get("completion")
                    or str(data.output_payload)
                )
            else:
                params["output"] = str(data.output_payload)

        # Extract context if available (important for hallucination detection)
        context = []
        if hasattr(data, "context") and data.context:
            if isinstance(data.context, list):
                context = data.context
            else:
                context = [str(data.context)]

        # Also check if context is embedded in input_payload
        if isinstance(data.input_payload, dict):
            embedded_context = (
                data.input_payload.get("context")
                or data.input_payload.get("documents")
                or data.input_payload.get("retrieved_docs")
                or data.input_payload.get("knowledge_base")
            )
            if embedded_context:
                if isinstance(embedded_context, list):
                    context.extend(embedded_context)
                else:
                    context.append(str(embedded_context))

        if context:
            params["context"] = context

        logger.info(f"Opik Hallucination test case parameters: {list(params.keys())}")
        return params


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
