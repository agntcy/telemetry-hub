# MCE Test Suite

Comprehensive test coverage for the Metrics Computation Engine (MCE) core components.

## Overview

- **Total Tests:** 481 (206 new core tests + 275 existing)
- **Test Coverage:** ~65-70% overall, ~85% for core components
- **Execution Time:** ~3.5s for new tests, ~8-10s for full suite
- **Status:** All tests passing, CI/CD integrated

## Test Files

### Core Components
- `test_processor.py` - Metrics computation orchestrator (16 tests)
- `test_registry.py` - Metric registration system (17 tests)
- `test_data_parser.py` - Raw trace parsing (32 tests)
- `test_session_aggregator.py` - Session grouping (23 tests)
- `test_trace_processor.py` - Processing pipeline (21 tests)
- `test_llm_judge.py` - LLM-as-judge system (23 tests)
- `test_transformers.py` - Session enrichment (25 tests)
- `test_util.py` - Utility functions (23 tests)
- `test_api.py` - API endpoints (23 tests)

### Existing Tests
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

## Test Coverage by Component

| Component | Tests | Coverage |
|-----------|-------|----------|
| Processor | 16 | 65-70% |
| Registry | 17 | 100% |
| Data Parser | 32 | 85-90% |
| Session Aggregator | 23 | 85-90% |
| Trace Processor | 21 | 80-85% |
| LLM Judge | 23 | 85-90% |
| Transformers | 25 | 70-75% |
| Utilities | 23 | 50-60% |
| API | 23 | 70-75% |

## Test Quality

- **Pass Rate:** 100% (206/206 new tests)
- **Flaky Tests:** 0
- **Execution Speed:** Fast (<5s for all new tests)
- **CI/CD:** Integrated in `.github/workflows/mce_tests.yaml`
- **Mocking:** External APIs only (DB, LLM)
- **Data:** Uses real production trace data for validation

## Documentation

Detailed component summaries available in:
- `TEST_PROCESSOR_SUMMARY.md`
- `TEST_REGISTRY_SUMMARY.md`
- `TEST_DATA_PARSER_SUMMARY.md`
- `TEST_TRACE_PROCESSOR_AGGREGATOR_SUMMARY.md`
- `TEST_LLM_JUDGE_SUMMARY.md`
- `TEST_TRANSFORMERS_SUMMARY.md`
- `TEST_UTIL_SUMMARY.md`
- `TEST_API_SUMMARY.md`

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
