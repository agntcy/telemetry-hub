# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import Mock, patch

from mce_metrics_plugin.session.groundedness import Groundedness
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.models.eval import BinaryGrading


def create_agent_span(
    span_id: str = "span_1",
    session_id: str = "test_session",
    entity_name: str = "agent",
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
    conversation_text="User: Hello\nBot: Hi there!",
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

    # Create SessionEntity directly like in other tests
    session = SessionEntity(session_id=session_id, spans=spans)

    # Ensure session has execution tree for agent_stats to work
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree

    if not hasattr(session, "execution_tree") or session.execution_tree is None:
        session.execution_tree = ExecutionTree()

    # Mock conversation data
    session.conversation_data = {"conversation": conversation_text}

    return session


class TestGroundedness:
    """Test suite for Groundedness metric with comprehensive coverage."""

    def test_groundedness_basic_properties(self):
        """Test basic metric properties and configuration."""
        metric = Groundedness()

        assert metric.name == "Groundedness"
        assert metric.aggregation_level == "session"
        assert "grounded" in metric.description.lower()
        assert "verifiable" in metric.description.lower()
        assert metric.required_parameters == ["conversation_data"]
        assert metric.validate_config() is True
        assert metric.supports_agent_computation() is True

    def test_groundedness_filter_coordinators_setting(self):
        """Test that the filter_coordinators setting is properly configured."""
        # Default should enable filtering
        metric_default = Groundedness()
        assert metric_default.filter_coordinators is True

        # Explicitly enabled
        metric_enabled = Groundedness(filter_coordinators=True)
        assert metric_enabled.filter_coordinators is True

        # Explicitly disabled
        metric_disabled = Groundedness(filter_coordinators=False)
        assert metric_disabled.filter_coordinators is False

    @pytest.mark.asyncio
    async def test_groundedness_session_level_success(self):
        """Test successful session-level groundedness computation with high score."""
        # Setup metric with mock jury
        metric = Groundedness()
        mock_jury = Mock()
        mock_jury.judge = Mock(
            return_value=(1, "Response is fully grounded in provided context")
        )
        metric.jury = mock_jury

        # Create mock session with conversation
        conversation_text = "User: What's the capital of France?\nBot: According to the provided data, the capital of France is Paris."
        session = create_session_with_conversation(
            conversation_text=conversation_text, agent_names=[]
        )

        # Execute computation
        result = await metric.compute(session)

        # Verify result
        assert result.value == 1
        assert result.reasoning == "Response is fully grounded in provided context"
        assert result.success is True
        assert result.metric_name == "Groundedness"
        assert result.session_id == ["test_session"]
        assert metric.description in result.description

        # Verify jury was called with correct parameters
        mock_jury.judge.assert_called_once()
        call_args = mock_jury.judge.call_args[0]
        assert conversation_text in call_args[0]
        assert call_args[1] == BinaryGrading

    @pytest.mark.asyncio
    async def test_groundedness_session_level_failure(self):
        """Test session-level groundedness computation with low score."""
        # Setup metric with mock jury (low score)
        metric = Groundedness()
        mock_jury = Mock()
        mock_jury.judge = Mock(
            return_value=(0, "Response contains unverifiable claims")
        )
        metric.jury = mock_jury

        # Create mock session with ungrounded conversation
        conversation_text = "User: Tell me about unicorns\nBot: Unicorns are real creatures that live in forests and have magical powers."
        session = create_session_with_conversation(
            conversation_text=conversation_text, agent_names=[]
        )

        # Execute computation
        result = await metric.compute(session)

        # Verify result
        assert result.value == 0
        assert result.reasoning == "Response contains unverifiable claims"
        assert result.success is True
        assert result.metric_name == "Groundedness"

    @pytest.mark.asyncio
    async def test_groundedness_no_model(self):
        """Test handling when no LLM judge is available."""
        # Setup metric without jury
        metric = Groundedness()
        metric.jury = None

        # Create mock session
        session = create_session_with_conversation(
            conversation_text="Test conversation", agent_names=[]
        )

        # Execute computation
        result = await metric.compute(session)

        # Verify error result
        assert result.success is False
        assert result.error_message == "No model available"
        assert result.value == -1  # Error value

    @pytest.mark.asyncio
    async def test_groundedness_agent_computation(self):
        """Test agent-level groundedness computation."""
        # Setup metric with mock jury
        metric = Groundedness()
        mock_jury = Mock()
        mock_jury.judge = Mock(
            side_effect=[
                (1, "Agent A responses are grounded"),
                (0, "Agent B responses contain speculation"),
            ]
        )
        metric.jury = mock_jury

        # Create mock session with agents
        session = create_session_with_conversation(agent_names=["agent_a", "agent_b"])

        # Mock the agent conversation extraction
        def mock_get_agent_conversation_text(agent_name):
            if agent_name == "agent_a":
                return "User: What time is it?\nAgent A: According to the system clock, it's 3:00 PM."
            elif agent_name == "agent_b":
                return "User: Will it rain?\nAgent B: I predict it will definitely rain tomorrow."
            return ""

        # Mock agent spans
        def mock_get_spans_for_agent(agent_name):
            return [Mock(span_id=f"{agent_name}_span_1")]

        # Mock the agent_stats property and methods together
        with (
            patch.object(
                type(session),
                "agent_stats",
                new_callable=lambda: property(
                    lambda self: {"agent_a": {}, "agent_b": {}}
                ),
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity.get_agent_conversation_text",
                side_effect=mock_get_agent_conversation_text,
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity._get_spans_for_agent",
                side_effect=mock_get_spans_for_agent,
            ),
        ):
            results = await metric.compute_with_dispatch(
                session, agent_computation=True
            )

        # Verify results
        assert len(results) == 2

        # Check agent_a result
        agent_a_result = next(r for r in results if r.metadata["agent_id"] == "agent_a")
        assert agent_a_result.value == 1
        assert agent_a_result.reasoning == "Agent A responses are grounded"
        assert agent_a_result.success is True
        assert agent_a_result.aggregation_level == "agent"
        assert agent_a_result.metadata["agent_id"] == "agent_a"
        assert agent_a_result.metadata["metric_type"] == "llm-as-a-judge"

        # Check agent_b result
        agent_b_result = next(r for r in results if r.metadata["agent_id"] == "agent_b")
        assert agent_b_result.value == 0
        assert agent_b_result.reasoning == "Agent B responses contain speculation"
        assert agent_b_result.success is True

    @pytest.mark.asyncio
    async def test_groundedness_agent_no_conversation_data(self):
        """Test agent computation when agent has no conversation data."""
        # Setup metric with mock jury
        metric = Groundedness()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Grounded"))
        metric.jury = mock_jury

        # Create session with agent that has no conversation
        session = create_session_with_conversation(agent_names=["silent_agent"])

        # Execute agent computation with mocked agent_stats and methods
        with (
            patch.object(
                type(session),
                "agent_stats",
                new_callable=lambda: property(lambda self: {"silent_agent": {}}),
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity.get_agent_conversation_text",
                return_value="",
            ),
        ):  # No conversation
            results = await metric.compute_with_dispatch(
                session, agent_computation=True
            )

        # Verify no results for silent agent
        assert len(results) == 0
        mock_jury.judge.assert_not_called()

    @pytest.mark.asyncio
    async def test_groundedness_agent_no_model(self):
        """Test agent computation when no LLM judge is available."""
        # Setup metric without jury
        metric = Groundedness()
        metric.jury = None

        # Create mock session
        session = create_session_with_conversation(agent_names=["agent_a"])

        # Execute agent computation with mocked agent_stats and methods
        with (
            patch.object(
                type(session),
                "agent_stats",
                new_callable=lambda: property(lambda self: {"agent_a": {}}),
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity.get_agent_conversation_text",
                return_value="Agent conversation",
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity._get_spans_for_agent",
                return_value=[Mock(span_id="span_1")],
            ),
        ):
            results = await metric.compute_with_dispatch(
                session, agent_computation=True
            )

        # Verify error result
        assert len(results) == 1
        result = results[0]
        assert result.success is False
        assert result.error_message == "No model available"
        assert result.value == -1  # Error value
        assert result.metadata["agent_id"] == "agent_a"

    @pytest.mark.asyncio
    async def test_groundedness_empty_session(self):
        """Test handling of session with no agents."""
        # Setup metric
        metric = Groundedness()
        metric.jury = Mock()

        # Create session with no agents
        session = create_session_with_conversation(agent_names=[])

        # Execute agent computation with empty agent_stats
        with patch.object(
            type(session), "agent_stats", new_callable=lambda: property(lambda self: {})
        ):
            results = await metric.compute_with_dispatch(
                session, agent_computation=True
            )

        # Verify empty results
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_groundedness_agent_exception_handling(self):
        """Test graceful handling of exceptions during agent computation."""
        # Setup metric
        metric = Groundedness()
        metric.jury = Mock()

        # Create session with problematic agent
        session = create_session_with_conversation(agent_names=["problematic_agent"])

        # Execute agent computation with mocked agent_stats and failing method
        with (
            patch.object(
                type(session),
                "agent_stats",
                new_callable=lambda: property(lambda self: {"problematic_agent": {}}),
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity.get_agent_conversation_text",
                side_effect=Exception("Conversation extraction failed"),
            ),
        ):
            results = await metric.compute_with_dispatch(
                session, agent_computation=True
            )

        # Verify error handling
        assert len(results) == 1
        result = results[0]
        assert result.success is False
        assert (
            "Error computing groundedness for agent problematic_agent"
            in result.error_message
        )
        assert "Conversation extraction failed" in result.error_message
        assert result.value == -1  # Error value
        assert result.metadata["agent_id"] == "problematic_agent"

    @pytest.mark.asyncio
    async def test_groundedness_prompt_formatting(self):
        """Test that conversation is properly formatted in the LLM prompt."""
        # Setup metric with mock jury
        metric = Groundedness()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Grounded"))
        metric.jury = mock_jury

        # Create session with specific conversation
        conversation_text = (
            "User: What's 2+2?\nBot: Based on mathematics, 2+2 equals 4."
        )
        session = create_session_with_conversation(
            conversation_text=conversation_text, agent_names=[]
        )

        # Execute computation
        result = await metric.compute(session)
        assert result is not None

        # Verify prompt contains conversation
        mock_jury.judge.assert_called_once()
        prompt = mock_jury.judge.call_args[0][0]
        assert conversation_text in prompt
        assert "You are an evaluator of Groundedness" in prompt
        assert "CONVERSATION:" in prompt

    @pytest.mark.asyncio
    async def test_groundedness_binary_grading(self):
        """Test that BinaryGrading is passed to judge method."""
        # Setup metric with mock jury
        metric = Groundedness()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Grounded"))
        metric.jury = mock_jury

        # Create session
        session = create_session_with_conversation(
            conversation_text="test", agent_names=[]
        )

        # Execute computation
        await metric.compute(session)

        # Verify BinaryGrading was passed
        mock_jury.judge.assert_called_once()
        assert mock_jury.judge.call_args[0][1] == BinaryGrading

    @pytest.mark.asyncio
    async def test_groundedness_session_no_conversation_data(self):
        """Test session computation when conversation_data is missing."""
        # Setup metric with mock jury
        metric = Groundedness()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Grounded"))
        metric.jury = mock_jury

        # Create session without conversation data
        session = create_session_with_conversation(agent_names=["agent"])
        session.conversation_data = None  # Remove conversation data

        # Execute computation
        result = await metric.compute(session)
        assert result is not None

        # Verify empty conversation was used
        mock_jury.judge.assert_called_once()
        prompt = mock_jury.judge.call_args[0][0]
        assert "CONVERSATION: " in prompt

    async def test_groundedness_agent_level_coordinator_skipped(self):
        """Test that coordinator agents are skipped when filtering is enabled."""
        # Setup metric with filtering enabled
        metric = Groundedness(filter_coordinators=True)
        mock_jury = Mock()
        metric.jury = mock_jury

        # Create session with coordinator agent
        session = create_session_with_conversation(
            agent_names=["supervisor"],
            conversation_text='System: Route to worker\nAssistant: {"next": "coder"}',
        )

        # Mock the role detection function to return skip=True
        with patch(
            "mce_metrics_plugin.session.groundedness.get_agent_role_and_skip_decision"
        ) as mock_role_func:
            mock_role_func.return_value = (
                True,
                {
                    "detected_role": "coordinator",
                    "skip_reason": "Agent performs coordination tasks",
                },
            )

            # Debug: Verify the mock is set up correctly
            print(f"Mock return value: {mock_role_func.return_value}")

            results = await metric.compute_agent_level(session)

            # Verify coordinator was skipped - no results should be returned
            assert len(results) == 0, (
                f"Expected no results for skipped agents, but got: {results}"
            )

            # Verify jury was not called (agent was skipped)
            mock_jury.judge.assert_not_called()

            # Verify role detection was called with correct parameters
            mock_role_func.assert_called_once_with(
                session, "supervisor", filter_coordinators=True
            )

    @patch("mce_metrics_plugin.session.groundedness.get_agent_role_and_skip_decision")
    async def test_groundedness_agent_level_processor_evaluated(
        self, mock_role_detection
    ):
        """Test that processor agents are evaluated when filtering is enabled."""
        # Setup mock role detection to identify agent as processor
        mock_role_detection.return_value = (
            False,  # should_skip = False
            {
                "filtering_enabled": True,
                "detected_role": "processor",
                "coordinator_score": 1,
                "processor_score": 7,
                "skip_reason": "Processor agents handle information and should be evaluated",
                "tool_calls": 2,
                "coordination_signals": 0,
                "processing_signals": 4,
            },
        )

        # Setup metric with filtering enabled
        metric = Groundedness(filter_coordinators=True)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Agent responses are grounded"))
        metric.jury = mock_jury

        # Create session with processor agent
        session = create_session_with_conversation(
            agent_names=["coder"],
            conversation_text="User: Calculate 2+2\nAssistant: Based on mathematical rules, the result is 4.",
        )

        # Execute agent-level computation with mocked agent_stats and methods
        with (
            patch.object(
                type(session),
                "agent_stats",
                new_callable=lambda: property(lambda self: {"coder": Mock()}),
            ),
            patch.object(
                session, "_get_spans_for_agent", return_value=[create_agent_span()]
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity.get_agent_conversation_text",
                return_value="User: Calculate 2+2\nAssistant: Based on mathematical rules, the result is 4.",
            ),
        ):
            results = await metric.compute_agent_level(session)

            # Verify processor was evaluated
            assert len(results) == 1
            result = results[0]

            # Check result indicates evaluation occurred
            assert result.value == 1
            assert result.reasoning == "Agent responses are grounded"

            # Verify jury was called for evaluation
            mock_jury.judge.assert_called_once()

            # Verify role detection was called
            mock_role_detection.assert_called_once_with(
                session, "coder", filter_coordinators=True
            )

    @patch("mce_metrics_plugin.session.groundedness.get_agent_role_and_skip_decision")
    async def test_groundedness_agent_level_filtering_disabled(
        self, mock_role_detection
    ):
        """Test that all agents are evaluated when filtering is disabled."""
        # Setup mock role detection to indicate filtering is disabled
        mock_role_detection.return_value = (
            False,  # should_skip = False (filtering disabled)
            {
                "filtering_enabled": False,
                "skip_reason": "Coordinator filtering disabled",
            },
        )

        # Setup metric with filtering disabled
        metric = Groundedness(filter_coordinators=False)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Responses are grounded"))
        metric.jury = mock_jury

        # Create session with coordinator agent (should be evaluated despite role)
        session = create_session_with_conversation(
            agent_names=["supervisor"],
            conversation_text='System: Route tasks\nAssistant: {"next": "finish"}',
        )

        # Execute agent-level computation with mocked agent_stats and methods
        with (
            patch.object(
                type(session),
                "agent_stats",
                new_callable=lambda: property(lambda self: {"supervisor": Mock()}),
            ),
            patch.object(
                session, "_get_spans_for_agent", return_value=[create_agent_span()]
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity.get_agent_conversation_text",
                return_value='System: Route tasks\nAssistant: {"next": "finish"}',
            ),
        ):
            results = await metric.compute_agent_level(session)

            # Verify agent was evaluated despite being coordinator
            assert len(results) == 1
            result = results[0]

            assert result.value == 1

            # Verify jury was called
            mock_jury.judge.assert_called_once()

            # Verify role detection was called with filtering disabled
            mock_role_detection.assert_called_once_with(
                session, "supervisor", filter_coordinators=False
            )

    @patch("mce_metrics_plugin.session.groundedness.get_agent_role_and_skip_decision")
    async def test_groundedness_agent_level_mixed_agents(self, mock_role_detection):
        """Test mixed scenario with both coordinator and processor agents."""

        # Setup mock role detection for different agent types
        def mock_role_side_effect(session, agent_name, filter_coordinators):
            if agent_name == "supervisor":
                return (
                    True,
                    {
                        "filtering_enabled": True,
                        "detected_role": "coordinator",
                        "coordinator_score": 6,
                        "processor_score": 1,
                        "skip_reason": "Coordinator agents focus on task routing",
                        "tool_calls": 0,
                        "coordination_signals": 4,
                        "processing_signals": 1,
                    },
                )
            elif agent_name == "coder":
                return (
                    False,
                    {
                        "filtering_enabled": True,
                        "detected_role": "processor",
                        "coordinator_score": 1,
                        "processor_score": 8,
                        "skip_reason": "Processor agents should be evaluated",
                        "tool_calls": 3,
                        "coordination_signals": 0,
                        "processing_signals": 5,
                    },
                )
            else:
                return (False, {})

        mock_role_detection.side_effect = mock_role_side_effect

        # Setup metric with filtering enabled
        metric = Groundedness(filter_coordinators=True)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Processor responses are grounded"))
        metric.jury = mock_jury

        # Create session with mixed agents
        session = create_session_with_conversation(
            agent_names=["supervisor", "coder"],
            conversation_text="Mixed agent conversation",
        )

        # Mock conversation extraction for different agents
        def mock_get_agent_conversation_text(agent_name):
            if agent_name == "supervisor":
                return "System: Coordinate tasks\nSupervisor: Routing to coder"
            elif agent_name == "coder":
                return (
                    "User: Fix bug\nCoder: Based on the error log, I'll apply this fix."
                )
            return ""

        # Execute agent-level computation with mocked agent_stats and methods
        with (
            patch.object(
                type(session),
                "agent_stats",
                new_callable=lambda: property(
                    lambda self: {"supervisor": Mock(), "coder": Mock()}
                ),
            ),
            patch.object(
                session, "_get_spans_for_agent", return_value=[create_agent_span()]
            ),
            patch(
                "mce_metrics_plugin.session.groundedness.SessionEntity.get_agent_conversation_text",
                side_effect=mock_get_agent_conversation_text,
            ),
        ):
            results = await metric.compute_agent_level(session)

            # Verify only processor agent was evaluated (supervisor skipped)
            assert len(results) == 1
            result = results[0]
            assert result.metadata["agent_id"] == "coder"
            assert result.value == 1
            assert result.reasoning == "Processor responses are grounded"

            # Verify jury was called only once (for processor agent)
            mock_jury.judge.assert_called_once()

            # Verify role detection was called for both agents
            assert mock_role_detection.call_count == 2
