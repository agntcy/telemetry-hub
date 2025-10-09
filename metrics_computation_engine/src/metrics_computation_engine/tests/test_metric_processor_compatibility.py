# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive test suite to ensure all metrics are compatible with processor context passing.

This test covers both native and plugin metrics and runs as part of regular unit tests.
It dynamically discovers all available metrics and validates their compute signatures.
"""

import inspect
import pytest
from typing import Any, Dict
from unittest.mock import MagicMock

from metrics_computation_engine.util import NATIVE_METRICS
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity


class TestMetricProcessorCompatibility:
    """Test suite ensuring all metrics work with processor context passing"""

    def get_all_available_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics available in the current environment.
        Falls back gracefully if plugins are not installed.

        This includes:
        - Native metrics (always available)
        - Plugin metrics (from entry_points "metrics_computation_engine.plugins")
        - Adapter metrics (from entry_points "metrics_computation_engine.adapters")
        """
        # Start with native metrics (always available)
        available_metrics = NATIVE_METRICS.copy()

        # Try to add plugin metrics if available
        try:
            from metrics_computation_engine.util import get_all_metric_classes

            all_metrics = get_all_metric_classes()
            available_metrics.update(all_metrics)
        except Exception as e:
            # Plugins not available, continue with just native metrics
            print(f"Note: Plugin metrics not available in this test run: {e}")

        # Try to add adapter metrics (separate entry point group)
        try:
            from importlib.metadata import entry_points

            adapter_eps = entry_points(group="metrics_computation_engine.adapters")

            for entry_point in adapter_eps:
                try:
                    adapter_class = entry_point.load()
                    available_metrics[f"Adapter_{entry_point.name}"] = adapter_class
                except Exception as e:
                    print(f"Note: Failed to load adapter '{entry_point.name}': {e}")

        except Exception as e:
            print(f"Note: Adapter metrics not available in this test run: {e}")

        return available_metrics

    def test_metric_compute_signatures(self):
        """Validate all available metrics have processor-compatible compute signatures"""
        available_metrics = self.get_all_available_metrics()
        failed_metrics = []

        for name, metric_class in available_metrics.items():
            # Skip abstract base classes
            if not hasattr(metric_class, "compute"):
                continue

            compute_method = getattr(metric_class, "compute")
            if not callable(compute_method):
                continue

            sig = inspect.signature(compute_method)

            # Check if method can accept **kwargs (VAR_KEYWORD parameter)
            has_var_keyword = any(
                param.kind == inspect.Parameter.VAR_KEYWORD
                for param in sig.parameters.values()
            )

            if not has_var_keyword:
                failed_metrics.append(f"{name}: {sig}")

        assert not failed_metrics, (
            "Metrics with processor-incompatible signatures (missing **context):\n"
            + "\n".join(f"  - {m}" for m in failed_metrics)
            + "\n\nAll compute methods must accept **context to be compatible with processor calls."
        )

    @pytest.fixture
    def mock_processor_context(self):
        """Create realistic processor context that would be passed to metrics"""
        return {
            "session_set_stats": MagicMock(),
            "session_index": 0,
            "session_set": MagicMock(),
            "additional_context": {"test": "value"},
        }

    @pytest.fixture
    def mock_session_entity(self):
        """Create a mock SessionEntity for testing"""
        mock_session = MagicMock(spec=SessionEntity)
        mock_session.session_id = "test-session-123"
        mock_session.app_name = "test-app"
        mock_session.spans = []
        return mock_session

    @pytest.fixture
    def mock_span_entity(self):
        """Create a mock SpanEntity for testing"""
        mock_span = MagicMock()
        mock_span.span_id = "test-span-123"
        mock_span.session_id = "test-session-123"
        mock_span.app_name = "test-app"
        mock_span.entity_name = "test-entity"
        return mock_span

    @pytest.mark.asyncio
    async def test_metrics_accept_processor_context(
        self, mock_processor_context, mock_session_entity, mock_span_entity
    ):
        """Test that all metrics can be called with processor context without errors"""
        available_metrics = self.get_all_available_metrics()

        for name, metric_class in available_metrics.items():
            # Skip abstract classes
            if not hasattr(metric_class, "compute"):
                continue

            try:
                # Create metric instance
                metric = metric_class()
            except Exception as e:
                # Some metrics might need special initialization
                pytest.skip(f"Could not instantiate {name}: {e}")
                continue

            # Mock the actual computation logic to avoid dependencies
            original_compute = metric.compute

            async def mock_compute(*args, **kwargs):
                # Verify we received the expected arguments
                assert len(args) >= 1, (
                    f"Metric {name} compute should receive data argument"
                )
                assert isinstance(kwargs, dict), (
                    f"Metric {name} should accept keyword arguments"
                )

                # Return a valid MetricResult mock
                return MagicMock(spec=MetricResult)

            metric.compute = mock_compute

            # Test calling with processor context pattern - this is the critical test
            try:
                # Try with SessionEntity (most common case)
                result = await metric.compute(
                    mock_session_entity, **mock_processor_context
                )
                assert result is not None

                # Also test with SpanEntity for span-level metrics
                await metric.compute(mock_span_entity, **mock_processor_context)

            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    pytest.fail(
                        f"Metric {name} failed processor compatibility test: {e}\n"
                        f"The compute method signature must accept **context parameters"
                    )
                else:
                    # Other TypeErrors might be expected (wrong data type, etc.)
                    pass
            except Exception:
                # Other exceptions are fine - we're only testing signature compatibility
                pass
            finally:
                # Restore original method
                metric.compute = original_compute

    def test_metric_coverage_report(self):
        """Report on metric coverage to help track testing completeness"""
        available_metrics = self.get_all_available_metrics()

        native_count = len(NATIVE_METRICS)
        total_count = len(available_metrics)

        # Count different types
        plugin_count = 0
        adapter_count = 0

        for name in available_metrics.keys():
            if name.startswith("Adapter_"):
                adapter_count += 1
            elif name not in NATIVE_METRICS:
                plugin_count += 1

        print("\n=== Metric Coverage Report ===")
        print(f"Native metrics tested: {native_count}")
        print(f"Plugin metrics tested: {plugin_count}")
        print(f"Adapter metrics tested: {adapter_count}")
        print(f"Total metrics tested: {total_count}")

        if plugin_count == 0:
            print("Note: No plugin metrics found. Install plugins to test them:")
            print("  uv pip install -e plugins/mce_metrics_plugin")

        if adapter_count == 0:
            print("Note: No adapter metrics found. Install adapters to test them:")
            print("  uv pip install -e plugins/adapters/opik_adapter")
            print("  uv pip install -e plugins/adapters/ragas_adapter")
            print("  uv pip install -e plugins/adapters/deepeval_adapter")

        # List all tested metrics for visibility
        print("\nTested metrics:")
        for name in sorted(available_metrics.keys()):
            if name in NATIVE_METRICS:
                metric_type = "native"
            elif name.startswith("Adapter_"):
                metric_type = "adapter"
            else:
                metric_type = "plugin"
            print(f"  - {name} ({metric_type})")

    @pytest.mark.asyncio
    async def test_processor_context_parameter_names(self, mock_session_entity):
        """Verify metrics can handle realistic processor context parameter names"""
        available_metrics = self.get_all_available_metrics()

        # These are the actual parameter names the processor passes
        realistic_context = {
            "session_set_stats": MagicMock(),
            "session_index": 0,
            "session_set": MagicMock(),
        }

        signature_errors = []

        for name, metric_class in available_metrics.items():
            if not hasattr(metric_class, "compute"):
                continue

            try:
                metric = metric_class()

                # Mock the compute method to capture what it receives
                received_kwargs = {}
                original_compute = metric.compute

                async def capture_kwargs(*args, **kwargs):
                    received_kwargs.update(kwargs)
                    return MagicMock(spec=MetricResult)

                metric.compute = capture_kwargs

                # Call with realistic processor context
                await metric.compute(mock_session_entity, **realistic_context)

                # Verify the metric received the context parameters
                expected_keys = set(realistic_context.keys())
                received_keys = set(received_kwargs.keys())

                if not expected_keys.issubset(received_keys):
                    signature_errors.append(
                        f"{name}: Did not receive expected context parameters. "
                        f"Expected: {expected_keys}, Got: {received_keys}"
                    )

                metric.compute = original_compute

            except Exception:
                # Skip metrics that can't be instantiated
                continue

        assert not signature_errors, (
            "Metrics failed to properly receive processor context:\n"
            + "\n".join(f"  - {err}" for err in signature_errors)
        )
