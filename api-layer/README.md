<!--
Copyright AGNTCY Contributors (https://github.com/agntcy)
SPDX-License-Identifier: Apache-2.0
-->

# API layer

The API layer is a REST API service that plugs on top of a DB and allows to abstract the underneath DB to downstream users. Currently, the API layer is supporting Clickhouse DB, but support for other DB can be added (contributions are welcome!).

## Local deployment

You can deploy a clickhouse DB and the API layer through the docker compose file that is [here](../deploy/docker-compose.yaml). A swagger is available for the API layer to see all the available API endpoints.

To deploy it, simply run the following:

```
cd ../deploy/
docker-compose up -d
```

Alternatively, you can run manually the API layer with the following command:

```
task api-layer-run
```
