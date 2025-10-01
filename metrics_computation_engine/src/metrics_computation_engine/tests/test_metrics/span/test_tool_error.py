import pytest
from metrics_computation_engine.metrics.span.tool_error import ToolError
from metrics_computation_engine.dal.api_client import traces_processor


def make_tool_span_dict(
    tool_name,
    span_id,
    session_id="session123",
    status_code="Ok",
    has_error_status=False,
):
    """Create a raw tool span dictionary that can be processed by traces_processor."""
    span_data = {
        "SpanId": span_id,
        "SpanName": f"{tool_name}.tool",
        "SpanAttributes": {
            "traceloop.entity.name": tool_name,
            "traceloop.span.kind": "tool",
            "session.id": session_id,
            "traceloop.entity.input": "Input to the tool",
            "traceloop.entity.output": "Tool output",
        },
        "TraceId": "trace123",
        "ParentSpanId": "parent",
        "Timestamp": "2024-01-01T00:00:00Z",
        "Duration": 1000000000,  # 1 second in nanoseconds
        "StatusCode": status_code,
        "sessionId": session_id,
        "startTime": 1234567890.0,
        "duration": 1000.0,
        "statusCode": 0 if status_code == "Ok" else 1,
        "FrameworkSpanKind": "TOOL",
    }

    # Add nested status field if requested (what the metric looks for)
    if has_error_status:
        span_data["Events.Attributes"] = [{"status": "error"}]

    return span_data


@pytest.mark.asyncio
async def test_tool_error_invalid_span():
    """Case 1: Span is not a tool, should fail with value -1."""
    metric = ToolError()

    # Create session data with an agent span (not a tool)
    session_data = {
        "session123": [
            {
                "SpanId": "1",
                "SpanName": "SomeAgent.agent",
                "SpanAttributes": {
                    "traceloop.entity.name": "SomeAgent",
                    "traceloop.span.kind": "agent",  # invalid entity_type for this metric
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


@pytest.mark.asyncio
async def test_tool_error_no_status():
    """Case 2: Valid tool span but no status field, should fail with value -1."""
    metric = ToolError()

    # Create session data with a tool span but no status
    session_data = {
        "session123": [
            make_tool_span_dict(
                "ToolX", "2", "session123", "Ok", has_error_status=False
            )
        ]
    }

    session_set = traces_processor(session_data)
    session = session_set.sessions[0]
    tool_span = session.tool_spans[0]  # Get the tool span

    result = await metric.compute(tool_span)
    assert result.success is False
    assert result.value == -1


@pytest.mark.asyncio
async def test_tool_error_with_status():
    """Case 3: Valid tool span with status field, should return the status value."""
    metric = ToolError()

    # Create session data with a tool span that has error status
    session_data = {
        "session123": [
            make_tool_span_dict(
                "ToolY", "3", "session123", "Error", has_error_status=True
            )
        ]
    }

    session_set = traces_processor(session_data)
    session = session_set.sessions[0]
    tool_span = session.tool_spans[0]  # Get the tool span

    result = await metric.compute(tool_span)
    assert result.success is True
    assert result.value == "error"  # The status value from Events.Attributes
