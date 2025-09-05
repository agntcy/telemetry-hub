# RAGAS Adapter for Metrics Computation Engine

This plugin provides integration between the Metrics Computation Engine and [RAGAS](https://github.com/explodinggradients/ragas) (Retrieval Augmented Generation Assessment) metrics.

## Overview

The RAGAS adapter enables the use of RAGAS metrics within the MCE framework, specifically designed for evaluating RAG applications and conversational AI systems.

## Supported Metrics

- **TopicAdherenceScore**: Measures how well a conversation stays on topic

## Installation

### Development Setup

```bash
# From the plugin directory
./dev-setup.sh
```

### Manual Installation

```bash
# Install in development mode
uv pip install -e .

# Or install specific dependencies
uv pip install ragas>=0.2.0 langchain-openai langchain-core
```

## Usage

### Basic Usage

```python
from metrics_computation_engine.registry import MetricRegistry

# Register the RAGAS adapter
registry = MetricRegistry()
registry.register_metric("ragas.TopicAdherenceScore")

# Use with processor
processor = MetricsProcessor(registry=registry)
results = await processor.compute_metrics(traces_by_session)
```

### Configuration

The RAGAS adapter requires LLM configuration:

```python
from metrics_computation_engine.models.requests import LLMJudgeConfig

llm_config = LLMJudgeConfig(
    LLM_MODEL_NAME="gpt-4o-mini",
    LLM_API_KEY="your-api-key",
    LLM_BASE_MODEL_URL="https://api.openai.com/v1"
)
```

## Metric Details

### TopicAdherenceScore

- **Type**: Session-level metric
- **Aggregation Level**: session
- **Required Entity Types**: llm
- **Description**: Evaluates how well a multi-turn conversation maintains focus on specified reference topics
- **Output**: Float score between 0.0 and 1.0

## Dependencies

- `ragas>=0.2.0`: Core RAGAS library
- `langchain-openai`: LLM integration
- `langchain-core`: Core LangChain functionality

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Contributing

1. Follow the existing code style and patterns
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass before submitting

## License

Apache License 2.0 - see the main project LICENSE file for details.
