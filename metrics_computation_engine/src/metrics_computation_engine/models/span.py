# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class SpanEntity(BaseModel):
    entity_type: Literal["agent", "tool", "llm", "workflow", "other"]
    span_id: str
    entity_name: str
    input_payload: Optional[Dict[str, Any]] = None
    output_payload: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    tool_definition: Optional[Dict[str, Any]] = None
    contains_error: bool
    timestamp: str
    parent_span_id: Optional[str]
    trace_id: Optional[str]
    session_id: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    raw_span_data: Dict[str, Any]
