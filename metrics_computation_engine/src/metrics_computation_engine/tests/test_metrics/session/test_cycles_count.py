# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

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

    session_entity = SessionEntity(session_id=spans[0].session_id, spans=spans)
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
    session_entity = SessionEntity(session_id=spans[0].session_id, spans=spans)
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == 1


@pytest.mark.asyncio
async def test_cycles_count_invalid_input_handling():
    """Case 3: Compute should gracefully handle unexpected data without crashing."""
    metric = CyclesCount()

    session_entity = SessionEntity(
        session_id="abc",
        spans=[],  # no spans at all
    )
    result = await metric.compute(session_entity)

    assert result.success
    assert result.value == 0


def make_agent_span(entity_type, entity_name, contains_error, span_id, agent_id):
    """Create a span with agent attribution for testing agent-level computation."""
    return SpanEntity(
        entity_type=entity_type,
        contains_error=contains_error,
        span_id=span_id,
        entity_name=entity_name,
        app_name="example_app",
        timestamp="2024-01-01T00:00:00Z",
        parent_span_id="parent",
        trace_id="trace123",
        session_id="session123",
        start_time="1234567890.0",
        end_time="1234567891.0",
        raw_span_data={"SpanAttributes": {"agent_id": agent_id}} if agent_id else {},
    )


def setup_session(session):
    """Ensure session has execution tree for agent_stats to work."""
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree

    if not hasattr(session, "execution_tree") or session.execution_tree is None:
        session.execution_tree = ExecutionTree()
    return session


@pytest.mark.asyncio
async def test_cycles_count_agent_computation_empty_session():
    """Test agent computation with empty session."""
    metric = CyclesCount()

    session_entity = SessionEntity(session_id="session123", spans=[])
    session_entity = setup_session(session_entity)

    results = await metric.compute_with_dispatch(session_entity, agent_computation=True)

    # Should return empty list for no agents
    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_cycles_count_agent_computation_single_agent():
    """Test agent computation with single agent having cycles."""
    metric = CyclesCount()

    # Create spans for one agent with a cycle pattern
    spans = [
        make_agent_span("agent", "search_agent", False, "agent1", "search_agent"),
        make_agent_span("tool", "web_search", False, "tool1", "search_agent"),
        make_agent_span("agent", "search_agent", False, "agent2", "search_agent"),
        make_agent_span("tool", "web_search", False, "tool2", "search_agent"),
        make_agent_span("tool", "api_call", False, "tool3", "search_agent"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute_with_dispatch(session_entity, agent_computation=True)

    # Should return list with one agent result
    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.success
    assert result.aggregation_level == "agent"
    assert result.metadata["agent_id"] == "search_agent"
    assert result.value == 1  # One cycle detected


@pytest.mark.asyncio
async def test_cycles_count_agent_computation_multiple_agents():
    """Test agent computation with multiple agents."""
    metric = CyclesCount()

    # Create spans for two different agents
    spans = [
        # Agent 1 with cycle pattern
        make_agent_span("agent", "search_agent", False, "agent1", "search_agent"),
        make_agent_span("tool", "web_search", False, "tool1", "search_agent"),
        make_agent_span("agent", "search_agent", False, "agent2", "search_agent"),
        make_agent_span("tool", "web_search", False, "tool2", "search_agent"),
        # Agent 2 with no cycles
        make_agent_span("agent", "data_agent", False, "agent3", "data_agent"),
        make_agent_span("tool", "data_fetch", False, "tool3", "data_agent"),
        make_agent_span("tool", "data_store", False, "tool4", "data_agent"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute_with_dispatch(session_entity, agent_computation=True)

    # Should return results for both agents
    assert isinstance(results, list)
    assert len(results) == 2

    # Find results by agent_id
    search_agent_result = next(
        (r for r in results if r.metadata["agent_id"] == "search_agent"), None
    )
    data_agent_result = next(
        (r for r in results if r.metadata["agent_id"] == "data_agent"), None
    )

    assert search_agent_result is not None
    assert data_agent_result is not None

    assert search_agent_result.success
    assert search_agent_result.value == 1  # Has cycle

    assert data_agent_result.success
    assert data_agent_result.value == 0  # No cycles


@pytest.mark.asyncio
async def test_cycles_count_supports_agent_computation():
    """Test that the metric indicates it supports agent computation."""
    metric = CyclesCount()
    assert metric.supports_agent_computation()


@pytest.mark.asyncio
async def test_cycles_count_backward_compatibility():
    """Test that session-level computation still works without context parameter."""
    metric = CyclesCount()

    spans = [
        SpanEntity(
            entity_type="agent",
            span_id="1",
            entity_name="test_agent",
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
            entity_name="test_tool",
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
    ]

    session_entity = SessionEntity(session_id=spans[0].session_id, spans=spans)

    # Test without context (should default to session-level)
    result = await metric.compute(session_entity)
    assert result.success
    assert result.aggregation_level == "session"
    assert isinstance(result.value, (int, float))

    # Test with explicit session-level context
    result = await metric.compute(session_entity, context={"agent_computation": False})
    assert result.success
    assert result.aggregation_level == "session"
    assert isinstance(result.value, (int, float))
