# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Tests for the SpanCounter metric plugin.
"""

import pytest
from unittest.mock import Mock
from span_counter import SpanCounter


class TestSpanCounter:
    """Test cases for SpanCounter metric."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metric = SpanCounter()

    def test_init(self):
        """Test SpanCounter initialization."""
        assert self.metric.name == "SpanCounter"
        assert self.metric.aggregation_level == "session"

    def test_required_parameters(self):
        """Test required parameters property."""
        assert self.metric.required_parameters == []

    def test_validate_config(self):
        """Test config validation."""
        assert self.metric.validate_config() is True

    @pytest.mark.asyncio
    async def test_compute_empty_data(self):
        """Test compute method with empty data."""
        result = await self.metric.compute([])

        assert result.metric_name == "SpanCounter"
        assert result.description == "Number of spans"
        assert result.value == 0
        assert result.aggregation_level == "session"
        assert result.session_id == []
        assert result.success is True
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_compute_with_data(self):
        """Test compute method with span data."""
        # Create mock span data
        mock_span1 = Mock()
        mock_span1.session_id = "session-123"
        mock_span2 = Mock()
        mock_span2.session_id = "session-123"
        mock_span3 = Mock()
        mock_span3.session_id = "session-123"

        data = [mock_span1, mock_span2, mock_span3]

        result = await self.metric.compute(data)

        assert result.metric_name == "SpanCounter"
        assert result.description == "Number of spans"
        assert result.value == 3
        assert result.aggregation_level == "session"
        assert result.session_id == ["session-123"]
        assert result.success is True
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_compute_single_span(self):
        """Test compute method with single span."""
        mock_span = Mock()
        mock_span.session_id = "session-456"

        data = [mock_span]

        result = await self.metric.compute(data)

        assert result.metric_name == "SpanCounter"
        assert result.value == 1
        assert result.session_id == ["session-456"]
        assert result.success is True
