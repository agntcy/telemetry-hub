# Metric Computation Engine

The Metric Computation Engine (MCE) is a tool for computing metrics from observability telemetry collected from our instrumentation SDK (https://github.com/agntcy/observe). The list of currently supported metrics is defined below, but the MCE was designed to make it easy to implement new metrics and extend the library over time.

The MCE is available as a Docker image for service deployment or as a Python package for direct integration. It can also be installed manually, as described below.

## Supported metrics

Metrics can be computed at three levels of aggregation: span level, session level and population level (which is a batch of sessions).

The current supported metrics are listed in the table below, along with their aggregation levels.
| Metric Name | Aggregation level |
| :---------: | :---------------: |
| Tool Utilisation Accuracy | Span |
| Tool Error | Span |
| Tool Error Rate | Session |
| Groundedness | Session |
| Agent to Agent Interactions | Session |
| Agent to Tool Interactions | Session |
| Cycles Count | Session |

**Tool Utilization Accuracy**: Measures the application's ability to select and use the appropriate tools efficiently.

**Tool Error**: Indicates whether a tool failed or not.

**Tool Error Rate**: Measures the rate of tool errors throughout a session.

**Groundedness**: Measures how much the output is backed by retrieved documents (in a RAG pipeline).

**Agent to Agent Interactions**: Counts the interactions between pairs of agents.

**Agent to Tool Interactions**: Counts the interactions between one agent and a tool.

**Cycle Count**: Counts how many times an entity returns to the previous entity.

## Prerequisites

Instrumentation of agentic apps must be done through [AGNTCY's observe SDK](https://github.com/agntcy/observe) as the MCE relies on its observability data schema.

## Getting started

Several [example scripts](./src/metrics_computation_engine/examples/) are available to help you get started with the MCE.

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

#### 2. LLM Judge Config (Optional)

The `llm_judge_config` parameter configures the LLM used for metrics that require LLM-as-a-Judge evaluation (such as `ToolUtilizationAccuracy` and `Groundedness`). When deploying as a service, LLM credentials can be configured via a `.env` file, making this parameter optional. If you do provide `llm_judge_config`, it will override the default credentials from the environment.

**Configuration options:**
- **LLM_MODEL_NAME**: The specific model to use (e.g., "gpt-4o")
- **LLM_BASE_MODEL_URL**: Base URL for LLM providers
- **LLM_API_KEY**: API key for model endpoints

**Example configurations:**

OpenAI:
```python
"llm_judge_config": {
    "LLM_MODEL_NAME": "gpt-4o",
    "LLM_BASE_MODEL_URL": "https://api.openai.com/v1",
    "LLM_API_KEY": "your-openai-api-key",
}
```

Anthropic:
```python
"llm_judge_config": {
    "LLM_MODEL_NAME": "claude-sonnet-4-20250514",
    "LLM_BASE_MODEL_URL": "https://api.anthropic.com/v1",
    "LLM_API_KEY": "your-anthropic-api-key",
}
```

Mistral:
```python
"llm_judge_config": {
    "LLM_MODEL_NAME": "mistral-large-latest",
    "LLM_BASE_MODEL_URL": "https://api.mistral.ai/v1",
    "LLM_API_KEY": "your-mistral-api-key",
}
```

Custom/Enterprise deployment:
```python
"llm_judge_config": {
    "LLM_MODEL_NAME": "your-model-name",
    "LLM_BASE_MODEL_URL": "https://your-enterprise-deployment-url",
    "LLM_API_KEY": "your-api-key",
}
```

**Note:** Most OpenAI-compatible LLM providers are supported. Replace the placeholder API keys with your actual credentials.

#### 3. Batch Config

The `batch_config` parameter determines which sessions from your database will be included in the metric computation. You have three options:

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

**Option 3: By App Name** (Not yet implemented)
```python
"batch_config": {
    "app_name": "my_agent_app"
}
```
This would retrieve agent sessions associated with a specific application or project name.

### Deployment as a service

For easy deployment of the MCE as a service, a [docker compose file](../deploy/docker-compose.yaml) is provided. This file locally deploys an instance of an OTel collector, an instance of Clickhouse DB, an instance of the API layer, and an instance of the MCE. OTel+Clickhouse is the default setup for retrieving and storing traces from agentic apps. The API layer provides an interface for other components such as the MCE to interact with the corresponding data. The MCE enables developers to measure their agentic applications.

When deploying as a service, you can configure LLM credentials using a `.env` file. This allows the system to define default credentials for LLM-as-a-Judge metrics without requiring the `llm_judge_config` parameter in each request. However, if you do provide `llm_judge_config` in your request, those credentials will take priority over the environment configuration.

To set up LLM credentials for service deployment, update the `env_file` path in the docker compose configuration:

```yaml
env_file:
  - ../metrics_computation_engine/.env.example
```

Once deployed, you can generate traces from an agentic app instrumented with our [Observe SDK](https://github.com/agntcy/observe/tree/main).

**API Endpoints**

- `GET /` - Returns endpoints
- `GET /status` - Get server status response
- `POST /compute_metrics` - Compute metrics from provided configuration

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

   Configure the following variables in your `.env` file:

   **Server Configuration:**
   - `HOST` - Server host (default: 0.0.0.0)
   - `PORT` - Server port (default: 8000)
   - `RELOAD` - Enable auto-reload (default: false)
   - `API_BASE_URL` - Data API endpoint (default: http://localhost:8080)

   **LLM Configuration:**
   - `LLM_BASE_MODEL_URL` - LLM endpoint (default: https://api.openai.com/v1)
   - `LLM_MODEL_NAME` - LLM Model name (default: gpt-4o)
   - `LLM_API_KEY` - LLM API key for LLM-based metrics, (Tested and supports most OpenAI compatible endpoints)

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

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Create a new Pull Request.
