# MCE Metrics Plugin

A comprehensive collection of extended MCE Evaluation Metrics for the [Metric Computation Engine (MCE)](https://github.com/agntcy/telemetry-hub/tree/main/metrics_computation_engine). This plugin extends MCE's core capabilities with advanced LLM-as-a-Judge based evaluations designed specifically for comprehensive agent performance assessment in agentic applications.

## Features

- **Advanced LLM-as-a-Judge Evaluations**: Sophisticated prompting techniques for qualitative assessment
- **Session-Level Analysis**: Comprehensive evaluation of complete agent interactions
- **Workflow Assessment**: Metrics focused on agent workflow efficiency and cohesion
- **Contextual Understanding**: Evaluation of context preservation and information retention
- **Goal-Oriented Metrics**: Assessment of goal achievement and intent recognition
- **Uncertainty Quantification**: LLM confidence scoring across interactions

## Installation

Install via MCE extras:
```bash
pip install "metrics-computation-engine[metrics-plugin]"
```

## Prerequisites

- [Metric Computation Engine (MCE)](https://github.com/agntcy/telemetry-hub/tree/main/metrics_computation_engine) installed
- Agentic applications instrumented with [AGNTCY's observe SDK](https://github.com/agntcy/observe)

## Available Metrics

All metrics operate at the **session level**, providing comprehensive evaluation throughout agent workflows.

### MCE Plugin Evaluation Metrics (MCE Plugin)

| Metric Name | Aggregation Level | Description |
|-------------|:-----------------:|-------------|
| **Component Conflict Rate** | Session | Evaluates if components contradict or interfere with each other |
| **Goal Success Rate** | Session | Measures if responses achieve user's specified goals |
| **Response Completeness** | Session | Evaluates how completely responses address user queries |
| **Workflow Efficiency** | Session | Measures efficiency using agent transition patterns |
| **Context Preservation** | Session | Evaluates maintenance of context throughout conversations |
| **Information Retention** | Session | Assesses how well information is retained across interactions |
| **Intent Recognition Accuracy** | Session | Measures accuracy of understanding user intents |
| **Consistency** | Session | Evaluates consistency across responses and actions |
| **Workflow Cohesion Index** | Session | Measures how cohesively workflow components work together |
| **Groundedness** | Session | Evaluates how well responses are grounded in available context and facts |

### LLM Confidence Metrics

| Metric Name | Aggregation Level | Description |
|-------------|:-----------------:|-------------|
| **LLM Average Confidence** | Session | Average confidence score across all LLM interactions in a session |
| **LLM Maximum Confidence** | Session | Highest confidence score observed in a session |
| **LLM Minimum Confidence** | Session | Lowest confidence score observed in a session |

## Usage

### Basic Usage

```python
import asyncio
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.requests import LLMJudgeConfig

# Import plugin metrics
from mce_metrics_plugin.session import (
    GoalSuccessRate,
    ContextPreservation,
    WorkflowCohesionIndex,
    ComponentConflictRate,
    ResponseCompleteness,
    InformationRetention,
    IntentRecognitionAccuracy,
)

async def evaluate_with_plugin():
    # Setup registry and register metrics
    registry = MetricRegistry()

    # Register plugin metrics directly by class
    session_metrics = [
        GoalSuccessRate,
        ContextPreservation,
        WorkflowCohesionIndex,
        ComponentConflictRate,
        ResponseCompleteness,
        InformationRetention,
        IntentRecognitionAccuracy,
    ]

    for metric in session_metrics:
        registry.register_metric(metric)

    # Configure LLM for judge-based metrics
    llm_config = LLMJudgeConfig(
        LLM_BASE_MODEL_URL="https://api.openai.com/v1",
        LLM_MODEL_NAME="gpt-4o",
        LLM_API_KEY="your-api-key-here"
    )

    # Process metrics
    model_handler = ModelHandler()
    processor = MetricsProcessor(
        model_handler=model_handler,
        registry=registry,
        llm_config=llm_config
    )

    # Load your session data
    # traces_by_session = load_your_session_data()

    results = await processor.compute_metrics(traces_by_session)
    return results
```

### Using with MCE Service

When using MCE as a REST API service, include plugin metrics in your request:

```json
{
  "metrics": [
    "GoalSuccessRate",
    "ContextPreservation",
    "WorkflowCohesionIndex",
    "ComponentConflictRate",
    "ResponseCompleteness",
    "Consistency",
    "Groundedness"
  ],
  "llm_judge_config": {
    "LLM_API_KEY": "your_api_key",
    "LLM_MODEL_NAME": "gpt-4o",
    "LLM_BASE_MODEL_URL": "https://api.openai.com/v1"
  },
  "data_fetching_infos": {
    "batch_config": {
      "time_range": { "start": "2000-06-20T15:04:05Z", "end": "2040-06-29T08:52:55Z" }
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

### Adding New Metrics

To add a new metric:

1. Create a new file in `src/mce_metrics_plugin/session/`
2. Implement the `BaseMetric` interface
3. Add entry point in `pyproject.toml`
4. Add tests in `tests/`
5. Update imports in `__init__.py`

Example metric structure:

```python
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult

class YourCustomMetric(BaseMetric):
    def __init__(self):
        super().__init__()
        self.name = "YourCustomMetric"
        self.aggregation_level = "session"

    async def compute(self, data: SessionEntity) -> MetricResult:
        # Implement your metric logic
        pass
```
