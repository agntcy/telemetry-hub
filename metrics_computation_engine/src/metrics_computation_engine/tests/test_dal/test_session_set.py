#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for SessionSet functionality.

Tests cover:
- SessionSet parsing and creation
- Stats builder functionality
- Mapping of stats to ApiMetric
- Statistical calculations
"""

from unittest.mock import MagicMock

from metrics_computation_engine.entities.models.session_set import (
    SessionSet,
    SessionSetStats,
)
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.api_metric import ApiMetric
from metrics_computation_engine.dal import ApiClient


class TestSessionSet:
    """Test suite for SessionSet class."""

    def test_empty_session_set_stats(self):
        """Test that empty SessionSet returns empty stats."""
        session_set = SessionSet(sessions=[])

        stats = session_set.stats
        assert isinstance(stats, SessionSetStats)
        assert stats.meta.count == 0
        assert len(stats.meta.session_ids) == 0
        assert stats.aggregate.avg_tool_calls == 0.0
        assert len(stats.histogram.tool_calls) == 0

    def test_session_set_with_single_session(self):
        """Test SessionSet with a single session."""
        # Create a mock session
        mock_session = MagicMock(spec=SessionEntity)
        mock_session.session_id = "test-app_123e4567-e89b-12d3-a456-426614174000"
        mock_session.spans = []

        session_set = SessionSet(sessions=[mock_session])

        assert len(session_set.sessions) == 1
        assert session_set.sessions[0] == mock_session

    def test_session_set_stats_meta_calculation(self):
        """Test that meta statistics are calculated correctly."""
        # Create mock sessions using the real SessionEntity model
        from metrics_computation_engine.entities.models.session import SessionEntity
        from metrics_computation_engine.entities.models.span import (
            SpanEntity as SpanEntityForTest,
        )

        mock_sessions = []
        for i in range(3):
            # Create a span with app name information
            mock_span = SpanEntityForTest(
                span_id=f"span_{i}",
                session_id=f"app{i}_123e4567-e89b-12d3-a456-426614174000",
                parent_span_id=None,
                start_time="2023-01-01T00:00:00Z",
                end_time="2023-01-01T00:01:40Z",
                timestamp="2023-01-01T00:00:00Z",
                entity_type="agent",
                entity_name=f"app{i}",
                contains_error=False,
                attrs={"app.name": f"app{i}"},
                raw_span_data={"ServiceName": f"app{i}"},
                app_name=f"app{i}",
            )

            mock_session = SessionEntity(
                session_id=f"app{i}_123e4567-e89b-12d3-a456-426614174000",
                spans=[mock_span],
                total_spans=1,
                duration=float(i * 100),  # Different durations for testing
                agent_transitions=None,
                agent_transition_counts=None,
                conversation_elements=None,
                tool_calls=None,
                input_query=None,
                final_response=None,
            )
            mock_sessions.append(mock_session)

        session_set = SessionSet(sessions=mock_sessions)
        stats = session_set.stats

        assert stats.meta.count == 3
        assert len(stats.meta.session_ids) == 3

        # Check session_ids format [uuid, app_name]
        for session_id_pair in stats.meta.session_ids:
            assert isinstance(session_id_pair, list)
            assert len(session_id_pair) == 2
            # UUID part should be longer, app_name should start with "app"
            uuid_part, app_name = session_id_pair
            assert len(uuid_part) > 10  # UUID format
            assert app_name.startswith("app")


class TestSessionSetWithRealData:
    """Test SessionSet with real trace data."""

    def test_session_set_from_api_noa_2(self, logger, api_noa_2_file_path):
        """Test SessionSet creation and stats from api_noa_2.json."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        # Basic structure tests
        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Stats tests
        stats = session_set.stats
        assert stats.meta.count > 0
        assert len(stats.meta.session_ids) == len(session_set.sessions)

        # Check that aggregate stats contain realistic values
        assert stats.aggregate.avg_tool_calls >= 0
        assert stats.aggregate.avg_llm_calls >= 0

        # Check that histogram stats have correct length
        assert len(stats.histogram.tool_calls) == len(session_set.sessions)
        assert len(stats.histogram.llm_calls) == len(session_set.sessions)

    def test_session_set_from_gls_linear(self, logger, gls_linear_file_path):
        """Test SessionSet creation and stats from gls_linear.json."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(gls_linear_file_path)

        # Basic structure tests
        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Stats tests
        stats = session_set.stats
        assert stats.meta.count > 0
        assert len(stats.meta.session_ids) == len(session_set.sessions)

    def test_session_set_stats_consistency(self, logger, api_noa_2_file_path):
        """Test that stats calculations are consistent."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        stats = session_set.stats

        # Meta count should match sessions count
        assert stats.meta.count == len(session_set.sessions)

        # Histogram lists should all have same length (number of sessions)
        histogram_lengths = [
            len(stats.histogram.tool_calls),
            len(stats.histogram.tool_fails),
            len(stats.histogram.llm_calls),
            len(stats.histogram.llm_fails),
        ]
        assert all(length == len(session_set.sessions) for length in histogram_lengths)

        # If there are sessions, aggregate averages should be calculated
        if len(session_set.sessions) > 0:
            # Average calculations should be consistent with histogram data
            if stats.histogram.tool_calls:
                expected_avg_tool_calls = sum(stats.histogram.tool_calls) / len(
                    stats.histogram.tool_calls
                )
                assert (
                    abs(stats.aggregate.avg_tool_calls - expected_avg_tool_calls)
                    < 0.001
                )

    def test_session_set_agent_stats(self, logger, api_noa_2_file_path):
        """Test that agent-specific statistics are calculated."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        # Check that agent stats exist if there are sessions
        if len(session_set.sessions) > 0:
            # Agent stats should be calculated
            # (Note: exact structure depends on implementation)
            assert session_set.stats is not None


class TestSessionSetToApiMetric:
    """Test conversion of SessionSet stats to ApiMetric format."""

    def test_session_stats_to_api_metric_structure(
        self, logger, sample_trace_data, tmp_path
    ):
        """Test that SessionSet stats can be mapped to ApiMetric format."""
        # Create temporary file with sample data
        import json

        temp_file = tmp_path / "sample.json"
        with open(temp_file, "w") as f:
            json.dump(sample_trace_data, f)

        # Load session set
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(str(temp_file))

        stats = session_set.stats

        # Test creating ApiMetric from stats
        for i, (session_id_parts, session) in enumerate(
            zip(stats.meta.session_ids, session_set.sessions)
        ):
            uuid_part, app_name = session_id_parts

            # Create application-level metrics
            app_metric = ApiMetric(
                app_id=app_name,
                app_name=app_name,
                session_id=uuid_part,
                span_id="n/a",
                trace_id="n/a",
                metrics={
                    "aggregation_level": "session",
                    "category": "application",
                    "name": app_name,
                    "eval.app.tool_calls": stats.histogram.tool_calls[i]
                    if i < len(stats.histogram.tool_calls)
                    else 0,
                    "eval.app.tool_fails": stats.histogram.tool_fails[i]
                    if i < len(stats.histogram.tool_fails)
                    else 0,
                    "eval.app.llm_calls": stats.histogram.llm_calls[i]
                    if i < len(stats.histogram.llm_calls)
                    else 0,
                    "eval.app.llm_fails": stats.histogram.llm_fails[i]
                    if i < len(stats.histogram.llm_fails)
                    else 0,
                },
            )

            # Verify ApiMetric structure
            assert isinstance(app_metric, ApiMetric)
            assert app_metric.app_name == app_name
            assert app_metric.session_id == uuid_part
            assert "eval.app.tool_calls" in app_metric.metrics
            assert app_metric.metrics["aggregation_level"] == "session"
            assert app_metric.metrics["category"] == "application"

    def test_api_metric_validation(self):
        """Test ApiMetric validation and structure."""
        metric = ApiMetric(
            app_id="test-app",
            app_name="test-app",
            session_id="test-session-123",
            metrics={
                "aggregation_level": "session",
                "category": "application",
                "eval.app.tool_calls": 5,
                "eval.app.llm_calls": 3,
            },
        )

        assert metric.app_id == "test-app"
        assert metric.app_name == "test-app"
        assert metric.session_id == "test-session-123"
        assert metric.metrics["eval.app.tool_calls"] == 5
        assert metric.metrics["eval.app.llm_calls"] == 3

    def test_api_metric_json_serialization(self):
        """Test that ApiMetric can be serialized to JSON."""
        metric = ApiMetric(
            app_id="test-app",
            app_name="test-app",
            session_id="test-session-123",
            metrics={"eval.app.tool_calls": 5},
        )

        # Test model_dump() for serialization
        metric_dict = metric.model_dump()
        assert isinstance(metric_dict, dict)
        assert metric_dict["app_id"] == "test-app"
        assert metric_dict["metrics"]["eval.app.tool_calls"] == 5


class TestSessionSetStatsCalculations:
    """Test specific statistical calculations in SessionSet."""

    def test_stats_calculation_with_real_data(self, logger, api_noa_2_file_path):
        """Test detailed stats calculations with real data."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        stats = session_set.stats

        # Test that stats are calculated
        assert isinstance(stats.aggregate.avg_tool_calls, (int, float))
        assert isinstance(stats.aggregate.avg_llm_calls, (int, float))
        assert stats.aggregate.avg_tool_calls >= 0
        assert stats.aggregate.avg_llm_calls >= 0

        # Test histogram data
        assert isinstance(stats.histogram.tool_calls, list)
        assert isinstance(stats.histogram.llm_calls, list)
        assert all(isinstance(x, (int, float)) for x in stats.histogram.tool_calls)
        assert all(isinstance(x, (int, float)) for x in stats.histogram.llm_calls)

    def test_stats_edge_cases(self):
        """Test stats calculations with edge cases."""
        # Test with no sessions
        empty_session_set = SessionSet(sessions=[])
        empty_stats = empty_session_set.stats

        assert empty_stats.meta.count == 0
        assert empty_stats.aggregate.avg_tool_calls == 0.0
        assert len(empty_stats.histogram.tool_calls) == 0


class TestSessionSetStatsCaching:
    """Test suite for SessionSet stats caching functionality."""

    def test_stats_are_cached(self, sample_session_set):
        """Test that stats are cached and not recomputed on subsequent calls."""
        # First call should compute stats
        stats1 = sample_session_set.stats

        # Verify cache is populated
        assert sample_session_set._cached_stats is not None
        assert sample_session_set._cache_hash is not None

        # Second call should return cached stats (same object)
        stats2 = sample_session_set.stats
        assert stats1 is stats2  # Should be the exact same object

    def test_cache_invalidation_on_session_modification(self, sample_session_set):
        """Test that cache is invalidated when sessions are modified."""
        # Get initial stats to populate cache
        stats1 = sample_session_set.stats
        initial_count = stats1.meta.count

        # Create a new mock session with all required attributes
        mock_session = MagicMock(spec=SessionEntity)
        mock_session.session_id = "new-app_987f6543-e21c-34e5-b678-123456789abc"
        mock_session.spans = []
        mock_session.total_llm_calls = 5
        mock_session.total_tool_calls = 3
        mock_session.duration = 100.0
        mock_session.agent_stats = {}

        # Ensure app_name property returns a string, not a MagicMock
        mock_session.app_name = "new-app"

        # Add all required attributes for metrics extraction
        mock_session.graph_determinism = 0.8
        mock_session.graph_coverage = 0.9
        mock_session.graph_dynamism = 0.7
        mock_session.user_intents = []
        mock_session.llm_calls = []
        mock_session.tool_calls = []
        mock_session.start_time = None
        mock_session.end_time = None
        mock_session.input_query = None
        mock_session.final_response = None
        mock_session.requirements = None

        # Add metrics-related attributes
        mock_session.tool_calls_failed = 0
        mock_session.tool_total_tokens = 100
        mock_session.total_tools_duration = 50.0
        mock_session.llm_calls_failed = 0
        mock_session.llm_total_tokens = 200
        mock_session.llm_input_tokens = 150
        mock_session.llm_output_tokens = 50
        mock_session.total_llm_duration = 30.0

        # Add session using the helper method (should invalidate cache)
        sample_session_set.add_session(mock_session)

        # Verify cache was invalidated
        assert sample_session_set._cached_stats is None
        assert sample_session_set._cache_hash is None

        # Get new stats
        stats2 = sample_session_set.stats
        assert stats2.meta.count == initial_count + 1

    def test_manual_cache_invalidation(self, sample_session_set):
        """Test manual cache invalidation."""
        # Populate cache
        sample_session_set.stats
        assert sample_session_set._cached_stats is not None

        # Manually invalidate
        sample_session_set.invalidate_stats_cache()
        assert sample_session_set._cached_stats is None
        assert sample_session_set._cache_hash is None

        # Next call should recompute
        sample_session_set.stats
        assert sample_session_set._cached_stats is not None

    def test_remove_session_invalidates_cache(self, sample_session_set):
        """Test that removing a session invalidates the cache."""
        # Get initial stats
        initial_stats = sample_session_set.stats
        initial_count = initial_stats.meta.count

        # Get a session ID to remove
        if sample_session_set.sessions:
            session_id_to_remove = sample_session_set.sessions[0].session_id

            # Remove session (should invalidate cache)
            removed = sample_session_set.remove_session(session_id_to_remove)
            assert removed is True

            # Verify cache was invalidated
            assert sample_session_set._cached_stats is None

            # Get new stats
            stats2 = sample_session_set.stats
            assert stats2.meta.count == initial_count - 1

    def test_hash_calculation_consistency(self, sample_session_set):
        """Test that hash calculation is consistent for the same data."""
        hash1 = sample_session_set._calculate_sessions_hash()
        hash2 = sample_session_set._calculate_sessions_hash()
        assert hash1 == hash2

    def test_hash_changes_with_data_modification(self, sample_session_set):
        """Test that hash changes when session data changes."""
        hash1 = sample_session_set._calculate_sessions_hash()

        # Modify sessions list
        if sample_session_set.sessions:
            # Change a session property that affects the hash
            original_duration = sample_session_set.sessions[0].duration
            sample_session_set.sessions[0].duration = (original_duration or 0) + 100

            hash2 = sample_session_set._calculate_sessions_hash()
            assert hash1 != hash2

            # Restore original value
            sample_session_set.sessions[0].duration = original_duration
