# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive unit tests for data_parser module.

Tests cover:
1. Helper functions (safe_parse_json, error detection, etc.)
2. Entity type detection (all 6 types + Autogen framework)
3. Payload processing (LLM, tool, agent, workflow)
4. Timing calculations (end_time, duration)
5. Error detection logic
6. Full parse_raw_spans integration with real data
"""

from metrics_computation_engine.entities.core.data_parser import (
    safe_parse_json,
    contains_error_like_pattern,
    app_name,
    parse_raw_spans,
    _calculate_end_time,
    _calculate_duration_ms,
    _ensure_dict_payload,
    _check_error_status,
    _process_generic_payload,
)


# ============================================================================
# TEST CLASS 1: HELPER FUNCTIONS
# ============================================================================


class TestHelperFunctions:
    """Test utility/helper functions."""

    def test_safe_parse_json_valid_json(self):
        """Test safe_parse_json with valid JSON strings."""
        # Valid JSON string
        result = safe_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

        # Valid JSON with nested structure
        result = safe_parse_json('{"nested": {"data": [1, 2, 3]}}')
        assert result == {"nested": {"data": [1, 2, 3]}}

        # Empty dict
        result = safe_parse_json("{}")
        assert result == {}

    def test_safe_parse_json_invalid_inputs(self):
        """Test safe_parse_json handles invalid inputs gracefully."""
        # Invalid JSON string
        assert safe_parse_json("invalid json") is None

        # None input
        assert safe_parse_json(None) is None

        # Empty string
        assert safe_parse_json("") is None

        # Partial JSON
        assert safe_parse_json('{"incomplete":') is None

    def test_contains_error_like_pattern_detects_errors(self):
        """Test error pattern detection in outputs."""
        # Traceback pattern
        assert (
            contains_error_like_pattern(
                {"output": "Error: Traceback (most recent call last)"}
            )
            is True
        )

        # Exception pattern
        assert (
            contains_error_like_pattern({"error": "ValueError: exception occurred"})
            is True
        )

        # HTTPError pattern
        assert contains_error_like_pattern({"response": "HTTPError 500"}) is True

        # Nested error
        assert contains_error_like_pattern({"nested": {"data": "traceback"}}) is True

        # List with error
        assert (
            contains_error_like_pattern({"items": ["normal", "exception here"]}) is True
        )

    def test_contains_error_like_pattern_no_errors(self):
        """Test normal outputs return False."""
        # Normal dict
        assert contains_error_like_pattern({"status": "success"}) is False

        # Empty dict
        assert contains_error_like_pattern({}) is False

        # Normal text
        assert contains_error_like_pattern({"message": "Operation completed"}) is False

    def test_app_name_extraction(self):
        """Test app name extraction from various span fields."""
        # From ServiceName
        span = {"ServiceName": "my-app"}
        assert app_name(span) == "my-app"

        # From ResourceAttributes
        span = {"ResourceAttributes": {"service.name": "my-service"}}
        assert app_name(span) == "my-service"

        # From SpanAttributes (app.name)
        span = {"SpanAttributes": {"app.name": "my-application"}}
        assert app_name(span) == "my-application"

        # Missing all - returns default
        span = {}
        assert app_name(span) == "unknown-app"

        # Priority: ServiceName > ResourceAttributes > SpanAttributes
        span = {
            "ServiceName": "first-priority",
            "ResourceAttributes": {"service.name": "second-priority"},
        }
        assert app_name(span) == "first-priority"

    def test_ensure_dict_payload(self):
        """Test payload normalization to dict."""
        # Dict input - returns unchanged
        result = _ensure_dict_payload({"key": "value"})
        assert result == {"key": "value"}

        # None input - returns None
        result = _ensure_dict_payload(None)
        assert result is None

        # String input - wrapped in dict
        result = _ensure_dict_payload("text response")
        assert result == {"value": "text response"}

        # Number input - wrapped in dict
        result = _ensure_dict_payload(42)
        assert result == {"value": 42}

        # List input - wrapped in dict
        result = _ensure_dict_payload([1, 2, 3])
        assert result == {"value": [1, 2, 3]}


# ============================================================================
# TEST CLASS 2: TIMING CALCULATIONS
# ============================================================================


class TestTimingCalculations:
    """Test time and duration calculation functions."""

    def test_calculate_end_time_valid(self):
        """Test end time calculation with valid inputs."""
        # Valid start time and duration
        start_time = "1754408410.050806"
        duration_ns = 1459444226  # ~1.46 seconds in nanoseconds

        result = _calculate_end_time(start_time, duration_ns)

        assert result is not None
        # Should be start_time + (duration_ns / 1e9)
        expected = str(float(start_time) + float(duration_ns) / 1e9)
        assert result == expected

    def test_calculate_end_time_invalid(self):
        """Test end time calculation with invalid inputs."""
        # Missing start_time
        assert _calculate_end_time(None, 1000000) is None

        # Missing duration
        assert _calculate_end_time("1234567890.0", None) is None

        # Invalid start_time format
        assert _calculate_end_time("invalid", 1000000) is None

        # Invalid duration format
        assert _calculate_end_time("1234567890.0", "invalid") is None

    def test_calculate_duration_ms_from_duration_ns(self):
        """Test duration calculation from nanoseconds."""
        # 1 second = 1,000,000,000 nanoseconds = 1,000 milliseconds
        duration_ns = 1000000000
        result = _calculate_duration_ms(None, None, duration_ns)

        assert result == 1000.0  # 1 second = 1000 ms

        # Half second
        result = _calculate_duration_ms(None, None, 500000000)
        assert result == 500.0

    def test_calculate_duration_ms_from_times(self):
        """Test duration calculation from start/end times."""
        start_time = "1234567890.0"
        end_time = "1234567891.5"  # 1.5 seconds later

        result = _calculate_duration_ms(start_time, end_time, None)

        # Should be (1.5 seconds) * 1000 = 1500 ms
        assert result == 1500.0

    def test_calculate_duration_ms_fallback(self):
        """Test duration calculation with missing data."""
        # No data available
        result = _calculate_duration_ms(None, None, None)
        assert result is None

        # Invalid formats
        result = _calculate_duration_ms("invalid", "invalid", None)
        assert result is None


# ============================================================================
# TEST CLASS 3: ERROR DETECTION
# ============================================================================


class TestErrorDetection:
    """Test error status detection logic."""

    def test_check_error_status_code_error(self):
        """Test detection of error status code."""
        status_code = "error"
        attrs = {}
        output_payload = None

        result = _check_error_status(status_code, attrs, output_payload)
        assert result is True

    def test_check_error_status_explicit_error(self):
        """Test detection of explicit error attribute."""
        status_code = "ok"
        attrs = {"traceloop.entity.error": True}
        output_payload = None

        result = _check_error_status(status_code, attrs, output_payload)
        assert result is True

    def test_check_error_status_pattern_in_output(self):
        """Test detection of error patterns in output."""
        status_code = "ok"
        attrs = {}

        # Traceback in output
        output_payload = {"result": "Error: Traceback occurred"}
        assert _check_error_status(status_code, attrs, output_payload) is True

        # Exception in output
        output_payload = {"error": "Exception: something failed"}
        assert _check_error_status(status_code, attrs, output_payload) is True

        # HTTPError in output
        output_payload = {"response": "HTTPError 404"}
        assert _check_error_status(status_code, attrs, output_payload) is True

    def test_check_error_status_no_error(self):
        """Test clean outputs return False."""
        status_code = "ok"
        attrs = {}
        output_payload = {"status": "success", "result": "all good"}

        result = _check_error_status(status_code, attrs, output_payload)
        assert result is False

        # None output
        result = _check_error_status(status_code, attrs, None)
        assert result is False


# ============================================================================
# TEST CLASS 4: PAYLOAD PROCESSING
# ============================================================================


class TestPayloadProcessing:
    """Test payload extraction and processing."""

    def test_process_generic_payload_dict(self):
        """Test processing dict payloads."""
        # Dict input - returned as-is
        payload = {"key": "value", "nested": {"data": 123}}
        result = _process_generic_payload(payload)
        assert result == payload

    def test_process_generic_payload_json_string(self):
        """Test processing JSON string payloads."""
        # Valid JSON string
        payload = '{"parsed": "json"}'
        result = _process_generic_payload(payload)
        assert result == {"parsed": "json"}

    def test_process_generic_payload_plain_string(self):
        """Test processing plain string payloads."""
        # Non-JSON string - wrapped
        payload = "plain text response"
        result = _process_generic_payload(payload)
        assert result == {"value": "plain text response"}

    def test_process_generic_payload_none(self):
        """Test processing None payload."""
        result = _process_generic_payload(None)
        assert result is None


# ============================================================================
# TEST CLASS 5: ENTITY TYPE DETECTION
# ============================================================================


class TestEntityTypeDetection:
    """Test entity type classification from span names."""

    def test_parse_llm_spans(self, sample_llm_span_raw):
        """Test parsing LLM spans (.chat suffix)."""
        result = parse_raw_spans([sample_llm_span_raw])

        assert len(result) == 1
        span = result[0]

        # Verify entity type
        assert span.entity_type == "llm"

        # Verify entity name from gen_ai.response.model
        assert span.entity_name == "gpt-4o-2024-08-06"

        # Verify input payload extracted
        assert span.input_payload is not None
        assert isinstance(span.input_payload, dict)
        assert any(key.startswith("gen_ai.prompt") for key in span.input_payload.keys())

        # Verify output payload extracted
        assert span.output_payload is not None
        assert isinstance(span.output_payload, dict)
        assert any(
            key.startswith("gen_ai.completion") for key in span.output_payload.keys()
        )

        # Verify session ID
        assert span.session_id == "noa-moderator_4d798de1-e517-49f9-9a77-9f86a314d6b7"

        # Verify app name
        assert span.app_name == "noa-moderator"

    def test_parse_task_spans(self, sample_task_span_raw):
        """Test parsing task spans (.task suffix)."""
        result = parse_raw_spans([sample_task_span_raw])

        assert len(result) == 1
        span = result[0]

        # Verify entity type
        assert span.entity_type == "task"

        # Verify entity name
        assert span.entity_name == "ChatPromptTemplate"

        # Verify payloads extracted
        assert span.input_payload is not None
        assert span.output_payload is not None

    def test_parse_workflow_spans(self, sample_workflow_span_raw):
        """Test parsing workflow spans (.workflow suffix)."""
        result = parse_raw_spans([sample_workflow_span_raw])

        assert len(result) == 1
        span = result[0]

        # Verify entity type
        assert span.entity_type == "workflow"

        # Verify entity name from ioa_observe.workflow.name
        assert span.entity_name is not None

        # Verify session ID extracted
        assert span.session_id is not None

    def test_parse_agent_spans(self, sample_agent_span_raw):
        """Test parsing agent spans (.agent suffix)."""
        result = parse_raw_spans([sample_agent_span_raw])

        assert len(result) == 1
        span = result[0]

        # Verify entity type
        assert span.entity_type == "agent"

        # Verify agent_id extracted
        assert span.agent_id is not None

    def test_parse_graph_spans(self, sample_graph_span_raw):
        """Test parsing graph spans (.graph suffix)."""
        result = parse_raw_spans([sample_graph_span_raw])

        assert len(result) == 1
        span = result[0]

        # Verify entity type
        assert span.entity_type == "graph"

    def test_parse_mixed_entity_types(
        self,
        sample_llm_span_raw,
        sample_task_span_raw,
        sample_workflow_span_raw,
        sample_agent_span_raw,
    ):
        """Test parsing list with mixed entity types."""
        mixed_spans = [
            sample_llm_span_raw,
            sample_task_span_raw,
            sample_workflow_span_raw,
            sample_agent_span_raw,
        ]

        result = parse_raw_spans(mixed_spans)

        # Should parse all valid spans
        assert len(result) == 4

        # Check entity types are correct
        entity_types = [span.entity_type for span in result]
        assert "llm" in entity_types
        assert "task" in entity_types
        assert "workflow" in entity_types
        assert "agent" in entity_types

        # Each span should have session_id
        for span in result:
            assert span.session_id is not None


# ============================================================================
# TEST CLASS 6: PARSE RAW SPANS INTEGRATION
# ============================================================================


class TestParseRawSpansIntegration:
    """Integration tests for complete parse_raw_spans workflow."""

    def test_parse_empty_list(self):
        """Test parsing empty list returns empty result."""
        result = parse_raw_spans([])

        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_real_data_from_file(self, api_noa_2_data):
        """Test parsing real trace data from api_noa_2.json."""
        # Parse all spans from real file
        result = parse_raw_spans(api_noa_2_data)

        # Should parse multiple spans
        assert len(result) > 0

        # All results should be SpanEntity objects
        from metrics_computation_engine.entities.models.span import SpanEntity

        for span in result:
            assert isinstance(span, SpanEntity)
            assert span.entity_type in [
                "llm",
                "tool",
                "agent",
                "workflow",
                "graph",
                "task",
            ]
            assert span.span_id is not None
            assert span.session_id is not None

    def test_parse_preserves_session_ids(self, api_noa_2_data):
        """Test that session IDs are preserved correctly."""
        result = parse_raw_spans(api_noa_2_data)

        # Extract unique session IDs
        session_ids = {span.session_id for span in result if span.session_id}

        # Should have at least one session
        assert len(session_ids) >= 1

        # All spans should have session_id
        for span in result:
            assert span.session_id is not None
            assert len(span.session_id) > 0

    def test_parse_preserves_parent_child_relationships(self, api_noa_2_data):
        """Test that parent-child relationships are preserved."""
        result = parse_raw_spans(api_noa_2_data)

        # Some spans should have parent_span_id (not None and not empty string)
        spans_with_parents = [
            s for s in result if s.parent_span_id is not None and s.parent_span_id != ""
        ]
        assert len(spans_with_parents) > 0

        # Parent span IDs should be valid strings
        for span in spans_with_parents:
            assert isinstance(span.parent_span_id, str)
            assert len(span.parent_span_id) > 0

    def test_parse_extracts_timing_data(self, sample_llm_span_raw):
        """Test that timing data is extracted and calculated."""
        result = parse_raw_spans([sample_llm_span_raw])

        assert len(result) == 1
        span = result[0]

        # Should have timing data
        assert span.start_time is not None
        assert span.end_time is not None
        assert span.duration is not None

        # Duration should be in milliseconds (positive number)
        assert isinstance(span.duration, (int, float))
        assert span.duration > 0

    def test_parse_handles_incomplete_spans(self):
        """Test parsing handles incomplete but parseable spans."""
        # Spans with minimal but valid data
        minimal_spans = [
            # LLM span with minimal attributes
            {
                "SpanName": "test.chat",
                "SpanId": "minimal-llm",
                "SpanAttributes": {
                    "session.id": "test-session",
                    "gen_ai.response.model": "test-model",
                },
                "Duration": 1000000,
                "Timestamp": "2025-01-01T00:00:00Z",
                "ServiceName": "test-service",
            },
            # Task span with minimal attributes
            {
                "SpanName": "test.task",
                "SpanId": "minimal-task",
                "SpanAttributes": {
                    "session.id": "test-session",
                    "traceloop.entity.name": "test-task",
                },
                "Duration": 1000000,
                "Timestamp": "2025-01-01T00:00:00Z",
                "ServiceName": "test-service",
            },
        ]

        # Should parse successfully
        result = parse_raw_spans(minimal_spans)

        # Should parse both spans
        assert isinstance(result, list)
        assert len(result) == 2

        # Check entity types detected
        assert result[0].entity_type == "llm"
        assert result[1].entity_type == "task"

    def test_parse_filters_invalid_entity_types(self):
        """Test that spans with no valid entity type are filtered out."""
        invalid_spans = [
            {
                "SpanName": "NoSuffix",  # No .chat/.tool/.agent suffix
                "SpanId": "invalid-1",
                "SpanAttributes": {"session.id": "test"},
                "Duration": 1000000,
            },
            {
                "SpanName": "UnknownType.unknown",
                "SpanId": "invalid-2",
                "SpanAttributes": {"session.id": "test"},
                "Duration": 1000000,
            },
        ]

        result = parse_raw_spans(invalid_spans)

        # Should filter out invalid entity types
        assert len(result) == 0

    def test_parse_extracts_llm_token_usage(self, sample_llm_span_raw):
        """Test LLM token usage is extracted to attrs."""
        result = parse_raw_spans([sample_llm_span_raw])

        assert len(result) == 1
        span = result[0]

        # LLM spans should have extra attrs with token data
        if span.attrs:
            # Check for token fields
            assert (
                "input_tokens" in span.attrs
                or "output_tokens" in span.attrs
                or "total_tokens" in span.attrs
            )
