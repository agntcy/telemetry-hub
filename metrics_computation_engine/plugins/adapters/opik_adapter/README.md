# MCE Opik Adapter

A Python adapter library that integrates [Opik](https://github.com/comet-ml/opik) metrics as third-party plugins for the [Metric Computation Engine (MCE)](https://github.com/agntcy/telemetry-hub/tree/main/metrics_computation_engine). This adapter enables seamless use of Opik's LLM evaluation metrics within the MCE framework for evaluating agentic applications.

## Installation

```bash
pip install mce-opik-adapter
```

## Prerequisites

- [Metric Computation Engine (MCE)](https://github.com/agntcy/telemetry-hub/tree/main/metrics_computation_engine) installed
- Agentic applications instrumented with [AGNTCY's observe SDK](https://github.com/agntcy/observe)

## Supported Opik Metrics

The adapter supports a wide range of Opik metrics, including but not limited to:

- **Hallucination** - Evaluates whether the model response contains hallucinations
- **Usefulness** - Evaluates the usefulness of a model response
- **Sentiment** - Measures the sentiment of a model response 

For a complete list of supported metrics, refer to the Opik documentation. Many metrics in this library will require which this adapter does not yet support. As we confirm compatibility of metrics, we will add it to the above list.

## Usage

### Basic Usage

```python
import asyncio
from mce_opik_adapter.adapter import OpikMetricAdapter
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.registry import MetricRegistry

# Initialize LLM configuration
llm_config = LLMJudgeConfig(
    LLM_BASE_MODEL_URL="https://api.openai.com/v1",
    LLM_MODEL_NAME="gpt-4o",
    LLM_API_KEY="your-api-key-here"
)

# Create registry and register Opik metrics
registry = MetricRegistry()

# Method 1: Direct registration with metric name
registry.register_metric(OpikMetricAdapter, "Hallucination")

# Method 2: Using get_metric_class helper with prefix
from metrics_computation_engine.util import get_metric_class
metric, metric_name = get_metric_class("opik.Hallucination")
registry.register_metric(metric, metric_name)
```

### Using with MCE REST API

When using the MCE as a service, include Opik metrics in your API request:

```json
{
  "metrics": [
    "opik.Hallucination",
    "opik.Usefulness",
    "opik.Sentiment"
  ],
  "llm_judge_config": {
    "LLM_API_KEY": "your-api-key",
    "LLM_MODEL_NAME": "gpt-4o",
    "LLM_BASE_MODEL_URL": "https://api.openai.com/v1"
  },
  "batch_config": {
    "num_sessions": 10
  }
}
```

## Configuration

### Environment Variables

Set up your environment variables for LLM access:

```bash
# .env file
LLM_BASE_MODEL_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o
LLM_API_KEY=sk-your-openai-api-key
```

## Supported Aggregation Levels

The adapter maps Opik metrics to different aggregation levels:

- **Span Level**: Evaluate individual agent interactions or tool calls
- **Session Level**: Evaluate complete conversation sessions

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Create a new Pull Request.
