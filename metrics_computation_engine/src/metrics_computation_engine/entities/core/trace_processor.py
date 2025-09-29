# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Trace Processing Module

Handles the processing of raw trace data into enriched session sets.
This module contains the core business logic for transforming trace data.
"""

import logging
from typing import Dict, List, Optional

from ..models.session_set import SessionSet
from .data_parser import parse_raw_spans
from .session_aggregator import SessionAggregator
from ..transformers.session_enrichers import SessionEnrichmentPipeline


class TraceProcessor:
    """
    Main processor for converting raw trace data into enriched session sets.

    This class encapsulates the entire processing pipeline:
    1. Parse raw spans into SpanEntity objects
    2. Aggregate spans into sessions
    3. Apply session filtering if needed
    4. Enrich sessions with additional analysis
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the trace processor."""
        self.logger = logger or logging.getLogger(__name__)
        self.aggregator = SessionAggregator()
        self.enrichment_pipeline = SessionEnrichmentPipeline()

    def process_raw_traces(
        self, raw_traces: List[Dict], session_id_filter: Optional[str] = None
    ) -> SessionSet:
        """
        Process raw trace data into an enriched session set.

        Args:
            raw_traces: List of raw trace dictionaries
            session_id_filter: Optional session ID to filter for

        Returns:
            SessionSet containing enriched session data

        Raises:
            ValueError: If no valid spans are found
        """
        if not raw_traces:
            raise ValueError("No trace data provided")

        self.logger.info(f"Processing {len(raw_traces)} raw trace records")

        # Step 1: Parse raw spans into SpanEntity objects
        span_entities = parse_raw_spans(raw_traces)
        self.logger.info(f"Parsed {len(span_entities)} span entities")

        if not span_entities:
            raise ValueError("No valid spans found in trace data")

        # Debug: log session IDs found in the parsed spans
        if span_entities:
            session_ids = {span.session_id for span in span_entities if span.session_id}
            self.logger.debug(f"Session IDs found in parsed spans: {session_ids}")

        # Step 2: Aggregate spans into sessions
        session_set = self.aggregator.aggregate_spans_to_sessions(span_entities)
        self.logger.info(f"Aggregated spans into {len(session_set.sessions)} sessions")

        # Step 3: Apply session filtering if requested
        if session_id_filter:
            session_set = self._filter_by_session_id(session_set, session_id_filter)

        # Step 4: Enrich sessions with additional analysis
        enriched_sessions = self.enrichment_pipeline.enrich_sessions(
            session_set.sessions
        )
        enriched_session_set = SessionSet(sessions=enriched_sessions)

        return enriched_session_set

    def process_grouped_sessions(
        self,
        grouped_sessions: Dict[str, List[Dict]],
        session_id_filter: Optional[str] = None,
    ) -> SessionSet:
        """
        Process pre-grouped session data into an enriched session set.

        This method is optimized for API responses where spans are already grouped by session_id.
        It avoids the overhead of flattening and re-grouping spans.

        Args:
            grouped_sessions: Dictionary with session_id as key and list of span dicts as value
            session_id_filter: Optional session ID to filter for

        Returns:
            SessionSet containing enriched session data

        Raises:
            ValueError: If no valid sessions are found
        """
        if not grouped_sessions:
            raise ValueError("No session data provided")

        self.logger.info(f"Processing {len(grouped_sessions)} pre-grouped sessions")

        sessions = []
        total_spans = 0

        for session_id, session_spans in grouped_sessions.items():
            if not session_spans:
                self.logger.warning(f"Session {session_id} has no spans, skipping")
                continue

            # Apply session filtering early if requested
            if session_id_filter and session_id != session_id_filter:
                continue

            # Parse spans for this session
            span_entities = parse_raw_spans(session_spans)
            if not span_entities:
                self.logger.warning(
                    f"No valid spans found in session {session_id}, skipping"
                )
                continue

            total_spans += len(span_entities)

            # Create session directly from parsed spans
            session_entity = self.aggregator.create_session_from_spans(
                session_id, span_entities
            )
            sessions.append(session_entity)

        self.logger.info(
            f"Processed {total_spans} spans across {len(sessions)} sessions"
        )

        if not sessions:
            raise ValueError("No valid sessions found in grouped data")

        # Create session set
        session_set = SessionSet(sessions=sessions)

        # Step 4: Enrich sessions with additional analysis
        enriched_sessions = self.enrichment_pipeline.enrich_sessions(
            session_set.sessions
        )
        enriched_session_set = SessionSet(sessions=enriched_sessions)

        return enriched_session_set

    def _filter_by_session_id(
        self, session_set: SessionSet, target_session_id: str
    ) -> SessionSet:
        """
        Filter sessions to find a specific session ID.

        Args:
            session_set: The session set to filter
            target_session_id: The session ID to look for

        Returns:
            SessionSet containing only the matching session

        Raises:
            ValueError: If the session is not found
        """
        specific_session = None

        # Look for exact match first, then partial match (in case session ID has service prefix)
        for session in session_set.sessions:
            if session.session_id == target_session_id:
                specific_session = session
                break
            elif target_session_id in session.session_id:
                specific_session = session
                self.logger.info(
                    f"Found session with ID containing '{target_session_id}': {session.session_id}"
                )
                break

        if not specific_session:
            raise ValueError(f"Session {target_session_id} not found in data")

        return SessionSet(sessions=[specific_session])


def create_pseudo_grouped_sessions_from_file(
    raw_traces: List[Dict],
) -> Dict[str, List[Dict]]:
    """
    Create a pseudo-grouped sessions dictionary from file traces.

    Groups traces by session_id to create the same structure as API responses.
    Parses session IDs in the format <service_name>_<uuid> to extract just the UUID part,
    matching the behavior of database retrieval.

    Args:
        raw_traces: List of raw trace dictionaries from file

    Returns:
        Dictionary with session_id as key and list of span dicts as value
    """
    grouped = {}

    for trace in raw_traces:
        # Extract session_id from trace
        session_id = None

        # Try different ways to extract session_id
        if isinstance(trace, dict):
            # Try SpanAttributes first
            span_attrs = trace.get("SpanAttributes", {})
            if isinstance(span_attrs, dict):
                session_id = span_attrs.get("session.id") or span_attrs.get(
                    "execution.id"
                )

            # Fallback to direct session_id field
            if not session_id:
                session_id = trace.get("session_id") or trace.get("sessionId")

        # Use a default session if no session_id found
        if not session_id:
            session_id = "file_session_default"
        else:
            # Parse session ID to extract UUID part (matching database behavior)
            # Expected format: <service_name>_<uuid>
            if "_" in session_id:
                # Split on the last underscore to handle service names with underscores
                parts = session_id.rsplit("_", 1)
                if len(parts) == 2:
                    # Check if the last part looks like a UUID (basic validation)
                    uuid_part = parts[1]
                    if len(uuid_part) == 36 and uuid_part.count("-") == 4:
                        session_id = uuid_part  # Use just the UUID part

        # Group by session_id and process trace metadata
        if session_id not in grouped:
            grouped[session_id] = []

        # Process the trace to match database response format
        processed_trace = trace.copy()

        # Extract the full session ID from span attributes for sessionId
        span_attrs = trace.get("SpanAttributes", {})
        if isinstance(span_attrs, dict):
            full_session_id = span_attrs.get("session.id") or span_attrs.get(
                "execution.id"
            )
            if full_session_id:
                processed_trace["sessionId"] = full_session_id

        # Add other fields that match database processing
        if "Timestamp" in processed_trace:
            from datetime import datetime

            timestamp = datetime.fromisoformat(processed_trace["Timestamp"])
            processed_trace["startTime"] = timestamp.timestamp()

        if "Duration" in processed_trace:
            processed_trace["duration"] = processed_trace["Duration"] * 0.000001

        # Set status code
        status_code = processed_trace.get("StatusCode", "Ok")
        processed_trace["statusCode"] = (
            2 if status_code in ["Error", "STATUS_CODE_ERROR"] else 0
        )

        # Set framework span kind
        span_kind = (
            span_attrs.get("traceloop.span.kind", "")
            if isinstance(span_attrs, dict)
            else ""
        )
        processed_trace["FrameworkSpanKind"] = str(span_kind).upper()

        grouped[session_id].append(processed_trace)

    return grouped
