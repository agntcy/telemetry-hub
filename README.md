# Agntcy - Telemetry Hub

This is a monorepo that contains the code for the API layer, and the metrics computation engine (MCE) of the AGNTCY observability and evaluation platform.


The API layer is responsible for accessing an Otel compatible database (like Clickhouse DB), to fetch telemetry that pushed to this database by an application.

The MCE is responsible for computing metrics from the telemetry data fetched by the API layer. It provides a REST API to compute metrics on a given set of sessions/spans.

# Getting Started

## Prerequisites

- Docker and Docker Compose installed on your machine.
- Python 3.11 or higher installed (for local development).
- An OpenAI API key for the MCE to compute metrics that require it.
- Clickhouse database running (if not using the provided Docker Compose setup).
- An instrumented application that sends telemetry data that uses the IoA Observe SDK (https://github.com/agntcy/observe/) to Clickhouse DB.

## Deployment

To run the API layer and MCE, you can use the provided Docker Compose setup. This will also set up Clickhouse, the API layer, and the MCE in a single command.

```bash
cd deploy/
docker-compose up -d
```

Once this is deployed, you can generate traces from an agentic app instrumented with our SDK, and pushing data to the newly deployed OTel collector. For more information on how to instrument your app, please refer to the [Observe SDK documentation](https://github.com/agntcy/observe/).

## Python Package Installation

For local development or custom deployments, you can install the Metrics Computation Engine and its plugins directly via pip:

### Quick Start - Complete Platform
```bash
# Install everything - core MCE + all adapters + native metrics
pip install "metrics-computation-engine[all]"
```

### Selective Installation
```bash
# Core MCE only
pip install metrics-computation-engine

# Core + specific adapters
pip install "metrics-computation-engine[deepeval]"
pip install "metrics-computation-engine[ragas]"
pip install "metrics-computation-engine[opik]"

# Core + native LLM-based metrics
pip install "metrics-computation-engine[metrics-plugin]"

# Core + all external adapters (no native metrics)
pip install "metrics-computation-engine[adapters]"

# Mix and match as needed
pip install "metrics-computation-engine[deepeval,metrics-plugin]"
```

> **Note for zsh users**: If you encounter `zsh: no matches found` errors, make sure to quote the package name with extras (e.g., `"metrics-computation-engine[opik]"`). This is because zsh treats square brackets as glob patterns.

### What Each Option Provides

| Option | Components | Use Case |
|--------|------------|----------|
| `[deepeval]` | DeepEval framework integration | Use DeepEval's comprehensive evaluation suite |
| `[ragas]` | RAGAS framework integration | RAG-specific evaluation metrics |
| `[opik]` | Opik framework integration | Comet ML's LLM evaluation platform |
| `[metrics-plugin]` | 10 native LLM-based session and 3 native span metrics | Advanced AI agent evaluation (see detailed list below) |
| `[adapters]` | All external framework adapters | Multi-framework evaluation capability |
| `[all]` | Everything above | Complete evaluation platform |

After installation, start the server:
```bash
mce-server
```

### Native Metrics Plugin - Complete List

The `[metrics-plugin]` option installs **13 advanced session-level and span metrics** for comprehensive AI agent evaluation:

#### LLM-as-a-Judge Evaluation Session Metrics (10)
- **ComponentConflictRate** - Evaluates if components contradict or interfere with each other
- **Consistency** - Evaluates consistency across responses and actions
- **ContextPreservation** - Evaluates maintenance of context throughout conversations
- **GoalSuccessRate** - Measures if responses achieve user's specified goals
- **Groundedness** - Evaluates how well responses are grounded in verifiable data and avoid hallucinations
- **InformationRetention** - Assesses how well information is retained across interactions
- **IntentRecognitionAccuracy** - Measures accuracy of understanding user intents
- **ResponseCompleteness** - Evaluates how completely responses address user queries
- **WorkflowCohesionIndex** - Measures how cohesively workflow components work together
- **WorkflowEfficiency** - Measures efficiency using agent transition patterns

#### LLM Confidence/Uncertainty Span Metrics (3)
- **LLMAverageConfidence** - Computes average confidence from LLM token probabilities
- **LLMMaximumConfidence** - Finds maximum confidence score in a session
- **LLMMinimumConfidence** - Finds minimum confidence score in a session

**Quick Installation:**
```bash
pip install "metrics-computation-engine[metrics-plugin]"
```

For detailed configuration and usage instructions, see the [MCE documentation](./metrics_computation_engine/README.md).
