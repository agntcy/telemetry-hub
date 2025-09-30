# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest

from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session_set import SessionSet
from metrics_computation_engine.entities.core.session_aggregator import (
    SessionAggregator,
)
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry

# Import the GoalSuccessRate directly from the plugin system
from mce_metrics_plugin.session.goal_success_rate import GoalSuccessRate


def create_session_from_spans(spans):
    """Helper function to create a session entity from spans using the new SessionAggregator API."""
    if not spans:
        raise ValueError("No spans provided")

    aggregator = SessionAggregator()
    session_id = spans[0].session_id
    session = aggregator.create_session_from_spans(session_id, spans)

    # Extract input_query and final_response from LLM spans for metric requirements
    for span in spans:
        if span.entity_type == "llm" and span.input_payload and span.output_payload:
            # Extract user input from the first user role prompt
            for key, value in span.input_payload.items():
                if key.startswith("gen_ai.prompt") and ".content" in key:
                    role_key = key.replace(".content", ".role")
                    role = span.input_payload.get(role_key, "")
                    if role == "user":
                        session.input_query = value
                        break

            # Extract final response from the output (last assistant/user response)
            for key, value in span.output_payload.items():
                if key.startswith("gen_ai.prompt") and ".content" in key:
                    role_key = key.replace(".content", ".role")
                    role = span.output_payload.get(role_key, "")
                    if role in [
                        "assistant",
                        "user",
                    ]:  # Sometimes responses are marked as "user" in test data
                        session.final_response = value

    return session


# Mock jury class to simulate LLM evaluation for GoalSuccessRate
class MockGoalSuccessRateJury:
    """Mock jury for testing GoalSuccessRate without actual LLM calls."""

    def __init__(self, default_score=1, default_reasoning=None):
        self.default_score = default_score
        self.default_reasoning = (
            default_reasoning or "Mock evaluation: Goal successfully achieved."
        )

    def judge(self, prompt, grading_cls):
        """Mock judge method that returns deterministic results based on prompt content."""
        # Analyze prompt content to return different scores for different scenarios
        prompt_lower = prompt.lower()

        # Check for successful mathematical operations first (more specific)
        if "2 + 2" in prompt and "4" in prompt:
            return float(
                1
            ), "Mock evaluation: Mathematical question correctly answered."

        # Check for successful code generation
        if "python function" in prompt_lower and "def " in prompt:
            return float(
                1
            ), "Mock evaluation: Code successfully generated as requested."

        # Check for travel planning success
        if "paris" in prompt_lower and "itinerary" in prompt_lower:
            return float(
                1
            ), "Mock evaluation: Travel planning request successfully fulfilled."

        # Check for clear failure scenarios (put after success checks)
        if any(
            fail_keyword in prompt_lower
            for fail_keyword in [
                "error",
                "failed",
                "cannot",
                "unable",
                "sorry",
                "apologize",
            ]
        ):
            return (
                float(0),
                "Mock evaluation: Goal not achieved due to error or inability to fulfill request.",
            )

        # Check for incomplete responses
        if any(
            incomplete_keyword in prompt_lower
            for incomplete_keyword in [
                "partial",
                "incomplete",
                "more information needed",
            ]
        ):
            return float(0), "Mock evaluation: Goal partially achieved but incomplete."

        # Default case - return configured default as float
        return float(self.default_score), self.default_reasoning


def make_llm_span(
    span_id: str,
    session_id: str = "session1",
    input_data: dict = None,
    output_data: dict = None,
):
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

    return SpanEntity(
        entity_type="llm",
        span_id=span_id,
        entity_name="travel_assistant",
        app_name="travel_assistant_app",
        timestamp="2025-06-20 21:37:02.832759",
        parent_span_id=None,
        trace_id="trace1",
        session_id=session_id,
        start_time="1750455422.83277",
        end_time="1750455423.7407782",
        input_payload=input_data or default_input,
        output_payload=output_data or default_output,
        contains_error=False,
        raw_span_data={},
    )


def make_non_llm_span(
    entity_type: str,
    span_id: str,
    session_id: str = "session1",
):
    """Helper function to create non-llm spans for testing."""
    return SpanEntity(
        entity_type=entity_type,
        span_id=span_id,
        entity_name="test_entity",
        app_name="travel_assistant_app",
        timestamp="2025-06-20 21:37:02.832759",
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


@pytest.mark.asyncio
async def test_compute_with_mock_jury_successful_goal():
    """Test computation with mock jury for a successful goal achievement."""
    metric = GoalSuccessRate()

    # Use mock jury instead of real LLM
    mock_jury = MockGoalSuccessRateJury(default_score=1)
    metric.init_with_model(mock_jury)

    # Create spans with a clear successful goal achievement
    spans = [
        make_llm_span(
            "llm_1",
            input_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "What is 2+2?",
                "gen_ai.prompt.1.role": "user",
            },
            output_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "What is 2+2?",
                "gen_ai.prompt.1.role": "user",
                "gen_ai.prompt.2.content": "4",
                "gen_ai.prompt.2.role": "user",
            },
        ),
    ]

    session_entity = create_session_from_spans(spans)
    result = await metric.compute(session_entity)

    assert result.success is True
    assert isinstance(result.value, float)
    assert 0.0 <= result.value <= 1.0
    assert result.span_id == ["llm_1"]
    assert result.session_id == ["session1"]
    assert result.metric_name == "GoalSuccessRate"
    assert result.aggregation_level == "session"
    assert isinstance(result.reasoning, str)
    assert len(result.reasoning) > 0
    assert "Mock evaluation" in result.reasoning


@pytest.mark.asyncio
async def test_compute_with_mock_jury_failed_goal():
    """Test computation with mock jury for a failed goal achievement."""
    metric = GoalSuccessRate()

    # Use mock jury that simulates failure
    mock_jury = MockGoalSuccessRateJury(default_score=0)
    metric.init_with_model(mock_jury)

    # Create spans with a failed goal achievement
    spans = [
        make_llm_span(
            "llm_1",
            input_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "What is 2+2?",
                "gen_ai.prompt.1.role": "user",
            },
            output_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "What is 2+2?",
                "gen_ai.prompt.1.role": "user",
                "gen_ai.prompt.2.content": "Sorry I cannot perform that mathematical calculation.",
                "gen_ai.prompt.2.role": "user",
            },
        ),
    ]

    session_entity = create_session_from_spans(spans)
    result = await metric.compute(session_entity)

    assert result.success is True  # Computation succeeded
    assert result.value == 0.0  # But goal failed
    assert result.span_id == ["llm_1"]
    assert result.session_id == ["session1"]
    assert result.metric_name == "GoalSuccessRate"
    assert result.aggregation_level == "session"
    assert isinstance(result.reasoning, str)
    assert len(result.reasoning) > 0
    assert "not achieved" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_compute_no_jury():
    """Test computation without any jury configured."""
    metric = GoalSuccessRate()
    # Don't initialize with any model

    spans = [
        make_llm_span(
            "llm_1",
            input_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "What is 2+2?",
                "gen_ai.prompt.1.role": "user",
            },
            output_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "What is 2+2?",
                "gen_ai.prompt.1.role": "user",
                "gen_ai.prompt.2.content": "2+2=4",
                "gen_ai.prompt.2.role": "user",
            },
        ),
    ]

    session_entity = create_session_from_spans(spans)
    result = await metric.compute(session_entity)

    assert result.success is False
    assert result.error_message == "No model available"
    assert result.span_id == ["llm_1"]
    assert result.session_id == ["session1"]


@pytest.mark.asyncio
async def test_goal_success_rate_mock_end_to_end():
    """Test GoalSuccessRate metric end-to-end using mock jury."""
    # Create test spans with llm data
    spans = [
        make_llm_span(
            "llm_1",
            input_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "Can you help me write a Python function to calculate the area of a circle?",
                "gen_ai.prompt.1.role": "user",
            },
            output_data={
                "gen_ai.prompt.0.content": "You are a math assistant",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "Can you help me write a Python function to calculate the area of a circle?",
                "gen_ai.prompt.1.role": "user",
                "gen_ai.prompt.2.content": "Here's a Python function to calculate the area of a circle:\n\nimport math\n\ndef circle_area(radius):\n    return math.pi * radius ** 2\n\nThis function takes the radius as input and returns the area using the formula π × r².",
                "gen_ai.prompt.2.role": "user",
            },
        ),
        make_non_llm_span("agent", "agent_1"),
    ]

    # Set up registry and processor with mock jury
    registry = MetricRegistry()
    registry.register_metric(GoalSuccessRate, "GoalSuccessRate")

    # Create a testable GoalSuccessRate that uses mock jury
    class MockableGoalSuccessRate(GoalSuccessRate):
        def create_model(self, llm_config):
            return MockGoalSuccessRateJury(default_score=1)

    registry = MetricRegistry()
    registry.register_metric(MockableGoalSuccessRate, "GoalSuccessRate")

    # Use dummy LLM config since we're using mock
    llm_config = LLMJudgeConfig(
        LLM_API_KEY="dummy_key",
        LLM_BASE_MODEL_URL="dummy_url",
        LLM_MODEL_NAME="dummy_model",
    )

    model_handler = ModelHandler()
    processor = MetricsProcessor(
        registry=registry,
        model_handler=model_handler,
        llm_config=llm_config,
    )

    session_entity = create_session_from_spans(spans)
    sessions_set = SessionSet(sessions=[session_entity])

    results = await processor.compute_metrics(sessions_set)

    # Validate results
    session_metrics = results.get("session_metrics", [])
    assert len(session_metrics) == 1

    goal_success_metric = session_metrics[0]
    assert goal_success_metric.metric_name == "GoalSuccessRate"
    assert isinstance(goal_success_metric.value, float)
    assert 0.0 <= goal_success_metric.value <= 1.0
    assert goal_success_metric.success is True
    assert goal_success_metric.reasoning is not None
    assert len(goal_success_metric.span_id) > 0
    assert len(goal_success_metric.session_id) > 0
    assert "Mock evaluation" in goal_success_metric.reasoning
