# Utility Functions Test Suite

## Overview

Test coverage for `util.py` - utility functions for metric loading, result formatting, and data processing.

**Tests:** 23 tests
**Coverage:** ~50-60% (focused on high-value functions)
**Execution Time:** ~0.28s

## Components Tested

- Metric loading and discovery (`get_metric_class`, `get_all_available_metrics`)
- Result formatting (`format_return`, `stringify_keys`)
- Tool definition extraction (`get_tool_definitions_from_span_attributes`)
- Chat history building (`build_chat_history_from_payload`)
- Cache management (`clear_metrics_cache`)

## Test Classes

### TestMetricLoading (4 tests)
- Load native metrics by name
- Handle non-existent metrics
- Dotted name handling
- Get all available metrics with metadata

### TestResultFormatting (5 tests)
- Format MetricResult objects to dicts
- Empty results handling
- Nested dict key stringification
- Non-dict input handling
- Structure preservation

### TestToolAndChatHelpers (5 tests)
- Tool definition extraction from attributes
- Chat history building from payloads
- Empty/invalid data handling

### TestCacheManagement (2 tests)
- Clear metrics cache
- Cache invalidation workflow

### TestUtilIntegration (3 tests)
- Get and format workflow
- Metric class loading integration
- Metadata structure validation

### TestUtilEdgeCases (4 tests)
- List of dicts stringification
- Dataclass result formatting
- Chat history with completions
- Tool definition gaps in numbering

## Running Tests

```bash
uv run pytest src/metrics_computation_engine/tests/test_util.py -v
```

## Key Features

- Focuses on most-used utility functions
- Tests metric loading and discovery
- Validates result formatting for API
- Fast execution
