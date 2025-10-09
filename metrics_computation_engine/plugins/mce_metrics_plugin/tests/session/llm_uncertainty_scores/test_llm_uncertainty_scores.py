# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import patch
import math

from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.core.session_aggregator import (
    SessionAggregator,
)

# Import the LLM uncertainty metrics directly from the plugin system
from mce_metrics_plugin.session.llm_uncertainty_scores import (
    LLMAverageConfidence,
    LLMMaximumConfidence,
    LLMMinimumConfidence,
)


def create_session_from_spans(spans):
    """Helper function to create a session entity from spans using the SessionAggregator API."""
    if not spans:
        raise ValueError("No spans provided")

    aggregator = SessionAggregator()
    session_id = spans[0].session_id
    session = aggregator.create_session_from_spans(session_id, spans)
    return session


def create_span_with_logprobs(
    span_id: str,
    session_id: str = "test_session",
    entity_name: str = "test_agent",
    agent_id: str = None,
    logprobs_data: list = None,
):
    """Create a span with logprobs data for testing."""
    if logprobs_data is None:
        logprobs_data = [
            {
                "token": "Hello",
                "logprob": -0.1,
                "bytes": [72, 101, 108, 108, 111],
                "top_logprobs": [
                    {
                        "token": "Hello",
                        "logprob": -0.1,
                        "bytes": [72, 101, 108, 108, 111],
                    },
                    {"token": "Hi", "logprob": -1.5, "bytes": [72, 105]},
                ],
            },
            {
                "token": " world",
                "logprob": -0.3,
                "bytes": [32, 119, 111, 114, 108, 100],
                "top_logprobs": [
                    {
                        "token": " world",
                        "logprob": -0.3,
                        "bytes": [32, 119, 111, 114, 108, 100],
                    },
                    {
                        "token": " there",
                        "logprob": -2.1,
                        "bytes": [32, 116, 104, 101, 114, 101],
                    },
                ],
            },
        ]

    output_payload = {"choices": [{"logprobs": {"content": logprobs_data}}]}

    # Add raw_span_data with agent information to help with agent identification
    raw_span_data = {"SpanAttributes": {"agent_id": agent_id}} if agent_id else {}

    return SpanEntity(
        entity_type="llm",
        span_id=span_id,
        entity_name=entity_name,
        app_name="test_app",
        timestamp="2025-06-20 21:37:02.832759",
        parent_span_id="parent",
        trace_id="trace1",
        session_id=session_id,
        start_time="1750455422.83277",
        end_time="1750455423.7407782",
        input_payload={"query": "test input"},
        output_payload=output_payload,
        contains_error=False,
        raw_span_data=raw_span_data,
    )


def setup_session_for_agents(agent_names, session_id="test_session"):
    """Helper to set up a session with multiple agents for testing."""
    spans = []

    for i, agent_name in enumerate(agent_names):
        span = create_span_with_logprobs(
            span_id=f"span_{i + 1}",
            session_id=session_id,
            entity_name=agent_name,
            agent_id=agent_name,  # Pass agent_id for proper agent identification
            logprobs_data=[
                {
                    "token": f"Agent{i + 1}",
                    "logprob": -(i + 1) * 0.2,  # Different confidence for each agent
                    "bytes": [65, 103, 101, 110, 116],
                    "top_logprobs": [
                        {
                            "token": f"Agent{i + 1}",
                            "logprob": -(i + 1) * 0.2,
                            "bytes": [65, 103, 101, 110, 116],
                        }
                    ],
                }
            ],
        )
        spans.append(span)

    from metrics_computation_engine.entities.models.session import SessionEntity

    session = SessionEntity(session_id=session_id, spans=spans)

    # Ensure session has execution tree for agent_stats to work
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree

    if not hasattr(session, "execution_tree") or session.execution_tree is None:
        session.execution_tree = ExecutionTree()

    return session


@pytest.mark.asyncio
async def test_average_confidence_session_level_computation():
    """Test LLMAverageConfidence computation at session level."""
    metric = LLMAverageConfidence()

    # Create a session with logprobs
    spans = [
        create_span_with_logprobs(
            "span1",
            logprobs_data=[
                {"token": "Hello", "logprob": -0.1, "bytes": [72], "top_logprobs": []},
                {"token": "world", "logprob": -0.3, "bytes": [119], "top_logprobs": []},
            ],
        )
    ]
    session = create_session_from_spans(spans)

    result = await metric.compute(session)

    assert result.metric_name == "Average Confidence"
    assert result.success is True
    assert result.aggregation_level == "session"
    assert isinstance(result.value, float)
    # Average of -0.1 and -0.3 is -0.2, so exp(-0.2) ≈ 0.8187
    expected_value = math.exp(-0.2)
    assert abs(result.value - expected_value) < 0.001


@pytest.mark.asyncio
async def test_minimum_confidence_session_level_computation():
    """Test LLMMinimumConfidence computation at session level."""
    metric = LLMMinimumConfidence()

    spans = [
        create_span_with_logprobs(
            "span1",
            logprobs_data=[
                {"token": "Hello", "logprob": -0.1, "bytes": [72], "top_logprobs": []},
                {"token": "world", "logprob": -0.5, "bytes": [119], "top_logprobs": []},
            ],
        )
    ]
    session = create_session_from_spans(spans)

    result = await metric.compute(session)

    assert result.metric_name == "Minimum Confidence"
    assert result.success is True
    assert result.aggregation_level == "session"
    # Min of -0.1 and -0.5 is -0.5, so exp(-0.5) ≈ 0.6065
    expected_value = math.exp(-0.5)
    assert abs(result.value - expected_value) < 0.001


@pytest.mark.asyncio
async def test_maximum_confidence_session_level_computation():
    """Test LLMMaximumConfidence computation at session level."""
    metric = LLMMaximumConfidence()

    spans = [
        create_span_with_logprobs(
            "span1",
            logprobs_data=[
                {"token": "Hello", "logprob": -0.1, "bytes": [72], "top_logprobs": []},
                {"token": "world", "logprob": -0.5, "bytes": [119], "top_logprobs": []},
            ],
        )
    ]
    session = create_session_from_spans(spans)

    result = await metric.compute(session)

    assert result.metric_name == "Maximum Confidence"
    assert result.success is True
    assert result.aggregation_level == "session"
    # Max of -0.1 and -0.5 is -0.1, so exp(-0.1) ≈ 0.9048
    expected_value = math.exp(-0.1)
    assert abs(result.value - expected_value) < 0.001


@pytest.mark.asyncio
async def test_supports_agent_computation():
    """Test that all metrics support agent computation."""
    average_metric = LLMAverageConfidence()
    min_metric = LLMMinimumConfidence()
    max_metric = LLMMaximumConfidence()

    assert average_metric.supports_agent_computation() is True
    assert min_metric.supports_agent_computation() is True
    assert max_metric.supports_agent_computation() is True


@pytest.mark.asyncio
async def test_empty_session_handling():
    """Test handling of session with no logprobs."""
    metric = LLMAverageConfidence()

    # Create a session with no logprobs
    spans = [
        SpanEntity(
            entity_type="llm",
            span_id="span1",
            entity_name="test_agent",
            app_name="test_app",
            timestamp="2025-06-20 21:37:02.832759",
            parent_span_id=None,
            trace_id="trace1",
            session_id="test_session",
            start_time="1750455422.83277",
            end_time="1750455423.7407782",
            input_payload={"query": "test"},
            output_payload={"response": "no logprobs"},
            contains_error=False,
            raw_span_data={},
        )
    ]
    session = create_session_from_spans(spans)

    result = await metric.compute(session)

    assert result.success is False
    assert result.value == -1
    assert result.error_message == "No logprobs found"


@pytest.mark.asyncio
async def test_agent_level_computation_single_agent():
    """Test agent-level computation with a single agent."""
    metric = LLMAverageConfidence()

    session = setup_session_for_agents(["agent1"])

    # Test agent computation
    context = {"agent_computation": True}
    results = await metric.compute_with_dispatch(session, context=context)

    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.aggregation_level == "agent"
    assert result.success is True
    assert "agent1" in result.metadata.get("agent_id", "")
    assert isinstance(result.value, float)


@pytest.mark.asyncio
async def test_agent_level_computation_multiple_agents():
    """Test agent-level computation with multiple agents."""
    metric = LLMMinimumConfidence()

    session = setup_session_for_agents(["agent1", "agent2", "agent3"])

    # Test agent computation
    context = {"agent_computation": True}
    results = await metric.compute_with_dispatch(session, context=context)

    assert isinstance(results, list)
    assert len(results) == 3

    agent_ids = [result.metadata.get("agent_id") for result in results]
    assert "agent1" in agent_ids
    assert "agent2" in agent_ids
    assert "agent3" in agent_ids

    # All should be successful and have different values
    for result in results:
        assert result.aggregation_level == "agent"
        assert result.success is True
        assert isinstance(result.value, float)


@pytest.mark.asyncio
async def test_agent_level_computation_no_agents():
    """Test agent-level computation when session has no agents."""
    metric = LLMMaximumConfidence()

    # Create session without agent_stats (simulating no agents)
    spans = [create_span_with_logprobs("span1")]
    session = create_session_from_spans(spans)

    # Mock the session to have empty agent_stats (no agents)
    # Don't try to delete it since it's a property

    context = {"agent_computation": True}
    results = await metric.compute_with_dispatch(session, context=context)

    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_agent_level_computation_agent_without_spans():
    """Test agent-level computation when an agent has no spans."""
    metric = LLMAverageConfidence()

    session = setup_session_for_agents(["agent1"])

    # Use patch to mock get_agent_view method
    class MockAgentView:
        def __init__(self):
            self.all_spans = []  # No spans

    # Patch the method on the session class instead of instance
    with patch(
        "metrics_computation_engine.entities.models.session.SessionEntity.get_agent_view",
        return_value=MockAgentView(),
    ):
        context = {"agent_computation": True}
        results = await metric.compute_with_dispatch(session, context=context)

    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.success is False
    assert result.value == -1
    assert "no spans to process" in result.error_message


@pytest.mark.asyncio
async def test_nested_context_extraction():
    """Test that nested context is properly extracted."""
    metric = LLMAverageConfidence()

    session = setup_session_for_agents(["agent1"])

    # Test with nested context
    nested_context = {"context": {"agent_computation": True}}
    results = await metric.compute_with_dispatch(session, **nested_context)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].aggregation_level == "agent"


@pytest.mark.asyncio
async def test_description_properties():
    """Test that all metrics have proper description properties."""
    average_metric = LLMAverageConfidence()
    min_metric = LLMMinimumConfidence()
    max_metric = LLMMaximumConfidence()

    assert hasattr(average_metric, "description")
    assert hasattr(min_metric, "description")
    assert hasattr(max_metric, "description")

    assert "average confidence" in average_metric.description.lower()
    assert "minimum confidence" in min_metric.description.lower()
    assert "maximum confidence" in max_metric.description.lower()


@pytest.mark.asyncio
async def test_aggregation_level_restoration():
    """Test that aggregation level is properly restored after agent computation."""
    metric = LLMAverageConfidence()
    original_level = metric.aggregation_level

    session = setup_session_for_agents(["agent1"])

    context = {"agent_computation": True}
    await metric.compute_with_dispatch(session, context=context)

    # Verify aggregation level is restored
    assert metric.aggregation_level == original_level


@pytest.mark.asyncio
async def test_agent_computation_with_exception_handling():
    """Test that exceptions in agent computation properly restore aggregation level."""
    metric = LLMAverageConfidence()
    original_level = metric.aggregation_level

    session = setup_session_for_agents(["agent1"])

    # Mock compute_uncertainty_score to raise an exception
    original_compute = metric.compute_uncertainty_score

    def mock_compute_with_error(log_probs_mapping):
        raise ValueError("Test error")

    metric.compute_uncertainty_score = mock_compute_with_error

    context = {"agent_computation": True}

    # This should handle the exception gracefully
    results = await metric.compute_with_dispatch(session, context=context)

    # Verify aggregation level is still restored
    assert metric.aggregation_level == original_level

    # Check that error was handled in results
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].success is False
    assert "Test error" in results[0].error_message

    # Restore original method
    metric.compute_uncertainty_score = original_compute
