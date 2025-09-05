# Context Preservation Plugin

A metric plugin for the AGNTCY Telemetry Hub metrics computation engine that counts the number of spans in a session.

## Description

This plugin implements a `ContextPreservation` metric that calculates the total number of spans within a session. It's designed as a demonstration sample for implementing metrics in the AGNTCY Telemetry Hub system.

## Features

- Counts spans at the session aggregation level
- No required parameters
- Returns detailed metric results with metadata
- Async computation support

## Installation

This plugin is designed to be used as part of the AGNTCY Telemetry Hub metrics computation engine ecosystem.

```bash
# Install in development mode
uv pip install -e .

# Or install from source
uv pip install .
```

## Usage

The `ContextPreservation` metric can be used within the metrics computation engine framework:

```python
from context_preservation import ContextPreservation

# Initialize the metric
metric = ContextPreservation()

# Compute the metric on span data
result = await metric.compute(span_data)
```

## Development

To set up the development environment:

```bash
# Install with development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .

# Type checking
mypy src/
```

## Metric Details

- **Name**: ContextPreservation
- **Aggregation Level**: session
- **Required Parameters**: None
- **Output**: Number of spans in the session
- **Unit**: Count (dimensionless)

## License

This project is licensed under the MIT License.
