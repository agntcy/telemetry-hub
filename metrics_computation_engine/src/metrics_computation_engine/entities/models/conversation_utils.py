# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Tuple
from datetime import datetime

from .span import SpanEntity


def extract_conversation_endpoints(
    llm_spans: List[SpanEntity],
    min_content_length: int = 3,
    support_prompt_format_in_output: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract input_query and final_response from LLM spans.

    This is a shared utility function used by both AgentView and EndToEndAttributesTransformer
    to ensure consistent behavior when extracting conversation endpoints.

    Args:
        llm_spans: List of LLM spans to analyze
        min_content_length: Minimum content length to consider (filters very short responses)
        support_prompt_format_in_output: Whether to support gen_ai.prompt.* format in output_payload
                                        (in addition to gen_ai.completion.*)

    Returns:
        Tuple of (input_query, final_response) where either can be None if not found

    Current default values for compatibility:
        - AgentView: min_content_length=3, support_prompt_format_in_output=True
        - EndToEndAttributesTransformer: min_content_length=10, support_prompt_format_in_output=False
    """
    if not llm_spans:
        return None, None

    # Extract input_query
    input_query = _extract_input_query(llm_spans)

    # Extract final_response
    final_response = _extract_final_response(
        llm_spans,
        min_content_length=min_content_length,
        support_prompt_format_in_output=support_prompt_format_in_output
    )

    return input_query, final_response


def _extract_input_query(llm_spans: List[SpanEntity]) -> Optional[str]:
    """
    Extract the first user input query from LLM spans.

    Logic:
    1. Find the latest LLM span (should contain full chat history)
    2. Extract prompt indices from input_payload
    3. Skip system messages, return first user message
    """
    # Find the latest LLM span (should contain chat history)
    try:
        latest_span = max(llm_spans, key=lambda x: datetime.fromisoformat(x.timestamp))
    except (ValueError, AttributeError):
        # Fallback if timestamp parsing fails
        latest_span = llm_spans[-1]

    if not latest_span.input_payload:
        return None

    # Extract prompt indices
    indexes = {
        int(key.split(".")[2])
        for key in latest_span.input_payload.keys()
        if key.startswith("gen_ai.prompt.")
        and len(key.split(".")) > 2
        and key.split(".")[2].isdigit()
    }

    # Process prompts in order to find first user input
    for i in sorted(indexes):
        role_key = f"gen_ai.prompt.{i}.role"
        content_key = f"gen_ai.prompt.{i}.content"

        if (
            role_key in latest_span.input_payload
            and latest_span.input_payload[role_key].lower() == "system"
        ):
            # Skip system messages
            continue

        if content_key in latest_span.input_payload:
            content = latest_span.input_payload[content_key]
            if content:  # Return the first user input
                return str(content)

    return None


def _extract_final_response(
    llm_spans: List[SpanEntity],
    min_content_length: int = 3,
    support_prompt_format_in_output: bool = True,
) -> Optional[str]:
    """
    Extract the last meaningful response from LLM spans.

    Logic:
    1. Iterate through spans in reverse chronological order
    2. Look for completion content in output_payload
    3. Apply filtering to skip system control messages
    4. Return first meaningful assistant response found
    """
    # Look through LLM spans in reverse chronological order for meaningful responses
    for span in sorted(
        llm_spans,
        key=lambda x: datetime.fromisoformat(x.timestamp),
        reverse=True,
    ):
        if not span.output_payload:
            continue

        # Check for completion format (preferred)
        completion_indexes = {
            int(key.split(".")[2])
            for key in span.output_payload.keys()
            if key.startswith("gen_ai.completion.")
            and len(key.split(".")) > 2
            and key.split(".")[2].isdigit()
        }

        # Check for prompt format in output (if supported)
        prompt_indexes = set()
        if support_prompt_format_in_output:
            prompt_indexes = {
                int(key.split(".")[2])
                for key in span.output_payload.keys()
                if key.startswith("gen_ai.prompt.")
                and len(key.split(".")) > 2
                and key.split(".")[2].isdigit()
            }

        # Combine both index sets and look for meaningful responses
        all_indexes = completion_indexes.union(prompt_indexes)
        for i in sorted(all_indexes, reverse=True):
            # Try completion format first, then prompt format
            if i in completion_indexes:
                content_key = f"gen_ai.completion.{i}.content"
                role_key = f"gen_ai.completion.{i}.role"
            else:
                content_key = f"gen_ai.prompt.{i}.content"
                role_key = f"gen_ai.prompt.{i}.role"

            if content_key in span.output_payload:
                content = span.output_payload[content_key]
                role = span.output_payload.get(role_key, "").lower()

                # Skip if content is empty
                if not content:
                    continue

                content_str = str(content).strip()

                # Apply filtering to skip system control messages
                if _is_system_control_message(content_str, min_content_length):
                    continue

                # This looks like a meaningful response
                if role == "assistant" or not role:  # Assistant or unknown role
                    return content_str

    return None


def _is_system_control_message(content_str: str, min_content_length: int) -> bool:
    """
    Check if content appears to be a system control message that should be filtered out.

    Returns True if the content should be skipped, False if it's a meaningful response.
    """
    # Skip obvious system control messages and analysis content
    return (
        # JSON control messages (both single and double quotes)
        content_str.startswith('{"next":')
        or content_str.startswith("{'next':")
        or content_str == '{"next": "FINISH"}'
        or content_str == "{'next': 'FINISH'}"
        or content_str.startswith('{"next": "')
        or content_str.startswith("{'next': '")
        or
        # Skip very short responses (likely control messages)
        len(content_str) < min_content_length
        or
        # Analysis content patterns (more specific)
        content_str.lower().startswith("the text contains")
        or content_str.lower().startswith("the word ")
        or "text contains" in content_str.lower()
        or
        # Only filter if it's clearly analysis content
        (
            content_str.lower().startswith("the ")
            and len(content_str) < 50
            and (
                "next" in content_str.lower()
                or "finish" in content_str.lower()
            )
        )
        or content_str.lower() == "next"
        or content_str.lower() == "finish"
        or content_str.lower().endswith(" is mentioned.")
        or content_str.lower().endswith(" is present.")
        or (
            "mentioned" in content_str.lower()
            and len(content_str) < 100
            and (
                "next" in content_str.lower()
                or "finish" in content_str.lower()
            )
        )
    )