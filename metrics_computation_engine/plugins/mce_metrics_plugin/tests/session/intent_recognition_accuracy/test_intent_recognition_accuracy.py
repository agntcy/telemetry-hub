# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import Mock
from datetime import datetime

from mce_metrics_plugin.session.intent_recognition_accuracy import (
    IntentRecognitionAccuracy,
)


def setup_session_for_agents(session):
    """Ensure session has execution tree for agent_stats to work."""
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree

    if not hasattr(session, "execution_tree") or session.execution_tree is None:
        session.execution_tree = ExecutionTree()
    return session


def create_mock_session_with_llm_data(session_id="test_session", app_name="test-app"):
    """Helper to create a mock session with LLM data for testing."""
    from metrics_computation_engine.entities.models.session import (
        SessionEntity,
        SpanEntity,
    )

    # Create a basic span to ensure app_name is available
    basic_span = SpanEntity(
        entity_type="llm",
        span_id="span1",
        entity_name="test_agent",
        app_name=app_name,
        timestamp="2025-10-06T10:00:00Z",
        parent_span_id=None,
        trace_id="trace1",
        session_id=session_id,
        start_time="1750455422.83277",
        end_time="1750455423.7407782",
        input_payload={},
        output_payload={},
        contains_error=False,
        raw_span_data={},
    )

    # Create session with the span
    session = SessionEntity(session_id=session_id, spans=[basic_span])

    def mock_populate_properties():
        # Simulate EndToEndAttributesTransformer extraction
        for span in session.llm_spans:
            if span.input_payload:
                for key, value in span.input_payload.items():
                    if key.startswith("gen_ai.prompt") and ".content" in key:
                        role_key = key.replace(".content", ".role")
                        role = span.input_payload.get(role_key, "unknown").lower()
                        if role == "user" and not hasattr(session, "input_query"):
                            session.input_query = value
                            break

            if span.output_payload:
                for key, value in span.output_payload.items():
                    if key.startswith("gen_ai.completion") and ".content" in key:
                        role_key = key.replace(".content", ".role")
                        role = span.output_payload.get(role_key, "assistant").lower()
                        if role == "assistant":
                            session.final_response = value

    mock_populate_properties()
    return session


@pytest.mark.asyncio
async def test_compute_with_mock_jury_successful_intent():
    """Test intent recognition accuracy computation with successful intent recognition."""
    # Create metric instance
    metric = IntentRecognitionAccuracy()

    # Create mock jury that returns high score
    mock_jury = Mock()
    mock_jury.judge = Mock(
        return_value=(
            1,
            "The assistant correctly identified the user's intent to get weather information and provided an appropriate response.",
        )
    )
    metric.jury = mock_jury

    # Create session with test data
    session = create_mock_session_with_llm_data()
    session.input_query = "What's the weather like today?"
    session.final_response = "I'll check the current weather for you. Today it's sunny with a temperature of 22°C."

    # Compute metric
    result = await metric.compute(session)

    # Verify result
    assert result.success is True
    assert result.value == 1
    assert (
        result.reasoning
        == "The assistant correctly identified the user's intent to get weather information and provided an appropriate response."
    )
    assert mock_jury.judge.called


@pytest.mark.asyncio
async def test_compute_with_mock_jury_failed_intent():
    """Test intent recognition accuracy computation with failed intent recognition."""
    # Create metric instance
    metric = IntentRecognitionAccuracy()

    # Create mock jury that returns low score
    mock_jury = Mock()
    mock_jury.judge = Mock(
        return_value=(
            0,
            "The assistant failed to identify the user's intent to get weather information and responded with irrelevant information.",
        )
    )
    metric.jury = mock_jury

    # Create session with test data
    session = create_mock_session_with_llm_data()
    session.input_query = "What's the weather like today?"
    session.final_response = "I can help you with math problems. What calculation would you like me to perform?"

    # Compute metric
    result = await metric.compute(session)

    # Verify result
    assert result.success is True
    assert result.value == 0
    assert (
        result.reasoning
        == "The assistant failed to identify the user's intent to get weather information and responded with irrelevant information."
    )
    assert mock_jury.judge.called


@pytest.mark.asyncio
async def test_compute_no_jury():
    """Test intent recognition accuracy computation when no jury model is available."""
    # Create metric instance without jury
    metric = IntentRecognitionAccuracy()
    metric.jury = None

    # Create session with test data
    session = create_mock_session_with_llm_data()
    session.input_query = "What's the weather like today?"
    session.final_response = "I'll check the current weather for you."

    # Compute metric
    result = await metric.compute(session)

    # Verify error result
    assert result.success is False
    assert result.error_message == "No model available"


@pytest.mark.asyncio
async def test_intent_recognition_accuracy_supports_agent_computation():
    """Test that IntentRecognitionAccuracy supports agent computation."""
    metric = IntentRecognitionAccuracy()
    assert metric.supports_agent_computation() is True


@pytest.mark.asyncio
async def test_intent_recognition_accuracy_agent_computation_empty_session():
    """Test agent computation with empty session returns empty results."""
    metric = IntentRecognitionAccuracy()

    from metrics_computation_engine.entities.models.session import SessionEntity

    session = SessionEntity(session_id="test_session", spans=[])

    context = {"agent_computation": True}
    result = await metric.compute_with_dispatch(session, context=context)

    assert result == []


@pytest.mark.asyncio
async def test_intent_recognition_accuracy_agent_computation_single_agent():
    """Test agent computation with single agent."""
    from metrics_computation_engine.entities.models.session import (
        SessionEntity,
        SpanEntity,
    )

    # Create spans for a single agent
    spans = [
        SpanEntity(
            entity_type="llm",
            span_id="span1",
            entity_name="weather_agent",
            app_name="weather-app",
            timestamp=datetime.now().isoformat(),
            parent_span_id=None,
            trace_id="trace1",
            session_id="session1",
            start_time="1750455422.83277",
            end_time="1750455423.7407782",
            input_payload={
                "gen_ai.prompt.0.role": "user",
                "gen_ai.prompt.0.content": "What's the weather like today?",
            },
            output_payload={
                "gen_ai.completion.0.role": "assistant",
                "gen_ai.completion.0.content": "I'll check the current weather for you. Today it's sunny with a temperature of 22°C.",
            },
            contains_error=False,
            raw_span_data={},
        )
    ]

    session = SessionEntity(session_id="session1", spans=spans)
    session = setup_session_for_agents(session)

    # Create metric with mock jury
    metric = IntentRecognitionAccuracy()
    mock_jury = Mock()
    mock_jury.judge = Mock(return_value=(1, "Correctly identified weather intent"))
    metric.jury = mock_jury

    # Test agent computation
    context = {"agent_computation": True}
    results = await metric.compute_with_dispatch(session, context=context)

    # Verify results
    assert len(results) == 1
    result = results[0]
    assert result.success is True
    assert result.value == 1
    assert (
        result.aggregation_level == "agent"
    )  # Should be "agent" for agent-level computation
    assert result.metadata["agent_id"] == "weather_agent"
    assert result.metadata["agent_input_query"] == "What's the weather like today?"
    assert (
        result.metadata["agent_final_response"]
        == "I'll check the current weather for you. Today it's sunny with a temperature of 22°C."
    )


@pytest.mark.asyncio
async def test_intent_recognition_accuracy_agent_computation_multiple_agents():
    """Test agent computation with multiple agents."""
    from metrics_computation_engine.entities.models.session import (
        SessionEntity,
        SpanEntity,
    )

    # Create spans for multiple agents
    spans = [
        SpanEntity(
            entity_type="llm",
            span_id="span1",
            entity_name="weather_agent",
            app_name="multi-agent-app",
            timestamp="2025-10-06T10:00:00Z",
            parent_span_id=None,
            trace_id="trace1",
            session_id="session1",
            start_time="1750455422.83277",
            end_time="1750455423.7407782",
            input_payload={
                "gen_ai.prompt.0.role": "user",
                "gen_ai.prompt.0.content": "What's the weather in Paris?",
            },
            output_payload={
                "gen_ai.completion.0.role": "assistant",
                "gen_ai.completion.0.content": "The weather in Paris is cloudy with 18°C.",
            },
            contains_error=False,
            raw_span_data={},
        ),
        SpanEntity(
            entity_type="llm",
            span_id="span2",
            entity_name="translation_agent",
            app_name="multi-agent-app",
            timestamp="2025-10-06T10:01:00Z",
            parent_span_id=None,
            trace_id="trace1",
            session_id="session1",
            start_time="1750455422.83277",
            end_time="1750455423.7407782",
            input_payload={
                "gen_ai.prompt.0.role": "user",
                "gen_ai.prompt.0.content": "Translate 'hello' to French",
            },
            output_payload={
                "gen_ai.completion.0.role": "assistant",
                "gen_ai.completion.0.content": "Bonjour",
            },
            contains_error=False,
            raw_span_data={},
        ),
    ]

    session = SessionEntity(session_id="session1", spans=spans)
    session = setup_session_for_agents(session)

    # Create metric with mock jury
    metric = IntentRecognitionAccuracy()
    mock_jury = Mock()
    mock_jury.judge = Mock(return_value=(1, "Correctly identified intent"))
    metric.jury = mock_jury

    # Test agent computation
    context = {"agent_computation": True}
    results = await metric.compute_with_dispatch(session, context=context)

    # Verify results
    assert len(results) == 2

    # Find results by agent
    weather_result = next(
        r for r in results if r.metadata["agent_id"] == "weather_agent"
    )
    translation_result = next(
        r for r in results if r.metadata["agent_id"] == "translation_agent"
    )

    # Verify both results have agent aggregation level
    assert weather_result.aggregation_level == "agent"
    assert translation_result.aggregation_level == "agent"

    assert (
        weather_result.metadata["agent_input_query"] == "What's the weather in Paris?"
    )
    assert (
        weather_result.metadata["agent_final_response"]
        == "The weather in Paris is cloudy with 18°C."
    )

    assert (
        translation_result.metadata["agent_input_query"]
        == "Translate 'hello' to French"
    )
    assert translation_result.metadata["agent_final_response"] == "Bonjour"


@pytest.mark.asyncio
async def test_intent_recognition_accuracy_session_level_computation():
    """Test session-level computation (default behavior)."""
    session = create_mock_session_with_llm_data()
    session.input_query = "test query"
    session.final_response = "test response"

    # Create metric with mock jury
    metric = IntentRecognitionAccuracy()
    mock_jury = Mock()
    mock_jury.judge = Mock(
        return_value=(1, "Session-level intent recognition successful")
    )
    metric.jury = mock_jury

    # Test session-level computation (no context)
    result = await metric.compute(session)

    assert result.success is True
    assert result.value == 1
    assert result.reasoning == "Session-level intent recognition successful"
    # Should not have agent-specific metadata
    assert "agent_id" not in result.metadata
