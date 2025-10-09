"""
Simple test for agent cache functionality.
Tests the core cache methods we implemented.
"""

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity


class TestCacheMetric(BaseMetric):
    """Minimal test metric for testing cache methods."""

    def __init__(self):
        self.name = "test_cache_metric"
        self.aggregation_level = "session"

    # Required abstract method implementations
    async def compute(self, session: SessionEntity, **context):
        return MetricResult(
            metric_name=self.name,
            value=0.5,
            aggregation_level="session",
            category="application",
            app_name="test",
            description="test",
            unit="test",
            reasoning="test",
            span_id="",
            session_id=[session.session_id],
            source="test",
            entities_involved=[],
            edges_involved=[],
            success=True,
            metadata={"session_id": session.session_id},
        )

    def create_model(self):
        return None

    def get_model_provider(self):
        return "test"

    def init_with_model(self, model):
        pass

    def required_parameters(self):
        return []

    def validate_config(self, config):
        return True


class TestAgentCacheFunctionality:
    """Test class for agent cache functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metric = TestCacheMetric()

    def test_check_session_cache_filters_agent_results(self):
        """Test that _check_session_cache filters out agent-level metrics."""
        # Mock cached data with mix of session and agent metrics
        cached_metrics = [
            {
                "metrics": {
                    "metric_name": "test_cache_metric",
                    "aggregation_level": "session",
                    "metadata": {"session_id": "test_session_123"},
                }
            },
            {
                "metrics": {
                    "metric_name": "test_cache_metric",
                    "aggregation_level": "session",
                    "metadata": {
                        "agent_id": "agent_1",
                        "session_id": "test_session_123",
                    },
                }
            },
        ]

        # Test - should only return the session metric without agent_id
        found, result = self.metric._check_session_cache(
            cached_metrics, "test_cache_metric"
        )

        assert found is True
        assert result["metrics"]["metadata"].get("agent_id") is None
        assert result["metrics"]["metadata"]["session_id"] == "test_session_123"

    def test_check_all_agents_cache_returns_agent_results(self):
        """Test that _check_all_agents_cache returns agent results."""
        # Mock cached data with agent metrics
        cached_metrics = [
            {
                "metrics": {
                    "metric_name": "test_cache_metric",
                    "value": 0.1,
                    "aggregation_level": "agent",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Test metric",
                    "unit": "percentage",
                    "reasoning": "Test reasoning",
                    "span_id": "",
                    "session_id": ["test_session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {
                        "agent_id": "agent_1",
                        "session_id": "test_session_123",
                    },
                }
            },
            {
                "metrics": {
                    "metric_name": "test_cache_metric",
                    "value": 0.2,
                    "aggregation_level": "agent",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Test metric",
                    "unit": "percentage",
                    "reasoning": "Test reasoning",
                    "span_id": "",
                    "session_id": ["test_session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {
                        "agent_id": "agent_2",
                        "session_id": "test_session_123",
                    },
                }
            },
        ]

        # Test - should return agent results for the metric
        results = self.metric._check_all_agents_cache(
            cached_metrics, "test_cache_metric"
        )

        assert results is not None
        assert len(results) == 2  # Both agent results
        for result in results:
            assert result.metric_name == "test_cache_metric"
            assert result.metadata["agent_id"] in ["agent_1", "agent_2"]

    def test_check_all_agents_cache_empty_returns_none(self):
        """Test that empty agent list returns None."""
        cached_metrics = []
        results = self.metric._check_all_agents_cache(
            cached_metrics, "test_cache_metric"
        )
        assert results is None

    def test_check_session_cache_no_match(self):
        """Test session cache when no matching metric found."""
        cached_metrics = [
            {
                "metrics": {
                    "metric_name": "other_metric",
                    "aggregation_level": "session",
                    "metadata": {"session_id": "test_session_123"},
                }
            }
        ]

        found, result = self.metric._check_session_cache(
            cached_metrics, "test_cache_metric"
        )
        assert found is False
        assert result is None

    def test_check_agent_cache_specific_agent(self):
        """Test that _check_agent_cache returns result for specific agent."""
        # Mock cached data with specific agent metric
        cached_metrics = [
            {
                "metrics": {
                    "metric_name": "test_cache_metric",
                    "value": 0.1,
                    "aggregation_level": "agent",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Test metric",
                    "unit": "percentage",
                    "reasoning": "Test reasoning",
                    "span_id": "",
                    "session_id": ["test_session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {
                        "agent_id": "agent_1",
                        "session_id": "test_session_123",
                    },
                }
            },
            {
                "metrics": {
                    "metric_name": "test_cache_metric",
                    "value": 0.2,
                    "aggregation_level": "agent",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Test metric",
                    "unit": "percentage",
                    "reasoning": "Test reasoning",
                    "span_id": "",
                    "session_id": ["test_session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {
                        "agent_id": "agent_2",
                        "session_id": "test_session_123",
                    },
                }
            },
        ]

        # Test - should return specific agent result
        result = self.metric._check_agent_cache(
            cached_metrics, "test_cache_metric", "agent_1"
        )

        assert result is not None
        assert result.metric_name == "test_cache_metric"
        assert result.metadata["agent_id"] == "agent_1"
        assert result.value == 0.1

    def test_check_agent_cache_no_match(self):
        """Test that _check_agent_cache returns None for non-existent agent."""
        cached_metrics = [
            {
                "metrics": {
                    "metric_name": "test_cache_metric",
                    "value": 0.1,
                    "aggregation_level": "agent",
                    "category": "application",
                    "app_name": "test_app",
                    "description": "Test metric",
                    "unit": "percentage",
                    "reasoning": "Test reasoning",
                    "span_id": "",
                    "session_id": ["test_session_123"],
                    "source": "test",
                    "entities_involved": [],
                    "edges_involved": [],
                    "success": True,
                    "metadata": {
                        "agent_id": "agent_1",
                        "session_id": "test_session_123",
                    },
                }
            }
        ]

        # Test - should return None for non-existent agent
        result = self.metric._check_agent_cache(
            cached_metrics, "test_cache_metric", "agent_999"
        )
        assert result is None

    def test_agent_view_caching(self):
        """Test that SessionEntity caches AgentView instances for efficient reuse."""
        from metrics_computation_engine.entities.models.session import SessionEntity

        # Create session with spans
        session = SessionEntity(session_id="test_session", spans=[])

        # First call should create and cache the agent view
        agent_view_1 = session.get_agent_view("agent_1")
        assert agent_view_1 is not None

        # Second call should return the same cached instance
        agent_view_2 = session.get_agent_view("agent_1")
        assert agent_view_1 is agent_view_2  # Same object reference

        # Different agent should get different view
        agent_view_different = session.get_agent_view("agent_2")
        assert agent_view_different is not agent_view_1

        # Verify cache structure exists
        assert hasattr(session, "_agent_views")
        assert "agent_1" in session._agent_views
        assert "agent_2" in session._agent_views
