# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Session enrichment transformers for extracting and enriching session data
based on span types and patterns.
"""

from typing import Dict, Any, List
from .base import DataPreservingTransformer
from .execution_tree_transformer import ExecutionTreeTransformer
from ..models.session import SessionEntity


class ConversationDataTransformer(DataPreservingTransformer):
    """
    Extracts conversation data from agent and LLM spans within a session.
    """

    def extract(self, session: SessionEntity) -> Dict[str, Any]:
        """Extract conversation elements from agent and LLM spans."""
        if not isinstance(session, SessionEntity):
            return {}

        conversation_elements = []
        tool_calls = []

        # Process LLM spans for conversation content
        if session.llm_spans:
            for span in session.llm_spans:
                if span.input_payload:
                    # Extract prompts from input
                    for key, value in span.input_payload.items():
                        if key.startswith("gen_ai.prompt") and ".content" in key:
                            role_key = key.replace(".content", ".role")
                            role = span.input_payload.get(role_key, "unknown")
                            conversation_elements.append(
                                {
                                    "role": role,
                                    "content": value,
                                    "span_id": span.span_id,
                                    "timestamp": span.timestamp,
                                }
                            )

                if span.output_payload:
                    # Extract completions from output
                    for key, value in span.output_payload.items():
                        if key.startswith("gen_ai.completion") and ".content" in key:
                            role_key = key.replace(".content", ".role")
                            role = span.output_payload.get(role_key, "assistant")
                            conversation_elements.append(
                                {
                                    "role": role,
                                    "content": value,
                                    "span_id": span.span_id,
                                    "timestamp": span.timestamp,
                                }
                            )

                        # Extract tool calls
                        if key.startswith("gen_ai.completion") and ".tool_calls" in key:
                            if isinstance(value, dict) or (
                                isinstance(value, str) and value.startswith("{")
                            ):
                                try:
                                    import json

                                    tool_call_data = (
                                        json.loads(value)
                                        if isinstance(value, str)
                                        else value
                                    )
                                    tool_calls.append(
                                        {
                                            "data": tool_call_data,
                                            "span_id": span.span_id,
                                            "timestamp": span.timestamp,
                                        }
                                    )
                                except (KeyError, AttributeError, TypeError):
                                    pass

        # Process agent spans for additional conversation context
        if session.agent_spans:
            for span in session.agent_spans:
                if span.input_payload and "value" in span.input_payload:
                    conversation_elements.append(
                        {
                            "role": "user",
                            "content": span.input_payload["value"],
                            "span_id": span.span_id,
                            "timestamp": span.timestamp,
                            "agent_name": span.entity_name,
                        }
                    )

                if span.output_payload and "value" in span.output_payload:
                    conversation_elements.append(
                        {
                            "role": "assistant",
                            "content": span.output_payload["value"],
                            "span_id": span.span_id,
                            "timestamp": span.timestamp,
                            "agent_name": span.entity_name,
                        }
                    )

        # Sort conversation elements by timestamp
        conversation_elements.sort(key=lambda x: x.get("timestamp", ""))

        return {
            "conversation_data": {
                "elements": conversation_elements,
                "tool_calls": tool_calls,
                "total_elements": len(conversation_elements),
                "total_tool_calls": len(tool_calls),
            }
        }


class WorkflowDataTransformer(DataPreservingTransformer):
    """
    Extracts workflow execution patterns and data, including legacy query/response fields.
    """

    def extract(self, session: SessionEntity) -> Dict[str, Any]:
        """Extract workflow execution patterns and data."""
        if not isinstance(session, SessionEntity):
            return {}

        workflow_data = {
            "workflows": [],
            "execution_pattern": [],
            "total_workflows": 0,
            "query": "",
            "response": "",
        }

        if session.workflow_spans:
            workflows = {}

            for span in session.workflow_spans:
                workflow_name = span.entity_name

                if workflow_name not in workflows:
                    workflows[workflow_name] = {
                        "name": workflow_name,
                        "executions": [],
                        "total_executions": 0,
                        "has_errors": False,
                    }

                execution = {
                    "span_id": span.span_id,
                    "timestamp": span.timestamp,
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                    "input_payload": span.input_payload,
                    "output_payload": span.output_payload,
                    "contains_error": span.contains_error,
                    "parent_span_id": span.parent_span_id,
                }

                workflows[workflow_name]["executions"].append(execution)
                workflows[workflow_name]["total_executions"] += 1
                if span.contains_error:
                    workflows[workflow_name]["has_errors"] = True

                # Add to execution pattern
                workflow_data["execution_pattern"].append(
                    {
                        "workflow": workflow_name,
                        "timestamp": span.timestamp,
                        "span_id": span.span_id,
                        "has_error": span.contains_error,
                    }
                )

            # Sort executions by timestamp for each workflow
            for workflow in workflows.values():
                workflow["executions"].sort(key=lambda x: x.get("timestamp", ""))

            # Sort execution pattern by timestamp
            workflow_data["execution_pattern"].sort(
                key=lambda x: x.get("timestamp", "")
            )

            workflow_data["workflows"] = list(workflows.values())
            workflow_data["total_workflows"] = len(workflows)

            # Extract legacy query and response from the latest workflow span
            latest_span = session.workflow_spans[-1]
            workflow_data["query"] = self._extract_query(latest_span)
            workflow_data["response"] = self._extract_response(latest_span)

        return {"workflow_data": workflow_data}

    def _extract_query(self, workflow_span) -> str:
        """Extract query from workflow span input (same logic as WorkflowDataExtractor)."""
        if not workflow_span.input_payload:
            return ""

        try:
            # Try new format first (chat_history)
            chat_history = workflow_span.input_payload.get("inputs", {}).get(
                "chat_history", []
            )
            if chat_history and len(chat_history) > 0:
                first_msg = chat_history[0]
                if isinstance(first_msg, dict) and "message" in first_msg:
                    return first_msg["message"]

            # Fallback: original extraction logic for backward compatibility
            messages = workflow_span.input_payload.get("inputs", {}).get("messages", [])
            if messages and len(messages) > 0:
                user_message = messages[0]
                if isinstance(user_message, list) and len(user_message) > 1:
                    return user_message[1]
        except Exception:
            pass

        return ""

    def _extract_response(self, workflow_span) -> str:
        """Extract response from workflow span output (same logic as WorkflowDataExtractor)."""
        if not workflow_span.output_payload:
            return ""

        try:
            messages = workflow_span.output_payload.get("outputs", {}).get(
                "messages", []
            )
            if messages:
                # Try to extract content from the last message
                for msg in reversed(messages):
                    if isinstance(msg, dict) and "kwargs" in msg:
                        content = msg["kwargs"].get("content", "")
                        if content:
                            return content
                # Fallback: convert entire messages to string
                return str(messages)
        except Exception:
            pass

        return ""


class ToolUsageTransformer(DataPreservingTransformer):
    """
    Extracts tool usage patterns and statistics from tool spans within a session.
    """

    def extract(self, session: SessionEntity) -> Dict[str, Any]:
        """Extract tool usage patterns and statistics."""
        if not isinstance(session, SessionEntity):
            return {}

        tool_data = {
            "tools": {},
            "usage_pattern": [],
            "statistics": {
                "total_tool_calls": 0,
                "unique_tools": 0,
                "failed_calls": 0,
                "success_rate": 0.0,
            },
        }

        if session.tool_spans:
            for span in session.tool_spans:
                tool_name = span.entity_name

                if tool_name not in tool_data["tools"]:
                    tool_data["tools"][tool_name] = {
                        "name": tool_name,
                        "calls": [],
                        "total_calls": 0,
                        "failed_calls": 0,
                        "tool_definition": span.tool_definition,
                    }

                call_data = {
                    "span_id": span.span_id,
                    "timestamp": span.timestamp,
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                    "input_payload": span.input_payload,
                    "output_payload": span.output_payload,
                    "contains_error": span.contains_error,
                    "parent_span_id": span.parent_span_id,
                }

                tool_data["tools"][tool_name]["calls"].append(call_data)
                tool_data["tools"][tool_name]["total_calls"] += 1

                if span.contains_error:
                    tool_data["tools"][tool_name]["failed_calls"] += 1

                # Add to usage pattern
                tool_data["usage_pattern"].append(
                    {
                        "tool": tool_name,
                        "timestamp": span.timestamp,
                        "span_id": span.span_id,
                        "success": not span.contains_error,
                    }
                )

                # Update statistics
                tool_data["statistics"]["total_tool_calls"] += 1
                if span.contains_error:
                    tool_data["statistics"]["failed_calls"] += 1

            # Sort calls by timestamp for each tool
            for tool in tool_data["tools"].values():
                tool["calls"].sort(key=lambda x: x.get("timestamp", ""))

            # Sort usage pattern by timestamp
            tool_data["usage_pattern"].sort(key=lambda x: x.get("timestamp", ""))

            # Calculate final statistics
            tool_data["statistics"]["unique_tools"] = len(tool_data["tools"])
            if tool_data["statistics"]["total_tool_calls"] > 0:
                success_calls = (
                    tool_data["statistics"]["total_tool_calls"]
                    - tool_data["statistics"]["failed_calls"]
                )
                tool_data["statistics"]["success_rate"] = (
                    success_calls / tool_data["statistics"]["total_tool_calls"]
                )

        return {"tool_data": tool_data}


class GraphDataTransformer(DataPreservingTransformer):
    """
    Extracts graph-related attributes from graph entity spans within a session.
    """

    def extract(self, session: SessionEntity) -> Dict[str, Any]:
        """Extract graph data from graph entity spans."""
        if not isinstance(session, SessionEntity):
            return {}

        result = {}

        # Use graph_spans if available, otherwise filter from all spans
        graph_spans = session.graph_spans or [
            span for span in session.spans if span.entity_type == "graph"
        ]

        if graph_spans:
            # Process the first graph span found (assuming one graph per session)
            graph_span = graph_spans[0]

            if graph_span.raw_span_data:
                # Look for attributes in SpanAttributes (the correct location)
                attributes = graph_span.raw_span_data.get("SpanAttributes", {})

                # Extract graph_determinism
                if "gen_ai.ioa.graph_determinism_score" in attributes:
                    result["graph_determinism"] = float(
                        attributes["gen_ai.ioa.graph_determinism_score"]
                    )

                # Extract graph_dynamism
                if "gen_ai.ioa.graph_dynamism" in attributes:
                    result["graph_dynamism"] = float(
                        attributes["gen_ai.ioa.graph_dynamism"]
                    )

                # Extract graph
                if "gen_ai.ioa.graph" in attributes:
                    result["graph"] = attributes["gen_ai.ioa.graph"]

        return result


class AgentTransitionTransformer(DataPreservingTransformer):
    """
    Extracts agent transitions and transition counts from agent spans.

    This transformer replicates the agent transition logic from dal_legacy
    to compute agent_transitions and agent_transition_counts for sessions.
    """

    def extract(self, session: SessionEntity) -> Dict[str, Any]:
        """Extract agent transitions from spans with Events.Attributes."""
        from collections import Counter

        if not isinstance(session, SessionEntity):
            return {}

        agent_events = []

        # Extract agent events from spans with Events.Attributes (same logic as dal_legacy)
        for span in session.spans:
            if (
                hasattr(span, "raw_span_data")
                and span.raw_span_data
                and (
                    span.raw_span_data.get("Events.Attributes")
                    or span.raw_span_data.get("EventsAttributes")
                )
            ):
                events = span.raw_span_data.get(
                    "Events.Attributes"
                ) or span.raw_span_data.get("EventsAttributes", [])
                if (
                    len(events) > 0
                    and isinstance(events[0], dict)
                    and "agent_name" in events[0]
                ):
                    agent_name = events[0]["agent_name"]
                    agent_events.append((span.span_id, agent_name))

        if not agent_events:
            return {"agent_transitions": [], "agent_transition_counts": Counter()}

        # Extract just the agent names for transition analysis
        agent_names = [event[1] for event in agent_events]

        # Compute transitions (same logic as dal_legacy)
        transitions = []
        for i in range(len(agent_names) - 1):
            if agent_names[i] != agent_names[i + 1]:
                transition = f"{agent_names[i]} -> {agent_names[i + 1]}"
                transitions.append(transition)

        return {
            "agent_transitions": transitions,
            "agent_transition_counts": Counter(transitions),
        }


class EndToEndAttributesTransformer(DataPreservingTransformer):
    """
    Transformer for extracting session-level input_query and final_response
    from LLM span conversation history.
    """

    def extract(self, session: SessionEntity) -> Dict[str, Any]:
        """Extract input_query and final_response from LLM spans."""
        if not isinstance(session, SessionEntity):
            return {}

        if not session.llm_spans:
            return {}

        # Use the latest invocation of the LLM which should maintain the whole chat history
        from datetime import datetime

        try:
            latest_span = max(
                session.llm_spans, key=lambda x: datetime.fromisoformat(x.timestamp)
            )
        except (ValueError, AttributeError):
            # Fallback if timestamp parsing fails
            latest_span = session.llm_spans[-1]

        if not latest_span.input_payload:
            return {}

        # Extract prompt indices
        indexes = {
            int(key.split(".")[2])
            for key in latest_span.input_payload.keys()
            if key.startswith("gen_ai.prompt.")
            and len(key.split(".")) > 2
            and key.split(".")[2].isdigit()
        }

        input_query, final_response = None, None

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
                if content and not input_query:  # Only set the first user input
                    input_query = content
                    break  # Stop after finding the first user input

        # Extract final_response from all LLM spans, looking for meaningful responses
        # We need to find the last meaningful assistant response, not just the last completion
        for span in sorted(
            session.llm_spans,
            key=lambda x: datetime.fromisoformat(x.timestamp),
            reverse=True,
        ):
            if span.output_payload:
                completion_indexes = {
                    int(key.split(".")[2])
                    for key in span.output_payload.keys()
                    if key.startswith("gen_ai.completion.")
                    and len(key.split(".")) > 2
                    and key.split(".")[2].isdigit()
                }

                # Look for meaningful completions (not just system control messages)
                for i in sorted(completion_indexes, reverse=True):
                    content_key = f"gen_ai.completion.{i}.content"
                    role_key = f"gen_ai.completion.{i}.role"

                    if content_key in span.output_payload:
                        content = span.output_payload[content_key]
                        role = span.output_payload.get(role_key, "").lower()

                        # Skip if content is empty or looks like system control
                        if not content:
                            continue

                        content_str = str(content).strip()

                        # Skip obvious system control messages and analysis content
                        if (
                            # JSON control messages (both single and double quotes)
                            content_str.startswith('{"next":')
                            or content_str.startswith(
                                "{'next':"
                            )  # Single quote version
                            or content_str == '{"next": "FINISH"}'
                            or content_str
                            == "{'next': 'FINISH'}"  # Single quote version
                            or content_str.startswith('{"next": "')
                            or content_str.startswith(
                                "{'next': '"
                            )  # Single quote version
                            or
                            # Short responses
                            len(content_str) < 10  # Skip very short responses
                            or
                            # Analysis content patterns (more specific)
                            content_str.lower().startswith("the text contains")
                            or content_str.lower().startswith("the word ")
                            or "text contains" in content_str.lower()
                            or
                            # Only filter if it's clearly analysis content, not just any text with "next"/"finish"
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
                        ):
                            continue

                        # This looks like a meaningful response
                        if role == "assistant" or not role:  # Assistant or unknown role
                            final_response = content_str
                            break

                # If we found a meaningful response, stop looking
                if final_response:
                    break

        result = {}
        if input_query:
            result["input_query"] = str(input_query)
        if final_response:
            result["final_response"] = str(final_response)

        return result


class SessionEnrichmentPipeline:
    """
    Pipeline for enriching session data with conversation, workflow, and tool usage data.
    """

    def __init__(self):
        self.transformers = [
            ConversationDataTransformer(),
            WorkflowDataTransformer(),  # Now includes both modern and legacy fields
            ToolUsageTransformer(),
            GraphDataTransformer(),
            AgentTransitionTransformer(),  # Add agent transition computation
            EndToEndAttributesTransformer(),  # Add input_query and final_response extraction
            ExecutionTreeTransformer(),
        ]

    def enrich_session(self, session: SessionEntity) -> SessionEntity:
        """
        Enrich a single session with data from all transformers.

        Args:
            session: SessionEntity to enrich

        Returns:
            Enriched SessionEntity with additional data fields populated
        """
        # Start with the original session data
        enriched_data = {}

        # Apply each transformer
        for transformer in self.transformers:
            transformer_result = transformer.transform(session)
            if isinstance(transformer_result, dict):
                enriched_data.update(transformer_result)

        # Create a new session with the enriched data
        session_dict = session.model_dump()
        session_dict.update(enriched_data)

        return SessionEntity(**session_dict)

    def enrich_sessions(self, sessions: List[SessionEntity]) -> List[SessionEntity]:
        """
        Enrich multiple sessions.

        Args:
            sessions: List of SessionEntity objects to enrich

        Returns:
            List of enriched SessionEntity objects
        """
        return [self.enrich_session(session) for session in sessions]
