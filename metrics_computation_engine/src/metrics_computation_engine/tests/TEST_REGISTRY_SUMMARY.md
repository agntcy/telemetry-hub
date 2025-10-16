# Registry Test Suite

## Overview

Test coverage for `registry.py` - the metric registration and management system.

**Tests:** 17 tests
**Coverage:** 100%
**Execution Time:** ~0.08s

## Components Tested

- Metric registration (with explicit and auto-generated names)
- Metric retrieval by name
- List all registered metrics
- Input validation
- State isolation between instances

## Test Classes

### TestRegistryBasicOperations (5 tests)
- Registry initialization
- Register with explicit name
- Register with auto-generated name
- Get existing metric
- Get non-existent metric returns None

### TestRegistryValidation (3 tests)
- Invalid metric class raises ValueError
- String/dict instead of class raises error
- Validates BaseMetric inheritance

### TestRegistryMultipleMetrics (4 tests)
- Register multiple different metrics
- Same name twice overwrites first
- List returns all metrics
- Mixed explicit and auto names

### TestRegistryEdgeCases (3 tests)
- Empty registry operations
- Special characters in names
- Instance isolation

### TestRegistryIntegration (2 tests)
- Full workflow (register → list → retrieve → overwrite)
- Processor usage pattern

## Running Tests

```bash
uv run pytest src/metrics_computation_engine/tests/test_registry.py -v
```

## Key Features

- 100% coverage of registry.py
- Tests validation logic
- Fast, deterministic
- No external dependencies
