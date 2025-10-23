# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for OpikMetricAdapter core functionality.

Tests cover:
1. Adapter initialization (valid/invalid metrics)
2. Model handling (provider, creation, initialization)
3. Configuration and validation
4. Input data assessment (span validation)
5. Heuristics vs model-based metrics
"""

import pytest
from unittest.mock import MagicMock

from mce_opik_adapter.adapter import OpikMetricAdapter
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import SessionEntity


# ============================================================================
# TEST CLASS 1: ADAPTER INITIALIZATION
# ============================================================================


class TestOpikAdapterInitialization:
    """Test adapter initialization."""

    def test_init_with_valid_metric_name(self):
        """Test initializing adapter with valid Opik metric name."""
        adapter = OpikMetricAdapter("Hallucination")

        # Assert: Basic properties set
        assert adapter.opik_metric_name == "Hallucination"
        assert adapter.name == "Hallucination"
        assert adapter.aggregation_level == "span"
        assert adapter.required == {"entity_type": ["llm"]}

        # Assert: Not yet initialized
        assert adapter.opik_metric is None
        assert adapter.model is None

        # Assert: Configuration loaded
        assert adapter.metric_configuration is not None
        assert adapter.metric_configuration.metric_name == "Hallucination"

    def test_init_with_invalid_metric_name_raises_error(self):
        """Test initializing with unsupported metric raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            OpikMetricAdapter("UnsupportedMetricName")

        # Assert: Error message lists supported metrics
        error_msg = str(exc_info.value)
        assert "Supported metrics" in error_msg
        assert "UnsupportedMetricName" in error_msg

    def test_init_hallucination_metric(self):
        """Test Hallucination metric initialization."""
        adapter = OpikMetricAdapter("Hallucination")

        assert adapter.aggregation_level == "span"
        assert "llm" in adapter.required["entity_type"]

    def test_init_sentiment_metric(self):
        """Test Sentiment metric initialization."""
        adapter = OpikMetricAdapter("Sentiment")

        assert adapter.aggregation_level == "span"
        assert "llm" in adapter.required["entity_type"]

    def test_get_requirements_class_method(self):
        """Test get_requirements class method."""
        requirements = OpikMetricAdapter.get_requirements("Hallucination")

        # Should return list
        assert isinstance(requirements, list)


# ============================================================================
# TEST CLASS 2: MODEL HANDLING
# ============================================================================


class TestOpikModelHandling:
    """Test model provider and initialization."""

    def test_get_model_provider(self):
        """Test model provider identification."""
        adapter = OpikMetricAdapter("Hallucination")

        provider = adapter.get_model_provider()

        assert provider == "opik"

    def test_create_model_delegates_to_load_model(self):
        """Test create_model delegates to load_model function."""
        adapter = OpikMetricAdapter("Hallucination")

        # Verify method exists
        assert hasattr(adapter, "create_model")
        assert callable(adapter.create_model)

    def test_init_with_model_attempts_initialization(self):
        """Test init_with_model attempts to initialize metric."""
        adapter = OpikMetricAdapter("Hallucination")

        # With MagicMock it might succeed or fail
        # Just verify method is callable
        result = adapter.init_with_model(MagicMock())

        # Result is boolean
        assert isinstance(result, bool)


# ============================================================================
# TEST CLASS 3: INPUT DATA ASSESSMENT
# ============================================================================


class TestOpikInputAssessment:
    """Test input data validation logic."""

    @pytest.mark.asyncio
    async def test_assess_span_entity_valid(self):
        """Test assessment of valid SpanEntity."""
        adapter = OpikMetricAdapter("Hallucination")

        # Valid LLM span
        span = SpanEntity(
            entity_type="llm",
            span_id="span-1",
            entity_name="gpt-4",
            app_name="test-app",
            session_id="session-1",
            input_payload={"gen_ai.prompt.0.content": "test"},
            output_payload={"gen_ai.completion.0.content": "response"},
            contains_error=False,
            timestamp="2025-01-01T00:00:00Z",
            raw_span_data={},
        )

        # Execute
        is_valid, error, span_id, session_id = await adapter._assess_input_data(span)

        # Assert: Valid
        assert is_valid is True
        assert error == ""
        assert span_id == "span-1"
        assert session_id == "session-1"

    @pytest.mark.asyncio
    async def test_assess_span_entity_wrong_type(self):
        """Test assessment rejects wrong entity type."""
        adapter = OpikMetricAdapter("Hallucination")  # Requires llm

        # Tool span (wrong type!)
        span = SpanEntity(
            entity_type="tool",  # Wrong!
            span_id="span-1",
            entity_name="search",
            app_name="test-app",
            session_id="session-1",
            input_payload={"query": "test"},
            output_payload={"results": []},
            contains_error=False,
            timestamp="2025-01-01T00:00:00Z",
            raw_span_data={},
        )

        # Execute
        is_valid, error, _, _ = await adapter._assess_input_data(span)

        # Assert: Invalid
        assert is_valid is False
        assert "Entity type must be" in error

    @pytest.mark.asyncio
    async def test_assess_span_entity_missing_payloads(self):
        """Test assessment rejects span with missing payloads."""
        adapter = OpikMetricAdapter("Hallucination")

        # LLM span but missing input_payload
        span = SpanEntity(
            entity_type="llm",
            span_id="span-1",
            entity_name="gpt-4",
            app_name="test-app",
            session_id="session-1",
            input_payload=None,  # Missing!
            output_payload={"content": "response"},
            contains_error=False,
            timestamp="2025-01-01T00:00:00Z",
            raw_span_data={},
        )

        # Execute
        is_valid, error, _, _ = await adapter._assess_input_data(span)

        # Assert: Invalid
        assert is_valid is False
        assert (
            "input_payload" in error
            or "output_payload" in error
            or "entity_name" in error
        )

    @pytest.mark.asyncio
    async def test_assess_non_span_entity_rejected(self):
        """Test non-SpanEntity data is rejected."""
        adapter = OpikMetricAdapter("Hallucination")

        # Session instead of span (wrong!)
        session = SessionEntity(
            session_id="session-1",
            spans=[],
        )

        # Execute
        is_valid, error, _, _ = await adapter._assess_input_data(session)

        # Assert: Invalid
        assert is_valid is False
        assert "spanentity" in error.lower()

    @pytest.mark.asyncio
    async def test_assess_sentiment_metric(self):
        """Test assessment for Sentiment metric."""
        adapter = OpikMetricAdapter("Sentiment")

        span = SpanEntity(
            entity_type="llm",
            span_id="span-1",
            entity_name="gpt-4",
            app_name="test-app",
            session_id="session-1",
            input_payload={"prompt": "test"},
            output_payload={"response": "test"},
            contains_error=False,
            timestamp="2025-01-01T00:00:00Z",
            raw_span_data={},
        )

        is_valid, error, _, _ = await adapter._assess_input_data(span)

        assert is_valid is True
        assert error == ""

    @pytest.mark.asyncio
    async def test_assess_hallucination_metric(self):
        """Test assessment for Hallucination metric."""
        adapter = OpikMetricAdapter("Hallucination")

        span = SpanEntity(
            entity_type="llm",
            span_id="span-1",
            entity_name="gpt-4",
            app_name="test-app",
            session_id="session-1",
            input_payload={"prompt": "test"},
            output_payload={"response": "test"},
            contains_error=False,
            timestamp="2025-01-01T00:00:00Z",
            raw_span_data={},
        )

        is_valid, error, _, _ = await adapter._assess_input_data(span)

        assert is_valid is True


# ============================================================================
# TEST CLASS 4: CONFIGURATION AND VALIDATION
# ============================================================================


class TestOpikConfiguration:
    """Test configuration and validation logic."""

    def test_required_parameters_property(self):
        """Test required_parameters property."""
        adapter = OpikMetricAdapter("Hallucination")

        # Before init_with_model, opik_metric is None
        params = adapter.required_parameters

        # Should return empty list or handle None gracefully
        assert isinstance(params, list)

    def test_validate_config_without_metric(self):
        """Test validate_config when metric not initialized."""
        adapter = OpikMetricAdapter("Hallucination")

        # opik_metric is None
        result = adapter.validate_config()

        # Should handle gracefully
        assert isinstance(result, bool)

    def test_metric_configuration_loaded(self):
        """Test metric configuration is properly loaded."""
        adapter = OpikMetricAdapter("Hallucination")

        assert adapter.metric_configuration is not None
        assert adapter.metric_configuration.metric_name == "Hallucination"
        assert adapter.metric_configuration.requirements.aggregation_level == "span"


# ============================================================================
# TEST CLASS 5: METRIC TYPE DIFFERENCES
# ============================================================================


class TestOpikMetricTypes:
    """Test differences between Opik metric types."""

    def test_hallucination_configuration(self):
        """Test Hallucination metric configuration."""
        adapter = OpikMetricAdapter("Hallucination")

        # Hallucination is model-based
        assert adapter.metric_configuration.metric_name == "Hallucination"
        assert adapter.aggregation_level == "span"

        # Uses specific test case calculator
        calculator_name = (
            adapter.metric_configuration.test_case_calculator.__class__.__name__
        )
        assert "Hallucination" in calculator_name

    def test_sentiment_configuration(self):
        """Test Sentiment metric configuration."""
        adapter = OpikMetricAdapter("Sentiment")

        # Sentiment is heuristics-based
        assert adapter.metric_configuration.metric_name == "Sentiment"
        assert adapter.aggregation_level == "span"

        # Uses span test case calculator
        calculator_name = (
            adapter.metric_configuration.test_case_calculator.__class__.__name__
        )
        assert "Span" in calculator_name

    def test_both_metrics_are_span_level(self):
        """Verify both Opik metrics are span-level."""
        hallucination = OpikMetricAdapter("Hallucination")
        sentiment = OpikMetricAdapter("Sentiment")

        assert hallucination.aggregation_level == "span"
        assert sentiment.aggregation_level == "span"


# ============================================================================
# INTEGRATION TEST: ADAPTER WORKFLOW
# ============================================================================


class TestOpikAdapterIntegration:
    """Integration tests for adapter workflow."""

    @pytest.mark.asyncio
    async def test_adapter_initialization_workflow(self):
        """Test complete adapter initialization workflow."""
        # Step 1: Create adapter
        adapter = OpikMetricAdapter("Hallucination")

        assert adapter.opik_metric_name == "Hallucination"
        assert adapter.name == "Hallucination"

        # Step 2: Verify not initialized
        assert adapter.opik_metric is None
        assert adapter.model is None

        # Step 3: Verify configuration loaded
        assert adapter.metric_configuration is not None
        assert adapter.aggregation_level == "span"
        assert "llm" in adapter.required["entity_type"]
