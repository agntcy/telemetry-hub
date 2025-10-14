# Metric Computation Engine

The Metric Computation Engine (MCE) is a tool for computing metrics from observability telemetry collected from our instrumentation SDK (https://github.com/agntcy/observe). The list of currently supported metrics is defined below, but the MCE was designed to make it easy to implement new metrics and extend the library over time.

## Prerequisites

- **Python 3.11 or higher**
- **[uv](https://docs.astral.sh/uv/) package manager** for dependency management
- **LLM API Key** (OpenAI, or custom endpoint) for LLM-based metrics
- **Mock LLM Proxy** (optional) use `mock-llm-proxy` CLI for local testing without real API keys
- **Agentic App**: Get started with [coffeeAgntcy](https://github.com/agntcy/coffeeAgntcy) reference Agentic App implementation using the AGNTCY ecosystem.
- **Instrumentation**: Agentic apps must be instrumented with [AGNTCY's observe SDK](https://github.com/agntcy/observe) as the MCE relies on its observability data schema

## Supported metrics

Metrics can be computed at three levels of aggregation: span level, session level and population level (which is a batch of sessions).

The current supported metrics are listed in the table below, along with their aggregation levels.

### Core Metrics

#### Span-Level Metrics
| Metric Name | Description |
| :---------: | :---------- |
| **Tool Utilization Accuracy** | Measures tool selection and usage efficiency |

#### Session-Level Metrics
| Metric Name | Description |
| :---------: | :---------- |
| **Agent to Agent Interactions** | Counts interactions between pairs of agents |
| **Agent to Tool Interactions** | Counts interactions between agents and tools |
| **Tool Error Rate** | Rate of tool errors throughout a session |
| **Cycles Count** | How many times an entity returns to previous entity |

#### Population-Level Metrics
| Metric Name | Description |
| :---------: | :---------- |
| **Graph Determinism Score** | Measures variance in execution patterns across multiple sessions |

## Plugin Architecture

The MCE uses a plugin-based architecture for extensibility:

- **Native Metrics Plugins**: Unique agent metrics to evaluate conversation, orchestration, tool usage quality
- **Third-party Adapter Plugins**: Third-party framework integrations (RAGAS, DeepEval, Opik)

### Native Metrics Plugin

The MCE includes a comprehensive **native metrics plugin** that provides 13 advanced session-level and span-level metrics for AI agent evaluation. These metrics use LLM-as-a-Judge techniques and confidence analysis for comprehensive assessment. For additional plugin metrics and detailed descriptions, see the Native Metrics Plugin README: [plugins/mce_metrics_plugin/README.md](./plugins/mce_metrics_plugin/README.md).

### Third-party Adapters

The MCE supports integration with popular evaluation frameworks through adapter plugins:

- **[DeepEval](https://github.com/confident-ai/deepeval)** - [plugins/adapters/deepeval_adapter/README.md](./plugins/adapters/deepeval_adapter/README.md)
- **[Opik](https://github.com/comet-ml/opik)** - [plugins/adapters/opik_adapter/README.md](./plugins/adapters/opik_adapter/README.md)
- **[RAGAS](https://github.com/explodinggradients/ragas)** - [plugins/adapters/ragas_adapter/README.md](./plugins/adapters/ragas_adapter/README.md)


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

# Mix and match as needed
pip install "metrics-computation-engine[deepeval,metrics-plugin]"
```

Note for zsh users: If you encounter `zsh: no matches found` errors, quote the package name with extras (e.g., `"metrics-computation-engine[opik]"`).


## Getting started

### Environment Configuration

Configure the following variables in your `.env` file:

```bash
# Server Configuration
HOST=0.0.0.0                    # MCE Server bind address
PORT=8000                       # MCE Server port
RELOAD=false                    # Enable auto-reload for development
LOG_LEVEL=info                  # Logging level (debug, info, warning, error)

# Data Access Configuration
API_BASE_URL=http://localhost:8080       # API-layer endpoint
PAGINATION_LIMIT=50                      # Max sessions per API request
PAGINATION_DEFAULT_MAX_SESSIONS=50       # Default max sessions when not specified
SESSIONS_TRACES_MAX=20                   # Max sessions per batch for trace retrieval

# LLM Configuration
LLM_BASE_MODEL_URL=https://api.openai.com/v1  # LLM API endpoint
LLM_MODEL_NAME=gpt-4o                          # LLM model name
LLM_API_KEY=sk-...                             # LLM API key
```

**Note**: LLM configuration can be provided via environment variables (global defaults) or per-request in the `llm_judge_config` parameter. Request-level configuration takes precedence.

### Mock LiteLLM Proxy

For local development you can avoid using real API keys by starting the bundled mock proxy. It implements the `POST /chat/completions` endpoint expected by LiteLLM and returns deterministic scores.

```bash
uv run mock-llm-proxy --port 8010
```

Update your `.env` or per-request config to point at the proxy:

```json
"llm_judge_config": {
  "LLM_BASE_MODEL_URL": "http://localhost:8010",
  "LLM_MODEL_NAME": "mock-model",
  "LLM_API_KEY": "test"
}
```

CLI options let you tune the score and reasoning. Run `uv run mock-llm-proxy --help` for the full list.

### Examples Directory

Several [example scripts](./src/metrics_computation_engine/examples/) are available to help you get started with the MCE:

- **Basic usage — service** (`service_test.py`): Sends a request to a running MCE server (POST `/compute_metrics`) with `metrics`, `llm_judge_config`, and `data_fetching_infos.batch_config.time_range`.
- **Basic usage — library** (`mce-demo.py`): Runs MCE in-process. Loads `data/sample_data.json`, builds a `MetricRegistry`, registers core and native plugin metrics, demonstrates 3rd‑party adapters (DeepEval, Opik), and executes `MetricsProcessor` with `LLMJudgeConfig` from `.env`.
- **Sample data** (`data/sample_data.json`): Synthetic raw spans used by `mce-demo.py`.

### MCE usage

The MCE can be used in two ways: as a [REST API service](./src/metrics_computation_engine/examples/service_test.py) or as a [Python module](./src/metrics_computation_engine/examples/mce-demo.py). Both methods allow you to compute various metrics on your agent telemetry data.

There are three main input parameters to the MCE, as shown in the examples above: `metrics`, `llm_judge_config`, and `data_fetching_infos`.

#### Metrics Parameter

The `metrics` parameter is a list of metric names that you want to compute. Each metric operates at different levels (span, session, or population) and may have different computational requirements. You can specify any combination of the available metrics:

```python
"metrics": [
    "ToolUtilizationAccuracy",
    "ToolError",
    "ToolErrorRate",
    "AgentToToolInteractions",
    "AgentToAgentInteractions",
    "CyclesCount",
    "Groundedness",
]
```

##### Using 3rd‑party adapters (RAGAS, DeepEval, Opik)

You can request 3rd‑party framework metrics through adapter plugins by using a dotted identifier in `metrics`:

- `deepeval.<MetricName>` (e.g., `deepeval.AnswerRelevancyMetric`)
- `opik.<MetricName>` (e.g., `opik.Hallucination`)
- `ragas.<MetricName>` (see adapter README for available names)

```python
"metrics": [
    "deepeval.AnswerRelevancyMetric",
]
```

#### LLM Judge Config

The `llm_judge_config` parameter configures the LLM used for metrics that require LLM-as-a-Judge evaluation (such as `ToolUtilizationAccuracy` and `Groundedness`):

```python
"llm_judge_config": {
    "LLM_API_KEY": "your_api_key", # API key for your LLM provider
    "LLM_MODEL_NAME": "gpt-4o", # The specific model to use (e.g., "gpt-4o")
    "LLM_BASE_MODEL_URL": "https://api.openai.com/v1" # API endpoint URL (supports OpenAI-compatible APIs)
}
```

#### Data Fetching Infos

Use `data_fetching_infos` to select which sessions to evaluate. You can provide a time range via `batch_config.time_range`, explicit `session_ids`, or both.

**By time range**
```json
"data_fetching_infos": {
  "batch_config": {
    "time_range": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-12-31T23:59:59Z"
    }
  },
  "session_ids": []
}
```

**By explicit session IDs**
```json
"data_fetching_infos": {
  "batch_config": {},
  "session_ids": ["<session_id_1>", "<session_id_2>", ... "<session_id_n>"]
}
```

### Deployment as a service

There are two ways to run the MCE service:

1. Docker Compose (recommended for a full local stack)
   - Use the provided [docker compose file](../deploy/docker-compose.yaml) to start OTel Collector, ClickHouse, the API layer, and the MCE.
   - Once up, instrument an app with our [Observe SDK](https://github.com/agntcy/observe/tree/main) to generate traces.

2. Run the server locally
   - Activate your virtual environment and start the server:
     ```bash
     source .venv/bin/activate
     mce-server
     ```
     or
     ```bash
     .venv/bin/activate
     uv run --env-file .env mce-server
     ```

**API Endpoints**

- `GET /` - Returns available endpoints
- `GET /metrics` - List all available metrics and their metadata
- `GET /status` - Health check and server status
- `POST /compute_metrics` - Compute metrics from JSON configuration (see examples/service_test.py)

The server provides automatic OpenAPI documentation at `http://<HOST>:<PORT>/docs` when running.

You can run the MCE by making a curl call to the endpoint `<HOST>:<PORT>` as defined in the `.env`. Perform an evaluation by sending a request to `/compute_metrics`:

Example:
```bash
curl -sS -X POST "http://<HOST>:<PORT>/compute_metrics" \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": [
      "Groundedness"
    ],
    "llm_judge_config": {
      "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
      "LLM_MODEL_NAME": "gpt-4o",
      "LLM_API_KEY": "api-key"
    },
    "data_fetching_infos": {
      "batch_config": {"time_range": {"start": "2000-06-20T15:04:05Z", "end": "2040-06-29T08:52:55Z"}},
      "session_ids": []
    }
  }'
```

## Troubleshooting

**Common Issues:**

- **`ModuleNotFoundError`**: Ensure virtual environment is activated and dependencies installed via `./install.sh`
- **LLM API Errors**: Verify API keys in `.env` file and check rate limits
- **Plugin Load Failures**: Run `./install-plugins.sh` to install required adapter plugins
- **Memory Issues**: Reduce batch sizes in configuration for large datasets
- **Docker Build Failures**: Check Docker daemon is running and remove any cached layers

For detailed debugging, enable verbose logging by setting `LOG_LEVEL=DEBUG` in your environment.

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Create a new Pull Request.
