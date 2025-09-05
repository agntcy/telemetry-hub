import pytest
from collections import Counter
from metrics_computation_engine.metrics.session.agent_to_agent_interactions import (
    AgentToAgentInteractions,
)
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict


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

    traces_by_session = {
        span1.session_id: [span1],
    }
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
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
    traces_by_session = {span2.session_id: [span2, span3, span4]}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
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
    traces_by_session = {span5.session_id: [span5, span6]}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
    assert result.success
    assert result.value == Counter()  # No transition Z -> Z

    # Case 4: None values in Events.Attributes are handled gracefully (robustness test)
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
    traces_by_session = {span2.session_id: [broken_span]}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
    assert result.success  # Now gracefully handles invalid data
    assert result.value == Counter()  # Returns empty counter instead of -1
    assert result.error_message is None  # No error message
