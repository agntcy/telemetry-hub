# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive unit tests for LLM Judge system.

Tests cover:
1. Response parsing utilities (safe_json_from_llm, parse_key_from_nested_dict)
2. LLMClient (initialization, provider detection, query - mocked)
3. Jury (initialization, prompt augmentation, consensus, judge - mocked)
4. Integration testing with full workflow
"""

import pytest
from unittest.mock import MagicMock, patch

from metrics_computation_engine.llm_judge.llm import LLMClient
from metrics_computation_engine.llm_judge.jury import Jury
from metrics_computation_engine.llm_judge.utils.response_parsing import (
    safe_json_from_llm,
    parse_key_from_nested_dict,
)
from metrics_computation_engine.models.eval import BinaryGrading


# ============================================================================
# TEST CLASS 1: RESPONSE PARSING UTILITIES
# ============================================================================


class TestResponseParsing:
    """Test LLM response parsing utilities."""

    def test_safe_json_from_llm_valid_json(self):
        """Test parsing valid JSON strings."""
        # Simple JSON
        content = '{"metric_score": 1, "score_reasoning": "Good"}'
        result = safe_json_from_llm(content)
        assert result == {"metric_score": 1, "score_reasoning": "Good"}

        # Nested JSON
        content = '{"data": {"nested": {"value": 42}}}'
        result = safe_json_from_llm(content)
        assert result == {"data": {"nested": {"value": 42}}}

    def test_safe_json_from_llm_with_markdown_blocks(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        # With ```json``` blocks
        content = '```json\n{"metric_score": 1}\n```'
        result = safe_json_from_llm(content)
        assert result == {"metric_score": 1}

        # With ``` blocks (no language)
        content = '```\n{"score": 0}\n```'
        result = safe_json_from_llm(content)
        assert result == {"score": 0}

        # With ```python blocks
        content = '```python\n{"data": "value"}\n```'
        result = safe_json_from_llm(content)
        assert result == {"data": "value"}

    def test_safe_json_from_llm_python_dict(self):
        """Test parsing Python dict strings (fallback to ast.literal_eval)."""
        # Python dict with single quotes
        content = "{'metric_score': 1, 'score_reasoning': 'Good'}"
        result = safe_json_from_llm(content)
        assert result == {"metric_score": 1, "score_reasoning": "Good"}

    def test_safe_json_from_llm_invalid(self):
        """Test parsing invalid content returns None."""
        # Invalid JSON
        assert safe_json_from_llm("not json at all") is None

        # Empty string
        assert safe_json_from_llm("") is None

        # Partial JSON
        assert safe_json_from_llm('{"incomplete":') is None

    def test_parse_key_from_nested_dict_found(self):
        """Test finding key in nested dictionary."""
        # Key at top level
        nested = {"metric_score": 1, "other": "data"}
        result = parse_key_from_nested_dict(nested, "metric_score")
        assert result == 1

        # Key in nested dict
        nested = {"outer": {"inner": {"target_key": "found"}}}
        result = parse_key_from_nested_dict(nested, "target_key")
        assert result == "found"

        # Key in list of dicts
        nested = {"items": [{"id": 1}, {"target_key": "value"}]}
        result = parse_key_from_nested_dict(nested, "target_key")
        assert result == "value"

    def test_parse_key_from_nested_dict_not_found(self):
        """Test key not found returns default."""
        nested = {"other": "data"}

        # Not found - returns None (default)
        result = parse_key_from_nested_dict(nested, "missing_key")
        assert result is None

        # Not found - returns custom default
        result = parse_key_from_nested_dict(nested, "missing_key", default="custom")
        assert result == "custom"

        # Non-dict input - returns default
        result = parse_key_from_nested_dict("not a dict", "key", default="default")
        assert result == "default"


# ============================================================================
# TEST CLASS 2: LLM CLIENT
# ============================================================================


class TestLLMClient:
    """Test LLMClient initialization and query logic."""

    def test_init_with_config(self):
        """Test LLMClient initialization with config."""
        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key-123",
            "api_version": "",
        }

        client = LLMClient(config)

        # Assert: Config extracted correctly
        assert client.model == "gpt-4"
        assert client.api_base == "https://api.openai.com/v1"
        assert client.api_key == "test-key-123"
        assert client.api_version == ""

    def test_determine_provider_openai(self):
        """Test provider determination for OpenAI."""
        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
            "api_version": "",  # Empty api_version → OpenAI
        }

        client = LLMClient(config)

        # Assert: Provider is openai
        assert client.custom_llm_provider == "openai"

    def test_determine_provider_custom(self):
        """Test provider determination for custom provider."""
        config = {
            "LLM_MODEL_NAME": "custom-model",
            "LLM_BASE_MODEL_URL": "https://custom.api.com",
            "LLM_API_KEY": "test-key",
            "api_version": "2024-01-01",  # Has api_version → Custom
        }

        client = LLMClient(config)

        # Assert: Provider is None (custom)
        assert client.custom_llm_provider is None

    @patch("metrics_computation_engine.llm_judge.llm.completion")
    def test_query_with_mock_litellm(self, mock_completion):
        """Test LLMClient.query() with mocked litellm."""
        # Setup mock response
        mock_response = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Perfect"}'
                    )
                )
            ]
        )
        mock_completion.return_value = mock_response

        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
            "api_version": "",
        }

        client = LLMClient(config)

        # Execute: Query LLM
        messages = [{"role": "user", "content": "test prompt"}]
        result = client.query(messages)

        # Assert: Mock was called
        mock_completion.assert_called_once()

        # Assert: Correct parameters passed
        call_args = mock_completion.call_args
        assert call_args.kwargs["model"] == "gpt-4"
        assert call_args.kwargs["api_base"] == "https://api.openai.com/v1"
        assert call_args.kwargs["api_key"] == "test-key"
        assert call_args.kwargs["messages"] == messages

        # Assert: Response returned
        assert result == mock_response


# ============================================================================
# TEST CLASS 3: JURY
# ============================================================================


class TestJury:
    """Test Jury orchestration and consensus logic."""

    def test_jury_init_single_model(self):
        """Test Jury initialization with single model."""
        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        jury = Jury(config, num_models=1)

        # Assert: One LLM created
        assert len(jury.llms) == 1
        assert isinstance(jury.llms[0], LLMClient)

        # Assert: System message set
        assert jury.system_message is not None
        assert jury.system_message["role"] == "system"
        assert len(jury.system_message["content"]) > 0

    def test_jury_init_multiple_models(self):
        """Test Jury initialization with multiple models for consensus."""
        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        jury = Jury(config, num_models=3)

        # Assert: Three LLMs created
        assert len(jury.llms) == 3
        for llm in jury.llms:
            assert isinstance(llm, LLMClient)

    def test_augment_prompt_with_schema(self):
        """Test prompt augmentation with Pydantic schema."""
        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test",
        }
        jury = Jury(config)

        # Use real BinaryGrading model
        prompt = "Evaluate this response:"
        augmented = jury.augment_prompt_with_schema(prompt, BinaryGrading)

        # Assert: Schema added to prompt
        assert "Evaluate this response:" in augmented
        assert "json schema" in augmented.lower()
        assert "metric_score" in augmented or "score" in augmented
        assert "score_reasoning" in augmented or "feedback" in augmented

    def test_consensus_score_calculation(self):
        """Test consensus score calculation from multiple responses."""
        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test",
        }
        jury = Jury(config, num_models=3)

        # Create mock responses with different scores
        mock_responses = [
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"metric_score": 1, "score_reasoning": "Good"}'
                        )
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"metric_score": 0, "score_reasoning": "Bad"}'
                        )
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"metric_score": 1, "score_reasoning": "Good"}'
                        )
                    )
                ]
            ),
        ]

        # Execute: Calculate consensus
        consensus = jury.consensus_score(mock_responses)

        # Assert: Average score = (1 + 0 + 1) / 3 = 0.666...
        assert "metric_score" in consensus
        assert abs(consensus["metric_score"] - (2 / 3)) < 0.01

        # Assert: Reasoning included
        assert "score_reasoning" in consensus
        assert isinstance(consensus["score_reasoning"], str)

    @patch("metrics_computation_engine.llm_judge.llm.completion")
    def test_judge_with_mock_llm(self, mock_completion):
        """Test Jury.judge() method with mocked LLM."""
        # Setup mock LLM response
        mock_completion.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "The response is excellent"}'
                    )
                )
            ]
        )

        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        jury = Jury(config, num_models=1)

        # Execute: Judge a prompt
        prompt = "Is this response good?"
        score, reasoning = jury.judge(prompt, BinaryGrading)

        # Assert: Score and reasoning returned
        assert score == 1
        assert reasoning == "The response is excellent"

        # Assert: Mock was called
        mock_completion.assert_called_once()

    @patch("metrics_computation_engine.llm_judge.llm.completion")
    def test_judge_handles_parsing_errors(self, mock_completion):
        """Test Jury handles unparseable LLM responses."""
        # Setup mock with invalid JSON response
        mock_completion.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content="Invalid JSON response that cannot be parsed"
                    )
                )
            ]
        )

        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        jury = Jury(config, num_models=1)

        # Execute & Assert: Should raise ValueError
        prompt = "Test prompt"
        with pytest.raises(ValueError) as exc_info:
            jury.judge(prompt, BinaryGrading)

        assert "Unable to parse LLM response" in str(exc_info.value)


# ============================================================================
# TEST CLASS 4: INTEGRATION TESTS
# ============================================================================


class TestLLMJudgeIntegration:
    """Integration tests for complete LLM Judge workflow."""

    @patch("metrics_computation_engine.llm_judge.llm.completion")
    def test_full_judge_workflow_mocked(self, mock_completion):
        """Test complete judge workflow with mocked LLM."""
        # Setup mock response
        mock_completion.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Response addresses the query completely"}'
                    )
                )
            ]
        )

        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        # Create jury
        jury = Jury(config, num_models=1)

        # Prepare prompt
        prompt = """
        Evaluate if the response answers the query.

        Query: What is 2+2?
        Response: The answer is 4.
        """

        # Execute: Full workflow
        score, reasoning = jury.judge(prompt, BinaryGrading)

        # Assert: Valid score and reasoning
        assert score in [0, 1]  # Binary grading
        assert isinstance(reasoning, str)
        assert len(reasoning) > 0

    @patch("metrics_computation_engine.llm_judge.llm.completion")
    def test_multiple_models_consensus(self, mock_completion):
        """Test consensus calculation with multiple LLM judges."""
        # Setup: Three models return different scores
        mock_responses = [
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"metric_score": 1, "score_reasoning": "Judge 1: Good"}'
                        )
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"metric_score": 1, "score_reasoning": "Judge 2: Good"}'
                        )
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"metric_score": 0, "score_reasoning": "Judge 3: Bad"}'
                        )
                    )
                ]
            ),
        ]

        mock_completion.side_effect = mock_responses

        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        jury = Jury(config, num_models=3)

        # Execute: Judge with 3 models
        score, reasoning = jury.judge("Test prompt", BinaryGrading)

        # Assert: Consensus score = (1 + 1 + 0) / 3 = 0.666...
        assert abs(score - (2 / 3)) < 0.01

        # Assert: Called 3 times (one per model)
        assert mock_completion.call_count == 3

    @patch("metrics_computation_engine.llm_judge.llm.completion")
    def test_structured_output_generation(self, mock_completion):
        """Test that structured output format is requested."""
        mock_completion.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Test"}'
                    )
                )
            ]
        )

        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        jury = Jury(config)

        # Execute
        jury.judge("Test prompt", BinaryGrading)

        # Assert: response_format parameter passed
        call_kwargs = mock_completion.call_args.kwargs
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestLLMJudgeEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_nested_dict_deep_nesting(self):
        """Test parsing very deeply nested dictionaries."""
        nested = {
            "level1": {
                "level2": {
                    "level3": {"level4": {"level5": {"target_key": "deep_value"}}}
                }
            }
        }

        result = parse_key_from_nested_dict(nested, "target_key")
        assert result == "deep_value"

    def test_parse_nested_dict_list_of_dicts(self):
        """Test parsing lists containing dictionaries."""
        nested = {
            "items": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"},
                {"target_key": "found_in_list", "extra": "data"},
            ]
        }

        result = parse_key_from_nested_dict(nested, "target_key")
        assert result == "found_in_list"

    def test_safe_json_with_whitespace(self):
        """Test JSON parsing with extra whitespace."""
        # Leading/trailing whitespace
        content = '  \n  {"metric_score": 1}  \n  '
        result = safe_json_from_llm(content)
        assert result == {"metric_score": 1}

    @patch("metrics_computation_engine.llm_judge.llm.completion")
    def test_jury_with_nested_response_structure(self, mock_completion):
        """Test Jury can extract score from nested response."""
        # Mock response with nested structure
        mock_completion.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"evaluation": {"metric_score": 1}, "score_reasoning": "Nested"}'
                    )
                )
            ]
        )

        config = {
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "test-key",
        }

        jury = Jury(config)

        # Execute
        score, reasoning = jury.judge("Test", BinaryGrading)

        # Assert: Nested score found
        assert score == 1
        assert reasoning == "Nested"
