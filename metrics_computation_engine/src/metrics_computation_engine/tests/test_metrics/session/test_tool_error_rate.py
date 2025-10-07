# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from metrics_computation_engine.metrics.session.tool_error_rate import ToolErrorRate
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.execution_tree import ExecutionTree
from metrics_computation_engine.models.eval import MetricResult


def setup_session(session):
    """Ensure session has execution tree for agent_stats to work."""
    if not hasattr(session, "execution_tree") or session.execution_tree is None:
        session.execution_tree = ExecutionTree()
    return session


def make_dummy_span(entity_type, contains_error, span_id):
    return SpanEntity(
        entity_type=entity_type,
        contains_error=contains_error,
        span_id=span_id,
        entity_name="dummy_tool",
        app_name="example_app",
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
    session_entity = SessionEntity(session_id="abc", spans=[])
    result = await metric.compute(session_entity)
    assert result.value == 0
    assert result.success

    # Case 2: All tool spans, no errors
    spans = [
        make_dummy_span("tool", False, "1"),
        make_dummy_span("tool", False, "2"),
    ]
    session_entity = SessionEntity(session_id=spans[0].session_id, spans=spans)
    result = await metric.compute(session_entity)
    assert result.value == 0
    assert result.success

    # Case 3: All tool spans, all errors
    spans = [
        make_dummy_span("tool", True, "1"),
        make_dummy_span("tool", True, "2"),
    ]
    session_entity = SessionEntity(session_id=spans[0].session_id, spans=spans)
    result = await metric.compute(session_entity)
    assert result.value == 100
    assert result.success

    # Case 4: Mixed
    spans = [
        make_dummy_span("tool", False, "1"),
        make_dummy_span("tool", True, "2"),
    ]
    session_entity = SessionEntity(session_id=spans[0].session_id, spans=spans)
    result = await metric.compute(session_entity)
    assert result.value == 50
    assert result.success


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
        raw_span_data={},
        attrs={"agent_id": agent_id} if agent_id else {},
    )


@pytest.mark.asyncio
async def test_tool_error_rate_agent_computation_empty_session():
    """Test agent computation with session that has no agents."""
    metric = ToolErrorRate()

    # Empty session
    session_entity = SessionEntity(session_id="empty", spans=[])
    session_entity = setup_session(session_entity)
    results = await metric.compute(session_entity, context={"agent_computation": True})

    # Should return empty list for no agents
    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_tool_error_rate_agent_computation_single_agent():
    """Test agent computation with single agent."""
    metric = ToolErrorRate()

    # Create spans for one agent with tools
    spans = [
        make_agent_span("agent", "search_agent", False, "agent1", "search_agent"),
        make_agent_span("tool", "web_search", False, "tool1", "search_agent"),
        make_agent_span("tool", "api_call", True, "tool2", "search_agent"),
        make_agent_span("tool", "data_fetch", False, "tool3", "search_agent"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute(session_entity, context={"agent_computation": True})

    # Should return list with one agent result
    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.success
    assert result.aggregation_level == "agent"
    assert result.metadata["agent_id"] == "search_agent"
    assert result.metadata["agent_tool_calls"] == 3
    assert result.metadata["agent_tool_errors"] == 1
    assert abs(result.value - 33.33) < 0.1  # 1 error out of 3 tools ≈ 33.33%


@pytest.mark.asyncio
async def test_tool_error_rate_agent_computation_multiple_agents():
    """Test agent computation with multiple agents."""
    metric = ToolErrorRate()

    # Create spans for two agents with different error rates
    spans = [
        # Agent 1: search_agent (2 tools, 1 error = 50% error rate)
        make_agent_span("agent", "search_agent", False, "agent1", "search_agent"),
        make_agent_span("tool", "web_search", False, "tool1", "search_agent"),
        make_agent_span("tool", "api_call", True, "tool2", "search_agent"),
        # Agent 2: analysis_agent (3 tools, 0 errors = 0% error rate)
        make_agent_span("agent", "analysis_agent", False, "agent2", "analysis_agent"),
        make_agent_span("tool", "data_processor", False, "tool3", "analysis_agent"),
        make_agent_span("tool", "chart_generator", False, "tool4", "analysis_agent"),
        make_agent_span("tool", "report_writer", False, "tool5", "analysis_agent"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute(session_entity, context={"agent_computation": True})

    # Should return list with two agent results
    assert isinstance(results, list)
    assert len(results) == 2

    # Verify each agent result
    results_by_agent = {r.metadata["agent_id"]: r for r in results}

    # Search agent verification
    search_result = results_by_agent["search_agent"]
    assert search_result.success
    assert search_result.aggregation_level == "agent"
    assert search_result.metadata["agent_tool_calls"] == 2
    assert search_result.metadata["agent_tool_errors"] == 1
    assert search_result.value == 50.0  # 1 error out of 2 tools = 50%

    # Analysis agent verification
    analysis_result = results_by_agent["analysis_agent"]
    assert analysis_result.success
    assert analysis_result.aggregation_level == "agent"
    assert analysis_result.metadata["agent_tool_calls"] == 3
    assert analysis_result.metadata["agent_tool_errors"] == 0
    assert analysis_result.value == 0.0  # 0 errors out of 3 tools = 0%


@pytest.mark.asyncio
async def test_tool_error_rate_agent_computation_no_tools():
    """Test agent computation with agents that have no tools."""
    metric = ToolErrorRate()

    # Create spans for agents with no tool calls
    spans = [
        make_agent_span(
            "agent", "coordinator_agent", False, "agent1", "coordinator_agent"
        ),
        make_agent_span("llm", "gpt-4", False, "llm1", "coordinator_agent"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute(session_entity, context={"agent_computation": True})

    # Should return list with one agent result
    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.success
    assert result.aggregation_level == "agent"
    assert result.metadata["agent_id"] == "coordinator_agent"
    assert result.metadata["agent_tool_calls"] == 0
    assert result.metadata["agent_tool_errors"] == 0
    assert result.value == 0.0  # No tools = 0% error rate


@pytest.mark.asyncio
async def test_tool_error_rate_agent_computation_all_errors():
    """Test agent computation where all tools have errors."""
    metric = ToolErrorRate()

    # Create spans where all tools have errors
    spans = [
        make_agent_span("agent", "faulty_agent", False, "agent1", "faulty_agent"),
        make_agent_span("tool", "broken_tool1", True, "tool1", "faulty_agent"),
        make_agent_span("tool", "broken_tool2", True, "tool2", "faulty_agent"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute(session_entity, context={"agent_computation": True})

    # Should return list with one agent result
    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.success
    assert result.aggregation_level == "agent"
    assert result.metadata["agent_id"] == "faulty_agent"
    assert result.metadata["agent_tool_calls"] == 2
    assert result.metadata["agent_tool_errors"] == 2
    assert result.value == 100.0  # 2 errors out of 2 tools = 100%


@pytest.mark.asyncio
async def test_tool_error_rate_session_level_computation():
    """Test session-level computation returns single MetricResult with various context scenarios."""
    metric = ToolErrorRate()

    # Create mixed spans
    spans = [
        make_dummy_span("tool", False, "1"),
        make_dummy_span("tool", True, "2"),
        make_dummy_span("tool", False, "3"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)

    # Test session-level computation (no context)
    result = await metric.compute(session_entity)
    assert not isinstance(result, list)  # Should be single MetricResult
    assert result.success
    assert result.aggregation_level == "session"
    assert abs(result.value - 33.33) < 0.1  # 1 error out of 3 tools

    # Test session-level computation (empty context)
    result = await metric.compute(session_entity, context={})
    assert not isinstance(result, list)  # Should be single MetricResult
    assert result.success
    assert result.aggregation_level == "session"

    # Test session-level computation (explicit false flag)
    result = await metric.compute(session_entity, context={"agent_computation": False})
    assert not isinstance(result, list)  # Should be single MetricResult
    assert result.success
    assert result.aggregation_level == "session"


@pytest.mark.asyncio
async def test_tool_error_rate_agent_metadata_completeness():
    """Test that agent results contain complete metadata."""
    metric = ToolErrorRate()

    # Create spans for one agent
    spans = [
        make_agent_span("agent", "test_agent", False, "agent1", "test_agent"),
        make_agent_span("tool", "tool_a", False, "tool1", "test_agent"),
        make_agent_span("tool", "tool_b", True, "tool2", "test_agent"),
    ]

    session_entity = SessionEntity(session_id="session123", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute(session_entity, context={"agent_computation": True})

    assert len(results) == 1
    result = results[0]

    # Verify all expected metadata fields are present
    metadata = result.metadata
    assert "agent_id" in metadata
    assert "agent_tool_calls" in metadata
    assert "agent_tool_errors" in metadata
    assert "agent_error_span_ids" in metadata
    assert "agent_tool_names" in metadata

    # Verify metadata values
    assert metadata["agent_id"] == "test_agent"
    assert metadata["agent_tool_calls"] == 2
    assert metadata["agent_tool_errors"] == 1
    assert len(metadata["agent_error_span_ids"]) == 1
    assert "tool2" in metadata["agent_error_span_ids"]
    assert set(metadata["agent_tool_names"]) == {"tool_a", "tool_b"}


@pytest.mark.asyncio
async def test_tool_error_rate_agent_computation_no_agents_but_tools():
    """Test agent computation with session that has tools but no agent spans."""
    metric = ToolErrorRate()

    # Session with only tool spans (no agent spans)
    spans = [
        make_dummy_span("tool", False, "tool1"),
        make_dummy_span("tool", True, "tool2"),
        make_dummy_span("tool", False, "tool3"),
    ]

    session_entity = SessionEntity(session_id="no_agents", spans=spans)
    session_entity = setup_session(session_entity)
    results = await metric.compute(session_entity, context={"agent_computation": True})

    # Should return empty list when no agent spans exist
    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_tool_error_rate_session_with_tool_errors():
    """Test session-level computation correctly handles tool errors."""
    metric = ToolErrorRate()

    # Session with mix of successful and failed tools
    spans = [
        make_dummy_span("tool", False, "tool1"),  # success
        make_dummy_span("tool", True, "tool2"),  # error
        make_dummy_span("tool", False, "tool3"),  # success
        make_dummy_span("tool", True, "tool4"),  # error
        make_dummy_span("llm", False, "llm1"),  # LLM (should be ignored)
    ]

    session_entity = SessionEntity(session_id="session_with_errors", spans=spans)
    session_entity = setup_session(session_entity)
    result = await metric.compute(session_entity)  # No agent_computation flag

    # Should return single MetricResult (not list)
    assert isinstance(result, MetricResult)
    assert not isinstance(result, list)

    # Should calculate 50% error rate (2 errors out of 4 tools)
    assert result.value == 50.0
    assert result.aggregation_level == "session"
    assert result.metric_name == "ToolErrorRate"

    # Verify metadata includes session-level info
    assert "agent_id" not in result.metadata  # No agent_id for session-level
    assert result.session_id == ["session_with_errors"]
