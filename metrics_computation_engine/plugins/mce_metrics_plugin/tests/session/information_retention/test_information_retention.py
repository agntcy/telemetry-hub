# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import Mock, patch

from mce_metrics_plugin.session.information_retention import InformationRetention
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
    conversation_text="User: What's your name?\nBot: I'm Claude. How can I help you?",
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
    session = SessionEntity(session_id=session_id, spans=spans)

    # Ensure session has execution tree for agent_stats to work
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree

    if not hasattr(session, "execution_tree") or session.execution_tree is None:
        session.execution_tree = ExecutionTree()

    # Mock conversation data
    session.conversation_data = {"conversation": conversation_text}

    return session


class TestInformationRetention:
    """Test suite for InformationRetention metric with comprehensive coverage."""

    def test_information_retention_basic_properties(self):
        """Test basic metric properties and configuration."""
        metric = InformationRetention()

        assert metric.name == "InformationRetention"
        assert metric.aggregation_level == "session"
        assert "information" in metric.description.lower()
        assert "retention" in metric.description.lower()
        assert metric.required_parameters == ["conversation_data"]
        assert metric.validate_config() is True
        assert metric.supports_agent_computation() is True

    @pytest.mark.asyncio
    async def test_information_retention_session_level_success(self):
        """Test successful session-level information retention computation with high score."""
        # Setup metric with mock jury
        metric = InformationRetention()
        mock_jury = Mock()
        mock_jury.judge = Mock(
            return_value=(1, "Assistant consistently retains information accurately")
        )
        metric.jury = mock_jury

        # Create mock session with retention conversation
        conversation_text = "User: My name is Alice\nBot: Nice to meet you Alice!\nUser: What's my name?\nBot: Your name is Alice."
        session = create_session_with_conversation(
            conversation_text=conversation_text, agent_names=[]
        )

        # Execute computation
        result = await metric.compute(session)

        # Verify result
        assert result.value == 1
        assert (
            result.reasoning == "Assistant consistently retains information accurately"
        )
        assert result.success is True
        assert result.metric_name == "InformationRetention"
        assert result.session_id == ["test_session"]
        assert metric.description in result.description

        # Verify jury was called with correct parameters
        mock_jury.judge.assert_called_once()
        call_args = mock_jury.judge.call_args[0]
        assert conversation_text in call_args[0]
        assert call_args[1] == BinaryGrading

    @pytest.mark.asyncio
    async def test_information_retention_session_level_failure(self):
        """Test session-level information retention computation with low score."""
        # Setup metric with mock jury (low score)
        metric = InformationRetention()
        mock_jury = Mock()
        mock_jury.judge = Mock(
            return_value=(0, "Assistant fails to retain key information")
        )
        metric.jury = mock_jury

        # Create mock session with poor retention conversation
        conversation_text = "User: My name is Bob\nBot: Hello there!\nUser: What's my name?\nBot: I'm not sure."
        session = create_session_with_conversation(
            conversation_text=conversation_text, agent_names=[]
        )

        # Execute computation
        result = await metric.compute(session)

        # Verify result
        assert result.value == 0
        assert result.reasoning == "Assistant fails to retain key information"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_information_retention_no_model(self):
        """Test handling when no LLM judge is available."""
        # Setup metric without jury
        metric = InformationRetention()
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
    async def test_information_retention_agent_computation(self):
        """Test agent-level information retention computation."""
        # Setup metric with mock jury
        metric = InformationRetention()
        mock_jury = Mock()
        mock_jury.judge = Mock(
            side_effect=[
                (1, "Agent A retains information well"),
                (0, "Agent B fails to retain information"),
            ]
        )
        metric.jury = mock_jury

        # Create mock session with agents
        session = create_session_with_conversation(agent_names=["agent_a", "agent_b"])

        # Mock the agent conversation extraction
        def mock_get_agent_conversation_text(agent_name):
            if agent_name == "agent_a":
                return "User: I like pizza\nAgent A: Got it, you like pizza\nUser: What do I like?\nAgent A: You like pizza"
            elif agent_name == "agent_b":
                return "User: I work at Google\nAgent B: Interesting\nUser: Where do I work?\nAgent B: I don't remember"
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
                "mce_metrics_plugin.session.information_retention.SessionEntity.get_agent_conversation_text",
                side_effect=mock_get_agent_conversation_text,
            ),
            patch(
                "mce_metrics_plugin.session.information_retention.SessionEntity._get_spans_for_agent",
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
        assert agent_a_result.reasoning == "Agent A retains information well"
        assert agent_a_result.success is True
        assert agent_a_result.aggregation_level == "agent"
        assert agent_a_result.metadata["agent_id"] == "agent_a"
        assert agent_a_result.metadata["metric_type"] == "llm-as-a-judge"

        # Check agent_b result
        agent_b_result = next(r for r in results if r.metadata["agent_id"] == "agent_b")
        assert agent_b_result.value == 0
        assert agent_b_result.reasoning == "Agent B fails to retain information"
        assert agent_b_result.success is True

    @pytest.mark.asyncio
    async def test_information_retention_agent_no_conversation_data(self):
        """Test agent computation when agent has no conversation data."""
        # Setup metric with mock jury
        metric = InformationRetention()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Good retention"))
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
                "mce_metrics_plugin.session.information_retention.SessionEntity.get_agent_conversation_text",
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
    async def test_information_retention_agent_no_model(self):
        """Test agent computation when no LLM judge is available."""
        # Setup metric without jury
        metric = InformationRetention()
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
                "mce_metrics_plugin.session.information_retention.SessionEntity.get_agent_conversation_text",
                return_value="Agent conversation",
            ),
            patch(
                "mce_metrics_plugin.session.information_retention.SessionEntity._get_spans_for_agent",
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
    async def test_information_retention_empty_session(self):
        """Test handling of session with no agents."""
        # Setup metric
        metric = InformationRetention()
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
    async def test_information_retention_agent_exception_handling(self):
        """Test graceful handling of exceptions during agent computation."""
        # Setup metric
        metric = InformationRetention()
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
                "mce_metrics_plugin.session.information_retention.SessionEntity.get_agent_conversation_text",
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
            "Error computing information retention for agent problematic_agent"
            in result.error_message
        )
        assert "Conversation extraction failed" in result.error_message
        assert result.value == -1  # Error value
        assert result.metadata["agent_id"] == "problematic_agent"

    @pytest.mark.asyncio
    async def test_information_retention_prompt_formatting(self):
        """Test that conversation is properly formatted in the LLM prompt."""
        # Setup metric with mock jury
        metric = InformationRetention()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Good retention"))
        metric.jury = mock_jury

        # Create session with specific conversation
        conversation_text = (
            "User: Remember I'm a teacher\nBot: I'll remember you're a teacher"
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
        assert "You are an evaluator of Information Retention" in prompt
        assert "RESPONSES to evaluate:" in prompt

    @pytest.mark.asyncio
    async def test_information_retention_binary_grading(self):
        """Test that BinaryGrading is passed to judge method."""
        # Setup metric with mock jury
        metric = InformationRetention()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Good retention"))
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
    async def test_information_retention_session_no_conversation_data(self):
        """Test session computation when conversation_data is missing."""
        # Setup metric with mock jury
        metric = InformationRetention()
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Good retention"))
        metric.jury = mock_jury

        # Create session without conversation_data
        session = create_session_with_conversation(agent_names=[])
        session.conversation_data = None

        # Execute computation
        result = await metric.compute(session)
        assert result is not None

        # Verify empty conversation is handled
        mock_jury.judge.assert_called_once()
        prompt = mock_jury.judge.call_args[0][0]
        assert "RESPONSES to evaluate: " in prompt

    @pytest.mark.asyncio
    async def test_information_retention_model_initialization(self):
        """Test model initialization methods."""
        # Test init_with_model
        metric = InformationRetention()
        mock_model = Mock()
        result = metric.init_with_model(mock_model)
        assert result is True
        assert metric.jury == mock_model

        # Test get_model_provider
        metric.get_default_provider = Mock(return_value="test_provider")
        provider = metric.get_model_provider()
        assert provider == "test_provider"
        metric.get_default_provider.assert_called_once()

        # Test create_model
        metric.create_native_model = Mock(return_value="test_model")
        llm_config = {"test": "config"}
        model = metric.create_model(llm_config)
        assert model == "test_model"
        metric.create_native_model.assert_called_once_with(llm_config)

    # ===== Agent Role Detection Tests =====

    def test_information_retention_filter_coordinators_setting(self):
        """Test that the filter_coordinators setting is properly configured."""
        # Test default behavior (filtering enabled)
        metric_default = InformationRetention()
        assert metric_default.filter_coordinators is True

        # Test explicit filtering enabled
        metric_enabled = InformationRetention(filter_coordinators=True)
        assert metric_enabled.filter_coordinators is True

        # Test filtering disabled
        metric_disabled = InformationRetention(filter_coordinators=False)
        assert metric_disabled.filter_coordinators is False

    @patch(
        "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
    )
    async def test_information_retention_agent_level_coordinator_skipped(
        self, mock_role_detection
    ):
        """Test that coordinator agents are skipped when filtering is enabled."""
        # Setup mock role detection to identify agent as coordinator
        mock_role_detection.return_value = (
            True,  # should_skip = True
            {
                "filtering_enabled": True,
                "detected_role": "coordinator",
                "coordinator_score": 6,
                "processor_score": 2,
                "skip_reason": "Coordinator agents focus on task routing/workflow management",
                "tool_calls": 0,
                "coordination_signals": 5,
                "processing_signals": 1,
            },
        )

        # Setup metric with filtering enabled
        metric = InformationRetention(filter_coordinators=True)
        mock_jury = Mock()
        metric.jury = mock_jury

        # Create session with coordinator agent
        session = create_session_with_conversation(
            agent_names=["supervisor"],
            conversation_text='System: Route to worker\nAssistant: {"next": "coder"}',
        )

        # Create session with coordinator agent
        session = create_session_with_conversation(
            agent_names=["supervisor"],
            conversation_text='System: Route to worker\nAssistant: {"next": "coder"}',
        )

        # Mock the role detection function to return skip=True
        with patch(
            "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
        ) as mock_role_func:
            mock_role_func.return_value = (
                True,
                {
                    "detected_role": "coordinator",
                    "skip_reason": "Agent performs coordination tasks",
                },
            )

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

    @patch(
        "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
    )
    async def test_information_retention_agent_level_processor_evaluated(
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
        metric = InformationRetention(filter_coordinators=True)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Agent retains information well"))
        metric.jury = mock_jury

        # Create session with processor agent
        session = create_session_with_conversation(
            agent_names=["coder"],
            conversation_text="User: Remember that 2+2=4\nAssistant: Got it, 2+2 equals 4.\nUser: What did I just tell you?\nAssistant: You told me that 2+2=4.",
        )

        # Create session with processor agent
        session = create_session_with_conversation(
            agent_names=["coder"],
            conversation_text="User: Remember that 2+2=4\nAssistant: Got it, 2+2 equals 4.\nUser: What did I just tell you?\nAssistant: You told me that 2+2=4.",
        )

        # Mock the role detection function and conversation method
        with (
            patch(
                "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
            ) as mock_role_func,
            patch.object(type(session), "get_agent_conversation_text") as mock_conv,
        ):
            mock_role_func.return_value = (
                False,
                {
                    "detected_role": "processor",
                    "skip_reason": "Processor agents should be evaluated",
                },
            )
            mock_conv.return_value = "User: Remember that 2+2=4\nAssistant: Got it, 2+2 equals 4.\nUser: What did I just tell you?\nAssistant: You told me that 2+2=4."

            results = await metric.compute_agent_level(session)

            # Verify processor was evaluated
            assert len(results) == 1
            result = results[0]

            # Check result indicates evaluation occurred
            assert result.value == 1
            assert result.reasoning == "Agent retains information well"

            # Verify jury was called for evaluation
            mock_jury.judge.assert_called_once()

            # Verify role detection was called
            mock_role_func.assert_called_once_with(
                session, "coder", filter_coordinators=True
            )

    @patch(
        "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
    )
    async def test_information_retention_agent_level_filtering_disabled(
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
        metric = InformationRetention(filter_coordinators=False)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Information retained properly"))
        metric.jury = mock_jury

        # Create session with coordinator agent (should be evaluated despite role)
        session = create_session_with_conversation(
            agent_names=["supervisor"],
            conversation_text="System: Remember task context\nAssistant: Context noted for task routing",
        )

        # Create session with coordinator agent (should be evaluated despite role)
        session = create_session_with_conversation(
            agent_names=["supervisor"],
            conversation_text="System: Remember task context\nAssistant: Context noted for task routing",
        )

        # Mock the role detection function and conversation method
        with (
            patch(
                "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
            ) as mock_role_func,
            patch.object(type(session), "get_agent_conversation_text") as mock_conv,
        ):
            mock_role_func.return_value = (
                False,
                {
                    "detected_role": "coordinator",
                    "skip_reason": "Filtering disabled - evaluating all agents",
                },
            )
            mock_conv.return_value = "System: Remember task context\nAssistant: Context noted for task routing"

            results = await metric.compute_agent_level(session)

            # Verify agent was evaluated despite being coordinator
            assert len(results) == 1
            result = results[0]

            assert result.value == 1

            # Verify jury was called
            mock_jury.judge.assert_called_once()

            # Verify role detection was called with filtering disabled
            mock_role_func.assert_called_once_with(
                session, "supervisor", filter_coordinators=False
            )

    @patch(
        "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
    )
    async def test_information_retention_agent_level_mixed_agents(
        self, mock_role_detection
    ):
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
            elif agent_name == "researcher":
                return (
                    False,
                    {
                        "filtering_enabled": True,
                        "detected_role": "processor",
                        "coordinator_score": 0,
                        "processor_score": 8,
                        "skip_reason": "Processor agents handle information",
                        "tool_calls": 3,
                        "coordination_signals": 0,
                        "processing_signals": 5,
                    },
                )

        mock_role_detection.side_effect = mock_role_side_effect

        # Setup metric
        metric = InformationRetention(filter_coordinators=True)
        mock_jury = Mock()
        mock_jury.judge = Mock(
            return_value=(1, "Researcher agent retains information well")
        )
        metric.jury = mock_jury

        # Create session with both agent types
        session = create_session_with_conversation(
            agent_names=["supervisor", "researcher"],
            conversation_text="Mixed agent information retention test",
        )

        # Create session with mixed agents
        session = create_session_with_conversation(
            agent_names=["supervisor", "researcher"],
            conversation_text="Mixed agent information retention test",
        )

        # Mock the role detection function and conversation method
        with (
            patch(
                "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
            ) as mock_role_func,
            patch.object(type(session), "get_agent_conversation_text") as mock_conv,
        ):
            mock_role_func.side_effect = mock_role_side_effect
            mock_conv.return_value = "Agent conversation with information"

            results = await metric.compute_agent_level(session)

            # Should have 1 result: supervisor skipped, researcher evaluated
            assert len(results) == 1

            # The result should be from the researcher (processor)
            result = results[0]
            assert result.value == 1

            # Jury called once (for researcher only)
            mock_jury.judge.assert_called_once()

            # Role detection called twice (once for each agent)
            assert mock_role_func.call_count == 2

    @patch(
        "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
    )
    async def test_information_retention_agent_level_role_detection_error(
        self, mock_role_detection
    ):
        """Test handling when role detection fails."""
        # Setup mock role detection to return analysis failure
        mock_role_detection.return_value = (
            False,  # should_skip = False (conservative)
            {
                "filtering_enabled": True,
                "detected_role": "unknown",
                "skip_reason": "Could not analyze agent behavior - evaluating conservatively",
                "analysis_failed": True,
            },
        )

        # Setup metric
        metric = InformationRetention(filter_coordinators=True)
        mock_jury = Mock()
        mock_jury.judge = Mock(return_value=(1, "Evaluated despite analysis failure"))
        metric.jury = mock_jury

        # Create session
        session = create_session_with_conversation(agent_names=["unknown_agent"])

        # Create session
        session = create_session_with_conversation(agent_names=["unknown_agent"])

        # Mock the role detection function and conversation method
        with (
            patch(
                "mce_metrics_plugin.session.information_retention.get_agent_role_and_skip_decision"
            ) as mock_role_func,
            patch.object(type(session), "get_agent_conversation_text") as mock_conv,
        ):
            mock_role_func.return_value = (
                False,
                {
                    "detected_role": "unknown",
                    "skip_reason": "Could not analyze agent behavior - evaluating conservatively",
                },
            )
            mock_conv.return_value = "Some conversation about information"

            results = await metric.compute_agent_level(session)

            # Verify agent was evaluated conservatively
            assert len(results) == 1
            result = results[0]

            assert result.value == 1

            # Verify jury was called
            mock_jury.judge.assert_called_once()

            # Verify role detection was called
            mock_role_func.assert_called_once_with(
                session, "unknown_agent", filter_coordinators=True
            )

        # Verify jury was called (conservative evaluation)
        mock_jury.judge.assert_called_once()
