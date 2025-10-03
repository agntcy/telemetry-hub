# MCE DeepEval Adapter

A Python adapter library that integrates [DeepEval](https://github.com/confident-ai/deepeval) metrics as third-party plugins for the [Metric Computation Engine (MCE)](https://github.com/agntcy/telemetry-hub/tree/main/metrics_computation_engine). This adapter enables seamless use of DeepEval's LLM evaluation metrics within the MCE framework for evaluating agentic applications.

## Installation

Install via MCE extras:
```bash
pip install "metrics-computation-engine[deepeval]"
```

## Prerequisites

- [Metric Computation Engine (MCE)](https://github.com/agntcy/telemetry-hub/tree/main/metrics_computation_engine) installed
- Agentic applications instrumented with [AGNTCY's observe SDK](https://github.com/agntcy/observe)

## Supported DeepEval Metrics

The following DeepEval metrics are supported by this adapter (use with the `deepeval.` prefix in service payloads):

| Metric Name | Description |
| :---------: | :---------- |
| **AnswerRelevancyMetric** | Measures how relevant the model answer is to the user query |
| **RoleAdherenceMetric** | Evaluates adherence to specified roles across a conversation |
| **TaskCompletionMetric** | Assesses whether the task was completed given tool calls and responses |
| **ConversationCompletenessMetric** | Evaluates whether the conversation covered necessary elements |
| **BiasMetric** | Detects various forms of bias in responses |
| **CoherenceMetric** | Scores coherence and logical flow of the output |
| **GroundednessMetric** | Evaluates how well outputs are grounded in the provided input/context |
| **TonalityMetric** | Evaluates tone and stylistic appropriateness of the output |
| **ToxicityMetric** | Identifies toxic or unsafe content in outputs |
| **AnswerCorrectnessMetric** | Measures correctness of the answer versus expected output |
| **GeneralStructureAndStyleMetric** | Evaluates structure and style quality of the output |

For requests to support additional DeepEval metrics, please file an issue in our repo: [agntcy/telemetry-hub](https://github.com/agntcy/telemetry-hub).

## Usage

### Basic Usage

```python
import asyncio
from mce_deepeval_adapter.adapter import DeepEvalMetricAdapter
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.registry import MetricRegistry

# Initialize LLM configuration
llm_config = LLMJudgeConfig(
    LLM_BASE_MODEL_URL="https://api.openai.com/v1",
    LLM_MODEL_NAME="gpt-4o",
    LLM_API_KEY="your-api-key-here"
)

# Create registry and register DeepEval metrics
registry = MetricRegistry()

# Method 1: Direct registration with metric name
registry.register_metric(DeepEvalMetricAdapter, "AnswerRelevancyMetric")

# Method 2: Using get_metric_class helper with prefix
from metrics_computation_engine.util import get_metric_class
metric, metric_name = get_metric_class("deepeval.RoleAdherenceMetric")
registry.register_metric(metric, metric_name)
```

### Using with MCE REST API

When using the MCE as a service, include DeepEval metrics in your API request:

```json
{
  "metrics": [
    "deepeval.AnswerRelevancyMetric",
    "deepeval.RoleAdherenceMetric",
  ],
  "llm_judge_config": {
    "LLM_API_KEY": "your-api-key",
    "LLM_MODEL_NAME": "gpt-4o",
    "LLM_BASE_MODEL_URL": "https://api.openai.com/v1"
  },
  "data_fetching_infos": {
    "batch_config": {
      "time_range": { "start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z" }
    },
    "session_ids": []
  }
}
```

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Create a new Pull Request.
