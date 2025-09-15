import pytest
from metrics_computation_engine.metrics.span.tool_utilization_accuracy import (
    ToolUtilizationAccuracy,
)
from metrics_computation_engine.models.span import SpanEntity


# Mock jury class to simulate LLM evaluation
class MockJury:
    def judge(self, prompt, grading_cls):
        assert "Hello" not in prompt
        return 1, "Tool was used correctly."


@pytest.mark.asyncio
async def test_tool_utilization_accuracy_invalid_span():
    """Case 1: Span is not a tool or is missing required fields, should fail with value -1."""
    metric = ToolUtilizationAccuracy()
    span = SpanEntity(
        entity_type="agent",  # invalid entity_type
        span_id="1",
        entity_name="SomeAgent",
        app_name="example_app",
        input_payload={"text": "Input to the tool"},
        output_payload={"text": "Tool output"},
        tool_definition={"text": "Tool definition text"},
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={},
        contains_error=False,
    )
    result = await metric.compute(span)
    assert result.success is False
    assert result.value == -1


@pytest.mark.asyncio
async def test_tool_utilization_accuracy_no_jury():
    """Case 2: Valid tool span, but no jury configured, should return error with value -1."""
    metric = ToolUtilizationAccuracy()
    span = SpanEntity(
        entity_type="tool",
        span_id="2",
        entity_name="ToolX",
        app_name="example_app",
        input_payload={"text": "Input to the tool"},
        output_payload={"text": "Tool output"},
        tool_definition={"text": "Tool definition text"},
        timestamp="",
        parent_span_id=None,
        trace_id="t2",
        session_id="s2",
        start_time=None,
        end_time=None,
        raw_span_data={},
        contains_error=False,
    )
    result = await metric.compute(span)
    assert result.success is False
    assert result.value == -1
    assert "credentials" in result.error_message.lower()


@pytest.mark.asyncio
async def test_tool_utilization_accuracy_with_jury():
    """Case 3: Valid tool span and jury configured, should return success with graded value."""
    jury = MockJury()
    metric = ToolUtilizationAccuracy()
    metric.init_with_model(jury)
    span = SpanEntity(
        entity_type="tool",
        span_id="3",
        entity_name="ToolY",
        app_name="example_app",
        input_payload={"text": "Input to the tool"},
        output_payload={"text": "Tool output"},
        tool_definition={"text": "Tool definition text"},
        timestamp="",
        parent_span_id=None,
        trace_id="t3",
        session_id="s3",
        start_time=None,
        end_time=None,
        raw_span_data={},
        contains_error=False,
    )
    result = await metric.compute(span)
    assert result.success is True
    assert result.value == 1
    assert result.reasoning == "Tool was used correctly."
