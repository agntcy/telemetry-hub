# Agntcy - Telemetry Hub

This is a monorepo that contains the code for the API layer, and the metrics computation engine (MCE) of the AGNTCY observability and evaluation platform.


The API layer is responsible for accessing an Otel compatible database (like Clickhouse DB), to fetch telemetry that pushed to this database by an application.

The MCE is responsible for computing metrics from the telemetry data fetched by the API layer. It provides a REST API to compute metrics on a given set of sessions/spans.

# Getting Started

## Prerequisites

- Docker and Docker Compose installed on your machine.
- Python 3.8 or higher installed (for local development).
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
