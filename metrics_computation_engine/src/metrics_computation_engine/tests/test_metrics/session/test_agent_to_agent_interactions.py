import pytest
from collections import Counter
from metrics_computation_engine.metrics.session.agent_to_agent_interactions import (
    AgentToAgentInteractions,
)
from metrics_computation_engine.models.span import SpanEntity


@pytest.mark.asyncio
async def test_agent_to_agent_interactions():
    metric = AgentToAgentInteractions()

    # Case 1: No Events.Attributes
    span1 = SpanEntity(
        entity_type="agent",
        span_id="1",
        entity_name="AgentA",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": []},
    )
    result = await metric.compute([span1])
    assert result.success
    assert result.value == Counter()

    # Case 2: Different agent transitions
    span2 = SpanEntity(
        entity_type="agent",
        span_id="2",
        entity_name="AgentB",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "A"}]},
    )
    span3 = SpanEntity(
        entity_type="agent",
        span_id="3",
        entity_name="AgentC",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "B"}]},
    )
    span4 = SpanEntity(
        entity_type="agent",
        span_id="4",
        entity_name="AgentD",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "C"}]},
    )
    result = await metric.compute([span2, span3, span4])
    assert result.success
    assert result.value == Counter(
        {
            "A -> B": 1,
            "B -> C": 1,
        }
    )

    # Case 3: Same agent repeated (no transition)
    span5 = SpanEntity(
        entity_type="agent",
        span_id="5",
        entity_name="AgentX",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "Z"}]},
    )
    span6 = SpanEntity(
        entity_type="agent",
        span_id="6",
        entity_name="AgentX",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "Z"}]},
    )
    result = await metric.compute([span5, span6])
    assert result.success
    assert result.value == Counter()  # No transition Z -> Z

    # Case 4: Invalid structure triggers error
    broken_span = SpanEntity(
        entity_type="agent",
        span_id="7",
        entity_name="AgentFail",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": None},  # Invalid type
    )
    result = await metric.compute([broken_span])
    assert not result.success
    assert result.value == -1
    assert isinstance(result.error_message, Exception)
