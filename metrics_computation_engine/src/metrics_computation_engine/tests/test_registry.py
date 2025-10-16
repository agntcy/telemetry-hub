# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive unit tests for MetricRegistry.

Tests cover:
1. Basic registration and retrieval operations
2. Input validation and error handling
3. Multiple metric management
4. Edge cases and state isolation
"""

import pytest

from metrics_computation_engine.registry import MetricRegistry


# ============================================================================
# TEST CLASS 1: BASIC OPERATIONS
# ============================================================================


class TestRegistryBasicOperations:
    """Test core registry operations (register, get, list)."""

    def test_registry_initialization(self):
        """Test registry starts empty and properly initialized."""
        registry = MetricRegistry()

        # Assert: Registry is empty
        assert hasattr(registry, "_metrics")
        assert isinstance(registry._metrics, dict)
        assert len(registry._metrics) == 0

        # Assert: List returns empty
        metrics_list = registry.list_metrics()
        assert isinstance(metrics_list, list)
        assert len(metrics_list) == 0

    def test_register_metric_with_explicit_name(self, mock_span_metric_class):
        """Test registering a metric with an explicit name."""
        registry = MetricRegistry()

        # Execute: Register with explicit name
        registry.register_metric(mock_span_metric_class, "CustomSpanMetric")

        # Assert: Metric is registered
        assert "CustomSpanMetric" in registry.list_metrics()
        assert len(registry.list_metrics()) == 1

        # Assert: Can retrieve the metric
        retrieved = registry.get_metric("CustomSpanMetric")
        assert retrieved is not None
        assert retrieved == mock_span_metric_class

    def test_register_metric_with_auto_name(self, mock_span_metric_class):
        """Test registering a metric with auto-generated name."""
        registry = MetricRegistry()

        # Execute: Register without name (None) - should use __name__
        registry.register_metric(mock_span_metric_class, None)

        # Assert: Metric registered with class name
        expected_name = mock_span_metric_class.__name__
        assert expected_name in registry.list_metrics()

        # Assert: Can retrieve by class name
        retrieved = registry.get_metric(expected_name)
        assert retrieved == mock_span_metric_class

    def test_get_metric_existing(self, mock_session_metric_class):
        """Test retrieving an existing metric."""
        registry = MetricRegistry()
        registry.register_metric(mock_session_metric_class, "TestMetric")

        # Execute: Get existing metric
        result = registry.get_metric("TestMetric")

        # Assert: Returns correct class
        assert result is not None
        assert result == mock_session_metric_class

    def test_get_metric_nonexistent(self):
        """Test retrieving a metric that doesn't exist."""
        registry = MetricRegistry()

        # Execute: Get non-existent metric
        result = registry.get_metric("NonExistentMetric")

        # Assert: Returns None (not an error)
        assert result is None


# ============================================================================
# TEST CLASS 2: VALIDATION
# ============================================================================


class TestRegistryValidation:
    """Test input validation and error handling."""

    def test_register_invalid_metric_raises_error(self, invalid_metric_class):
        """Test that registering a non-BaseMetric class raises ValueError."""
        registry = MetricRegistry()

        # Execute & Assert: Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            registry.register_metric(invalid_metric_class, "InvalidMetric")

        # Assert: Error message mentions BaseMetric
        assert "must inherit from BaseMetric" in str(exc_info.value)

    def test_register_string_instead_of_class(self):
        """Test that registering a string raises appropriate error."""
        registry = MetricRegistry()

        # Execute & Assert: Should raise error
        with pytest.raises((ValueError, TypeError, AttributeError)):
            registry.register_metric("not_a_class", "StringMetric")

    def test_register_dict_instead_of_class(self):
        """Test that registering a dict raises appropriate error."""
        registry = MetricRegistry()

        # Execute & Assert: Should raise error
        with pytest.raises((ValueError, TypeError, AttributeError)):
            registry.register_metric({"not": "a_class"}, "DictMetric")


# ============================================================================
# TEST CLASS 3: MULTIPLE METRICS
# ============================================================================


class TestRegistryMultipleMetrics:
    """Test managing multiple metrics in registry."""

    def test_register_multiple_different_metrics(
        self,
        mock_span_metric_class,
        mock_session_metric_class,
        mock_population_metric_class,
    ):
        """Test registering multiple different metrics."""
        registry = MetricRegistry()

        # Execute: Register 3 different metrics
        registry.register_metric(mock_span_metric_class, "Metric1")
        registry.register_metric(mock_session_metric_class, "Metric2")
        registry.register_metric(mock_population_metric_class, "Metric3")

        # Assert: All appear in list
        metrics_list = registry.list_metrics()
        assert len(metrics_list) == 3
        assert "Metric1" in metrics_list
        assert "Metric2" in metrics_list
        assert "Metric3" in metrics_list

        # Assert: Each can be retrieved individually
        assert registry.get_metric("Metric1") == mock_span_metric_class
        assert registry.get_metric("Metric2") == mock_session_metric_class
        assert registry.get_metric("Metric3") == mock_population_metric_class

    def test_register_same_name_twice_overwrites(
        self, mock_span_metric_class, mock_session_metric_class
    ):
        """Test that registering the same name twice overwrites the first."""
        registry = MetricRegistry()

        # Execute: Register metric "TestMetric" twice
        registry.register_metric(mock_span_metric_class, "TestMetric")
        registry.register_metric(mock_session_metric_class, "TestMetric")

        # Assert: Second registration overwrites first
        result = registry.get_metric("TestMetric")
        assert result == mock_session_metric_class  # Second one
        assert result != mock_span_metric_class  # Not first one

        # Assert: Only one entry in list
        metrics_list = registry.list_metrics()
        assert len(metrics_list) == 1
        assert metrics_list.count("TestMetric") == 1

    def test_list_metrics_returns_all(
        self,
        mock_span_metric_class,
        mock_session_metric_class,
        mock_population_metric_class,
    ):
        """Test list_metrics returns all registered metrics."""
        registry = MetricRegistry()

        # Register 5 metrics with different names
        metrics_to_register = [
            (mock_span_metric_class, "MetricA"),
            (mock_session_metric_class, "MetricB"),
            (mock_population_metric_class, "MetricC"),
            (mock_span_metric_class, "MetricD"),
            (mock_session_metric_class, "MetricE"),
        ]

        for metric_class, name in metrics_to_register:
            registry.register_metric(metric_class, name)

        # Execute: Get list
        metrics_list = registry.list_metrics()

        # Assert: All 5 present
        assert len(metrics_list) == 5

        # Assert: No duplicates
        assert len(set(metrics_list)) == 5

        # Assert: All expected names present
        for _, name in metrics_to_register:
            assert name in metrics_list

    def test_mixed_explicit_and_auto_names(
        self, mock_span_metric_class, mock_session_metric_class
    ):
        """Test mixing explicit names and auto-generated names."""
        registry = MetricRegistry()

        # Execute: Register with mixed naming
        registry.register_metric(mock_span_metric_class, "ExplicitName")  # Explicit
        registry.register_metric(mock_session_metric_class, None)  # Auto

        # Assert: Both registered
        metrics_list = registry.list_metrics()
        assert len(metrics_list) == 2
        assert "ExplicitName" in metrics_list
        assert mock_session_metric_class.__name__ in metrics_list

        # Assert: Both retrievable
        assert registry.get_metric("ExplicitName") is not None
        assert registry.get_metric(mock_session_metric_class.__name__) is not None


# ============================================================================
# TEST CLASS 4: EDGE CASES
# ============================================================================


class TestRegistryEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_registry_operations(self):
        """Test operations on empty registry don't cause errors."""
        registry = MetricRegistry()

        # Execute operations on empty registry
        metrics_list = registry.list_metrics()
        result = registry.get_metric("AnyName")

        # Assert: No errors, proper null values
        assert metrics_list == []
        assert result is None

    def test_special_characters_in_name(self, mock_span_metric_class):
        """Test metric names with special characters."""
        registry = MetricRegistry()

        # Execute: Register with special characters
        special_names = [
            "metric.with.dots",
            "metric-with-dashes",
            "metric_with_underscores",
            "MetricWithCamelCase",
            "metric123",
        ]

        for name in special_names:
            registry.register_metric(mock_span_metric_class, name)

        # Assert: All stored and retrievable
        metrics_list = registry.list_metrics()
        assert len(metrics_list) == len(special_names)

        for name in special_names:
            assert name in metrics_list
            assert registry.get_metric(name) is not None

    def test_registry_state_isolation(
        self, mock_span_metric_class, mock_session_metric_class
    ):
        """Test that separate registry instances are isolated."""
        # Create two separate registries
        registry1 = MetricRegistry()
        registry2 = MetricRegistry()

        # Execute: Register different metrics in each
        registry1.register_metric(mock_span_metric_class, "Metric1")
        registry2.register_metric(mock_session_metric_class, "Metric2")

        # Assert: No cross-contamination
        assert "Metric1" in registry1.list_metrics()
        assert "Metric1" not in registry2.list_metrics()

        assert "Metric2" in registry2.list_metrics()
        assert "Metric2" not in registry1.list_metrics()

        assert len(registry1.list_metrics()) == 1
        assert len(registry2.list_metrics()) == 1


# ============================================================================
# INTEGRATION TEST: FULL REGISTRY WORKFLOW
# ============================================================================


class TestRegistryIntegration:
    """Integration tests for complete registry workflows."""

    def test_full_registry_workflow(
        self,
        mock_span_metric_class,
        mock_session_metric_class,
        mock_population_metric_class,
    ):
        """Test complete workflow: register, list, retrieve, overwrite."""
        registry = MetricRegistry()

        # Step 1: Start empty
        assert len(registry.list_metrics()) == 0

        # Step 2: Register metrics
        registry.register_metric(mock_span_metric_class, "SpanMetric")
        registry.register_metric(mock_session_metric_class, "SessionMetric")

        # Step 3: Verify registration
        assert len(registry.list_metrics()) == 2
        assert registry.get_metric("SpanMetric") == mock_span_metric_class
        assert registry.get_metric("SessionMetric") == mock_session_metric_class

        # Step 4: Add more
        registry.register_metric(mock_population_metric_class, "PopMetric")
        assert len(registry.list_metrics()) == 3

        # Step 5: Overwrite existing
        registry.register_metric(mock_population_metric_class, "SpanMetric")
        assert len(registry.list_metrics()) == 3  # Still 3, not 4
        assert (
            registry.get_metric("SpanMetric") == mock_population_metric_class
        )  # Overwritten

        # Step 6: Get non-existent
        assert registry.get_metric("NonExistent") is None

        # Step 7: List contains all current
        final_list = registry.list_metrics()
        assert "SpanMetric" in final_list
        assert "SessionMetric" in final_list
        assert "PopMetric" in final_list

    def test_registry_with_processor_pattern(
        self, mock_span_metric_class, mock_session_metric_class
    ):
        """Test registry usage pattern similar to how processor uses it."""
        # This simulates the common pattern in processor.py
        registry = MetricRegistry()

        # Step 1: Register multiple metrics (like in main.py)
        metrics_to_register = [
            (mock_span_metric_class, "Metric1"),
            (mock_session_metric_class, "Metric2"),
        ]

        for metric_class, name in metrics_to_register:
            registry.register_metric(metric_class, name)

        # Step 2: List all metrics (like processor does)
        all_metrics = registry.list_metrics()
        assert len(all_metrics) == 2

        # Step 3: Get each metric by name (like processor does)
        for metric_name in all_metrics:
            metric_class = registry.get_metric(metric_name)
            assert metric_class is not None

            # Verify it's a valid metric class
            from metrics_computation_engine.metrics.base import BaseMetric

            assert issubclass(metric_class, BaseMetric)
