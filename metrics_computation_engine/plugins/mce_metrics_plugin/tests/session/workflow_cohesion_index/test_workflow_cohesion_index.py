# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from mce_metrics_plugin.session.workflow_cohesion_index import WorkflowCohesionIndex
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.models.eval import BinaryGrading


def create_agent_span(
    span_id: str = "span_1",
    session_id: str = "test_session",
    entity_name: str = "agent",
    agent_id: str = None,
    input_content: str = "test input",
    output_content: str = "test output"
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
    conversation_text="User: Hello\nBot: Hi there!",
    agent_names=None
):
    """Helper to set up a session with conversation data and optional agents."""
    if agent_names is None:
        agent_names = ["agent_a"]

    spans = []
    for i, agent_name in enumerate(agent_names):
        span = create_agent_span(
            span_id=f"span_{i+1}",
            session_id=session_id,
            entity_name=agent_name,
            agent_id=agent_name,
            input_content=f"Input for {agent_name}",
            output_content=f"Output from {agent_name}"
        )
        spans.append(span)

    # Create SessionEntity directly like in other tests
    session = SessionEntity(session_id=session_id, spans=spans)

    # Ensure session has execution tree for agent_stats to work
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree
    if not hasattr(session, 'execution_tree') or session.execution_tree is None:
        session.execution_tree = ExecutionTree()

    # Mock conversation data
    session.conversation_data = conversation_text

    return session


class TestWorkflowCohesionIndex:
    """Test suite for WorkflowCohesionIndex metric with comprehensive coverage."""

    def test_workflow_cohesion_index_basic_properties(self):
        """Test basic metric properties and configuration."""
        metric = WorkflowCohesionIndex()

        assert metric.name == "WorkflowCohesionIndex"
        assert metric.aggregation_level == "session"
        assert "cohesion" in metric.description.lower()
        assert "workflow" in metric.description.lower()
        assert metric.required_parameters == ["conversation_data"]
        assert metric.validate_config() is True
        assert metric.supports_agent_computation() is True

    def test_workflow_cohesion_index_filter_coordinators_setting(self):
        """Test that the filter_coordinators setting is properly configured."""
        # Default should enable filtering
        metric_default = WorkflowCohesionIndex()
        assert metric_default.filter_coordinators is True

        # Explicitly enabled
        metric_enabled = WorkflowCohesionIndex(filter_coordinators=True)
        assert metric_enabled.filter_coordinators is True

        # Explicitly disabled
        metric_disabled = WorkflowCohesionIndex(filter_coordinators=False)
        assert metric_disabled.filter_coordinators is False

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_session_level_high_cohesion(self):
        """Test session-level workflow cohesion computation with high cohesion score."""
        # Setup metric with mock jury
        metric = WorkflowCohesionIndex()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "High cohesion"))
        metric.jury = mock_jury

        # Create session with good conversation
        session = create_session_with_conversation(
            conversation_text="User: Please help me.\nAgent: I'll help you with that task step by step."
        )

        # Execute computation
        result = await metric.compute(session)

        # Verify result
        assert result.value == 1  # High cohesion
        assert result.success is True
        assert result.metric_name == "WorkflowCohesionIndex"
        assert result.session_id == ["test_session"]
        assert metric.description in result.description
        assert result.reasoning == "High cohesion"

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_session_level_low_cohesion(self):
        """Test session-level workflow cohesion computation with low cohesion score."""
        # Setup metric with mock jury
        metric = WorkflowCohesionIndex()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(0, "Low cohesion"))
        metric.jury = mock_jury

        # Create session with fragmented conversation
        session = create_session_with_conversation(
            conversation_text="User: Help me\nAgent: Error 404\nAgent: Unrelated response"
        )

        # Execute computation
        result = await metric.compute(session)

        # Verify result
        assert result.value == 0  # Low cohesion
        assert result.success is True
        assert result.reasoning == "Low cohesion"

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_no_conversation_data(self):
        """Test handling when no conversation data is available."""
        # Setup metric
        metric = WorkflowCohesionIndex()
        metric.jury = AsyncMock()

        # Create session without conversation data
        session = create_session_with_conversation()
        session.conversation_data = None

        # Execute computation
        result = await metric.compute(session)

        # Verify error result
        assert result.success is False
        assert result.value == -1  # Error value
        assert "No conversation data found" in result.error_message

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_agent_computation(self):
        """Test agent-level workflow cohesion computation."""
        # Setup metric with mock jury
        metric = WorkflowCohesionIndex()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Agent cohesion"))
        metric.jury = mock_jury

        # Create session with agents
        session = create_session_with_conversation(
            agent_names=["agent_a", "agent_b"],
            conversation_text="User: Help\nAgent A: Starting\nAgent B: Continuing"
        )

        # Mock agent conversation function
        def mock_get_agent_conversation_data(agent_name):
            return f"User: Help\nAgent {agent_name}: I'll help with that."

        # Mock the agent_stats property and methods
        with patch.object(type(session), 'agent_stats', new_callable=lambda: property(lambda self: {"agent_a": {}, "agent_b": {}})), \
             patch('mce_metrics_plugin.session.workflow_cohesion_index.SessionEntity.get_agent_conversation_text', side_effect=mock_get_agent_conversation_data), \
             patch('mce_metrics_plugin.session.workflow_cohesion_index.SessionEntity._get_spans_for_agent', return_value=[Mock(span_id="span_1")]):
            results = await metric.compute(session, agent_computation=True)

        # Verify results
        assert len(results) == 2  # Two agents

        # Check that both agents have results
        agent_ids = [r.metadata["agent_id"] for r in results]
        assert "agent_a" in agent_ids
        assert "agent_b" in agent_ids

        # Check result structure
        for result in results:
            assert result.success is True
            assert result.aggregation_level == "agent"
            assert result.metadata["metric_type"] == "llm-as-a-judge"
            assert result.reasoning == "Agent cohesion"

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_empty_session(self):
        """Test handling of session with no agents."""
        # Setup metric
        metric = WorkflowCohesionIndex()

        # Create session with no agents
        session = create_session_with_conversation(agent_names=[])

        # Execute agent computation with empty agent_stats
        with patch.object(type(session), 'agent_stats', new_callable=lambda: property(lambda self: {})):
            results = await metric.compute(session, agent_computation=True)

        # Verify empty results
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_agent_exception_handling(self):
        """Test graceful handling of exceptions during agent computation."""
        # Setup metric
        metric = WorkflowCohesionIndex()
        metric.jury = AsyncMock()

        # Create session with problematic agent
        session = create_session_with_conversation(agent_names=["problematic_agent"])

        # Execute agent computation with mocked agent_stats and failing method
        with patch.object(type(session), 'agent_stats', new_callable=lambda: property(lambda self: {"problematic_agent": {}})), \
             patch('mce_metrics_plugin.session.workflow_cohesion_index.SessionEntity._get_spans_for_agent', side_effect=Exception("Span extraction failed")):
            results = await metric.compute(session, agent_computation=True)

        # Verify error handling
        assert len(results) == 1
        result = results[0]
        assert result.success is False
        assert "Error computing workflow cohesion index for agent problematic_agent" in result.error_message
        assert "Span extraction failed" in result.error_message
        assert result.value == -1  # Error value
        assert result.metadata["agent_id"] == "problematic_agent"

    def test_workflow_cohesion_index_agent_level_coordinator_skipped(self):
        """Test that coordinator agents are skipped when filtering is enabled."""
        # Setup metric with filtering enabled
        metric = WorkflowCohesionIndex(filter_coordinators=True)

        # Create session with coordinator agent
        session = create_session_with_conversation(agent_names=["supervisor"])

        # Mock the role detection function to return skip=True
        with patch('mce_metrics_plugin.session.workflow_cohesion_index.get_agent_role_and_skip_decision') as mock_role_func:
            mock_role_func.return_value = (True, {
                'detected_role': 'coordinator',
                'skip_reason': 'Agent performs coordination tasks'
            })

            results = metric._compute_agent_level(session)

            # Verify coordinator was skipped - no results should be returned
            assert len(results) == 0, f"Expected no results for skipped agents, but got: {results}"

            # Verify role detection was called with correct parameters
            mock_role_func.assert_called_once_with(session, "supervisor", filter_coordinators=True)

    @patch('mce_metrics_plugin.session.workflow_cohesion_index.get_agent_role_and_skip_decision')
    def test_workflow_cohesion_index_agent_level_processor_evaluated(self, mock_role_detection):
        """Test that processor agents are evaluated when filtering is enabled."""
        # Setup mock role detection to identify agent as processor
        mock_role_detection.return_value = (
            False,  # should_skip = False
            {
                'filtering_enabled': True,
                'detected_role': 'processor',
                'coordinator_score': 1,
                'processor_score': 7,
                'skip_reason': 'Processor agents handle information and should be evaluated',
                'tool_calls': 2,
                'coordination_signals': 0,
                'processing_signals': 4
            }
        )

        # Setup metric with filtering enabled
        metric = WorkflowCohesionIndex(filter_coordinators=True)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Agent cohesion"))
        metric.jury = mock_jury

        # Create session with processor agent
        session = create_session_with_conversation(agent_names=["coder"])

        # Mock agent conversation function
        def mock_get_agent_conversation_text(agent_name):
            return f"User: Help\nAgent {agent_name}: I'll assist you with that task."

        # Execute agent-level computation with mocked agent_stats and methods
        with patch.object(type(session), 'agent_stats', new_callable=lambda: property(lambda self: {"coder": {}})), \
             patch('mce_metrics_plugin.session.workflow_cohesion_index.SessionEntity.get_agent_conversation_text', side_effect=mock_get_agent_conversation_text), \
             patch('mce_metrics_plugin.session.workflow_cohesion_index.SessionEntity._get_spans_for_agent', return_value=[create_agent_span()]):

            results = metric._compute_agent_level(session)

            # Verify processor was evaluated
            assert len(results) == 1
            result = results[0]

            # Check result indicates evaluation occurred
            assert result.success is True
            assert result.aggregation_level == "agent"

            # Verify role detection was called
            mock_role_detection.assert_called_once_with(session, "coder", filter_coordinators=True)

    @patch('mce_metrics_plugin.session.workflow_cohesion_index.get_agent_role_and_skip_decision')
    def test_workflow_cohesion_index_agent_level_filtering_disabled(self, mock_role_detection):
        """Test that all agents are evaluated when filtering is disabled."""
        # Setup mock role detection to indicate filtering is disabled
        mock_role_detection.return_value = (
            False,  # should_skip = False (filtering disabled)
            {
                'filtering_enabled': False,
                'skip_reason': 'Coordinator filtering disabled'
            }
        )

        # Setup metric with filtering disabled
        metric = WorkflowCohesionIndex(filter_coordinators=False)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Agent cohesion"))
        metric.jury = mock_jury

        # Create session with coordinator agent (should be evaluated despite role)
        session = create_session_with_conversation(agent_names=["supervisor"])

        # Mock agent conversation function
        def mock_get_agent_conversation_text(agent_name):
            return f"User: Help\nAgent {agent_name}: I'll coordinate this task."

        # Execute agent-level computation with mocked agent_stats and methods
        with patch.object(type(session), 'agent_stats', new_callable=lambda: property(lambda self: {"supervisor": {}})), \
             patch('mce_metrics_plugin.session.workflow_cohesion_index.SessionEntity.get_agent_conversation_text', side_effect=mock_get_agent_conversation_text), \
             patch('mce_metrics_plugin.session.workflow_cohesion_index.SessionEntity._get_spans_for_agent', return_value=[create_agent_span()]):

            results = metric._compute_agent_level(session)

            # Verify agent was evaluated despite being coordinator
            assert len(results) == 1
            result = results[0]

            assert result.success is True

            # Verify role detection was called with filtering disabled
            mock_role_detection.assert_called_once_with(session, "supervisor", filter_coordinators=False)

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_session_exception_handling(self):
        """Test graceful handling of exceptions during session computation."""
        # Setup metric with failing jury
        metric = WorkflowCohesionIndex()
        mock_jury = Mock()
        mock_jury.judge = Mock(side_effect=Exception("LLM error"))
        metric.jury = mock_jury

        # Create session with valid conversation data
        session = create_session_with_conversation()

        # Execute computation - should handle gracefully
        result = await metric.compute(session)

        # Verify error result structure
        assert result.value == -1  # Error value
        assert result.success is False
        assert result.error_message is not None  # Should have error message

    @pytest.mark.asyncio
    async def test_workflow_cohesion_index_invalid_llm_response(self):
        """Test handling of invalid LLM responses."""
        # Setup metric with invalid jury response
        metric = WorkflowCohesionIndex()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=None)  # Invalid response
        metric.jury = mock_jury

        # Create session with conversation
        session = create_session_with_conversation()

        # Execute computation
        result = await metric.compute(session)

        # Verify error handling
        assert result.success is False
        assert result.value == -1
        assert result.error_message is not None