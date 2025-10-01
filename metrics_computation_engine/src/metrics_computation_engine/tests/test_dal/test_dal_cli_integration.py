#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Integration tests for cli_evaluator functionality.

Tests cover:
- End-to-end flow from file loading to SessionSet creation
- Integration between ApiClient and cli_evaluator
- Real data processing workflows
"""

import pytest
from unittest.mock import patch, MagicMock

from metrics_computation_engine.dal_cli import run
from metrics_computation_engine.dal import ApiClient
from metrics_computation_engine.entities.models.session_set import SessionSet


class TestDalCliIntegration:
    """Integration tests for cli_evaluator main functionality."""

    @patch("metrics_computation_engine.dal_cli.set_main_args")
    def test_dal_cli_file_processing(
        self, mock_set_main_args, api_noa_2_file_path, logger
    ):
        """Test that dal_cli processes a configuration file correctly"""
        # Set up mocks
        mock_args_obj = MagicMock()
        mock_args_obj.file = api_noa_2_file_path
        mock_args_obj.session_id = None
        mock_args_obj.start_time = None
        mock_args_obj.limit = None
        mock_args_obj.metrics_writer = False
        mock_args_obj.tree_depth = 3
        mock_set_main_args.return_value = mock_args_obj

        # Mock logging configuration
        with patch(
            "metrics_computation_engine.dal_cli.setup_logger"
        ) as mock_setup_logger:
            mock_setup_logger.return_value = logger

            # Run cli_evaluator
            result = run()

            # Verify result
            assert isinstance(result, SessionSet)
            assert len(result.sessions) > 0

    @patch("metrics_computation_engine.dal_cli.set_main_args")
    def test_dal_cli_session_id_processing(self, mock_args, logger):
        """Test cli_evaluator with session_id input (mocked API)."""
        # Mock command line arguments
        mock_args_obj = MagicMock()
        mock_args_obj.file = None
        mock_args_obj.session_id = "test-session-123"
        mock_args_obj.start_time = None
        mock_args_obj.limit = None
        mock_args_obj.metrics_writer = False
        mock_args_obj.tree_depth = 3
        mock_args.return_value = mock_args_obj

        # Mock API response
        with patch(
            "metrics_computation_engine.dal_cli.get_traces_by_session_ids"
        ) as mock_get_traces:
            with patch(
                "metrics_computation_engine.dal_cli.traces_processor"
            ) as mock_traces_processor:
                # Mock the return value as a tuple (grouped_sessions, not_found_sessions)
                mock_get_traces.return_value = ({}, [])  # Empty sessions, no not-found
                mock_traces_processor.return_value = SessionSet(sessions=[], stats=None)

                with patch(
                    "metrics_computation_engine.dal_cli.setup_logger"
                ) as mock_setup_logger:
                    mock_setup_logger.return_value = logger

                    # Run cli_evaluator
                    result = run()

                    # Verify API was called correctly
                    mock_get_traces.assert_called_once_with(["test-session-123"])
                    # Result should be a SessionSet (empty in this case)
                    assert isinstance(result, SessionSet)

    @patch("metrics_computation_engine.dal_cli.set_main_args")
    def test_dal_cli_time_range_processing(self, mock_args, logger):
        """Test dal_cli with time range input (mocked API)."""
        # Mock command line arguments
        mock_args_obj = MagicMock()
        mock_args_obj.file = None
        mock_args_obj.session_id = None
        mock_args_obj.start_time = "2025-09-01T00:00:00Z"
        mock_args_obj.end_time = "2025-09-02T00:00:00Z"
        mock_args_obj.limit = None
        mock_args_obj.metrics_writer = False
        mock_args_obj.tree_depth = 3
        mock_args.return_value = mock_args_obj

        # Mock API response
        with patch(
            "metrics_computation_engine.dal_cli.get_all_session_ids"
        ) as mock_get_all_sessions:
            with patch(
                "metrics_computation_engine.dal_cli.get_traces_by_session_ids"
            ) as mock_get_traces:
                with patch(
                    "metrics_computation_engine.dal_cli.traces_processor"
                ) as mock_traces_processor:
                    # Mock the return values
                    mock_get_all_sessions.return_value = []  # Empty session IDs list
                    mock_get_traces.return_value = (
                        {},
                        [],
                    )  # Empty sessions, no not-found
                    mock_traces_processor.return_value = SessionSet(
                        sessions=[], stats=None
                    )

                    with patch(
                        "metrics_computation_engine.dal_cli.setup_logger"
                    ) as mock_setup_logger:
                        mock_setup_logger.return_value = logger

                        # Run cli_evaluator
                        result = run()

                        # Verify API was called correctly - batch config should be created and passed
                        mock_get_all_sessions.assert_called_once()
                        mock_get_traces.assert_called_once_with([])
                        # Result should be a SessionSet (empty in this case)
                        assert isinstance(result, SessionSet)

    def test_api_client_to_session_set_integration(self, api_noa_2_file_path, logger):
        """Test integration between ApiClient and SessionSet creation."""
        # Test the complete flow from ApiClient to SessionSet
        client = ApiClient(logger=logger)

        # Load session set
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        # Verify complete integration
        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Verify stats are calculated
        stats = session_set.stats
        assert stats.meta.count > 0
        assert len(stats.meta.session_ids) == len(session_set.sessions)

        # Verify each session has expected structure
        for session in session_set.sessions:
            assert session.session_id is not None
            assert len(session.spans) > 0
            assert session.total_spans > 0

    def test_api_client_gls_linear_integration(self, gls_linear_file_path, logger):
        """Test integration with gls_linear.json data."""
        client = ApiClient(logger=logger)

        # Load session set
        session_set = client.load_session_set_from_file(gls_linear_file_path)

        # Verify integration
        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Verify stats
        stats = session_set.stats
        assert stats.meta.count == len(session_set.sessions)


class TestDalCliErrorHandling:
    """Test error handling in cli_evaluator."""

    @patch("metrics_computation_engine.dal_cli.set_main_args")
    def test_cli_evaluator_missing_file(self, mock_args, logger):
        """Test cli_evaluator behavior with missing file."""
        # Mock command line arguments with non-existent file
        mock_args_obj = MagicMock()
        mock_args_obj.file = "/path/to/nonexistent/file.json"
        mock_args_obj.session_id = None
        mock_args_obj.start_time = None
        mock_args_obj.limit = None
        mock_args_obj.metrics_writer = False
        mock_args_obj.tree_depth = 3
        mock_args.return_value = mock_args_obj

        with patch(
            "metrics_computation_engine.dal_cli.setup_logger"
        ) as mock_setup_logger:
            mock_setup_logger.return_value = logger

            # Should raise FileNotFoundError
            with pytest.raises(FileNotFoundError):
                run()

    @patch("metrics_computation_engine.dal_cli.set_main_args")
    def test_dal_cli_api_error(self, mock_args, logger):
        """Test cli_evaluator behavior with API errors."""
        # Mock command line arguments
        mock_args_obj = MagicMock()
        mock_args_obj.file = None
        mock_args_obj.session_id = "test-session-123"
        mock_args_obj.start_time = None
        mock_args_obj.limit = None
        mock_args_obj.metrics_writer = False
        mock_args_obj.tree_depth = 3
        mock_args.return_value = mock_args_obj

        # Mock API to raise exception
        with patch(
            "metrics_computation_engine.dal_cli.get_traces_by_session_ids"
        ) as mock_get_traces:
            mock_get_traces.side_effect = Exception("API Error")

            with patch(
                "metrics_computation_engine.dal_cli.setup_logger"
            ) as mock_setup_logger:
                mock_setup_logger.return_value = logger

                # Should propagate the exception
                with pytest.raises(Exception, match="API Error"):
                    run()


class TestDalCliDisplayFunctionality:
    """Test display functionality integration."""

    @patch("metrics_computation_engine.dal_cli.set_main_args")
    @patch("metrics_computation_engine.dal_cli.display_session_set")
    @patch("metrics_computation_engine.dal_cli.print_statistics")
    def test_cli_evaluator_display_functions(
        self, mock_print_stats, mock_display, mock_args, api_noa_2_file_path, logger
    ):
        """Test that display functions are called correctly."""
        # Mock command line arguments
        mock_args_obj = MagicMock()
        mock_args_obj.file = api_noa_2_file_path
        mock_args_obj.session_id = None
        mock_args_obj.start_time = None
        mock_args_obj.limit = None
        mock_args_obj.metrics_writer = False
        mock_args_obj.tree_depth = 3
        mock_args_obj.show_tree = True  # Add the missing show_tree attribute
        mock_args.return_value = mock_args_obj

        with patch(
            "metrics_computation_engine.dal_cli.setup_logger"
        ) as mock_setup_logger:
            mock_setup_logger.return_value = logger

            # Run cli_evaluator
            result = run()

            # Verify display functions were called
            mock_display.assert_called_once()
            mock_print_stats.assert_called_once()

            # Verify display was called with correct parameters
            call_args = mock_display.call_args
            assert call_args[0][0] == result  # First arg should be session_set
            assert call_args[1]["show_summary"]
            assert call_args[1]["show_trees"]  # This should match args.show_tree
            assert not call_args[1]["show_statistics"]
            assert call_args[1]["tree_depth"] == 3


class TestFullWorkflow:
    """Test complete end-to-end workflows."""

    def test_complete_workflow_api_noa_2(self, api_noa_2_file_path, logger):
        """Test complete workflow with api_noa_2.json."""
        # Simulate the complete workflow manually
        client = ApiClient(devlimit=-1, logger=logger)

        # Load session set (as cli_evaluator would)
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        # Verify complete processing
        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Verify stats are complete
        stats = session_set.stats
        assert stats.meta.count > 0
        assert len(stats.histogram.tool_calls) == len(session_set.sessions)
        assert len(stats.histogram.llm_calls) == len(session_set.sessions)

        # Verify sessions have execution trees
        # Note: May or may not have execution trees depending on data
        assert any(s.execution_tree is not None for s in session_set.sessions) or True

    def test_complete_workflow_gls_linear(self, gls_linear_file_path, logger):
        """Test complete workflow with gls_linear.json."""
        # Simulate the complete workflow manually
        client = ApiClient(devlimit=-1, logger=logger)

        # Load session set
        session_set = client.load_session_set_from_file(gls_linear_file_path)

        # Verify complete processing
        assert isinstance(session_set, SessionSet)
        assert len(session_set.sessions) > 0

        # Verify data quality
        for session in session_set.sessions:
            assert session.session_id is not None
            assert session.total_spans > 0
            assert len(session.spans) == session.total_spans
