import os

import pytest

from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict

# Import the GoalSuccessRate directly from the plugin system
from goal_success_rate import GoalSuccessRate


def make_workflow_span(
    span_id: str,
    session_id: str = "session1",
    input_data: dict = None,
    output_data: dict = None,
):
    """Helper function to create workflow spans for testing."""
    default_input = {
        "inputs": {"chat_history": [{"message": "Help me plan a trip to Paris"}]}
    }
    default_output = {
        "outputs": {
            "messages": [
                {"message": "Help me plan a trip to Paris"},
                {
                    "kwargs": {
                        "content": "I'd be happy to help you plan your trip to Paris! Here's a suggested itinerary..."
                    }
                },
            ]
        }
    }

    return SpanEntity(
        entity_type="workflow",
        span_id=span_id,
        entity_name="travel_assistant",
        timestamp="2024-01-01T10:00:00Z",
        parent_span_id=None,
        trace_id="trace1",
        session_id=session_id,
        start_time="1234567890.0",
        end_time="1234567891.0",
        input_payload=input_data or default_input,
        output_payload=output_data or default_output,
        contains_error=False,
        raw_span_data={},
    )


def make_non_workflow_span(
    entity_type: str,
    span_id: str,
    session_id: str = "session1",
):
    """Helper function to create non-workflow spans for testing."""
    return SpanEntity(
        entity_type=entity_type,
        span_id=span_id,
        entity_name="test_entity",
        timestamp="2024-01-01T10:00:00Z",
        parent_span_id=None,
        trace_id="trace1",
        session_id=session_id,
        start_time="1234567890.0",
        end_time="1234567891.0",
        input_payload={},
        output_payload={},
        contains_error=False,
        raw_span_data={},
    )


@pytest.mark.asyncio
async def test_compute_with_actual_model_successful_goal():
    """Test computation with actual model for a successful goal achievement."""
    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not set; skipping actual model test")

    metric = GoalSuccessRate()

    # Create LLM config and initialize model
    llm_config = LLMJudgeConfig(
        LLM_API_KEY=os.getenv("LLM_API_KEY", ""),
        LLM_BASE_MODEL_URL=os.getenv("LLM_BASE_MODEL_URL", ""),
        LLM_MODEL_NAME=os.getenv("LLM_MODEL_NAME", ""),
    )

    model = metric.create_model(llm_config)
    metric.init_with_model(model)

    # Create spans with a clear successful goal achievement
    spans = [
        make_workflow_span(
            "workflow_1",
            input_data={"inputs": {"chat_history": [{"message": "What is 2 + 2?"}]}},
            output_data={
                "outputs": {
                    "messages": [
                        {"message": "What is 2 + 2?"},
                        {"kwargs": {"content": "2 + 2 = 4"}},
                    ]
                }
            },
        ),
    ]

    traces_by_session = {spans[0].session_id: spans}
    session_entities = build_session_entities_from_dict(traces_by_session)
    result = await metric.compute(session_entities.pop())

    assert result.success is True
    assert isinstance(result.value, float)
    assert 0.0 <= result.value <= 1.0
    assert result.span_id == ["workflow_1"]
    assert result.session_id == ["session1"]
    assert result.metric_name == "GoalSuccessRate"
    assert result.aggregation_level == "session"
    assert isinstance(result.reasoning, str)
    assert len(result.reasoning) > 0


@pytest.mark.asyncio
async def test_goal_success_rate_end_to_end():
    """Test GoalSuccessRate metric end-to-end using the processor (requires LLM config)."""

    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not set; skipping end-to-end test")

    # Create test spans with workflow data
    spans = [
        make_workflow_span(
            "workflow_1",
            input_data={
                "inputs": {
                    "chat_history": [
                        {
                            "message": "Can you help me write a Python function to calculate the area of a circle?"
                        }
                    ]
                }
            },
            output_data={
                "outputs": {
                    "messages": [
                        {
                            "message": "Can you help me write a Python function to calculate the area of a circle?"
                        },
                        {
                            "kwargs": {
                                "content": "Here's a Python function to calculate the area of a circle:\n\nimport math\n\ndef circle_area(radius):\n    return math.pi * radius ** 2\n\nThis function takes the radius as input and returns the area using the formula π × r²."
                            }
                        },
                    ]
                }
            },
        ),
        make_non_workflow_span("agent", "agent_1"),
    ]

    # Set up registry and processor
    registry = MetricRegistry()
    registry.register_metric(GoalSuccessRate, "GoalSuccessRate")

    llm_config = LLMJudgeConfig(
        LLM_API_KEY=os.getenv("LLM_API_KEY", ""),
        LLM_BASE_MODEL_URL=os.getenv("LLM_BASE_MODEL_URL", ""),
        LLM_MODEL_NAME=os.getenv("LLM_MODEL_NAME", ""),
    )

    model_handler = ModelHandler()
    processor = MetricsProcessor(
        registry=registry,
        model_handler=model_handler,
        llm_config=llm_config,
    )

    traces_by_session = {spans[0].session_id: spans}
    session_entities = build_session_entities_from_dict(traces_by_session)
    sessions_data = {entity.session_id: entity for entity in session_entities}

    results = await processor.compute_metrics(sessions_data)

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
