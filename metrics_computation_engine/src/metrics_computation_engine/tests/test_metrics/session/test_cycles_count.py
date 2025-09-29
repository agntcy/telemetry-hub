import pytest
from metrics_computation_engine.metrics.session.cycles import CyclesCount
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import SessionEntity


@pytest.mark.asyncio
async def test_cycles_count_no_agents_or_tools():
    """Case 1: No spans with agent/tool entity_type, should return 0 cycles."""
    metric = CyclesCount()

    default_input = {
        "gen_ai.prompt.0.content": "You are a travel agent",
        "gen_ai.prompt.0.role": "system",
        "gen_ai.prompt.1.content": "Help me plan a trip to Paris",
        "gen_ai.prompt.1.role": "user",
    }

    default_output = {
        "gen_ai.prompt.0.content": "You are a travel agent",
        "gen_ai.prompt.0.role": "system",
        "gen_ai.prompt.1.content": "Help me plan a trip to Paris",
        "gen_ai.prompt.1.role": "user",
        "gen_ai.prompt.2.content": "I'd be happy to help you plan your trip to Paris! Here's a suggested itinerary...",
        "gen_ai.prompt.2.role": "user",
    }

    spans = [
        SpanEntity(
            entity_type="llm",
            span_id="1",
            entity_name="NotRelevant",
            app_name="example_app",
            timestamp="2025-06-20 21:37:02.832759",
            parent_span_id=None,
            trace_id="t1",
            session_id="s1",
            start_time=None,
            input_payload=default_input,
            output_payload=default_output,
            end_time=None,
            raw_span_data={},
            contains_error=False,
        )
    ]

    session_entity = SessionEntity(
        session_id=spans[0].session_id,
        spans=spans
    )
    result = await metric.compute(session_entity)
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
            app_name="example_app",
            timestamp="2025-06-20 21:37:02.832759",
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
            app_name="example_app",
            timestamp="2025-06-20 21:40:02.832759",
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
            app_name="example_app",
            timestamp="2025-06-20 21:45:02.832759",
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
            app_name="example_app",
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
    session_entity = SessionEntity(
        session_id=spans[0].session_id,
        spans=spans
    )
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == 1


@pytest.mark.asyncio
async def test_cycles_count_invalid_input_handling():
    """Case 3: Compute should gracefully handle unexpected data without crashing."""
    metric = CyclesCount()

    session_entity = SessionEntity(
        session_id="abc",
        spans=[]  # no spans at all
    )
    result = await metric.compute(session_entity)

    assert result.success
    assert result.value == 0
