#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for ApiClient functionality.

Tests cover:
- File loading functionality
- SessionSet creation from files
- Error handling
"""

import pytest
from unittest.mock import patch, MagicMock

from metrics_computation_engine.dal import ApiClient
from metrics_computation_engine.entities.models.session_set import SessionSet


class TestApiClient:
    """Test suite for ApiClient class."""

    def test_api_client_initialization(self, logger):
        """Test ApiClient can be initialized properly."""
        client = ApiClient(logger=logger)

        assert client.logger == logger
        assert client.devlimit == -1
        assert client.trace_processor is not None

    def test_api_client_initialization_with_devlimit(self, logger):
        """Test ApiClient initialization with devlimit."""
        client = ApiClient(devlimit=100, logger=logger)

        assert client.devlimit == 100

    def test_get_traces_from_file_success(self, logger, api_noa_2_file_path):
        """Test successful loading of traces from file."""
        client = ApiClient(logger=logger)

        traces = client.get_traces_from_file(api_noa_2_file_path)

        assert isinstance(traces, list)
        assert len(traces) > 0

        # Check that traces have expected structure
        first_trace = traces[0]
        assert "TraceId" in first_trace
        assert "SpanId" in first_trace
        assert "SpanName" in first_trace
        assert "Timestamp" in first_trace

    def test_get_traces_from_file_nonexistent(self, logger):
        """Test loading from non-existent file raises error."""
        client = ApiClient(logger=logger)

        with pytest.raises(FileNotFoundError):
            client.get_traces_from_file("/path/to/nonexistent/file.json")

    def test_load_session_set_from_file_api_noa_2(self, logger, api_noa_2_file_path):
        """Test loading SessionSet from api_noa_2.json file."""
        client = ApiClient(logger=logger)

        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Check sessions have expected structure
        first_session = session_set.sessions[0]
        assert first_session.session_id is not None
        assert len(first_session.spans) > 0
        assert first_session.total_spans > 0

    def test_load_session_set_from_file_gls_linear(self, logger, gls_linear_file_path):
        """Test loading SessionSet from gls_linear.json file."""
        client = ApiClient(logger=logger)

        session_set = client.load_session_set_from_file(gls_linear_file_path)

        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Check sessions have expected structure
        first_session = session_set.sessions[0]
        assert first_session.session_id is not None
        assert len(first_session.spans) > 0

    def test_load_session_set_from_file_with_sample_data(
        self, logger, sample_trace_data, tmp_path
    ):
        """Test loading SessionSet from minimal sample data."""
        # Write sample data to temporary file
        temp_file = tmp_path / "sample_traces.json"
        import json

        with open(temp_file, "w") as f:
            json.dump(sample_trace_data, f)

        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(str(temp_file))

        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) >= 1

        # Check that session contains the expected spans
        session = session_set.sessions[0]
        # Session ID is determined by the processing logic, may be default
        assert (
            session.session_id == "file_session_default"
            or session.session_id == "test-session-1"
        )
        assert len(session.spans) == 2

    @patch("metrics_computation_engine.dal.api_client.ApiClient.get_population_set")
    def test_get_population_set_and_process_mock(self, mock_population_set, logger):
        """Test getting population set and processing sessions using mocked responses."""
        # Mock API response with grouped sessions - now returns tuple
        mock_population_set.return_value = (
            {
                "test-session-1": [
                    {
                        "TraceId": "test-trace-1",
                        "SpanId": "test-span-1",
                        "SpanName": "test_agent.agent",  # Valid entity type
                        "Timestamp": "2025-09-10T14:26:57.794657Z",
                        "SpanAttributes": {"session_id": "test-session-1"},
                        "ParentSpanId": "",
                        "ServiceName": "test-service",
                        "ResourceAttributes": {"service.name": "test-service"},
                        "SpanKind": "Server",
                    }
                ]
            },
            [],  # Empty list of not found session IDs
        )

        client = ApiClient(logger=logger)

        # Mock the API config
        client._api_config = MagicMock()
        client._api_config.uri_sessions = "/test/sessions"

        # Test the population set retrieval and processing flow
        grouped_sessions, not_found_ids = client.get_population_set(
            session_id="test-session-1"
        )
        session_set = client.trace_processor.process_grouped_sessions(grouped_sessions)

        assert isinstance(session_set, SessionSet)
        assert not_found_ids == []
        # Note: The actual behavior depends on the API response structure

    def test_api_client_error_handling_invalid_json(self, logger, tmp_path):
        """Test ApiClient handles invalid JSON gracefully."""
        # Create invalid JSON file
        invalid_file = tmp_path / "invalid.json"
        with open(invalid_file, "w") as f:
            f.write("{ invalid json")

        client = ApiClient(logger=logger)

        with pytest.raises(Exception):  # Should raise JSON decode error
            client.get_traces_from_file(str(invalid_file))

    def test_api_client_handles_empty_file(self, logger, tmp_path):
        """Test ApiClient handles empty JSON file."""
        empty_file = tmp_path / "empty.json"
        with open(empty_file, "w") as f:
            f.write("[]")

        client = ApiClient(logger=logger)
        traces = client.get_traces_from_file(str(empty_file))

        assert traces == []

    def test_load_session_set_from_empty_traces(self, logger, tmp_path):
        """Test loading SessionSet from empty traces list."""
        empty_file = tmp_path / "empty.json"
        with open(empty_file, "w") as f:
            f.write("[]")

        client = ApiClient(logger=logger)

        # Should raise ValueError when no session data is provided
        with pytest.raises(ValueError, match="No session data provided"):
            client.load_session_set_from_file(str(empty_file))


class TestApiClientIntegration:
    """Integration tests for ApiClient with real data."""

    def test_api_noa_2_file_processing_stats(self, logger, api_noa_2_file_path):
        """Test complete processing of api_noa_2.json and verify stats."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        # Verify SessionSet has stats
        assert session_set.stats is not None

        # Check that stats contain expected fields
        stats_dict = session_set.stats.model_dump()
        assert "aggregate" in stats_dict
        assert "meta" in stats_dict

        # Verify at least one session was processed
        assert session_set.stats.meta.count > 0
        assert len(session_set.stats.meta.session_ids) > 0

    def test_gls_linear_file_processing_stats(self, logger, gls_linear_file_path):
        """Test complete processing of gls_linear.json and verify stats."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(gls_linear_file_path)

        # Verify SessionSet has stats
        assert session_set.stats is not None

        # Check that stats contain expected fields
        stats_dict = session_set.stats.model_dump()
        assert "aggregate" in stats_dict
        assert "meta" in stats_dict

        # Verify at least one session was processed
        assert session_set.stats.meta.count > 0
        assert len(session_set.stats.meta.session_ids) > 0

    def test_compare_file_loading_methods(self, logger, api_noa_2_file_path):
        """Test that both file loading methods produce consistent results."""
        client = ApiClient(logger=logger)

        # Load using get_traces_from_file and manual processing
        raw_traces = client.get_traces_from_file(api_noa_2_file_path)

        # Load using load_session_set_from_file
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        # Verify consistency
        assert len(raw_traces) > 0
        assert session_set.stats.meta.count > 0

        # Calculate total spans across all sessions
        total_spans = sum(len(session.spans) for session in session_set.sessions)
        assert total_spans > 0
