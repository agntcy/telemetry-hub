import pytest
from metrics_computation_engine.metrics.span.task_delegation_accuracy import (
    TaskDelegationAccuracy,
)
from metrics_computation_engine.dal.api_client import traces_processor


# Mock jury class to simulate LLM evaluation
class MockJury:
    def judge(self, prompt, grading_cls):
        assert "Hello" not in prompt
        return 1, "Task delegation was accurate."


def make_agent_span_dict(
    agent_name,
    span_id,
    session_id="session123",
    input_text="Input to the agent",
    output_text="Agent output",
):
    """Create a raw agent span dictionary that can be processed by traces_processor."""
    return {
        "SpanId": span_id,
        "SpanName": f"{agent_name}.agent",
        "SpanAttributes": {
            "ioa_observe.entity.name": agent_name,
            "traceloop.span.kind": "agent",
            "session.id": session_id,
            # These are the keys that data_parser looks for agent input/output:
            "ioa_observe.entity.input": input_text,
            "ioa_observe.entity.output": output_text,
        },
        "TraceId": "trace123",
        "ParentSpanId": "parent",
        "Timestamp": "2024-01-01T00:00:00Z",
        "Duration": 1000000000,  # 1 second in nanoseconds
        "StatusCode": "Ok",
        "sessionId": session_id,
        "startTime": 1234567890.0,
        "duration": 1000.0,
        "statusCode": 0,
        "FrameworkSpanKind": "AGENT",
    }


@pytest.mark.asyncio
async def test_task_delegation_accuracy_invalid_span():
    """Case 1: Span is not an agent, should fail with value -1."""
    metric = TaskDelegationAccuracy()

    # Create session data with a tool span (not an agent)
    session_data = {
        "session123": [
            {
                "SpanId": "1",
                "SpanName": "SomeTool.tool",
                "SpanAttributes": {
                    "traceloop.entity.name": "SomeTool",
                    "traceloop.span.kind": "tool",  # invalid entity_type for this metric
                    "session.id": "session123",
                },
                "TraceId": "trace123",
                "ParentSpanId": "parent",
                "Timestamp": "2024-01-01T00:00:00Z",
                "Duration": 1000000000,
                "StatusCode": "Ok",
                "sessionId": "session123",
                "startTime": 1234567890.0,
                "duration": 1000.0,
                "statusCode": 0,
                "FrameworkSpanKind": "TOOL",
            }
        ]
    }

    session_set = traces_processor(session_data)
    session = session_set.sessions[0]
    tool_span = session.tool_spans[0]  # Get the tool span

    result = await metric.compute(tool_span)
    assert result.success is False
    assert result.value == -1


@pytest.mark.asyncio
async def test_task_delegation_accuracy_no_jury():
    """Case 2: Valid agent span, but no jury configured, should return error with value -1."""
    metric = TaskDelegationAccuracy()

    # Create session data with a valid agent span
    session_data = {"session123": [make_agent_span_dict("AgentX", "2", "session123")]}

    session_set = traces_processor(session_data)
    session = session_set.sessions[0]
    agent_span = session.agent_spans[0]  # Get the agent span

    result = await metric.compute(agent_span)
    assert result.success is False
    assert result.value == -1
    assert "credentials" in result.error_message.lower()


@pytest.mark.asyncio
async def test_task_delegation_accuracy_with_jury():
    """Case 3: Valid agent span and jury configured, should return success with graded value."""
    jury = MockJury()
    metric = TaskDelegationAccuracy()
    metric.init_with_model(jury)

    # Create session data with a valid agent span
    session_data = {"session123": [make_agent_span_dict("AgentY", "3", "session123")]}

    session_set = traces_processor(session_data)
    session = session_set.sessions[0]
    agent_span = session.agent_spans[0]  # Get the agent span

    result = await metric.compute(agent_span)
    assert result.success is True
    assert result.value == 1
    assert result.reasoning == "Task delegation was accurate."


@pytest.mark.asyncio
async def test_task_delegation_accuracy_missing_data():
    """Case 4: Agent span missing required fields (input/output), should fail."""
    metric = TaskDelegationAccuracy()
    metric.init_with_model(MockJury())

    # Create session data with an agent span missing input/output
    session_data = {
        "session123": [
            {
                "SpanId": "4",
                "SpanName": "AgentZ.agent",
                "SpanAttributes": {
                    "ioa_observe.entity.name": "AgentZ",
                    "traceloop.span.kind": "agent",
                    "session.id": "session123",
                    # Missing ioa_observe.entity.input and ioa_observe.entity.output
                },
                "TraceId": "trace123",
                "ParentSpanId": "parent",
                "Timestamp": "2024-01-01T00:00:00Z",
                "Duration": 1000000000,
                "StatusCode": "Ok",
                "sessionId": "session123",
                "startTime": 1234567890.0,
                "duration": 1000.0,
                "statusCode": 0,
                "FrameworkSpanKind": "AGENT",
            }
        ]
    }

    session_set = traces_processor(session_data)
    session = session_set.sessions[0]
    agent_span = session.agent_spans[0]  # Get the agent span

    result = await metric.compute(agent_span)
    assert result.success is False
    assert result.value == -1
    assert "missing required data" in result.error_message.lower()
