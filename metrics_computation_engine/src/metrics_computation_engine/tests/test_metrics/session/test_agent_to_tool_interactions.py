# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from collections import Counter
from metrics_computation_engine.metrics.session.agent_to_tool_interactions import (
    AgentToToolInteractions,
)
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import SessionEntity


@pytest.mark.asyncio
async def test_agent_to_tool_interactions():
    metric = AgentToToolInteractions()

    # Case 1: No tool spans
    session_entity = SessionEntity(session_id="s1", spans=[])
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == Counter()

    # Case 2: One tool span with valid attributes
    span1 = SpanEntity(
        entity_type="tool",
        span_id="1",
        entity_name="ToolX",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={
            "SpanAttributes": {
                "ioa_observe.workflow.name": "AgentA",
                "traceloop.entity.name": "ToolX",
            }
        },
    )
    session_entity = SessionEntity(session_id=span1.session_id, spans=[span1])
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == Counter({"(Agent: AgentA) -> (Tool: ToolX)": 1})

    # Case 3: Two spans, same transition
    span2 = SpanEntity(
        entity_type="tool",
        span_id="2",
        entity_name="ToolX",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={
            "SpanAttributes": {
                "ioa_observe.workflow.name": "AgentA",
                "traceloop.entity.name": "ToolX",
            }
        },
    )
    session_entity = SessionEntity(session_id=span1.session_id, spans=[span1, span2])
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == Counter({"(Agent: AgentA) -> (Tool: ToolX)": 2})

    # Case 4: Different agent-tool pair
    span3 = SpanEntity(
        entity_type="tool",
        span_id="3",
        entity_name="ToolY",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={
            "SpanAttributes": {
                "ioa_observe.workflow.name": "AgentB",
                "traceloop.entity.name": "ToolY",
            }
        },
    )
    session_entity = SessionEntity(
        session_id=span1.session_id, spans=[span1, span2, span3]
    )
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == Counter(
        {"(Agent: AgentA) -> (Tool: ToolX)": 2, "(Agent: AgentB) -> (Tool: ToolY)": 1}
    )

    # Case 5: Invalid span attributes
    span4 = SpanEntity(
        entity_type="tool",
        span_id="4",
        entity_name="ToolZ",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={
            "SpanAttributes": {}  # Missing required keys
        },
    )
    session_entity = SessionEntity(session_id=span4.session_id, spans=[span4])
    result = await metric.compute(session_entity)
    assert not result.success
    assert result.value == -1
    assert isinstance(result.error_message, Exception)
