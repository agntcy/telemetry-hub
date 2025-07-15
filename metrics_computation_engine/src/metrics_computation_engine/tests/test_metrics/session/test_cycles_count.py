import pytest
from metrics_computation_engine.metrics.session.cycles import CyclesCount
from metrics_computation_engine.models.span import SpanEntity


@pytest.mark.asyncio
async def test_cycles_count_no_agents_or_tools():
    """Case 1: No spans with agent/tool entity_type, should return 0 cycles."""
    metric = CyclesCount()
    spans = [
        SpanEntity(
            entity_type="llm",
            span_id="1",
            entity_name="NotRelevant",
            timestamp="",
            parent_span_id=None,
            trace_id="t1",
            session_id="s1",
            start_time=None,
            end_time=None,
            raw_span_data={},
            contains_error=False,
        )
    ]
    result = await metric.compute(spans)
    assert result.success
    assert result.value == 0


@pytest.mark.asyncio
async def test_cycles_count_with_one_cycle():
    """
    Case 2: A → B → A → B is a repeating pattern, should be identified as one cycle.
    """
    metric = CyclesCount()
    spans = [
        SpanEntity(
            entity_type="agent",
            span_id="1",
            entity_name="A",
            timestamp="",
            parent_span_id=None,
            trace_id="t1",
            session_id="s1",
            start_time=None,
            end_time=None,
            raw_span_data={},
            contains_error=False,
        ),
        SpanEntity(
            entity_type="tool",
            span_id="2",
            entity_name="B",
            timestamp="",
            parent_span_id=None,
            trace_id="t1",
            session_id="s1",
            start_time=None,
            end_time=None,
            raw_span_data={},
            contains_error=False,
        ),
        SpanEntity(
            entity_type="agent",
            span_id="3",
            entity_name="A",
            timestamp="",
            parent_span_id=None,
            trace_id="t1",
            session_id="s1",
            start_time=None,
            end_time=None,
            raw_span_data={},
            contains_error=False,
        ),
        SpanEntity(
            entity_type="tool",
            span_id="4",
            entity_name="B",
            timestamp="",
            parent_span_id=None,
            trace_id="t1",
            session_id="s1",
            start_time=None,
            end_time=None,
            raw_span_data={},
            contains_error=False,
        ),
    ]
    result = await metric.compute(spans)
    assert result.success
    assert result.value == 1


@pytest.mark.asyncio
async def test_cycles_count_invalid_input_handling():
    """Case 3: Compute should gracefully handle unexpected data without crashing."""
    metric = CyclesCount()
    result = await metric.compute([])  # no spans at all
    assert result.success
    assert result.value == 0
