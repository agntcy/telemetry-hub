# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Core transformers for common data extraction tasks.
"""

import json
from typing import List, Dict, Any, Optional
from .base import DataPreservingTransformer, DataTransformer
from ..types import SpanDataType
from ..models.span import SpanEntity


class EntityFilter(DataTransformer):
    """Filter data by entity types."""

    def __init__(self, entity_types: List[str]):
        self.entity_types = entity_types
        self.filtered_span_ids = []  # Store span IDs of filtered spans

    def transform(self, data: SpanDataType) -> Optional[SpanDataType]:
        """Filter data to only include specified entity types."""
        # Reset span IDs for each transform call
        self.filtered_span_ids = []

        if isinstance(data, list):
            # Full validation - check all items
            if not all(isinstance(item, SpanEntity) for item in data):
                raise TypeError(
                    "Expected List[SpanEntity], but found non-SpanEntity items"
                )

            filtered_spans = [d for d in data if d.entity_type in self.entity_types]
            # Store the span IDs of filtered spans
            self.filtered_span_ids = [span.span_id for span in filtered_spans]
            return filtered_spans
        elif isinstance(data, SpanEntity):
            # Single SpanEntity - return as-is if it matches filter, else return None
            if data.entity_type in self.entity_types:
                self.filtered_span_ids = [data.span_id]
                return data
            return None
        elif isinstance(data, dict):
            # Dict[str, List[SpanEntity]] case - validate all lists fully
            for key, value in data.items():
                if isinstance(value, list):
                    if not all(isinstance(item, SpanEntity) for item in value):
                        raise TypeError(
                            f"Expected List[SpanEntity] for key '{key}', but found non-SpanEntity items"
                        )
                else:
                    raise TypeError(
                        f"Expected List[SpanEntity] for key '{key}', but got {type(value)}"
                    )

            filtered_data = {}
            all_filtered_span_ids = []

            for key, value in data.items():
                if isinstance(value, list):
                    filtered_spans = [
                        d for d in value if d.entity_type in self.entity_types
                    ]
                    filtered_data[key] = filtered_spans
                    # Collect span IDs from all filtered spans
                    all_filtered_span_ids.extend(
                        [span.span_id for span in filtered_spans]
                    )

            self.filtered_span_ids = all_filtered_span_ids
            return filtered_data
        else:
            raise TypeError(f"Expected SpanDataType, but got {type(data)}")


class WorkflowDataExtractor(DataPreservingTransformer):
    """Extract workflow query and response from workflow spans."""

    def extract(self, data) -> Dict[str, Any]:
        # Get original data if available
        original_data = (
            data.get("original_data", data) if isinstance(data, dict) else data
        )

        # Find workflow spans
        workflow_spans = []
        if isinstance(original_data, list):
            workflow_spans = [
                d
                for d in original_data
                if hasattr(d, "entity_type") and d.entity_type == "workflow"
            ]

        if workflow_spans:
            workflow_span = workflow_spans[-1]
            query = self._extract_workflow_query(workflow_span.input_payload)
            response = self._extract_workflow_response(workflow_span.output_payload)
        else:
            query = ""
            response = ""

        return {
            "query": query,
            "response": response,
            "workflow_span": workflow_spans[0] if workflow_spans else None,
        }

    # TODO: clean this up for better extraction
    def _extract_workflow_query(self, workflow_input) -> str:
        try:
            if isinstance(workflow_input, str):
                workflow_input = json.loads(workflow_input)
            # Try to get the initial user query from chat_history (new format)
            chat_history = workflow_input.get("inputs", {}).get("chat_history", [])
            if chat_history and len(chat_history) > 0:
                first_msg = chat_history[0]
                if isinstance(first_msg, dict) and "message" in first_msg:
                    return first_msg["message"]
            # Fallback: original extraction logic for backward compatibility
            messages = workflow_input.get("inputs", {}).get("messages", [])
            if messages and len(messages) > 0:
                user_message = messages[0]
                if isinstance(user_message, list) and len(user_message) > 1:
                    return user_message[1]
            return ""
        except Exception:
            return ""

    def _extract_workflow_response(self, workflow_output) -> str:
        try:
            if isinstance(workflow_output, str):
                workflow_output = json.loads(workflow_output)
            messages = workflow_output.get("outputs", {}).get("messages", [])
            if messages:
                return str(messages)
            return ""
        except Exception:
            return ""


class WorkflowResponsesExtractor(DataPreservingTransformer):
    """Extract all workflow responses from workflow spans."""

    def extract(self, data) -> Dict[str, Any]:
        # Get original data if available
        original_data = (
            data.get("original_data", data) if isinstance(data, dict) else data
        )

        # Find workflow spans
        workflow_spans = []
        if isinstance(original_data, list):
            workflow_spans = [
                d
                for d in original_data
                if hasattr(d, "entity_type") and d.entity_type == "workflow"
            ]

        if workflow_spans:
            workflow_span = workflow_spans[0]
            responses = self._extract_workflow_responses(workflow_span.output_payload)
        else:
            responses = ""

        return {
            "responses": responses,
            "workflow_span": workflow_spans[0] if workflow_spans else None,
        }

    def _extract_workflow_responses(self, workflow_output) -> str:
        """Extract all responses from workflow output payload, excluding the first query."""
        try:
            if isinstance(workflow_output, str):
                workflow_output = json.loads(workflow_output)

            # Navigate: outputs -> messages -> get all message content except first (query)
            messages = workflow_output.get("outputs", {}).get("messages", [])
            if len(messages) > 1:
                # Get all messages except the first one (which is the query)
                response_messages = messages[1:]  # Skip first message (query)
                responses = []
                for message in response_messages:
                    if isinstance(message, dict):
                        kwargs = message.get("kwargs", {})
                        content = kwargs.get("content", "")
                        if content:  # Only add non-empty content
                            responses.append(content)
                return "\n\n".join(responses)  # Return concatenated string
            return ""
        except Exception:
            return ""


class ConversationDataExtractor(DataPreservingTransformer):
    """Extract conversation data from agent spans."""

    def __init__(self, entity_types: Optional[List[str]] = None):
        if entity_types is None:
            entity_types = ["agent"]
        self.entity_types = entity_types

    def extract(self, data) -> Dict[str, Any]:
        """Extract conversation from agent spans."""
        # Get original data if available
        original_data = (
            data.get("original_data", data) if isinstance(data, dict) else data
        )

        # Find agent spans
        agent_spans = []
        if isinstance(original_data, list):
            agent_spans = [
                d
                for d in original_data
                if hasattr(d, "entity_type") and d.entity_type in self.entity_types
            ]

        conversation = self._build_conversation(agent_spans)

        return {"conversation": conversation}

    def _build_conversation(self, agent_spans) -> str:
        """Build conversation string from agent spans."""
        if not agent_spans:
            return ""

        conversation_parts = []
        for span in agent_spans:
            if hasattr(span, "input_payload") and hasattr(span, "output_payload"):
                conversation_parts.append(
                    f"INPUT: {span.input_payload}\nOUTPUT: {span.output_payload}"
                )

        return "\n\n".join(conversation_parts)


class GroundTruthEnricher(DataPreservingTransformer):
    """Add ground truth information based on query."""

    def __init__(self, dataset=None):
        self.dataset = dataset

    def extract(self, data) -> Dict[str, Any]:
        query = ""
        if isinstance(data, dict):
            query = data.get("query", "")

        ground_truth = self._search_ground_truth(query, self.dataset)

        return {"ground_truth": ground_truth.get("answer", "No ground truth available")}

    def _search_ground_truth(self, query: str, dataset) -> Dict[str, str]:
        return {"query": "", "answer": ""}


class PromptFormatter(DataTransformer):
    """Format data into a prompt using a template."""

    def __init__(self, prompt_template: str):
        self.prompt_template = prompt_template

    def transform(self, data):
        if not isinstance(data, dict):
            return self.prompt_template

        format_data = data.copy()
        format_data.pop("original_data", None)
        format_data.pop("workflow_span", None)

        try:
            return self.prompt_template.format(**format_data)
        except KeyError:
            missing_keys = {
                key: ""
                for key in [
                    "query",
                    "response",
                    "conversation",
                    "ground_truth",
                    "responses",
                ]
            }
            missing_keys.update(format_data)
            return self.prompt_template.format(**missing_keys)
