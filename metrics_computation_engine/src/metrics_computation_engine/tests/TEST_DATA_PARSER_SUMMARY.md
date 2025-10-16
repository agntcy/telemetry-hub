# Data Parser Test Suite

## Overview

Test coverage for `entities/core/data_parser.py` - the critical entry point for parsing raw OpenTelemetry traces into SpanEntity objects.

**Tests:** 32 tests
**Coverage:** ~85-90%
**Execution Time:** ~0.16s

## Components Tested

- Entity type detection (llm, tool, agent, workflow, graph, task)
- Payload extraction (input/output from various formats)
- Timing calculations (start_time, end_time, duration)
- Error status detection
- Session ID extraction
- App name extraction
- Tool definition extraction
- Token usage extraction for LLM spans

## Test Classes

### TestHelperFunctions (6 tests)
- JSON parsing with error handling (`safe_parse_json`)
- Error pattern detection in outputs
- App name extraction from span fields
- Payload normalization to dict format

### TestTimingCalculations (5 tests)
- End time calculation from start + duration
- Duration in milliseconds from nanoseconds
- Fallback duration calculation from timestamps
- Invalid input handling

### TestErrorDetection (3 tests)
- Explicit error attribute detection
- Error pattern matching (traceback, exception, httperror)
- Clean output validation

### TestPayloadProcessing (4 tests)
- Dict payload handling
- JSON string parsing
- Plain string wrapping
- None handling

### TestEntityTypeDetection (6 tests)
- LLM spans (`.chat` suffix)
- Task spans (`.task` suffix)
- Workflow spans (`.workflow` suffix)
- Agent spans (`.agent` suffix)
- Graph spans (`.graph` suffix)
- Mixed entity types in single batch

### TestParseRawSpansIntegration (8 tests)
- Empty list handling
- Real production data (api_noa_2.json - 83 spans)
- Session ID preservation
- Parent-child relationships
- Timing data extraction
- Incomplete span handling
- Invalid entity type filtering
- LLM token usage extraction

## Running Tests

```bash
uv run pytest src/metrics_computation_engine/tests/test_data_parser.py -v
```

## Key Features

- Uses real production trace data for validation
- Tests all 6 entity types
- Validates against actual OpenTelemetry format
- Critical for all downstream processing
