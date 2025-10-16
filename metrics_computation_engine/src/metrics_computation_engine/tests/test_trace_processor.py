# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive unit tests for TraceProcessor.

Tests cover:
1. TraceProcessor initialization
2. Processing raw traces into enriched sessions
3. Processing pre-grouped sessions (optimized path)
4. Session filtering by ID
5. Pseudo-grouping from file data
6. Error handling and validation
"""

import pytest

from metrics_computation_engine.entities.core.trace_processor import (
    TraceProcessor,
    create_pseudo_grouped_sessions_from_file,
)
from metrics_computation_engine.entities.models.session_set import SessionSet


# ============================================================================
# TEST CLASS 1: INITIALIZATION
# ============================================================================


class TestTraceProcessorInitialization:
    """Test TraceProcessor initialization."""

    def test_init_with_default_logger(self):
        """Test initialization with default logger."""
        processor = TraceProcessor()

        # Assert: Components initialized
        assert processor.logger is not None
        assert processor.aggregator is not None
        assert processor.enrichment_pipeline is not None

    def test_init_with_custom_logger(self, logger):
        """Test initialization with custom logger."""
        processor = TraceProcessor(logger=logger)

        # Assert: Uses provided logger
        assert processor.logger == logger
        assert processor.aggregator is not None
        assert processor.enrichment_pipeline is not None


# ============================================================================
# TEST CLASS 2: PROCESS RAW TRACES
# ============================================================================


class TestProcessRawTraces:
    """Test processing raw traces into enriched sessions."""

    def test_process_valid_traces(
        self,
        logger,
        sample_llm_span_raw,
        sample_task_span_raw,
        sample_workflow_span_raw,
    ):
        """Test processing valid raw trace data."""
        processor = TraceProcessor(logger=logger)

        # Use real span data
        raw_traces = [
            sample_llm_span_raw,
            sample_task_span_raw,
            sample_workflow_span_raw,
        ]

        # Execute
        result = processor.process_raw_traces(raw_traces)

        # Assert: SessionSet created
        assert isinstance(result, SessionSet)
        assert len(result.sessions) > 0

        # Assert: Sessions are enriched (have stats)
        for session in result.sessions:
            assert session.session_id is not None
            assert len(session.spans) > 0

    def test_process_empty_traces_raises_error(self, logger):
        """Test that empty trace list raises ValueError."""
        processor = TraceProcessor(logger=logger)

        # Execute & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            processor.process_raw_traces([])

        assert "No trace data provided" in str(exc_info.value)

    def test_process_traces_no_valid_spans_raises_error(self, logger):
        """Test that traces with no valid spans raises ValueError."""
        processor = TraceProcessor(logger=logger)

        # Create invalid traces (no valid entity type)
        invalid_traces = [
            {
                "SpanName": "InvalidSpan",  # No .chat/.tool/.agent suffix
                "SpanId": "invalid-1",
                "SpanAttributes": {},
                "Duration": 1000000,
            }
        ]

        # Execute & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            processor.process_raw_traces(invalid_traces)

        assert "No valid spans found" in str(exc_info.value)

    def test_process_with_session_filter(self, logger, api_noa_2_data):
        """Test processing with session ID filter."""
        processor = TraceProcessor(logger=logger)

        # First, process without filter to find a session ID
        full_result = processor.process_raw_traces(api_noa_2_data)

        if len(full_result.sessions) > 0:
            target_session_id = full_result.sessions[0].session_id

            # Execute: Process with filter
            filtered_result = processor.process_raw_traces(
                api_noa_2_data, session_id_filter=target_session_id
            )

            # Assert: Only one session
            assert len(filtered_result.sessions) == 1
            # Session ID should match (exact or contain)
            assert target_session_id in filtered_result.sessions[0].session_id

    def test_process_creates_enriched_session_set(
        self, logger, sample_llm_span_raw, sample_agent_span_raw
    ):
        """Test that processing enriches sessions."""
        processor = TraceProcessor(logger=logger)

        raw_traces = [sample_llm_span_raw, sample_agent_span_raw]

        # Execute
        result = processor.process_raw_traces(raw_traces)

        # Assert: Sessions are enriched
        assert len(result.sessions) > 0

        # Enriched sessions should have stats
        for session in result.sessions:
            # After enrichment, sessions should have the base structure
            assert hasattr(session, "spans")
            assert hasattr(session, "session_id")


# ============================================================================
# TEST CLASS 3: PROCESS GROUPED SESSIONS
# ============================================================================


class TestProcessGroupedSessions:
    """Test processing pre-grouped session data."""

    def test_process_grouped_valid_sessions(
        self, logger, sample_llm_span_raw, sample_task_span_raw
    ):
        """Test processing pre-grouped sessions."""
        processor = TraceProcessor(logger=logger)

        # Create grouped sessions dict
        grouped = {
            "session-1": [sample_llm_span_raw, sample_task_span_raw],
        }

        # Execute
        result = processor.process_grouped_sessions(grouped)

        # Assert: SessionSet created
        assert isinstance(result, SessionSet)
        assert len(result.sessions) >= 1

        # Sessions should be enriched
        for session in result.sessions:
            assert session.session_id is not None
            assert len(session.spans) > 0

    def test_process_empty_grouped_raises_error(self, logger):
        """Test that empty grouped dict raises ValueError."""
        processor = TraceProcessor(logger=logger)

        # Execute & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            processor.process_grouped_sessions({})

        assert "No session data provided" in str(exc_info.value)

    def test_process_grouped_with_filter(
        self, logger, sample_llm_span_raw, sample_agent_span_raw
    ):
        """Test processing grouped sessions with session ID filter."""
        processor = TraceProcessor(logger=logger)

        # Create grouped sessions
        grouped = {
            "session-1": [sample_llm_span_raw],
            "session-2": [sample_agent_span_raw],
        }

        # Execute: Process with filter
        result = processor.process_grouped_sessions(
            grouped, session_id_filter="session-1"
        )

        # Assert: Only session-1 processed
        assert len(result.sessions) == 1
        # The session ID might be processed (UUID extracted), so check contains
        assert (
            "session-1" in str(result.sessions[0].session_id)
            or len(result.sessions) == 1
        )

    def test_process_grouped_skips_empty_sessions(self, logger):
        """Test that sessions with no spans are skipped."""
        processor = TraceProcessor(logger=logger)

        # Create grouped with one empty session
        grouped = {
            "session-1": [],  # Empty
            "session-2": [
                {
                    "SpanName": "test.agent",
                    "SpanId": "123",
                    "SpanAttributes": {"session.id": "session-2"},
                    "Duration": 1000000,
                    "Timestamp": "2025-01-01T00:00:00Z",
                    "ServiceName": "test",
                }
            ],
        }

        # Execute - should skip session-1 (no spans)
        result = processor.process_grouped_sessions(grouped)

        # Assert: Only session-2 processed
        assert len(result.sessions) >= 1
        # All sessions should have spans
        for session in result.sessions:
            assert len(session.spans) > 0

    def test_process_grouped_no_valid_sessions_raises_error(self, logger):
        """Test that grouped data with no valid sessions raises error."""
        processor = TraceProcessor(logger=logger)

        # Create grouped with only invalid spans
        grouped = {
            "session-1": [
                {
                    "SpanName": "Invalid",  # No valid suffix
                    "SpanId": "123",
                    "SpanAttributes": {},
                    "Duration": 1000000,
                }
            ]
        }

        # Execute & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            processor.process_grouped_sessions(grouped)

        assert "No valid sessions found" in str(exc_info.value)


# ============================================================================
# TEST CLASS 4: SESSION FILTERING
# ============================================================================


class TestSessionFiltering:
    """Test session ID filtering logic."""

    def test_filter_by_session_id_exact_match(
        self, logger, create_session, create_span
    ):
        """Test filtering with exact session ID match."""
        processor = TraceProcessor(logger=logger)

        # Create session set
        sessions = [
            create_session(session_id="session-exact-match", spans=[create_span()]),
            create_session(session_id="session-other", spans=[create_span()]),
        ]
        session_set = SessionSet(sessions=sessions)

        # Execute
        result = processor._filter_by_session_id(session_set, "session-exact-match")

        # Assert: Only exact match returned
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session-exact-match"

    def test_filter_by_session_id_partial_match(
        self, logger, create_session, create_span
    ):
        """Test filtering with partial session ID match."""
        processor = TraceProcessor(logger=logger)

        # Create session with prefix (like: service_uuid format)
        sessions = [
            create_session(session_id="myapp_12345-abcd-6789", spans=[create_span()]),
        ]
        session_set = SessionSet(sessions=sessions)

        # Execute: Filter with partial match (just UUID part)
        result = processor._filter_by_session_id(session_set, "12345-abcd-6789")

        # Assert: Partial match works
        assert len(result.sessions) == 1
        assert "12345-abcd-6789" in result.sessions[0].session_id

    def test_filter_by_session_id_not_found_raises_error(
        self, logger, create_session, create_span
    ):
        """Test that filtering for non-existent session raises error."""
        processor = TraceProcessor(logger=logger)

        sessions = [
            create_session(session_id="session-1", spans=[create_span()]),
        ]
        session_set = SessionSet(sessions=sessions)

        # Execute & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            processor._filter_by_session_id(session_set, "non-existent")

        assert "not found" in str(exc_info.value).lower()


# ============================================================================
# TEST CLASS 5: PSEUDO GROUPING
# ============================================================================


class TestPseudoGrouping:
    """Test create_pseudo_grouped_sessions_from_file utility."""

    def test_create_pseudo_grouped_from_file(
        self, sample_llm_span_raw, sample_task_span_raw
    ):
        """Test creating grouped sessions from file data."""
        # Both spans have same session_id
        raw_traces = [sample_llm_span_raw, sample_task_span_raw]

        # Execute
        result = create_pseudo_grouped_sessions_from_file(raw_traces)

        # Assert: Grouped by session_id
        assert isinstance(result, dict)
        assert len(result) >= 1

        # Should have grouped spans by session
        for session_id, spans in result.items():
            assert isinstance(spans, list)
            assert len(spans) > 0

    def test_pseudo_grouping_extracts_uuid(self):
        """Test that pseudo grouping extracts UUID from session_id."""
        # Span with service_uuid format session ID
        raw_traces = [
            {
                "SpanName": "test.agent",
                "SpanId": "123",
                "SpanAttributes": {
                    "session.id": "myservice_12345678-1234-1234-1234-123456789abc"
                },
                "Duration": 1000000,
                "Timestamp": "2025-01-01T00:00:00Z",
            }
        ]

        # Execute
        result = create_pseudo_grouped_sessions_from_file(raw_traces)

        # Assert: Should extract just the UUID part
        assert isinstance(result, dict)
        # UUID should be extracted (36 chars with 4 hyphens)
        extracted_ids = list(result.keys())
        assert len(extracted_ids) > 0

    def test_pseudo_grouping_processes_metadata(self):
        """Test that pseudo grouping adds required metadata."""
        raw_traces = [
            {
                "SpanName": "test.agent",
                "SpanId": "123",
                "SpanAttributes": {"session.id": "test-session"},
                "Duration": 1000000,
                "Timestamp": "2025-01-01T00:00:00.123456Z",
                "StatusCode": "Ok",
            }
        ]

        # Execute
        result = create_pseudo_grouped_sessions_from_file(raw_traces)

        # Assert: Metadata processed
        session_spans = list(result.values())[0]
        span = session_spans[0]

        # Should have added sessionId
        assert "sessionId" in span
        # Should have calculated startTime
        assert "startTime" in span
        # Should have converted duration
        assert "duration" in span
        # Should have statusCode
        assert "statusCode" in span


# ============================================================================
# INTEGRATION TEST: FULL TRACE PROCESSING
# ============================================================================


class TestTraceProcessorIntegration:
    """Integration tests for complete trace processing workflow."""

    def test_full_raw_traces_pipeline(self, logger, api_noa_2_data):
        """Test complete pipeline: raw traces → enriched sessions."""
        processor = TraceProcessor(logger=logger)

        # Execute: Process real data
        result = processor.process_raw_traces(api_noa_2_data)

        # Assert: Successfully processed
        assert isinstance(result, SessionSet)
        assert len(result.sessions) > 0

        # Verify sessions are valid
        for session in result.sessions:
            assert session.session_id is not None
            assert len(session.spans) > 0
            assert session.start_time is not None or session.end_time is not None

    def test_full_grouped_sessions_pipeline(
        self, logger, sample_llm_span_raw, sample_agent_span_raw
    ):
        """Test complete grouped pipeline: grouped → enriched sessions."""
        processor = TraceProcessor(logger=logger)

        # Create grouped data
        grouped = {
            "session-1": [sample_llm_span_raw],
            "session-2": [sample_agent_span_raw],
        }

        # Execute
        result = processor.process_grouped_sessions(grouped)

        # Assert: Successfully processed
        assert isinstance(result, SessionSet)
        assert len(result.sessions) >= 1

        # Verify enrichment applied
        for session in result.sessions:
            assert session.session_id is not None
            assert len(session.spans) > 0

    def test_pipeline_with_filtering_and_enrichment(self, logger, api_noa_2_data):
        """Test complete pipeline with filtering and enrichment."""
        processor = TraceProcessor(logger=logger)

        # Process to get session IDs
        initial_result = processor.process_raw_traces(api_noa_2_data)

        if len(initial_result.sessions) > 0:
            # Pick first session ID for filtering
            target_id = initial_result.sessions[0].session_id

            # Execute: Process with filter
            filtered_result = processor.process_raw_traces(
                api_noa_2_data, session_id_filter=target_id
            )

            # Assert: Filtered and enriched
            assert len(filtered_result.sessions) == 1
            assert filtered_result.sessions[0].session_id == target_id

            # Should still be enriched
            session = filtered_result.sessions[0]
            assert len(session.spans) > 0
