# Processor Test Suite

## Overview

Test coverage for `processor.py` - the core metrics computation orchestrator.

**Tests:** 16 tests
**Coverage:** ~65-70%
**Execution Time:** ~0.12s

## Components Tested

- Metrics computation orchestration
- Metric classification by aggregation level
- Entity type filtering for span metrics
- Session requirements validation
- Error handling and isolation
- Concurrent metric execution

## Test Classes

### TestEmptyDataHandling (3 tests)
- Empty SessionSet handling
- Empty sessions (no spans)
- Entity filtering with no matches

### TestMetricComputation (4 tests)
- Span-level metrics across sessions
- Session-level metrics
- Population-level metrics
- Multiple concurrent metrics

### TestMetricExecutionOrder (3 tests)
- Metric classification by aggregation level
- Entity type filtering
- Session requirements validation

### TestErrorHandling (5 tests)
- Metric initialization failures
- Metric compute() exceptions
- One failing metric doesn't stop others
- Error result structure validation
- Failure deduplication

### TestProcessorIntegration (1 test)
- Complete workflow with all metric types

## Running Tests

```bash
uv run pytest src/metrics_computation_engine/tests/test_processor.py -v
```

## Key Features

- Tests metric orchestration logic
- Validates concurrent execution
- Error isolation (one failure doesn't break all)
- Uses mock metrics (no LLM costs)
- Fast execution
