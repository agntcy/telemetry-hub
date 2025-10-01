#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Configuration and utility tests.

Tests cover:
- Configuration management in ApiClient
- Utility functions in dal.utils
- Integration with external dependencies
"""

import pytest
import os
import tempfile
from unittest.mock import patch

from metrics_computation_engine.dal import ApiClient


class TestConfiguration:
    """Test configuration management."""

    def test_api_client_default_configuration(self, logger):
        """Test ApiClient with default configuration."""
        client = ApiClient(logger=logger)

        # Verify default settings
        assert client.devlimit == -1
        assert client.logger == logger

    def test_api_client_custom_devlimit(self, logger):
        """Test ApiClient with custom devlimit."""
        client = ApiClient(devlimit=5, logger=logger)

        assert client.devlimit == 5

    @patch.dict(os.environ, {"API_BASE_URL": "http://localhost:8080"})
    def test_api_client_environment_configuration(self, logger):
        """Test ApiClient configuration from environment variables."""
        # This would test environment-based configuration if implemented
        client = ApiClient(logger=logger)

        # For now, just verify client creation succeeds
        assert client is not None


class TestFileHandling:
    """Test file handling utilities."""

    def test_api_client_file_path_validation(self, logger):
        """Test ApiClient file path validation."""
        client = ApiClient(logger=logger)

        # Test with non-existent file
        with pytest.raises(FileNotFoundError):
            client.load_session_set_from_file("/path/to/nonexistent/file.json")

    def test_api_client_file_permissions(self, logger):
        """Test ApiClient with file permission issues."""
        client = ApiClient(logger=logger)

        # Create a temporary file without read permissions
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write('{"sessions": []}')
            temp_path = temp_file.name

        try:
            # Remove read permissions
            os.chmod(temp_path, 0o000)

            # Should raise PermissionError
            with pytest.raises(PermissionError):
                client.load_session_set_from_file(temp_path)
        finally:
            # Restore permissions and clean up
            os.chmod(temp_path, 0o644)
            os.unlink(temp_path)


class TestLoggingIntegration:
    """Test logging integration."""

    def test_api_client_logging(self, logger):
        """Test ApiClient logging functionality."""
        client = ApiClient(logger=logger)

        # Verify logger is set correctly
        assert client.logger == logger

    def test_api_client_without_logger(self):
        """Test ApiClient without explicit logger."""
        # Should not raise an error
        client = ApiClient()
        assert client is not None


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery mechanisms."""

    def test_api_client_malformed_json(self, logger):
        """Test ApiClient behavior with malformed JSON."""
        client = ApiClient(logger=logger)

        # Create temporary file with malformed JSON
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_file.write('{"sessions": [malformed json}')
            temp_path = temp_file.name

        try:
            # Should raise appropriate JSON error
            with pytest.raises(Exception):  # Could be JSONDecodeError or similar
                client.load_session_set_from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_api_client_empty_file(self, logger):
        """Test ApiClient behavior with empty file."""
        client = ApiClient(logger=logger)

        # Create empty temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_path = temp_file.name

        try:
            # Should handle empty file gracefully or raise appropriate error
            with pytest.raises(Exception):
                client.load_session_set_from_file(temp_path)
        finally:
            os.unlink(temp_path)


class TestPerformanceConsiderations:
    """Test performance-related functionality."""

    def test_api_client_devlimit_functionality(self, api_noa_2_file_path, logger):
        """Test ApiClient devlimit functionality."""
        # Test with limit
        limited_client = ApiClient(devlimit=1, logger=logger)
        session_set_limited = limited_client.load_session_set_from_file(
            api_noa_2_file_path
        )

        # Test without limit
        unlimited_client = ApiClient(devlimit=-1, logger=logger)
        session_set_unlimited = unlimited_client.load_session_set_from_file(
            api_noa_2_file_path
        )

        # Limited should have fewer or equal sessions
        assert len(session_set_limited.sessions) <= len(session_set_unlimited.sessions)


class TestDataValidation:
    """Test data validation and integrity."""

    def test_api_client_data_integrity(self, api_noa_2_file_path, logger):
        """Test data integrity through ApiClient processing."""
        client = ApiClient(logger=logger)
        session_set = client.load_session_set_from_file(api_noa_2_file_path)

        # Verify data integrity
        for session in session_set.sessions:
            # Session should have required fields
            assert session.session_id is not None
            assert session.total_spans >= 0
            assert len(session.spans) >= 0
