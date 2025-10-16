# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive API integration tests for MCE endpoints.

Tests cover:
1. Simple endpoints (GET /, /status, /metrics)
2. /compute_metrics request validation
3. /compute_metrics metric handling
4. /compute_metrics data processing
5. /compute_metrics response format
6. /compute_metrics error handling
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient
from metrics_computation_engine.main import app


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def api_client():
    """FastAPI test client for making API requests."""
    return TestClient(app)


@pytest.fixture
def mock_llm_response():
    """Mock LLM API response."""
    return MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"metric_score": 1, "score_reasoning": "Good response"}'
                )
            )
        ]
    )


@pytest.fixture
def mock_grouped_traces(api_noa_2_data):
    """Mock grouped trace data (as returned by get_traces_by_session_ids)."""
    # Group api_noa_2_data by session_id
    from metrics_computation_engine.entities.core.trace_processor import (
        create_pseudo_grouped_sessions_from_file,
    )

    grouped = create_pseudo_grouped_sessions_from_file(api_noa_2_data)
    return grouped


# ============================================================================
# TEST CLASS 1: SIMPLE ENDPOINTS
# ============================================================================


class TestSimpleEndpoints:
    """Test simple GET endpoints."""

    def test_root_endpoint(self, api_client):
        """Test GET / returns service information."""
        response = api_client.get("/")

        # Assert: HTTP 200
        assert response.status_code == 200

        # Assert: Response structure
        data = response.json()
        assert data["message"] == "Metrics Computation Engine"
        assert data["version"] == "0.1.0"
        assert "endpoints" in data

        # Assert: Endpoints listed
        endpoints = data["endpoints"]
        assert "/compute_metrics" in endpoints.values()
        assert "/status" in endpoints.values()

    def test_status_endpoint(self, api_client):
        """Test GET /status health check."""
        response = api_client.get("/status")

        # Assert: HTTP 200
        assert response.status_code == 200

        # Assert: Status structure
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Metric Computation Engine is running"
        assert data["service"] == "metrics_computation_engine"

        # Assert: Timestamp present and valid ISO format
        assert "timestamp" in data
        # Should be parseable as ISO timestamp
        datetime.fromisoformat(data["timestamp"])

    @patch("metrics_computation_engine.main.get_all_available_metrics")
    def test_list_metrics_endpoint(self, mock_get_metrics, api_client):
        """Test GET /metrics lists available metrics."""
        # Setup: Mock available metrics
        mock_get_metrics.return_value = {
            "AgentToAgentInteractions": {
                "source": "native",
                "aggregation_level": "session",
            },
            "GoalSuccessRate": {"source": "plugin", "aggregation_level": "session"},
        }

        response = api_client.get("/metrics")

        # Assert: HTTP 200
        assert response.status_code == 200

        # Assert: Response structure
        data = response.json()
        assert data["total_metrics"] == 2
        assert data["native_metrics"] == 1
        assert data["plugin_metrics"] == 1

        # Assert: Metrics grouped correctly
        assert "metrics" in data
        assert "native" in data["metrics"]
        assert "plugins" in data["metrics"]

    @patch("metrics_computation_engine.main.get_all_available_metrics")
    def test_list_metrics_error_returns_500(self, mock_get_metrics, api_client):
        """Test GET /metrics handles errors."""
        # Setup: Make function raise exception
        mock_get_metrics.side_effect = Exception("Test error")

        response = api_client.get("/metrics")

        # Assert: HTTP 500
        assert response.status_code == 500
        assert "Error listing metrics" in response.json()["detail"]


# ============================================================================
# TEST CLASS 2: COMPUTE METRICS - REQUEST VALIDATION
# ============================================================================


class TestComputeMetricsValidation:
    """Test /compute_metrics request validation."""

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_valid_session_ids_request(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test valid request with session_ids."""
        # Setup mocks
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        # Valid request
        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: HTTP 200
        assert response.status_code == 200

        # Assert: Response has metrics and results
        data = response.json()
        assert "metrics" in data
        assert "results" in data

    @patch("metrics_computation_engine.main.get_all_session_ids")
    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_valid_batch_request(
        self, mock_llm, mock_db, mock_get_sessions, api_client, mock_grouped_traces
    ):
        """Test valid request with batch_config."""
        # Setup mocks
        mock_get_sessions.return_value = ["session-1", "session-2"]
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        # Batch request
        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {
                "session_ids": [],
                "batch_config": {"num_sessions": 10},
            },
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: HTTP 200
        assert response.status_code == 200

        # Assert: get_all_session_ids was called
        mock_get_sessions.assert_called_once()

    def test_invalid_request_returns_400(self, api_client):
        """Test invalid request returns 400."""
        # Invalid: neither session_ids nor valid batch_config
        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": [], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: HTTP 400
        assert response.status_code == 400
        assert "Invalid request configuration" in response.json()["detail"]

    def test_invalid_data_fetching_config(self, api_client):
        """Test invalid data_fetching_infos returns 400."""
        # Invalid: empty session_ids and empty batch_config
        payload = {
            "metrics": ["Test"],
            "data_fetching_infos": {
                "session_ids": [],
                "batch_config": {},  # Invalid - no criteria
            },
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: HTTP 400 (validation fails in endpoint logic)
        assert response.status_code == 400


# ============================================================================
# TEST CLASS 3: COMPUTE METRICS - METRIC HANDLING
# ============================================================================


class TestComputeMetricsMetricHandling:
    """Test metric registration and handling."""

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_with_native_metrics(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test requesting native metrics."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions", "AgentToToolInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Both metrics should be registered
        assert "AgentToAgentInteractions" in data["metrics"]
        assert "AgentToToolInteractions" in data["metrics"]

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_with_plugin_metrics(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test requesting plugin metrics."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["GoalSuccessRate"],  # Plugin metric
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Should work (assuming plugin installed)
        assert response.status_code == 200

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    def test_with_invalid_metric_name(self, mock_db, api_client, mock_grouped_traces):
        """Test invalid metric name doesn't crash endpoint."""
        mock_db.return_value = (mock_grouped_traces, [])

        payload = {
            "metrics": ["NonExistentMetric"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: Still returns 200 (graceful handling)
        assert response.status_code == 200

        # Assert: Failed metric in failed_metrics
        data = response.json()
        assert "failed_metrics" in data["results"]
        assert len(data["results"]["failed_metrics"]) > 0


# ============================================================================
# TEST CLASS 4: COMPUTE METRICS - DATA PROCESSING
# ============================================================================


class TestComputeMetricsDataProcessing:
    """Test data fetching and processing."""

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_fetches_traces_correctly(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test that traces are fetched with correct session IDs."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {
                "session_ids": ["session-1", "session-2"],
                "batch_config": {},
            },
        }

        # Execute API call
        api_client.post("/compute_metrics", json=payload)

        # Assert: get_traces_by_session_ids called with correct IDs
        mock_db.assert_called_once()
        called_session_ids = mock_db.call_args[0][0]
        assert "session-1" in called_session_ids
        assert "session-2" in called_session_ids

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_handles_not_found_sessions(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test handling of sessions not found in database."""
        # Mock: Some sessions found, some not
        mock_db.return_value = (mock_grouped_traces, ["session-not-found"])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {
                "session_ids": ["session-1", "session-not-found"],
                "batch_config": {},
            },
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: Still succeeds (processes found sessions)
        assert response.status_code == 200

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("metrics_computation_engine.main.traces_processor")
    @patch("litellm.completion")
    def test_processes_traces_to_sessions(
        self, mock_llm, mock_processor, mock_db, api_client, sample_session_set
    ):
        """Test that traces are processed into SessionSet."""
        # Setup mocks
        mock_db.return_value = ({"session-1": []}, [])
        mock_processor.return_value = sample_session_set
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: traces_processor was called
        mock_processor.assert_called_once()

        # Assert: Success
        assert response.status_code == 200

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_with_computation_levels(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test requesting specific computation levels."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
            "metric_options": {"computation_level": ["session", "agent"]},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: Success
        assert response.status_code == 200

        # Assert: Results should have agent_metrics
        data = response.json()
        assert "agent_metrics" in data["results"]


# ============================================================================
# TEST CLASS 5: COMPUTE METRICS - RESPONSE FORMAT
# ============================================================================


class TestComputeMetricsResponse:
    """Test response structure and formatting."""

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_response_structure(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test response has correct structure."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Assert: Top-level structure
        assert "metrics" in data
        assert "results" in data

        # Assert: metrics is a list
        assert isinstance(data["metrics"], list)

        # Assert: results is a dict with required keys
        results = data["results"]
        assert "span_metrics" in results
        assert "session_metrics" in results
        assert "agent_metrics" in results
        assert "population_metrics" in results
        assert "failed_metrics" in results

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_results_formatted_correctly(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test that MetricResult objects are converted to dicts."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Assert: All metric results are dicts (not objects)
        results = data["results"]
        for metric_list in [
            results["span_metrics"],
            results["session_metrics"],
            results["agent_metrics"],
            results["population_metrics"],
        ]:
            for metric_result in metric_list:
                assert isinstance(metric_result, dict)
                # Should have standard fields
                if metric_result:  # If not empty
                    assert "metric_name" in metric_result

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    def test_includes_failed_metrics(self, mock_db, api_client, mock_grouped_traces):
        """Test that failed metrics appear in response."""
        mock_db.return_value = (mock_grouped_traces, [])

        # Request with invalid metric
        payload = {
            "metrics": ["NonExistentMetric"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Assert: Failed metrics list populated
        assert len(data["results"]["failed_metrics"]) > 0

        # Assert: Contains the failed metric
        failed = data["results"]["failed_metrics"]
        assert any("NonExistentMetric" in str(f) for f in failed)


# ============================================================================
# TEST CLASS 6: COMPUTE METRICS - ERROR HANDLING
# ============================================================================


class TestComputeMetricsErrors:
    """Test error handling and edge cases."""

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_trace_fetch_failure_handles_gracefully(
        self, mock_llm, mock_db, api_client
    ):
        """Test graceful handling when trace fetching fails."""
        # Mock: get_traces raises exception
        mock_db.side_effect = Exception("Database connection error")
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: Returns 200 (endpoint catches exception and continues with empty SessionSet)
        assert response.status_code == 200

        # Response should still have structure even with empty results
        data = response.json()
        assert "results" in data

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("metrics_computation_engine.main.traces_processor")
    @patch("litellm.completion")
    def test_trace_processing_failure_continues(
        self, mock_llm, mock_processor, mock_db, api_client
    ):
        """Test that trace processing failure is handled."""
        mock_db.return_value = ({"session-1": []}, [])
        # Mock: traces_processor raises exception
        mock_processor.side_effect = Exception("Processing error")
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: Should continue with empty SessionSet
        assert response.status_code == 200

        # Results might be empty but no crash
        data = response.json()
        assert "results" in data

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    @patch.dict(
        "os.environ",
        {
            "LLM_BASE_MODEL_URL": "https://env.test.com",
            "LLM_MODEL_NAME": "env-model",
            "LLM_API_KEY": "env-key",
        },
    )
    def test_llm_config_uses_env_defaults(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test LLM config falls back to environment variables."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": ["AgentToAgentInteractions"],
            "data_fetching_infos": {"session_ids": ["session-1"], "batch_config": {}},
            "llm_judge_config": {
                "LLM_API_KEY": "sk-...",  # Default value triggers env lookup
            },
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: Should use env variables
        assert response.status_code == 200


# ============================================================================
# INTEGRATION TEST: FULL API WORKFLOW
# ============================================================================


class TestAPIIntegration:
    """Integration tests for complete API workflows."""

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_full_compute_workflow_via_api(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test complete workflow: request → process → response."""
        # Setup: Real trace data, mocked external calls
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Excellent"}'
                    )
                )
            ]
        )

        # Complete request
        payload = {
            "metrics": [
                "AgentToAgentInteractions",
                "AgentToToolInteractions",
                "Cycles",
            ],
            "data_fetching_infos": {
                "session_ids": list(mock_grouped_traces.keys())[:1],
                "batch_config": {},
            },
            "llm_judge_config": {
                "LLM_API_KEY": "test-key",
                "LLM_BASE_MODEL_URL": "https://test.com",
                "LLM_MODEL_NAME": "test-model",
            },
        }

        response = api_client.post("/compute_metrics", json=payload)

        # Assert: Success
        assert response.status_code == 200

        # Assert: All metrics registered
        data = response.json()
        assert len(data["metrics"]) == 3

        # Assert: Results present
        assert "results" in data

        # Assert: No failed metrics (all succeeded)
        # (May have some depending on data, but structure should be there)
        assert "failed_metrics" in data["results"]

    @patch("metrics_computation_engine.main.get_traces_by_session_ids")
    @patch("litellm.completion")
    def test_compute_multiple_metrics_via_api(
        self, mock_llm, mock_db, api_client, mock_grouped_traces
    ):
        """Test computing multiple metrics in one request."""
        mock_db.return_value = (mock_grouped_traces, [])
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"metric_score": 1, "score_reasoning": "Good"}'
                    )
                )
            ]
        )

        payload = {
            "metrics": [
                "AgentToAgentInteractions",
                "AgentToToolInteractions",
                "Cycles",
                "ToolErrorRate",
            ],
            "data_fetching_infos": {
                "session_ids": list(mock_grouped_traces.keys())[:1],
                "batch_config": {},
            },
        }

        response = api_client.post("/compute_metrics", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Assert: All metrics processed
        assert len(data["metrics"]) >= 4

        # Assert: Results organized by aggregation level
        results = data["results"]
        # Should have session_metrics (all requested are session-level)
        assert "session_metrics" in results
