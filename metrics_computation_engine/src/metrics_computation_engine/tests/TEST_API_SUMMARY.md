# API Integration Test Suite

## Overview

Test coverage for FastAPI endpoints in `main.py` using TestClient for API integration testing.

**Tests:** 23 tests
**Coverage:** ~70-75% of main.py
**Execution Time:** ~3.54s

## Endpoints Tested

- `GET /` - Root/service info
- `GET /status` - Health check
- `GET /metrics` - List available metrics
- `POST /compute_metrics` - Main computation endpoint

## Test Classes

### TestSimpleEndpoints (4 tests)
- Root endpoint info
- Status health check
- Metrics listing
- Error handling (500)

### TestComputeMetricsValidation (4 tests)
- Valid session_ids request
- Valid batch_config request
- Invalid request returns 400
- Data fetching config validation

### TestComputeMetricsMetricHandling (3 tests)
- Native metrics registration
- Plugin metrics registration
- Invalid metric name handling

### TestComputeMetricsDataProcessing (4 tests)
- Trace fetching with correct session IDs
- Not found sessions handling
- Trace processing to SessionSet
- Computation levels (session/agent)

### TestComputeMetricsResponse (3 tests)
- Response structure validation
- MetricResult formatting to dicts
- Failed metrics in response

### TestComputeMetricsErrors (3 tests)
- Trace fetch failure handling
- Processing failure recovery
- LLM config environment defaults

### TestAPIIntegration (2 tests)
- Full compute workflow via API
- Multiple metrics in one request

## Running Tests

```bash
uv run pytest src/metrics_computation_engine/tests/test_api.py -v
```

## Mocking Strategy

**Mocked:**
- `get_traces_by_session_ids()` - No real database
- `get_all_session_ids()` - No real database
- `litellm.completion()` - No real LLM API calls

**Real (Not Mocked):**
- FastAPI app, Registry, Processor, TraceProcessor, Metrics, Request/Response models

## Key Features

- Tests actual HTTP layer with TestClient
- Validates API contract (request/response format)
- Tests component integration via HTTP
- All external APIs mocked (no costs, fast execution)
