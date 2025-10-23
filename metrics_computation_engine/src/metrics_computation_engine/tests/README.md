# MCE Test Suite

Comprehensive test coverage for the Metrics Computation Engine (MCE) core components.

## Overview

- **Total Tests:** 481 (206 core + 275 existing)
- **Test Coverage:** ~65-70% overall, ~85% for core components
- **Execution Time:** ~3.5s for core tests, ~8-10s for full suite
- **Status:** All tests passing, CI/CD integrated

## Test Files

### Core Components
- `test_processor.py` - Metrics computation orchestrator (16 tests, 65-70% coverage)
- `test_registry.py` - Metric registration system (17 tests, 100% coverage)
- `test_data_parser.py` - Raw trace parsing (32 tests, 85-90% coverage)
- `test_session_aggregator.py` - Session grouping (23 tests, 85-90% coverage)
- `test_trace_processor.py` - Processing pipeline (21 tests, 80-85% coverage)
- `test_llm_judge.py` - LLM-as-judge system (23 tests, 85-90% coverage)
- `test_transformers.py` - Session enrichment (25 tests, 70-75% coverage)
- `test_util.py` - Utility functions (23 tests, 50-60% coverage)
- `test_api.py` - API endpoints (23 tests, 70-75% coverage)

### Supporting Tests
- `test_dal/` - Data access layer (7 tests)
- `test_metrics/` - Native metrics (10 tests)
- `test_metric_processor_compatibility.py` - Compatibility (1 test)

### Test Infrastructure
- `conftest.py` - Shared fixtures and test utilities

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific component
uv run pytest src/metrics_computation_engine/tests/test_processor.py -v

# Run with coverage
uv run pytest --cov=src/metrics_computation_engine --cov-report=term-missing

# Quick run (quiet mode)
uv run pytest -q
```

## Component Details

### Processor (`test_processor.py`)
Tests the core metrics computation orchestrator including:
- Metrics computation and orchestration
- Metric classification by aggregation level
- Entity type filtering and session requirements
- Error handling and isolation
- Concurrent metric execution

### Registry (`test_registry.py`)
Tests the metric registration and management system:
- Metric registration with explicit and auto-generated names
- Metric retrieval and listing
- Input validation
- State isolation between instances

### Data Parser (`test_data_parser.py`)
Tests parsing raw OpenTelemetry traces into SpanEntity objects:
- Entity type detection (llm, tool, agent, workflow, graph, task)
- Payload extraction from various formats
- Timing calculations and error detection
- Session ID, app name, and tool definition extraction
- Uses real production trace data for validation

### Session Aggregator (`test_session_aggregator.py`)
Tests session grouping and filtering:
- Aggregating spans into sessions by session_id
- Duration calculation strategies
- Multi-criteria filtering (entity types, errors, span count)
- Time range filtering and session retrieval

### Trace Processor (`test_trace_processor.py`)
Tests the trace processing pipeline:
- Raw trace processing pipeline
- Pre-grouped session processing
- Session ID filtering
- Enrichment pipeline integration

### LLM Judge (`test_llm_judge.py`)
Tests the LLM-as-a-judge metric evaluation system:
- Judge orchestration and consensus
- LLM client wrapper
- Response parsing utilities
- All LLM API calls mocked (no costs)

### Transformers (`test_transformers.py`)
Tests session transformers and enrichers:
- Base transformer classes
- Agent transitions, conversation extraction
- Workflow patterns and execution trees
- Data preservation through pipeline

### Utilities (`test_util.py`)
Tests utility functions:
- Metric loading and discovery
- Result formatting
- Tool definition and chat history extraction
- Cache management

### API (`test_api.py`)
Tests FastAPI endpoints using TestClient:
- Root, status, and metrics listing endpoints
- Main computation endpoint (`/compute_metrics`)
- Request validation and response formatting
- Database and LLM calls mocked

## Test Quality

- **Pass Rate:** 100% (481/481 tests)
- **Flaky Tests:** 0
- **Execution Speed:** Fast (<5s for core tests)
- **Mocking:** External APIs only (DB, LLM)
- **Data:** Uses real production trace data for validation

## Contributing

When adding new tests:
1. Use existing fixtures from `conftest.py`
2. Follow the Arrange-Act-Assert pattern
3. Mock external dependencies only
4. Add docstrings describing what's being tested
5. Run tests locally before committing

## CI/CD

Tests automatically run on every PR via GitHub Actions workflow `mce_tests.yaml`.
All tests must pass before merge.

### Test Collection
- Core component tests: 206
- Data access layer tests: 7
- Native metrics tests: 10
- Plugin tests: 254
- Compatibility tests: 1
- **Total: 481 tests**
