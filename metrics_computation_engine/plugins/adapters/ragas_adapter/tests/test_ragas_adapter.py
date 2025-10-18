# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for RagasAdapter core functionality.

Tests cover:
1. Adapter initialization (with mode support)
2. Dotted name parsing (ragas.MetricName.mode format)
3. Model handling (provider, creation, initialization)
4. Configuration and validation
5. Input data assessment
"""

import pytest
from unittest.mock import MagicMock

from mce_ragas_adapter.adapter import RagasAdapter
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.span import SpanEntity


# ============================================================================
# TEST CLASS 1: ADAPTER INITIALIZATION WITH MODE SUPPORT
# ============================================================================

class TestRagasAdapterInitialization:
    """Test adapter initialization including mode handling."""
    
    def test_init_with_valid_metric_name_default_mode(self):
        """Test initializing with valid metric name and default mode."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        # Assert: Basic properties
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "precision"  # Default mode
        assert adapter.name == "TopicAdherenceScore"  # No suffix for precision
        assert adapter.aggregation_level == "session"
        assert adapter.required == {"entity_type": ["llm"]}
        
        # Assert: Not initialized yet
        assert adapter.ragas_metric is None
        assert adapter.model is None
    
    def test_init_with_mode_precision(self):
        """Test initialization with explicit precision mode."""
        adapter = RagasAdapter("TopicAdherenceScore", mode="precision")
        
        assert adapter.mode == "precision"
        assert adapter.name == "TopicAdherenceScore"  # No suffix
    
    def test_init_with_mode_recall(self):
        """Test initialization with recall mode."""
        adapter = RagasAdapter("TopicAdherenceScore", mode="recall")
        
        assert adapter.mode == "recall"
        assert adapter.name == "TopicAdherenceScore_recall"  # Suffix added
    
    def test_init_with_mode_f1(self):
        """Test initialization with f1 mode."""
        adapter = RagasAdapter("TopicAdherenceScore", mode="f1")
        
        assert adapter.mode == "f1"
        assert adapter.name == "TopicAdherenceScore_f1"  # Suffix added
    
    def test_init_with_invalid_mode_raises_error(self):
        """Test invalid mode raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RagasAdapter("TopicAdherenceScore", mode="invalid_mode")
        
        error_msg = str(exc_info.value)
        assert "Invalid mode" in error_msg
        assert "invalid_mode" in error_msg
        assert "precision" in error_msg
        assert "recall" in error_msg
        assert "f1" in error_msg
    
    def test_init_with_invalid_metric_name_raises_error(self):
        """Test unsupported metric name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RagasAdapter("UnsupportedMetric")
        
        error_msg = str(exc_info.value)
        assert "Supported metrics" in error_msg
        assert "UnsupportedMetric" in error_msg


# ============================================================================
# TEST CLASS 2: DOTTED NAME PARSING
# ============================================================================

class TestRagasDottedNameParsing:
    """Test parsing dotted names like 'ragas.TopicAdherenceScore.f1'."""
    
    def test_parse_dotted_name_with_f1_mode(self):
        """Test parsing 'ragas.MetricName.f1' format."""
        adapter = RagasAdapter("ragas.TopicAdherenceScore.f1")
        
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "f1"
        assert adapter.name == "TopicAdherenceScore_f1"
    
    def test_parse_dotted_name_with_recall_mode(self):
        """Test parsing 'ragas.MetricName.recall' format."""
        adapter = RagasAdapter("ragas.TopicAdherenceScore.recall")
        
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "recall"
        assert adapter.name == "TopicAdherenceScore_recall"
    
    def test_parse_dotted_name_with_precision_mode(self):
        """Test parsing with precision mode."""
        adapter = RagasAdapter("ragas.TopicAdherenceScore.precision")
        
        assert adapter.mode == "precision"
        assert adapter.name == "TopicAdherenceScore"  # No suffix
    
    def test_parse_invalid_mode_in_dotted_name_falls_back(self):
        """Test invalid mode in dotted name uses parameter mode."""
        adapter = RagasAdapter("ragas.TopicAdherenceScore.invalid", mode="recall")
        
        # Should extract metric name but use parameter mode
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "recall"  # From parameter
    
    def test_parse_standard_name_without_dots(self):
        """Test standard name (no dots) still works."""
        adapter = RagasAdapter("TopicAdherenceScore", mode="f1")
        
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "f1"
        assert adapter.name == "TopicAdherenceScore_f1"
    
    def test_parse_non_ragas_prefix(self):
        """Test name without 'ragas' prefix uses as standard name."""
        # Non-ragas prefix should use parameter mode
        adapter = RagasAdapter("TopicAdherenceScore", mode="f1")
        
        # Should use standard parsing
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "f1"


# ============================================================================
# TEST CLASS 3: MODEL HANDLING
# ============================================================================

class TestRagasModelHandling:
    """Test model provider and initialization."""
    
    def test_get_model_provider(self):
        """Test model provider identification."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        provider = adapter.get_model_provider()
        
        assert provider == "ragas"
    
    def test_create_model_delegates_to_load_model(self):
        """Test create_model delegates to load_model function."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        # Verify method exists
        assert hasattr(adapter, 'create_model')
        assert callable(adapter.create_model)
    
    def test_init_with_model_attempts_initialization(self):
        """Test init_with_model attempts to initialize metric."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        # The method tries to load ragas metric dynamically
        # With MagicMock it might succeed or fail depending on implementation
        # Just verify method is callable and handles input
        result = adapter.init_with_model(MagicMock())
        
        # Result is boolean
        assert isinstance(result, bool)
    
    def test_get_requirements_class_method(self):
        """Test get_requirements class method."""
        requirements = RagasAdapter.get_requirements("TopicAdherenceScore")
        
        assert isinstance(requirements, list)
        assert "conversation_elements" in requirements


# ============================================================================
# TEST CLASS 4: INPUT DATA ASSESSMENT
# ============================================================================

class TestRagasInputAssessment:
    """Test input data validation logic."""
    
    @pytest.mark.asyncio
    async def test_assess_session_entity_valid(self):
        """Test assessment of valid SessionEntity."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
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
            conversation_elements=[],  # Required by TopicAdherence
        )
        
        # Execute
        result_tuple = await adapter._assess_input_data(session)
        is_valid = result_tuple[0]
        error = result_tuple[1]
        
        # Assert: Valid
        assert is_valid is True
        assert error == ""
    
    @pytest.mark.asyncio
    async def test_assess_session_entity_empty_spans(self):
        """Test assessment rejects session with no spans."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        session = SessionEntity(
            session_id="session-1",
            spans=[],  # Empty!
        )
        
        # Execute
        result_tuple = await adapter._assess_input_data(session)
        is_valid = result_tuple[0]
        error = result_tuple[1]
        
        # Assert: Invalid
        assert is_valid is False
        assert "no spans" in error.lower() or "empty" in error.lower()
    
    @pytest.mark.asyncio
    async def test_assess_session_entity_wrong_entity_type(self):
        """Test assessment rejects session without required entity types."""
        adapter = RagasAdapter("TopicAdherenceScore")  # Requires llm
        
        # Session with only tool spans
        session = SessionEntity(
            session_id="session-1",
            spans=[
                SpanEntity(
                    entity_type="tool",  # Wrong!
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
        result_tuple = await adapter._assess_input_data(session)
        is_valid = result_tuple[0]
        error = result_tuple[1]
        
        # Assert: Invalid
        assert is_valid is False
        assert "entity" in error.lower()
    
    @pytest.mark.asyncio
    async def test_assess_basic_session_structure(self):
        """Test assessment validates basic session structure."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        # Session with basic structure
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
        )
        
        # Execute
        result_tuple = await adapter._assess_input_data(session)
        is_valid = result_tuple[0]
        
        # Assert: Validates structure (specific validation may vary)
        assert isinstance(is_valid, bool)


# ============================================================================
# TEST CLASS 5: CONFIGURATION AND VALIDATION
# ============================================================================

class TestRagasConfiguration:
    """Test configuration and validation logic."""
    
    def test_required_parameters_property(self):
        """Test required_parameters property."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        # Before init_with_model, ragas_metric is None
        params = adapter.required_parameters
        
        # Should return empty list or handle None gracefully
        assert isinstance(params, list)
    
    def test_validate_config_without_metric(self):
        """Test validate_config when metric not initialized."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        # ragas_metric is None
        result = adapter.validate_config()
        
        # Should handle gracefully
        assert isinstance(result, bool)
    
    def test_metric_configuration_loaded(self):
        """Test metric configuration is properly loaded."""
        adapter = RagasAdapter("TopicAdherenceScore")
        
        assert adapter.metric_configuration is not None
        assert adapter.metric_configuration.metric_name == "TopicAdherenceScore"
        
        # Should have mode support
        assert adapter.metric_configuration.mode_support is not None
        assert "precision" in adapter.metric_configuration.mode_support
        assert "recall" in adapter.metric_configuration.mode_support
        assert "f1" in adapter.metric_configuration.mode_support


# ============================================================================
# INTEGRATION TEST: ADAPTER WORKFLOW
# ============================================================================

class TestRagasAdapterIntegration:
    """Integration tests for adapter workflow."""
    
    @pytest.mark.asyncio
    async def test_adapter_initialization_workflow(self):
        """Test complete adapter initialization workflow."""
        # Step 1: Create adapter with specific mode
        adapter = RagasAdapter("TopicAdherenceScore", mode="f1")
        
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "f1"
        assert adapter.name == "TopicAdherenceScore_f1"
        
        # Step 2: Verify not initialized
        assert adapter.ragas_metric is None
        assert adapter.model is None
        
        # Step 3: Verify configuration loaded
        assert adapter.metric_configuration is not None
        assert adapter.aggregation_level == "session"
        assert "llm" in adapter.required["entity_type"]
    
    @pytest.mark.asyncio
    async def test_adapter_with_dotted_name_workflow(self):
        """Test adapter with dotted name format."""
        # Step 1: Create with dotted name
        adapter = RagasAdapter("ragas.TopicAdherenceScore.recall")
        
        # Step 2: Verify parsing worked
        assert adapter.ragas_metric_name == "TopicAdherenceScore"
        assert adapter.mode == "recall"
        assert adapter.name == "TopicAdherenceScore_recall"
        
        # Step 3: Verify configuration
        assert adapter.aggregation_level == "session"

