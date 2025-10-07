# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel


class SpanEntity(BaseModel):
    entity_type: Literal["agent", "tool", "llm", "workflow", "graph", "task", "other"]
    span_id: str
    entity_name: str
    app_name: str
    agent_id: Optional[str] = None
    input_payload: Optional[Dict[str, Any]] = None
    output_payload: Optional[Dict[str, Any]] = None
    expected_output: Optional[Union[str, Dict[str, Any], List[Dict[str, Any]]]] = None
    message: Optional[str] = None
    tool_definition: Optional[Dict[str, Any]] = None
    contains_error: bool
    timestamp: str
    parent_span_id: Optional[str] = None
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration: Optional[float] = None  # Duration in milliseconds
    attrs: Optional[Dict[str, Any]] = None
    raw_span_data: Dict[str, Any]
