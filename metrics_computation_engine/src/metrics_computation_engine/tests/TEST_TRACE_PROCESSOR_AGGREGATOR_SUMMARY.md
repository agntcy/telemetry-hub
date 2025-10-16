# Trace Processor & Session Aggregator Test Suite

## Overview

Test coverage for the trace processing pipeline - converting raw traces into structured session data.

**Tests:** 44 tests (23 aggregator + 21 processor)
**Coverage:** ~83% combined
**Execution Time:** ~0.28s

## Components Tested

### Session Aggregator (`session_aggregator.py`)
- Aggregating spans into sessions by session_id
- Session creation from span lists
- Duration calculation strategies
- Multi-criteria filtering (entity types, errors, span count)
- Time range filtering
- Session retrieval by ID

### Trace Processor (`trace_processor.py`)
- Raw trace processing pipeline
- Pre-grouped session processing
- Session ID filtering
- Enrichment pipeline integration
- Pseudo-grouping from file data

## Test Classes

### Session Aggregator Tests
- `TestAggregateSpansToSessions` (5 tests)
- `TestCreateSessionFromSpans` (4 tests)
- `TestDurationCalculation` (3 tests)
- `TestFilterSessionsByCriteria` (4 tests)
- `TestSessionRetrieval` (2 tests)
- `TestTimeRangeFiltering` (4 tests)
- `TestSessionAggregatorIntegration` (1 test)

### Trace Processor Tests
- `TestTraceProcessorInitialization` (2 tests)
- `TestProcessRawTraces` (5 tests)
- `TestProcessGroupedSessions` (5 tests)
- `TestSessionFiltering` (3 tests)
- `TestPseudoGrouping` (3 tests)
- `TestTraceProcessorIntegration` (3 tests)

## Running Tests

```bash
# Both test files
uv run pytest src/metrics_computation_engine/tests/test_session_aggregator.py \
             src/metrics_computation_engine/tests/test_trace_processor.py -v

# Individual files
uv run pytest src/metrics_computation_engine/tests/test_session_aggregator.py -v
uv run pytest src/metrics_computation_engine/tests/test_trace_processor.py -v
```

## Key Features

- Tests complete trace → session pipeline
- Uses real production data
- Validates session grouping logic
- Tests enrichment integration
- Fast execution
