"""
Tests for session-level cache functionality.

This module contains tests for session-level metric caching behavior,
including cache lookup, cache miss handling, and session-only filtering.
"""

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity
from typing import Dict, Any, Optional


class SessionCacheTestMetric(BaseMetric):
    """Test metric implementation for session cache testing."""

    def __init__(self):
        self.name = "test_session_metric"
        self.aggregation_level = "session"

    # Required abstract method implementations
    async def compute(self, session: SessionEntity, context: Optional[Dict[str, Any]] = None):
        return MetricResult(
            metric_name=self.name, value=0.75, aggregation_level="session",
            category="application", app_name="test", description="test",
            unit="test", reasoning="test", span_id="", session_id=[session.session_id],
            source="test", entities_involved=[], edges_involved=[], success=True,
            metadata={"session_id": session.session_id}
        )

    def create_model(self): return None
    def get_model_provider(self): return "test"
    def init_with_model(self, model): pass
    def required_parameters(self): return []
    def validate_config(self, config): return True


class TestSessionCacheFunctionality:
    """Test class for session-level cache functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metric = SessionCacheTestMetric()

    def test_session_cache_hit(self):
        """Test successful cache hit for session-level metric."""
        # Mock cached data
        cached_session_metrics = [
            {
                "metrics": {
                    "metric_name": "test_session_metric",
                    "value": 0.85,
                    "aggregation_level": "session",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Cached session metric",
                    "unit": "percentage",
                    "reasoning": "From cache",
                    "span_id": "",
                    "session_id": ["session_456"],
                    "source": "cache",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {"session_id": "session_456"}
                }
            }
        ]

        # Test cache lookup using _check_session_cache directly
        found, result = self.metric._check_session_cache(cached_session_metrics, "test_session_metric")

        # Verify cache hit
        assert found is True
        assert result is not None
        assert result["metrics"]["value"] == 0.85
        assert result["metrics"]["metadata"]["session_id"] == "session_456"

    def test_session_cache_miss(self):
        """Test cache miss for session-level metric."""
        # Empty cached data
        cached_session_metrics = []

        # Test cache lookup
        found, result = self.metric._check_session_cache(cached_session_metrics, "test_session_metric")

        # Verify cache miss
        assert found is False
        assert result is None

    def test_session_cache_with_wrong_metric_name(self):
        """Test cache miss when metric name doesn't match."""
        cached_metrics = [
            {
                "metrics": {
                    "metric_name": "different_metric",
                    "value": 0.5,
                    "aggregation_level": "session",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Different metric",
                    "unit": "percentage",
                    "reasoning": "Different reasoning",
                    "span_id": "",
                    "session_id": ["session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {"session_id": "session_123"}
                }
            }
        ]

        # Test cache lookup for different metric
        found, result = self.metric._check_session_cache(cached_metrics, "test_session_metric")

        # Verify cache miss due to name mismatch
        assert found is False
        assert result is None

    def test_session_cache_filters_agent_metrics(self):
        """Test that session cache ignores agent-level metrics."""
        mixed_metrics = [
            {
                "metrics": {
                    "metric_name": "test_session_metric",
                    "value": 0.6,
                    "aggregation_level": "session",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Agent metric",
                    "unit": "percentage",
                    "reasoning": "Agent level",
                    "span_id": "",
                    "session_id": ["session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {"agent_id": "agent_1", "session_id": "session_123"}  # Has agent_id
                }
            },
            {
                "metrics": {
                    "metric_name": "test_session_metric",
                    "value": 0.8,
                    "aggregation_level": "session",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Session metric",
                    "unit": "percentage",
                    "reasoning": "Session level",
                    "span_id": "",
                    "session_id": ["session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {"session_id": "session_123"}  # No agent_id - pure session metric
                }
            }
        ]

        # Test cache lookup
        found, result = self.metric._check_session_cache(mixed_metrics, "test_session_metric")

        # Verify it returns the session-only metric (value 0.8), not the agent metric (value 0.6)
        assert found is True
        assert result is not None
        assert result["metrics"]["value"] == 0.8
        assert "agent_id" not in result["metrics"]["metadata"]

    def test_session_cache_with_json_string_metrics(self):
        """Test cache handling when metrics are stored as JSON strings."""
        import json
        cached_metrics = [
            {
                "metrics": json.dumps({
                    "metric_name": "test_session_metric",
                    "value": 0.9,
                    "aggregation_level": "session",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "JSON string metric",
                    "unit": "percentage",
                    "reasoning": "Parsed from JSON",
                    "span_id": "",
                    "session_id": ["session_json"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {"session_id": "session_json"}
                })
            }
        ]

        # Test cache lookup with JSON string
        found, result = self.metric._check_session_cache(cached_metrics, "test_session_metric")

        # Verify JSON parsing works
        assert found is True
        assert result is not None
        # The JSON string gets parsed into the metrics field
        metrics_data = result["metrics"]
        if isinstance(metrics_data, str):
            # JSON was parsed by _check_session_cache
            import json
            metrics_data = json.loads(metrics_data)
        assert metrics_data["value"] == 0.9
        assert metrics_data["metadata"]["session_id"] == "session_json"

    def test_session_cache_with_malformed_json(self):
        """Test cache handling with malformed JSON strings."""
        cached_metrics = [
            {
                "metrics": "invalid json string {"  # Malformed JSON
            },
            {
                "metrics": {
                    "metric_name": "test_session_metric",
                    "value": 0.7,
                    "aggregation_level": "session",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Valid metric",
                    "unit": "percentage",
                    "reasoning": "Valid entry",
                    "span_id": "",
                    "session_id": ["session_valid"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {"session_id": "session_valid"}
                }
            }
        ]

        # Test cache lookup - should skip malformed JSON and return valid entry
        found, result = self.metric._check_session_cache(cached_metrics, "test_session_metric")

        # Verify it finds the valid metric despite malformed JSON
        assert found is True
        assert result is not None
        assert result["metrics"]["value"] == 0.7

    def test_session_cache_adds_missing_default_fields(self):
        """Test that session cache adds default values for missing required fields."""
        cached_metrics = [
            {
                "metrics": {
                    "metric_name": "test_session_metric",
                    "value": 0.5,
                    "aggregation_level": "session",
                    "description": "Compatibility test",
                    "unit": "percentage",
                    "reasoning": "Backward compatibility",
                    "span_id": "",
                    "session_id": ["session_compat"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    # Missing category and app_name - should be added by cache logic
                    "metadata": {"session_id": "session_compat"}
                }
            }
        ]

        # Test cache lookup
        found, result = self.metric._check_session_cache(cached_metrics, "test_session_metric")

        # Verify cache hit and backward compatibility
        assert found is True
        assert result is not None
        assert result["metrics"]["value"] == 0.5
        assert result["metrics"]["metadata"]["session_id"] == "session_compat"