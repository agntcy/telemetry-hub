# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import Mock, patch

from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.core.session_aggregator import (
    SessionAggregator,
)
from metrics_computation_engine.models.eval import BinaryGrading

# Import the ContextPreservation metric directly from the plugin system
from mce_metrics_plugin.session.context_preservation import ContextPreservation


def create_session_from_spans(spans):
    """Helper function to create a session entity from spans using the SessionAggregator API."""
    if not spans:
        raise ValueError("No spans provided")

    aggregator = SessionAggregator()
    session_id = spans[0].session_id
    session = aggregator.create_session_from_spans(session_id, spans)
    return session


def create_agent_span(
    span_id: str,
    session_id: str = "test_session",
    entity_name: str = "test_agent",
    agent_id: str = None,
    input_content: str = "test input",
    output_content: str = "test output",
):
    """Create an agent span for testing."""
    # Add raw_span_data with agent information to help with agent identification
    raw_span_data = {"SpanAttributes": {"agent_id": agent_id}} if agent_id else {}

    return SpanEntity(
        entity_type="agent",
        span_id=span_id,
        entity_name=entity_name,
        app_name="test_app",
        timestamp="2025-06-20 21:37:02.832759",
        parent_span_id="parent",
        trace_id="trace1",
        session_id=session_id,
        start_time="1750455422.83277",
        end_time="1750455423.7407782",
        input_payload={"query": input_content},
        output_payload={"response": output_content},
        contains_error=False,
        raw_span_data=raw_span_data,
    )


def create_session_with_conversation(
    session_id="test_session",
    conversation_text="User: Hello\nAssistant: Hi there!",
    agent_names=None,
):
    """Helper to set up a session with conversation data and optional agents."""
    if agent_names is None:
        agent_names = ["assistant"]

    spans = []
    for i, agent_name in enumerate(agent_names):
        span = create_agent_span(
            span_id=f"span_{i + 1}",
            session_id=session_id,
            entity_name=agent_name,
            agent_id=agent_name,
            input_content=f"Input for {agent_name}",
            output_content=f"Output from {agent_name}",
        )
        spans.append(span)

    # Create SessionEntity directly like in LLM uncertainty tests
    from metrics_computation_engine.entities.models.session import SessionEntity

    session = SessionEntity(session_id=session_id, spans=spans)

    # Ensure session has execution tree for agent_stats to work
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree

    if not hasattr(session, "execution_tree") or session.execution_tree is None:
        session.execution_tree = ExecutionTree()

    # Mock conversation data
    session.conversation_data = {"conversation": conversation_text}

    return session


@pytest.mark.asyncio
async def test_context_preservation_basic_properties():
    """Test basic properties of ContextPreservation metric."""
    metric = ContextPreservation()

    assert metric.name == "ContextPreservation"
    assert metric.aggregation_level == "session"
    assert "conversation context" in metric.description.lower()
    assert metric.required_parameters == ["conversation_data"]
    assert metric.validate_config() is True
    assert metric.supports_agent_computation() is True


@pytest.mark.asyncio
async def test_context_preservation_session_level_success():
    """Test ContextPreservation computation at session level with successful judgment."""
    metric = ContextPreservation()

    # Mock the jury to return a successful judgment
    mock_jury = Mock()
    mock_jury.judge.return_value = (
        1.0,
        "The response is highly relevant and well-structured.",
    )
    metric.jury = mock_jury

    # Create session with conversation data
    session = create_session_with_conversation(
        conversation_text="User: What is 2+2?\nAssistant: 2+2 equals 4."
    )

    result = await metric.compute(session)

    assert result.metric_name == "ContextPreservation"
    assert result.success is True
    assert result.aggregation_level == "session"
    assert result.value == 1.0
    assert result.reasoning == "The response is highly relevant and well-structured."
    assert result.description == metric.description
    assert (
        result.app_name == "unknown-app"
    )  # Default when session has no clear app name
    assert len(result.session_id) == 1
    assert result.session_id[0] == "test_session"


@pytest.mark.asyncio
async def test_context_preservation_session_level_failure():
    """Test ContextPreservation computation at session level with failing judgment."""
    metric = ContextPreservation()

    # Mock the jury to return a failing judgment
    mock_jury = Mock()
    mock_jury.judge.return_value = (0.0, "The response is irrelevant and unclear.")
    metric.jury = mock_jury

    session = create_session_with_conversation(
        conversation_text="User: What is the capital of France?\nAssistant: I like pizza."
    )

    result = await metric.compute(session)

    assert result.metric_name == "ContextPreservation"
    assert result.success is True
    assert result.value == 0.0
    assert result.reasoning == "The response is irrelevant and unclear."
    assert result.description == metric.description


@pytest.mark.asyncio
async def test_context_preservation_no_model():
    """Test ContextPreservation computation when no model is available."""
    metric = ContextPreservation()
    # Don't set metric.jury (no model)

    session = create_session_with_conversation()

    result = await metric.compute(session)

    assert result.metric_name == "ContextPreservation"
    assert result.success is False
    assert result.error_message == "No model available"
    assert result.value == -1  # Error value


@pytest.mark.asyncio
async def test_context_preservation_agent_computation():
    """Test ContextPreservation computation at agent level."""
    metric = ContextPreservation()

    # Mock the jury
    mock_jury = Mock()
    mock_jury.judge.side_effect = [
        (1.0, "Agent 1 response is excellent."),
        (0.0, "Agent 2 response is poor."),
    ]
    metric.jury = mock_jury

    # Create session with multiple agents
    session = create_session_with_conversation(agent_names=["agent1", "agent2"])

    # Mock agent conversation data using proper mocking technique
    with patch(
        "mce_metrics_plugin.session.context_preservation.SessionEntity.get_agent_conversation_text"
    ) as mock_get_conversation:
        mock_get_conversation.side_effect = lambda agent: f"Conversation for {agent}"

        with patch(
            "mce_metrics_plugin.session.context_preservation.SessionEntity._get_spans_for_agent"
        ) as mock_get_spans:
            mock_get_spans.side_effect = lambda agent: [
                create_agent_span(f"span_{agent}", agent_id=agent, entity_name=agent)
            ]

            # Call with agent computation context
            results = await metric.compute(session, agent_computation=True)

    assert isinstance(results, list)
    assert len(results) == 2

    # Check first agent result
    result1 = results[0]
    assert result1.metric_name == "ContextPreservation"
    assert result1.aggregation_level == "agent"
    assert result1.value == 1.0
    assert result1.success is True
    assert result1.metadata["agent_id"] == "agent1"
    assert result1.description == metric.description

    # Check second agent result
    result2 = results[1]
    assert result2.aggregation_level == "agent"
    assert result2.value == 0.0
    assert result2.metadata["agent_id"] == "agent2"


@pytest.mark.asyncio
async def test_context_preservation_agent_no_conversation_data():
    """Test ContextPreservation agent computation when agent has no conversation data."""
    metric = ContextPreservation()
    mock_jury = Mock()
    metric.jury = mock_jury

    session = create_session_with_conversation(agent_names=["agent1"])

    # Mock no conversation data for agent
    with patch(
        "mce_metrics_plugin.session.context_preservation.SessionEntity.get_agent_conversation_text"
    ) as mock_get_conversation:
        mock_get_conversation.return_value = ""  # Empty conversation

        results = await metric.compute(session, agent_computation=True)

    assert isinstance(results, list)
    assert len(results) == 0  # No results for agents without conversation data


@pytest.mark.asyncio
async def test_context_preservation_agent_no_model():
    """Test ContextPreservation agent computation when no model is available."""
    metric = ContextPreservation()
    # Don't set metric.jury (no model)

    session = create_session_with_conversation(agent_names=["agent1"])

    with patch(
        "mce_metrics_plugin.session.context_preservation.SessionEntity.get_agent_conversation_text"
    ) as mock_get_conversation:
        mock_get_conversation.return_value = "Some conversation"

        with patch(
            "mce_metrics_plugin.session.context_preservation.SessionEntity._get_spans_for_agent"
        ) as mock_get_spans:
            mock_get_spans.return_value = [
                create_agent_span("span_1", agent_id="agent1", entity_name="agent1")
            ]

            results = await metric.compute(session, agent_computation=True)

    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.success is False
    assert result.error_message == "No model available"
    assert result.metadata["agent_id"] == "agent1"
    assert result.aggregation_level == "agent"


@pytest.mark.asyncio
async def test_context_preservation_empty_session():
    """Test ContextPreservation with empty session (no agents)."""
    metric = ContextPreservation()
    mock_jury = Mock()
    metric.jury = mock_jury

    # Create minimal session and use property access mocking
    session = create_session_with_conversation(agent_names=["dummy"])

    # Mock the agent_stats property to return empty dict
    with patch.object(
        type(session), "agent_stats", new_callable=lambda: property(lambda self: {})
    ):
        results = await metric.compute(session, agent_computation=True)

    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_context_preservation_agent_exception_handling():
    """Test ContextPreservation agent computation with exception handling."""
    metric = ContextPreservation()
    mock_jury = Mock()
    metric.jury = mock_jury

    session = create_session_with_conversation(agent_names=["agent1"])

    # Mock conversation method to raise exception
    with patch(
        "mce_metrics_plugin.session.context_preservation.SessionEntity.get_agent_conversation_text"
    ) as mock_get_conversation:
        mock_get_conversation.side_effect = Exception("Test error")

        results = await metric.compute(session, agent_computation=True)

    assert isinstance(results, list)
    assert len(results) == 1

    result = results[0]
    assert result.success is False
    assert (
        "Error computing context preservation for agent agent1" in result.error_message
    )
    assert "Test error" in result.error_message
    assert result.metadata["agent_id"] == "agent1"
    assert result.description == metric.description


@pytest.mark.asyncio
async def test_context_preservation_prompt_formatting():
    """Test that the conversation is properly formatted in the prompt."""
    metric = ContextPreservation()

    mock_jury = Mock()
    mock_jury.judge.return_value = (1.0, "Good response")
    metric.jury = mock_jury

    conversation = "User: Hello\nAssistant: Hi there!"
    session = create_session_with_conversation(conversation_text=conversation)

    await metric.compute(session)

    # Check that judge was called with proper prompt
    mock_jury.judge.assert_called_once()
    call_args = mock_jury.judge.call_args[0]
    prompt = call_args[0]

    assert conversation in prompt
    assert "CONVERSATION to evaluate:" in prompt
    assert "Context Preservation" in prompt


@pytest.mark.asyncio
async def test_context_preservation_binary_grading():
    """Test that BinaryGrading is passed to the judge."""
    metric = ContextPreservation()

    mock_jury = Mock()
    mock_jury.judge.return_value = (1.0, "Good response")
    metric.jury = mock_jury

    session = create_session_with_conversation()

    await metric.compute(session)

    # Check that BinaryGrading was passed as second argument
    call_args = mock_jury.judge.call_args[0]
    assert len(call_args) == 2
    assert call_args[1] == BinaryGrading


@pytest.mark.asyncio
async def test_context_preservation_session_no_conversation_data():
    """Test ContextPreservation when session has no conversation data."""
    metric = ContextPreservation()

    mock_jury = Mock()
    mock_jury.judge.return_value = (0.0, "No conversation to evaluate")
    metric.jury = mock_jury

    session = create_session_with_conversation()
    session.conversation_data = None  # No conversation data

    result = await metric.compute(session)

    assert result.success is True
    # Should still work, just with empty conversation string
    mock_jury.judge.assert_called_once()


@pytest.mark.asyncio
async def test_context_preservation_model_initialization():
    """Test model initialization methods."""
    metric = ContextPreservation()

    # Test init_with_model
    mock_model = Mock()
    result = metric.init_with_model(mock_model)
    assert result is True
    assert metric.jury == mock_model

    # Test get_model_provider (inherits from base)
    with patch.object(metric, "get_default_provider") as mock_provider:
        mock_provider.return_value = "openai"
        provider = metric.get_model_provider()
        assert provider == "openai"

    # Test create_model (inherits from base)
    with patch.object(metric, "create_native_model") as mock_create:
        mock_create.return_value = mock_model
        llm_config = {"model": "gpt-4"}
        model = metric.create_model(llm_config)
        assert model == mock_model
