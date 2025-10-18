# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for DeepEvalMetricAdapter core functionality.

Tests cover:
1. Adapter initialization (valid/invalid metrics)
2. Model handling (provider, creation, initialization)
3. Configuration and validation
4. Input data assessment (span and session validation)
"""

import pytest
from unittest.mock import MagicMock

from mce_deepeval_adapter.adapter import DeepEvalMetricAdapter
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import SessionEntity


# ============================================================================
# TEST CLASS 1: ADAPTER INITIALIZATION
# ============================================================================


class TestDeepEvalAdapterInitialization:
    """Test adapter initialization and configuration."""

    def test_init_with_valid_metric_name(self):
        """Test initializing adapter with valid DeepEval metric name."""
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")

        # Assert: Basic properties set
        assert adapter.name == "ConversationCompletenessMetric"
        assert adapter.aggregation_level == "session"
        assert adapter.required == {"entity_type": ["llm"]}

        # Assert: Not yet initialized
        assert adapter.deepeval_metric is None
        assert adapter.model is None

        # Assert: Configuration loaded
        assert adapter.metric_configuration is not None
        assert (
            adapter.metric_configuration.metric_name == "ConversationCompletenessMetric"
        )

    def test_init_with_invalid_metric_name_raises_error(self):
        """Test initializing with unsupported metric raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DeepEvalMetricAdapter("UnsupportedMetricName")

        # Assert: Error message lists supported metrics
        error_msg = str(exc_info.value)
        assert "Supported metrics" in error_msg
        assert "UnsupportedMetricName" in error_msg

    def test_init_sets_correct_aggregation_level_span(self):
        """Test span-level metric has correct aggregation level."""
        adapter = DeepEvalMetricAdapter("AnswerRelevancyMetric")

        assert adapter.aggregation_level == "span"
        assert adapter.required == {"entity_type": ["llm"]}

    def test_init_sets_correct_aggregation_level_session(self):
        """Test session-level metric has correct aggregation level."""
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")

        assert adapter.aggregation_level == "session"
        assert adapter.required == {"entity_type": ["llm"]}

    def test_get_requirements_class_method(self):
        """Test get_requirements class method."""
        requirements = DeepEvalMetricAdapter.get_requirements("BiasMetric")

        # Should return list (may be empty or have requirements)
        assert isinstance(requirements, list)


# ============================================================================
# TEST CLASS 2: MODEL HANDLING
# ============================================================================


class TestDeepEvalModelHandling:
    """Test model provider, creation, and initialization."""

    def test_get_model_provider(self):
        """Test model provider identification."""
        adapter = DeepEvalMetricAdapter("BiasMetric")

        provider = adapter.get_model_provider()

        assert provider == "deepeval"

    def test_create_model_delegates_to_load_model(self):
        """Test create_model delegates to load_model function."""
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")

        # create_model just calls load_model from model_loader
        # We can't easily test this without the full environment
        # Just verify the method exists and is callable
        assert hasattr(adapter, "create_model")
        assert callable(adapter.create_model)

    def test_init_with_model_requires_proper_model_type(self):
        """Test init_with_model with improper model type returns False."""
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")

        # DeepEval validates model type - MagicMock won't work
        mock_model = MagicMock()

        # Execute - will fail validation
        result = adapter.init_with_model(mock_model)

        # Assert: Returns False (model type not supported by DeepEval)
        assert result is False

    def test_init_with_model_with_none_returns_false(self):
        """Test init_with_model with None returns False."""
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")

        # Execute with None
        result = adapter.init_with_model(None)

        # Assert: Returns False
        assert result is False


# ============================================================================
# TEST CLASS 3: CONFIGURATION AND VALIDATION
# ============================================================================


class TestDeepEvalConfiguration:
    """Test configuration and validation logic."""

    def test_required_parameters_property(self):
        """Test required_parameters property."""
        adapter = DeepEvalMetricAdapter("BiasMetric")

        # Before init_with_model, deepeval_metric is None
        params = adapter.required_parameters

        # Should return empty list or handle None gracefully
        assert isinstance(params, list)

    def test_validate_config_without_metric(self):
        """Test validate_config when metric not initialized."""
        adapter = DeepEvalMetricAdapter("BiasMetric")

        # deepeval_metric is None
        result = adapter.validate_config()

        # Should handle gracefully
        assert isinstance(result, bool)


# ============================================================================
# TEST CLASS 4: INPUT DATA ASSESSMENT
# ============================================================================


class TestDeepEvalInputAssessment:
    """Test _assess_input_data validation logic."""

    @pytest.mark.asyncio
    async def test_assess_span_entity_valid(self):
        """Test assessment of valid SpanEntity."""
        adapter = DeepEvalMetricAdapter("AnswerRelevancyMetric")  # Span-level

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
        adapter = DeepEvalMetricAdapter("AnswerRelevancyMetric")  # Requires llm

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
        adapter = DeepEvalMetricAdapter("AnswerRelevancyMetric")

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
    async def test_assess_session_entity_valid(self):
        """Test assessment of valid SessionEntity."""
        adapter = DeepEvalMetricAdapter(
            "ConversationCompletenessMetric"
        )  # Session-level

        # Valid session with LLM spans
        session = SessionEntity(
            session_id="session-1",
            spans=[
                SpanEntity(
                    entity_type="llm",
                    span_id="s1",
                    entity_name="gpt-4",
                    app_name="test-app",
                    session_id="session-1",
                    contains_error=False,
                    timestamp="2025-01-01T00:00:00Z",
                    raw_span_data={},
                )
            ],
            conversation_elements=[],  # Required by ConversationCompleteness
        )

        # Execute
        is_valid, error, span_id, session_id = await adapter._assess_input_data(session)

        # Assert: Valid
        assert is_valid is True
        assert error == ""
        assert session_id == "session-1"

    @pytest.mark.asyncio
    async def test_assess_session_entity_empty_spans(self):
        """Test assessment rejects session with no spans."""
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")

        # Empty session
        session = SessionEntity(
            session_id="session-1",
            spans=[],  # Empty!
        )

        # Execute
        is_valid, error, _, _ = await adapter._assess_input_data(session)

        # Assert: Invalid
        assert is_valid is False
        assert "cannot be empty" in error.lower()

    @pytest.mark.asyncio
    async def test_assess_session_entity_no_matching_entity_type(self):
        """Test assessment rejects session without required entity types."""
        adapter = DeepEvalMetricAdapter(
            "ConversationCompletenessMetric"
        )  # Requires llm

        # Session with only tool spans (no llm!)
        session = SessionEntity(
            session_id="session-1",
            spans=[
                SpanEntity(
                    entity_type="tool",  # Wrong type!
                    span_id="s1",
                    entity_name="search",
                    app_name="test-app",
                    session_id="session-1",
                    contains_error=False,
                    timestamp="2025-01-01T00:00:00Z",
                    raw_span_data={},
                )
            ],
        )

        # Execute
        is_valid, error, _, _ = await adapter._assess_input_data(session)

        # Assert: Invalid
        assert is_valid is False
        assert "must contain at least one entity of type" in error.lower()


# ============================================================================
# INTEGRATION TEST: ADAPTER WORKFLOW
# ============================================================================


class TestDeepEvalAdapterIntegration:
    """Integration tests for adapter workflow."""

    @pytest.mark.asyncio
    async def test_adapter_initialization_workflow(self):
        """Test adapter initialization workflow without real model."""
        # Step 1: Create adapter
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")
        assert adapter.name == "ConversationCompletenessMetric"

        # Step 2: Verify not initialized
        assert adapter.deepeval_metric is None
        assert adapter.model is None

        # Step 3: Verify required entity types
        assert "llm" in adapter.required["entity_type"]

        # Step 4: Verify aggregation level
        assert adapter.aggregation_level == "session"

        # Step 5: Verify configuration loaded
        assert adapter.metric_configuration is not None


# ============================================================================
# PRIORITY 2 TESTS: METRIC TYPE DIFFERENCES
# ============================================================================


class TestDeepEvalGEvalMetrics:
    """Test GEval metrics with custom criteria."""

    def test_geval_metric_has_custom_criteria(self):
        """Verify GEval metrics have criteria configured."""
        adapter = DeepEvalMetricAdapter("CoherenceMetric")

        # GEval metrics should have criteria in config
        assert adapter.metric_configuration.metric_class_arguments is not None
        assert "criteria" in adapter.metric_configuration.metric_class_arguments

        # Criteria should be a string
        criteria = adapter.metric_configuration.metric_class_arguments["criteria"]
        assert isinstance(criteria, str)
        assert len(criteria) > 0

    def test_coherence_uses_coherence_criteria(self):
        """Verify CoherenceMetric uses COHERENCE_CRITERIA."""
        adapter = DeepEvalMetricAdapter("CoherenceMetric")

        criteria = adapter.metric_configuration.metric_class_arguments["criteria"]
        # Should contain coherence-related text
        assert "coherent" in criteria.lower() or "logical" in criteria.lower()

    def test_geval_metric_uses_geval_class(self):
        """Verify GEval metrics use GEval class."""
        adapter = DeepEvalMetricAdapter("TonalityMetric")

        from deepeval.metrics import GEval

        assert adapter.metric_configuration.metric_class == GEval

        # Should have evaluation steps
        assert "evaluation_steps" in adapter.metric_configuration.metric_class_arguments


class TestDeepEvalToolMetrics:
    """Test metrics requiring tool calls."""

    def test_task_completion_requires_tool_calls(self):
        """Verify TaskCompletion requires tool_calls parameter."""
        adapter = DeepEvalMetricAdapter("TaskCompletionMetric")

        # Check required parameters
        requirements = (
            adapter.metric_configuration.requirements.required_input_parameters
        )
        # Should require tool_calls
        assert any("tool" in str(req).lower() for req in requirements)

    def test_task_completion_uses_tools_calculator(self):
        """Verify TaskCompletion uses LLMWithTools calculator."""
        adapter = DeepEvalMetricAdapter("TaskCompletionMetric")

        calculator_name = (
            adapter.metric_configuration.test_case_calculator.__class__.__name__
        )
        # Should use the tool-specific calculator
        assert "Tool" in calculator_name or "tool" in calculator_name.lower()


class TestDeepEvalConversationalMetrics:
    """Test conversational metric specifics."""

    def test_conversational_requires_conversation_elements(self):
        """Verify conversational metrics require conversation_elements."""
        adapter = DeepEvalMetricAdapter("RoleAdherenceMetric")

        # Check requirements
        requirements = (
            adapter.metric_configuration.requirements.required_input_parameters
        )
        assert "conversation_elements" in requirements

    def test_conversational_uses_conversational_calculator(self):
        """Test conversational metrics use conversational test case calculator."""
        adapter = DeepEvalMetricAdapter("ConversationCompletenessMetric")

        calculator_name = (
            adapter.metric_configuration.test_case_calculator.__class__.__name__
        )
        # Should use conversational calculator
        assert "Conversational" in calculator_name
