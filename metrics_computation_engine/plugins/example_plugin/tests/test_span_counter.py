"""
Tests for the SpanCounter metric plugin.
"""

import pytest
from span_counter import SpanCounter

# Import SessionEntity and SpanEntity from the main codebase
try:
    from metrics_computation_engine.entities.models.session import SessionEntity
    from metrics_computation_engine.entities.models.span import SpanEntity
except ImportError:
    # Fallback mock for test environments where import fails
    class SpanEntity:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class SessionEntity:
        def __init__(self, session_id, spans):
            self.session_id = session_id
            self.spans = spans
            self.agent_spans = []
            self.workflow_spans = []


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
        session = SessionEntity(session_id="", spans=[])
        result = await self.metric.compute(session)

        assert result.metric_name == "SpanCounter"
        assert result.description == "Number of spans in the session"
        assert result.value == 0
        assert result.aggregation_level == "session"
        assert result.session_id == ""
        assert result.success is True
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_compute_with_data(self):
        """Test compute method with span data."""
        # Create real span data
        span_kwargs = dict(
            entity_type="agent",
            span_id="1",
            entity_name="AgentA",
            app_name="example_app",
            contains_error=False,
            timestamp="",
            parent_span_id=None,
            trace_id="t1",
            session_id="session-123",
            start_time=None,
            end_time=None,
            raw_span_data={},
        )
        span1 = SpanEntity(**span_kwargs)
        span2 = SpanEntity(**{**span_kwargs, "span_id": "2"})
        span3 = SpanEntity(**{**span_kwargs, "span_id": "3"})
        session = SessionEntity(session_id="session-123", spans=[span1, span2, span3])

        result = await self.metric.compute(session)

        assert result.metric_name == "SpanCounter"
        assert result.description == "Number of spans in the session"
        assert result.value == 3
        assert result.aggregation_level == "session"
        assert result.session_id == "session-123"
        assert result.success is True
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_compute_single_span(self):
        """Test compute method with single span."""
        span = SpanEntity(
            entity_type="agent",
            span_id="1",
            entity_name="AgentA",
            app_name="example_app",
            contains_error=False,
            timestamp="",
            parent_span_id=None,
            trace_id="t1",
            session_id="session-456",
            start_time=None,
            end_time=None,
            raw_span_data={},
        )
        session = SessionEntity(session_id="session-456", spans=[span])

        result = await self.metric.compute(session)

        assert result.metric_name == "SpanCounter"
        assert result.value == 1
        assert result.session_id == "session-456"
        assert result.success is True
