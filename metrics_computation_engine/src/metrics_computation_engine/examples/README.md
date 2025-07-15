# MCE usage

This folder contains a few tests to illustrate how the MCE can be used. This assumes that you have installed the MCE already.

## Run the MCE as a package

The test script `mce_as_package_test.py` showcase an example of how to use the MCE as a python package, that can be imported directly into your pipeline. In that case, the data is loaded directly from a json file (examples are provided in the `data/` folder).


## Run the MCE as a service

In this use case, the MCE is deployed as a service in a docker container (see `deploy/docker-compose.yaml`). The MCE is deployed along with the API layer, an instance of Clickhouse DB and an OTel Collector to which you can instrument an application to push telemetry data into.

We provide two test scripts to show how the MCE works in such setting: `service_test.py` and `simple_service_test.py`.

You can use the `load_clickhouse_db.sh` script to pre-load the Clickhouse DB with sample data to ease up your initial testing.
