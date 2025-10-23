# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive unit tests for SessionAggregator.

Tests cover:
1. Aggregating spans into sessions
2. Creating sessions from span lists
3. Duration calculation strategies
4. Session filtering by various criteria
5. Session retrieval operations
6. Time range filtering
"""

import pytest

from metrics_computation_engine.entities.core.session_aggregator import (
    SessionAggregator,
    _calculate_session_duration_from_spans,
)
from metrics_computation_engine.entities.models.session_set import SessionSet


# ============================================================================
# TEST CLASS 1: AGGREGATE SPANS TO SESSIONS
# ============================================================================


class TestAggregateSpansToSessions:
    """Test span-to-session aggregation logic."""

    def test_aggregate_single_session(self, create_span):
        """Test aggregating spans from single session."""
        aggregator = SessionAggregator()

        # Create 3 spans with same session_id
        spans = [
            create_span(span_id="s1", session_id="session-1", entity_type="agent"),
            create_span(span_id="s2", session_id="session-1", entity_type="tool"),
            create_span(span_id="s3", session_id="session-1", entity_type="llm"),
        ]

        # Execute
        result = aggregator.aggregate_spans_to_sessions(spans)

        # Assert: One session created
        assert isinstance(result, SessionSet)
        assert len(result.sessions) == 1

        session = result.sessions[0]
        assert session.session_id == "session-1"
        assert len(session.spans) == 3

        # Spans should be sorted by timestamp
        assert session.spans[0].span_id == "s1"
        assert session.spans[1].span_id == "s2"
        assert session.spans[2].span_id == "s3"

    def test_aggregate_multiple_sessions(self, create_span):
        """Test aggregating spans from multiple sessions."""
        aggregator = SessionAggregator()

        # Create spans from 3 different sessions
        spans = [
            create_span(span_id="s1", session_id="session-1", entity_type="agent"),
            create_span(span_id="s2", session_id="session-2", entity_type="tool"),
            create_span(span_id="s3", session_id="session-1", entity_type="llm"),
            create_span(span_id="s4", session_id="session-3", entity_type="workflow"),
            create_span(span_id="s5", session_id="session-2", entity_type="agent"),
        ]

        # Execute
        result = aggregator.aggregate_spans_to_sessions(spans)

        # Assert: Three sessions created
        assert len(result.sessions) == 3

        # Find each session
        session_ids = {s.session_id for s in result.sessions}
        assert session_ids == {"session-1", "session-2", "session-3"}

        # Check span counts
        session_1 = next(s for s in result.sessions if s.session_id == "session-1")
        session_2 = next(s for s in result.sessions if s.session_id == "session-2")
        session_3 = next(s for s in result.sessions if s.session_id == "session-3")

        assert len(session_1.spans) == 2  # s1, s3
        assert len(session_2.spans) == 2  # s2, s5
        assert len(session_3.spans) == 1  # s4

    def test_aggregate_empty_list(self):
        """Test aggregating empty span list."""
        aggregator = SessionAggregator()

        # Execute
        result = aggregator.aggregate_spans_to_sessions([])

        # Assert: Empty SessionSet
        assert isinstance(result, SessionSet)
        assert len(result.sessions) == 0

    def test_aggregate_filters_spans_without_session_id(self, create_span):
        """Test that spans without session_id are filtered out."""
        aggregator = SessionAggregator()

        # Create spans, some with session_id, some without
        span_with_id = create_span(span_id="s1", session_id="session-1")
        span_without_id = create_span(span_id="s2", session_id=None)

        spans = [span_with_id, span_without_id]

        # Execute
        result = aggregator.aggregate_spans_to_sessions(spans)

        # Assert: Only span with session_id included
        assert len(result.sessions) == 1
        assert len(result.sessions[0].spans) == 1
        assert result.sessions[0].spans[0].span_id == "s1"

    def test_aggregate_sorts_spans_by_timestamp(self, create_span):
        """Test that spans are sorted by timestamp within session."""
        aggregator = SessionAggregator()

        # Create spans with different timestamps (out of order)
        spans = [
            create_span(
                span_id="s3", session_id="session-1", timestamp="2025-01-01T00:00:02Z"
            ),
            create_span(
                span_id="s1", session_id="session-1", timestamp="2025-01-01T00:00:00Z"
            ),
            create_span(
                span_id="s2", session_id="session-1", timestamp="2025-01-01T00:00:01Z"
            ),
        ]

        # Execute
        result = aggregator.aggregate_spans_to_sessions(spans)

        # Assert: Spans sorted by timestamp
        session = result.sessions[0]
        assert session.spans[0].span_id == "s1"  # Earliest
        assert session.spans[1].span_id == "s2"  # Middle
        assert session.spans[2].span_id == "s3"  # Latest


# ============================================================================
# TEST CLASS 2: CREATE SESSION FROM SPANS
# ============================================================================


class TestCreateSessionFromSpans:
    """Test single session creation from span list."""

    def test_create_session_valid_spans(self, create_span):
        """Test creating session from valid span list."""
        aggregator = SessionAggregator()

        spans = [
            create_span(span_id="s1", session_id="session-1"),
            create_span(span_id="s2", session_id="session-1"),
        ]

        # Execute
        session = aggregator.create_session_from_spans("session-1", spans)

        # Assert: Session created correctly
        assert session.session_id == "session-1"
        assert len(session.spans) == 2
        assert session.start_time is not None
        assert session.end_time is not None

    def test_create_session_calculates_timing(self, create_span):
        """Test that session timing is calculated correctly."""
        aggregator = SessionAggregator()

        # Create spans with timing data
        spans = [
            create_span(
                span_id="s1",
                session_id="session-1",
                timestamp="2025-01-01T00:00:00Z",
                start_time="1704067200.0",
                end_time="1704067201.0",
            ),
            create_span(
                span_id="s2",
                session_id="session-1",
                timestamp="2025-01-01T00:00:01Z",
                start_time="1704067201.0",
                end_time="1704067203.0",
            ),
        ]

        # Execute
        session = aggregator.create_session_from_spans("session-1", spans)

        # Assert: Timing calculated
        assert session.start_time is not None
        assert session.end_time is not None
        assert session.duration is not None
        assert session.duration > 0

    def test_create_session_sorts_spans(self, create_span):
        """Test that spans are sorted by timestamp."""
        aggregator = SessionAggregator()

        # Create spans out of order
        spans = [
            create_span(span_id="s3", timestamp="2025-01-01T00:00:02Z"),
            create_span(span_id="s1", timestamp="2025-01-01T00:00:00Z"),
            create_span(span_id="s2", timestamp="2025-01-01T00:00:01Z"),
        ]

        # Execute
        session = aggregator.create_session_from_spans("session-1", spans)

        # Assert: Sorted
        assert session.spans[0].span_id == "s1"
        assert session.spans[1].span_id == "s2"
        assert session.spans[2].span_id == "s3"

    def test_create_session_empty_raises_error(self):
        """Test that creating session from empty list raises error."""
        aggregator = SessionAggregator()

        # Execute & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            aggregator.create_session_from_spans("session-1", [])

        assert "No spans provided" in str(exc_info.value)


# ============================================================================
# TEST CLASS 3: DURATION CALCULATION
# ============================================================================


class TestDurationCalculation:
    """Test session duration calculation logic."""

    def test_calculate_duration_from_span_times(self, create_span):
        """Test duration calculation from span start/end times."""
        # Create spans with start_time and end_time
        spans = [
            create_span(
                span_id="s1",
                start_time="1704067200.0",  # Start: 0s
                end_time="1704067201.0",  # End: 1s
            ),
            create_span(
                span_id="s2",
                start_time="1704067201.0",  # Start: 1s
                end_time="1704067203.5",  # End: 3.5s
            ),
        ]

        # Execute
        duration = _calculate_session_duration_from_spans(spans)

        # Assert: Duration from earliest start to latest end
        # 0s to 3.5s = 3.5 seconds = 3500 ms
        assert duration == 3500.0

    def test_calculate_duration_no_data(self):
        """Test duration calculation with no timing data."""
        from metrics_computation_engine.entities.models.span import SpanEntity

        # Spans without start_time/end_time
        spans = [
            SpanEntity(
                entity_type="agent",
                span_id="s1",
                entity_name="test",
                app_name="test",
                timestamp="2025-01-01T00:00:00Z",
                contains_error=False,
                raw_span_data={},
                start_time=None,
                end_time=None,
            )
        ]

        # Execute
        duration = _calculate_session_duration_from_spans(spans)

        # Assert: None when no timing data
        assert duration is None

    def test_calculate_duration_empty_list(self):
        """Test duration calculation with empty list."""
        duration = _calculate_session_duration_from_spans([])
        assert duration is None


# ============================================================================
# TEST CLASS 4: FILTER SESSIONS BY CRITERIA
# ============================================================================


class TestFilterSessionsByCriteria:
    """Test multi-criteria session filtering."""

    def test_filter_by_entity_types(self, create_session, create_span):
        """Test filtering sessions by entity types."""
        aggregator = SessionAggregator()

        # Create sessions with different entity types
        session1 = create_session(
            session_id="s1",
            spans=[
                create_span(span_id="sp1", entity_type="agent"),
                create_span(span_id="sp2", entity_type="tool"),
            ],
        )

        session2 = create_session(
            session_id="s2",
            spans=[
                create_span(span_id="sp3", entity_type="llm"),
                create_span(span_id="sp4", entity_type="workflow"),
            ],
        )

        session_set = SessionSet(sessions=[session1, session2])

        # Execute: Filter for sessions with agent spans
        result = aggregator.filter_sessions_by_criteria(
            session_set, entity_types=["agent"]
        )

        # Assert: Only session1 has agent spans
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s1"

    def test_filter_by_has_errors(self, create_session, create_span):
        """Test filtering sessions by error status."""
        aggregator = SessionAggregator()

        # Session with errors
        session1 = create_session(
            session_id="s1",
            spans=[
                create_span(span_id="sp1", contains_error=True),
                create_span(span_id="sp2", contains_error=False),
            ],
        )

        # Session without errors
        session2 = create_session(
            session_id="s2",
            spans=[
                create_span(span_id="sp3", contains_error=False),
            ],
        )

        session_set = SessionSet(sessions=[session1, session2])

        # Execute: Filter for sessions with errors
        result = aggregator.filter_sessions_by_criteria(session_set, has_errors=True)

        # Assert: Only session1 has errors
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s1"

        # Execute: Filter for sessions without errors
        result = aggregator.filter_sessions_by_criteria(session_set, has_errors=False)

        # Assert: Only session2 has no errors
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s2"

    def test_filter_by_min_spans(self, create_session, create_span):
        """Test filtering sessions by minimum span count."""
        aggregator = SessionAggregator()

        # Sessions with different span counts
        session1 = create_session(
            session_id="s1",
            spans=[
                create_span(span_id="sp1"),
                create_span(span_id="sp2"),
                create_span(span_id="sp3"),
            ],
        )

        session2 = create_session(
            session_id="s2",
            spans=[
                create_span(span_id="sp4"),
            ],
        )

        session_set = SessionSet(sessions=[session1, session2])

        # Execute: Filter for sessions with at least 2 spans
        result = aggregator.filter_sessions_by_criteria(session_set, min_spans=2)

        # Assert: Only session1 has >= 2 spans
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s1"

    def test_filter_multiple_criteria(self, create_session, create_span):
        """Test filtering with multiple criteria combined."""
        aggregator = SessionAggregator()

        # Session 1: has agent, has errors, 3 spans
        session1 = create_session(
            session_id="s1",
            spans=[
                create_span(span_id="sp1", entity_type="agent", contains_error=True),
                create_span(span_id="sp2", entity_type="tool"),
                create_span(span_id="sp3", entity_type="llm"),
            ],
        )

        # Session 2: has agent, no errors, 2 spans
        session2 = create_session(
            session_id="s2",
            spans=[
                create_span(span_id="sp4", entity_type="agent"),
                create_span(span_id="sp5", entity_type="tool"),
            ],
        )

        # Session 3: no agent, no errors, 3 spans
        session3 = create_session(
            session_id="s3",
            spans=[
                create_span(span_id="sp6", entity_type="llm"),
                create_span(span_id="sp7", entity_type="tool"),
                create_span(span_id="sp8", entity_type="workflow"),
            ],
        )

        session_set = SessionSet(sessions=[session1, session2, session3])

        # Execute: Filter for agent + no errors + min 2 spans
        result = aggregator.filter_sessions_by_criteria(
            session_set, entity_types=["agent"], has_errors=False, min_spans=2
        )

        # Assert: Only session2 matches all criteria
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s2"


# ============================================================================
# TEST CLASS 5: SESSION RETRIEVAL
# ============================================================================


class TestSessionRetrieval:
    """Test session retrieval operations."""

    def test_get_session_by_id_exists(self, create_session, create_span):
        """Test retrieving existing session by ID."""
        aggregator = SessionAggregator()

        sessions = [
            create_session(session_id="s1", spans=[create_span()]),
            create_session(session_id="s2", spans=[create_span()]),
            create_session(session_id="s3", spans=[create_span()]),
        ]

        session_set = SessionSet(sessions=sessions)

        # Execute: Get session s2
        result = aggregator.get_session_by_id(session_set, "s2")

        # Assert: Found session s2
        assert result is not None
        assert result.session_id == "s2"

    def test_get_session_by_id_not_found(self, create_session, create_span):
        """Test retrieving non-existent session returns None."""
        aggregator = SessionAggregator()

        sessions = [
            create_session(session_id="s1", spans=[create_span()]),
        ]

        session_set = SessionSet(sessions=sessions)

        # Execute: Get non-existent session
        result = aggregator.get_session_by_id(session_set, "non-existent")

        # Assert: Returns None
        assert result is None


# ============================================================================
# TEST CLASS 6: TIME RANGE FILTERING
# ============================================================================


class TestTimeRangeFiltering:
    """Test time range filtering operations."""

    def test_filter_by_time_range(self, create_session, create_span):
        """Test filtering sessions by time range."""
        aggregator = SessionAggregator()

        # Create sessions at different times
        session1 = create_session(
            session_id="s1",
            spans=[create_span()],
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )

        session2 = create_session(
            session_id="s2",
            spans=[create_span()],
            start_time="2025-01-01T01:00:00Z",
            end_time="2025-01-01T01:01:00Z",
        )

        session3 = create_session(
            session_id="s3",
            spans=[create_span()],
            start_time="2025-01-01T02:00:00Z",
            end_time="2025-01-01T02:01:00Z",
        )

        session_set = SessionSet(sessions=[session1, session2, session3])

        # Execute: Filter for time range covering session2
        result = aggregator.get_sessions_by_time_range(
            session_set,
            start_time="2025-01-01T00:30:00Z",
            end_time="2025-01-01T01:30:00Z",
        )

        # Assert: Only session2 in range
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s2"

    def test_filter_by_start_time_only(self, create_session, create_span):
        """Test filtering with only start_time."""
        aggregator = SessionAggregator()

        sessions = [
            create_session(
                session_id="s1",
                spans=[create_span()],
                start_time="2025-01-01T00:00:00Z",
                end_time="2025-01-01T00:01:00Z",
            ),
            create_session(
                session_id="s2",
                spans=[create_span()],
                start_time="2025-01-01T02:00:00Z",
                end_time="2025-01-01T02:01:00Z",
            ),
        ]

        session_set = SessionSet(sessions=sessions)

        # Execute: Filter for sessions starting after 01:00
        result = aggregator.get_sessions_by_time_range(
            session_set, start_time="2025-01-01T01:00:00Z", end_time=None
        )

        # Assert: Only session2
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s2"

    def test_filter_by_end_time_only(self, create_session, create_span):
        """Test filtering with only end_time."""
        aggregator = SessionAggregator()

        sessions = [
            create_session(
                session_id="s1",
                spans=[create_span()],
                start_time="2025-01-01T00:00:00Z",
                end_time="2025-01-01T00:01:00Z",
            ),
            create_session(
                session_id="s2",
                spans=[create_span()],
                start_time="2025-01-01T02:00:00Z",
                end_time="2025-01-01T02:01:00Z",
            ),
        ]

        session_set = SessionSet(sessions=sessions)

        # Execute: Filter for sessions ending before 01:00
        result = aggregator.get_sessions_by_time_range(
            session_set, start_time=None, end_time="2025-01-01T01:00:00Z"
        )

        # Assert: Only session1
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "s1"

    def test_filter_no_time_range_returns_all(self, create_session, create_span):
        """Test that no time filter returns all sessions."""
        aggregator = SessionAggregator()

        sessions = [
            create_session(session_id="s1", spans=[create_span()]),
            create_session(session_id="s2", spans=[create_span()]),
        ]

        session_set = SessionSet(sessions=sessions)

        # Execute: No time filters
        result = aggregator.get_sessions_by_time_range(
            session_set, start_time=None, end_time=None
        )

        # Assert: All sessions returned
        assert len(result.sessions) == 2


# ============================================================================
# INTEGRATION TEST: FULL AGGREGATION WORKFLOW
# ============================================================================


class TestSessionAggregatorIntegration:
    """Integration tests for complete aggregation workflows."""

    def test_full_aggregation_workflow(self, create_span):
        """Test complete aggregation workflow with real-like data."""
        aggregator = SessionAggregator()

        # Create realistic multi-session span data
        spans = [
            # Session 1 - Multi-agent conversation
            create_span(
                span_id="s1-1",
                session_id="session-1",
                entity_type="workflow",
                timestamp="2025-01-01T00:00:00Z",
            ),
            create_span(
                span_id="s1-2",
                session_id="session-1",
                entity_type="agent",
                timestamp="2025-01-01T00:00:01Z",
            ),
            create_span(
                span_id="s1-3",
                session_id="session-1",
                entity_type="llm",
                timestamp="2025-01-01T00:00:02Z",
            ),
            # Session 2 - Tool-heavy session
            create_span(
                span_id="s2-1",
                session_id="session-2",
                entity_type="agent",
                timestamp="2025-01-01T01:00:00Z",
            ),
            create_span(
                span_id="s2-2",
                session_id="session-2",
                entity_type="tool",
                timestamp="2025-01-01T01:00:01Z",
                contains_error=True,
            ),
        ]

        # Step 1: Aggregate
        session_set = aggregator.aggregate_spans_to_sessions(spans)
        assert len(session_set.sessions) == 2

        # Step 2: Filter by entity type
        agent_sessions = aggregator.filter_sessions_by_criteria(
            session_set, entity_types=["agent"]
        )
        assert len(agent_sessions.sessions) == 2  # Both have agents

        # Step 3: Filter by errors
        error_sessions = aggregator.filter_sessions_by_criteria(
            session_set, has_errors=True
        )
        assert len(error_sessions.sessions) == 1
        assert error_sessions.sessions[0].session_id == "session-2"

        # Step 4: Get specific session
        specific = aggregator.get_session_by_id(session_set, "session-1")
        assert specific is not None
        assert len(specific.spans) == 3
