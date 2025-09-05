# Metric Computation Engine

The Metric Computation Engine (MCE) is a tool for computing metrics from observability telemetry collected from our instrumentation SDK (https://github.com/agntcy/observe). The list of currently supported metrics is defined below, but the MCE was designed to make it easy to implement new metrics and extend the library over time.

The MCE is available as a Docker image for service deployment or as a Python package for direct integration. It can also be installed manually, as described below.

## Supported metrics

Metrics can be computed at three levels of aggregation: span level, session level and population level (which is a batch of sessions).

The current supported metrics are listed in the table below, along with their aggregation levels.

### Core Metrics

#### Span-Level Metrics
| Metric Name | Description |
| :---------: | :---------- |
| **Tool Utilization Accuracy** | Measures tool selection and usage efficiency |
| **Tool Error** | Indicates whether a tool failed or not |
| **Agent Interpretation Score** | Measures the value of an agent interaction |
| **Task Delegation Accuracy** | Assesses if task delegation was accurate with respect to input |
| **Hallucination Detection** | Detects hallucinations in LLM outputs *(in development)* |

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

### 🆕 Custom Evaluation Metrics (MCE Plugin)
| Metric Name | Aggregation level | Description |
| :---------: | :---------------: | :---------- |
| **Component Conflict Rate** | Session | Evaluates if components contradict or interfere with each other |
| **Goal Success Rate** | Session | Measures if responses achieve user's specified goals |
| **Response Completeness** | Session | Evaluates how completely responses address user queries |
| **Workflow Efficiency** | Session | Measures efficiency using agent transition patterns |
| **Context Preservation** | Session | Evaluates maintenance of context throughout conversations |
| **Information Retention** | Session | Assesses how well information is retained across interactions |
| **Intent Recognition Accuracy** | Session | Measures accuracy of understanding user intents |
| **Consistency** | Session | Evaluates consistency across responses and actions |
| **Workflow Cohesion Index** | Session | Measures how cohesively workflow components work together |

The **Custom Evaluation Metrics** from the MCE Plugin provide advanced LLM as a Judge based evaluations for comprehensive agent performance assessment. These metrics use sophisticated prompting techniques to evaluate qualitative aspects of agent interactions and outcomes.

## Third-party Integrations

The MCE supports integration with popular evaluation frameworks through adapter plugins:

- **[RAGAS](https://github.com/explodinggradients/ragas)**
- **[DeepEval](https://github.com/confident-ai/deepeval)** - Comprehensive LLM evaluation suite
- **[Opik](https://github.com/comet-ml/opik)** - LLM observability and evaluation platform

Each adapter automatically converts MCE data formats to framework-specific schemas for seamless integration.

## Prerequisites

- **Python 3.10 or higher**
- **[uv](https://docs.astral.sh/uv/) package manager** for dependency management
- **LLM API Key** (OpenAI, or custom endpoint) for LLM-based metrics
- **Instrumentation**: Agentic apps must be instrumented with [AGNTCY's observe SDK](https://github.com/agntcy/observe) as the MCE relies on its observability data schema

## Getting started

Several [example scripts](./src/metrics_computation_engine/examples/) are available to help you get started with the MCE.

### Examples Directory

The examples directory contains 40+ scripts organized by use case:

- **Basic Usage**: `service_test.py`, `simple_service_test.py` - API and module integration
- **Metrics Testing**: `test_single_agent_metrics.py`, `test_span_metrics.py` - Individual metric validation
- **Third-party Integration**: `plugin_w_mce_as_library.py` - DeepEval, RAGAS integration examples
- **Debugging & Analysis**: `debug_tool_util.py`, `analyze_sessions.py` - Troubleshooting tools

Each script includes inline documentation and can be run independently with proper environment setup.

## Plugin Architecture

The MCE uses a plugin-based architecture for extensibility:

- **Core Metrics**: Built-in metrics for standard agent evaluation
- **Adapter Plugins**: Third-party framework integrations (RAGAS, DeepEval, Opik)
- **Custom Plugins**: User-defined metrics following the BaseMetric interface

See [README-plugin.md](./README-plugin.md) for detailed plugin development guide.

### MCE usage

The MCE can be used in two ways: as a [REST API service](./src/metrics_computation_engine/examples/service_test.py) or as a [Python module](./src/metrics_computation_engine/examples/mce_as_package_test.py). Both methods allow you to compute various metrics on your agent telemetry data. The preferred usage for the MCE is to deploy it as a service.

There are three main input parameters to the MCE, as you will see in the above test code: `metrics`, `llm_judge_config`, and `batch_config`.

#### 1. Metrics Parameter

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

#### 2. LLM Judge Config

The `llm_judge_config` parameter configures the LLM used for metrics that require LLM-as-a-Judge evaluation (such as `ToolUtilizationAccuracy` and `Groundedness`):

```python
"llm_judge_config": {
    "LLM_API_KEY": "your_api_key",
    "LLM_MODEL_NAME": "gpt-4o",
    "LLM_BASE_MODEL_URL": "https://api.openai.com/v1"
}
```

**Configuration options:**
- **LLM_API_KEY**: API key for your LLM provider
- **LLM_MODEL_NAME**: The specific model to use (e.g., "gpt-4o")
- **LLM_BASE_MODEL_URL**: API endpoint URL (supports OpenAI-compatible APIs)

#### 3. Batch Config

The `batch_config` parameter determines which sessions from your database will be included in the metric computation. You have three options (they can be mixed):

**Option 1: By Number of Sessions**
```python
"batch_config": {
    "num_sessions": 10  # Get the last 10 sessions
}
```
This retrieves the most recent N agent sessions from the database.

**Option 2: By Time Range**
```python
"batch_config": {
    "time_range": {
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-12-31T23:59:59Z"
    }
}
```
This retrieves all agent sessions that occurred within the specified time window.

**Option 3: By App Name**
```python
"batch_config": {
    "app_name": "my_agent_app"
}
```
This would retrieve agent sessions associated with a specific application or project name.

#### 4. Group of session

You can omit `batch_config` and use `session ids` for computing metrics for a given set of know session ids.
```python
"session_ids": ["1", "3"]
```
This retrieves sessions associated ids 1 and 3.


### Deployment as a service

For easy deployment of the MCE as a service, a [docker compose file](../deploy/docker-compose.yaml) is provided. This file locally deploys an instance of an OTel collector, an instance of Clickhouse DB, an instance of the API layer, and an instance of the MCE. OTel+Clickhouse is the default setup for retrieving and storing traces from agentic apps. The API layer provides an interface for other components such as the MCE to interact with the corresponding data. The MCE enables developers to measure their agentic applications.

Once deployed, you can generate traces from an agentic app instrumented with our [Observe SDK](https://github.com/agntcy/observe/tree/main).

**API Endpoints**

- `GET /` - Returns available endpoints
- `GET /metrics` - List all available metrics and their metadata
- `GET /status` - Health check and server status
- `POST /compute_metrics` - Compute metrics from JSON configuration (see examples/service_test.py)

The server provides automatic OpenAPI documentation at `http://localhost:8000/docs` when running.

### Manual installation for module usage.

To install MCE manually, you will need:
- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

1. **Install uv** (if not installed)
  If you are installing in the OS:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    or

    If you are installing in a virtual environment (mamba, conda):
    ```bash
    pip install uv
    ```
2. **Install the package**:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

## Environment Configuration

Configure the following variables in your `.env` file:

### Server Configuration
```bash
HOST=0.0.0.0                    # Server bind address
PORT=8000                       # Server port
RELOAD=false                    # Enable auto-reload for development
LOG_LEVEL=info                  # Logging level (debug, info, warning, error)
```

### Data Access Configuration
```bash
API_BASE_URL=http://localhost:8080       # API layer endpoint
PAGINATION_LIMIT=50                      # Max sessions per API request
PAGINATION_DEFAULT_MAX_SESSIONS=50       # Default max sessions when not specified
SESSIONS_TRACES_MAX=20                   # Max sessions per batch for trace retrieval
```

### LLM Configuration
```bash
LLM_BASE_MODEL_URL=https://api.openai.com/v1  # LLM API endpoint
LLM_MODEL_NAME=gpt-4o                          # LLM model name
LLM_API_KEY=sk-...                             # LLM API key
```

**Note**: LLM configuration can be provided via environment variables (global defaults) or per-request in the `llm_judge_config` parameter. Request-level configuration takes precedence.

4. **Run the server**:

   ```bash
   source .venv/bin/activate
   mce-server
   ```
   or

   ```bash
    .venv/bin/activate
   uv run --env-file .env  mce-server
   ```

The server will be available at `http://localhost:8000`
This assumes that you have the API layer deployed at the address defined through the env variable `API_BASE_URL`.

### Running Unit Tests

This project uses `pytest` for running unit tests.

1. **Run All Tests**:
   ```bash
   uv run pytest
   ```

2. **Run Tests in a Specific Folder**:
   ```bash
   uv run pytest tests/test_metrics
   ```

3. **Run a Specific Test File**:
   ```bash
   uv run pytest tests/mce_tests/test_metrics/session/test_agent_to_tool_interactions.py
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
