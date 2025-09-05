import pytest
from metrics_computation_engine.metrics.session.tool_error_rate import ToolErrorRate
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict


def make_dummy_span(entity_type, contains_error, span_id):
    return SpanEntity(
        entity_type=entity_type,
        contains_error=contains_error,
        span_id=span_id,
        entity_name="dummy_tool",
        timestamp="2024-01-01T00:00:00Z",
        parent_span_id="parent",
        trace_id="trace123",
        session_id="session123",
        start_time="1234567890.0",
        end_time="1234567891.0",
        raw_span_data={},
    )


@pytest.mark.asyncio
async def test_tool_error_rate_all_cases():
    metric = ToolErrorRate()

    # Case 1: No tool spans
    traces_by_session = {"abc": []}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
    assert result.value == 0
    assert result.success

    # Case 2: All tool spans, no errors
    spans = [
        make_dummy_span("tool", False, "1"),
        make_dummy_span("tool", False, "2"),
    ]
    traces_by_session = {spans[0].session_id: spans}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
    assert result.value == 0
    assert result.success

    # Case 3: All tool spans, all errors
    spans = [
        make_dummy_span("tool", True, "1"),
        make_dummy_span("tool", True, "2"),
    ]
    traces_by_session = {spans[0].session_id: spans}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
    assert result.value == 100
    assert result.success

    # Case 4: Mixed
    spans = [
        make_dummy_span("tool", False, "1"),
        make_dummy_span("tool", True, "2"),
    ]
    traces_by_session = {spans[0].session_id: spans}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())
    assert result.value == 50
    assert result.success
