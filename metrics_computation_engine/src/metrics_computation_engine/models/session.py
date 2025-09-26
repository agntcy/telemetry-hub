# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict, List, Optional
from collections import Counter
from pydantic import BaseModel

from metrics_computation_engine.models.span import SpanEntity


class ConversationElement(BaseModel):
    """Represents a single turn in a conversation."""

    role: str
    content: str


class ToolCall(BaseModel):
    """Represents a tool call with all necessary information."""

    name: str
    description: str
    input_parameters: Dict[str, Any]
    output: Dict[str, Any]


class SessionEntity(BaseModel):
    """
    Pure data model for session-level entity.
    Contains only the fields that are actually used by metrics.
    """

    # Core session metadata
    session_id: str
    spans: List[SpanEntity]
    app_name: str = ""

    # End-to-End results
    input_query: str = ""
    final_response: str = ""
    ground_truth: str = "No ground truth available"

    # Timing information
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Entity-specific spans (used by metrics for filtering)
    agent_spans: Optional[List[SpanEntity]] = None
    tool_spans: Optional[List[SpanEntity]] = None
    llm_spans: Optional[List[SpanEntity]] = None

    # Data extracted by transformers (used by metrics)
    conversation_data: Optional[Dict[str, Any]] = None

    # Agent interaction data (needed by AgentToAgentInteractions)
    agent_transitions: Optional[List[str]] = None
    agent_transition_counts: Optional[Counter] = None

    conversation_elements: Optional[List[ConversationElement]] = None

    tool_calls: Optional[List[ToolCall]] = None

    user_input: Optional[str] = None
    final_response: Optional[str] = None
