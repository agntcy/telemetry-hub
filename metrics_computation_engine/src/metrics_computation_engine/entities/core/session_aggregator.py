# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pandas as pd
from typing import List, Optional

from ..models.span import SpanEntity
from ..models.session import SessionEntity
from ..models.session_set import SessionSet


def _calculate_session_duration_from_spans(spans: List[SpanEntity]) -> Optional[float]:
    """
    Calculate session duration from span start_time and end_time.
    Takes the earliest start_time and latest end_time to account for parallel execution.

    Args:
        spans: List of SpanEntity objects (should be sorted by timestamp)

    Returns:
        Duration in milliseconds, or None if cannot be calculated
    """
    if not spans:
        return None

    # Extract valid start and end times
    start_times = []
    end_times = []

    for span in spans:
        if span.start_time:
            try:
                start_times.append(float(span.start_time))
            except (ValueError, TypeError):
                pass

        if span.end_time:
            try:
                end_times.append(float(span.end_time))
            except (ValueError, TypeError):
                pass

    # Calculate session duration from earliest start to latest end
    if start_times and end_times:
        earliest_start = min(start_times)
        latest_end = max(end_times)
        return (latest_end - earliest_start) * 1000  # Convert to milliseconds

    return None


class SessionAggregator:
    """
    Aggregates spans into session objects based on session_id.
    Uses pandas for efficient filtering and sorting operations.
    """

    def __init__(self):
        pass

    def aggregate_spans_to_sessions(self, spans: List[SpanEntity]) -> SessionSet:
        """
        Aggregate a list of spans into sessions based on session_id.

        Args:
            spans: List of SpanEntity objects

        Returns:
            SessionSet containing all aggregated sessions
        """
        if not spans:
            return SessionSet(sessions=[])

        # Convert spans to DataFrame for efficient processing
        span_data = []
        for span in spans:
            span_data.append(
                {
                    "span": span,
                    "session_id": span.session_id,
                    "timestamp": span.timestamp,
                    "entity_type": span.entity_type,
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                }
            )

        df = pd.DataFrame(span_data)

        # Filter out spans without session_id
        df = df[df["session_id"].notna()]

        if df.empty:
            return SessionSet(sessions=[])

        # Sort by timestamp for each session
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values(["session_id", "timestamp"])

        sessions = []

        # Group spans by session_id
        for session_id, session_df in df.groupby("session_id"):
            session_spans = session_df["span"].tolist()

            # Calculate session timing - prioritize span start_time/end_time over timestamps
            start_time = None
            end_time = None
            duration_ms = None

            # First try to calculate duration from span start_time and end_time (most accurate)
            duration_ms = _calculate_session_duration_from_spans(session_spans)

            # For session start_time and end_time, use timestamps as metadata
            valid_timestamps = session_df["timestamp"].dropna()
            if not valid_timestamps.empty:
                start_time = (
                    valid_timestamps.min().isoformat()
                    if pd.notna(valid_timestamps.min())
                    else None
                )
                end_time = (
                    valid_timestamps.max().isoformat()
                    if pd.notna(valid_timestamps.max())
                    else None
                )

            # If we couldn't calculate from spans, try timestamp-based calculation as fallback
            if duration_ms is None and start_time and end_time:
                try:
                    start_ts = pd.to_datetime(start_time)
                    end_ts = pd.to_datetime(end_time)
                    duration_ms = (end_ts - start_ts).total_seconds() * 1000
                except Exception:
                    pass

            session = SessionEntity(
                session_id=session_id,
                spans=session_spans,
                start_time=start_time,
                end_time=end_time,
                duration=duration_ms,
            )

            sessions.append(session)

        return SessionSet(sessions=sessions)

    def create_session_from_spans(
        self, session_id: str, spans: List[SpanEntity]
    ) -> SessionEntity:
        """
        Create a single session entity from a list of spans.

        This method is optimized for cases where spans are already grouped by session_id.

        Args:
            session_id: The session ID
            spans: List of SpanEntity objects for this session

        Returns:
            SessionEntity for the given spans
        """
        if not spans:
            raise ValueError(f"No spans provided for session {session_id}")

        # Sort spans by timestamp
        sorted_spans = sorted(spans, key=lambda s: s.timestamp or "")

        # Calculate session timing
        start_time = None
        end_time = None
        duration_ms = None

        # Calculate duration from span start_time and end_time
        duration_ms = _calculate_session_duration_from_spans(sorted_spans)

        # For session start_time and end_time, use timestamps as metadata
        valid_timestamps = [s.timestamp for s in sorted_spans if s.timestamp]
        if valid_timestamps:
            start_time = min(valid_timestamps)
            end_time = max(valid_timestamps)

        # If we couldn't calculate from spans, try timestamp-based calculation as fallback
        if duration_ms is None and start_time and end_time:
            try:
                start_ts = pd.to_datetime(start_time)
                end_ts = pd.to_datetime(end_time)
                duration_ms = (end_ts - start_ts).total_seconds() * 1000
            except Exception:
                pass

        return SessionEntity(
            session_id=session_id,
            spans=sorted_spans,
            start_time=start_time,
            end_time=end_time,
            duration=duration_ms,
        )

    def filter_sessions_by_criteria(
        self,
        session_set: SessionSet,
        entity_types: Optional[List[str]] = None,
        has_errors: Optional[bool] = None,
        min_spans: Optional[int] = None,
    ) -> SessionSet:
        """
        Filter sessions based on various criteria.

        Args:
            session_set: SessionSet to filter
            entity_types: Filter sessions that contain spans of these entity types
            has_errors: Filter sessions with/without errors
            min_spans: Filter sessions with at least this many spans

        Returns:
            Filtered SessionSet
        """
        filtered_sessions = []

        for session in session_set.sessions:
            # Check entity type filter
            if entity_types:
                session_entity_types = {span.entity_type for span in session.spans}
                if not any(et in session_entity_types for et in entity_types):
                    continue

            # Check error filter
            if has_errors is not None:
                session_has_errors = any(span.contains_error for span in session.spans)
                if session_has_errors != has_errors:
                    continue

            # Check minimum spans filter
            if min_spans and len(session.spans) < min_spans:
                continue

            filtered_sessions.append(session)

        return SessionSet(sessions=filtered_sessions)

    def get_session_by_id(
        self, session_set: SessionSet, session_id: str
    ) -> Optional[SessionEntity]:
        """
        Get a specific session by its ID.

        Args:
            session_set: SessionSet to search
            session_id: ID of the session to find

        Returns:
            SessionEntity if found, None otherwise
        """
        for session in session_set.sessions:
            if session.session_id == session_id:
                return session
        return None

    def get_sessions_by_time_range(
        self,
        session_set: SessionSet,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> SessionSet:
        """
        Filter sessions by time range.

        Args:
            session_set: SessionSet to filter
            start_time: Start time in ISO format
            end_time: End time in ISO format

        Returns:
            Filtered SessionSet
        """
        if not start_time and not end_time:
            return session_set

        filtered_sessions = []

        for session in session_set.sessions:
            session_start = (
                pd.to_datetime(session.start_time, errors="coerce")
                if session.start_time
                else None
            )
            session_end = (
                pd.to_datetime(session.end_time, errors="coerce")
                if session.end_time
                else None
            )

            # Skip sessions without valid timestamps
            if session_start is None and session_end is None:
                continue

            # Check if session overlaps with the time range
            if start_time:
                filter_start = pd.to_datetime(start_time, errors="coerce")
                if filter_start and session_end and session_end < filter_start:
                    continue

            if end_time:
                filter_end = pd.to_datetime(end_time, errors="coerce")
                if filter_end and session_start and session_start > filter_end:
                    continue

            filtered_sessions.append(session)

        return SessionSet(sessions=filtered_sessions)
