import pytest
from collections import Counter
from metrics_computation_engine.metrics.session.agent_to_tool_interactions import (
    AgentToToolInteractions,
)
from metrics_computation_engine.models.span import SpanEntity


@pytest.mark.asyncio
async def test_agent_to_tool_interactions():
    metric = AgentToToolInteractions()

    # Case 1: No tool spans
    result = await metric.compute([])
    assert result.success
    assert result.value == Counter()

    # Case 2: One tool span with valid attributes
    span1 = SpanEntity(
        entity_type="tool",
        span_id="1",
        entity_name="ToolX",
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
    result = await metric.compute([span1])
    assert result.success
    assert result.value == Counter({"(Agent: AgentA) -> (Tool: ToolX)": 1})

    # Case 3: Two spans, same transition
    span2 = SpanEntity(
        entity_type="tool",
        span_id="2",
        entity_name="ToolX",
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
    result = await metric.compute([span1, span2])
    assert result.success
    assert result.value == Counter({"(Agent: AgentA) -> (Tool: ToolX)": 2})

    # Case 4: Different agent-tool pair
    span3 = SpanEntity(
        entity_type="tool",
        span_id="3",
        entity_name="ToolY",
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
    result = await metric.compute([span1, span2, span3])
    assert result.success
    assert result.value == Counter(
        {"(Agent: AgentA) -> (Tool: ToolX)": 2, "(Agent: AgentB) -> (Tool: ToolY)": 1}
    )

    # Case 5: Invalid span attributes
    span4 = SpanEntity(
        entity_type="tool",
        span_id="4",
        entity_name="ToolZ",
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
    result = await metric.compute([span4])
    assert not result.success
    assert result.value == -1
    assert isinstance(result.error_message, Exception)
