# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Enhanced AgentView with conversation context caching.
This extends the existing AgentView to include agent-specific conversation data.
"""

from typing import Dict, Any, TYPE_CHECKING
from metrics_computation_engine.entities.models.session import AgentView

if TYPE_CHECKING:
    from metrics_computation_engine.entities.models.session import SessionEntity


class EnhancedAgentView(AgentView):
    """
    Extended AgentView with cached agent-specific conversation context.

    This class leverages the existing conversation_data logic but applies it
    to agent-specific spans, with proper caching to avoid recomputation.
    """

    def __init__(self, agent_name: str, session: "SessionEntity"):
        """Initialize with existing AgentView caching + conversation context."""
        super().__init__(agent_name, session)

        # Cached conversation data (computed lazily)
        self._agent_conversation_data = None
        self._agent_conversation_text = None

    @property
    def conversation_data(self) -> Dict[str, Any]:
        """
        Get agent-specific conversation data with caching.

        Reuses existing ConversationDataTransformer logic but applied to agent spans only.
        """
        if self._agent_conversation_data is None:
            self._agent_conversation_data = self._build_agent_conversation_data()
        return self._agent_conversation_data

    @property
    def conversation_text(self) -> str:
        """
        Get agent conversation as formatted text for Context Preservation evaluation.

        Returns chronological conversation including agent communications,
        LLM reasoning, and tool interactions.
        """
        if self._agent_conversation_text is None:
            self._agent_conversation_text = self._build_conversation_text()
        return self._agent_conversation_text

    def _build_agent_conversation_data(self) -> Dict[str, Any]:
        """
        Build conversation data for this agent using existing transformer logic.

        This leverages the same extraction patterns as ConversationDataTransformer
        but applies them to agent-specific spans only.
        """
        conversation_elements = []
        tool_calls = []

        # Process LLM spans for this agent (reuse existing logic)
        for span in self.llm_spans:
            if span.input_payload:
                # Extract prompts from input (same logic as ConversationDataTransformer)
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
                                "agent_name": self.agent_name,
                            }
                        )

            if span.output_payload:
                # Extract completions from output (same logic as ConversationDataTransformer)
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
                                "agent_name": self.agent_name,
                            }
                        )

                    # Extract tool calls (same logic as ConversationDataTransformer)
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
                                        "agent_name": self.agent_name,
                                    }
                                )
                            except (KeyError, AttributeError, TypeError):
                                pass

        # Process agent spans (same logic as ConversationDataTransformer)
        agent_spans = [s for s in self.all_spans if s.entity_type == "agent"]
        for span in agent_spans:
            if span.input_payload and "value" in span.input_payload:
                conversation_elements.append(
                    {
                        "role": "user",
                        "content": span.input_payload["value"],
                        "span_id": span.span_id,
                        "timestamp": span.timestamp,
                        "agent_name": self.agent_name,
                    }
                )

            if span.output_payload and "value" in span.output_payload:
                conversation_elements.append(
                    {
                        "role": "assistant",
                        "content": span.output_payload["value"],
                        "span_id": span.span_id,
                        "timestamp": span.timestamp,
                        "agent_name": self.agent_name,
                    }
                )

        # Include tool interactions for complete context
        for span in self.tool_spans:
            if span.input_payload:
                conversation_elements.append(
                    {
                        "role": "tool_input",
                        "content": f"Tool call to {span.entity_name}: {span.input_payload}",
                        "span_id": span.span_id,
                        "timestamp": span.timestamp,
                        "agent_name": self.agent_name,
                    }
                )

            if span.output_payload:
                conversation_elements.append(
                    {
                        "role": "tool_output",
                        "content": f"Tool {span.entity_name} result: {span.output_payload}",
                        "span_id": span.span_id,
                        "timestamp": span.timestamp,
                        "agent_name": self.agent_name,
                    }
                )

        # Sort by timestamp (same as ConversationDataTransformer)
        conversation_elements.sort(key=lambda x: x.get("timestamp", ""))

        return {
            "elements": conversation_elements,
            "tool_calls": tool_calls,
            "total_elements": len(conversation_elements),
            "total_tool_calls": len(tool_calls),
        }

    def _build_conversation_text(self) -> str:
        """
        Build formatted conversation text for LLM evaluation.

        Creates a chronological text representation suitable for Context Preservation
        evaluation, including all agent interactions, reasoning, and tool usage.
        """
        conversation_data = self.conversation_data
        elements = conversation_data.get("elements", [])

        if not elements:
            return ""

        # Build formatted conversation
        conversation_lines = []
        for element in elements:
            role = element.get("role", "unknown")
            content = element.get("content", "")

            if role == "user":
                conversation_lines.append(f"User: {content}")
            elif role == "assistant":
                conversation_lines.append(f"Assistant: {content}")
            elif role == "system":
                conversation_lines.append(f"System: {content}")
            elif role == "tool_input":
                conversation_lines.append(f"[{content}]")
            elif role == "tool_output":
                conversation_lines.append(f"[{content}]")

        return "\n".join(conversation_lines)


# Extension method for SessionEntity to create enhanced agent views
def get_enhanced_agent_view(
    session: "SessionEntity", agent_name: str
) -> EnhancedAgentView:
    """
    Factory method to create enhanced agent views with conversation caching.

    This can be added to SessionEntity or used as a standalone factory.
    """
    return EnhancedAgentView(agent_name, session)
