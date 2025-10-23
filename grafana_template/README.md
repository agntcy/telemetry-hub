# Grafana Metric Template

This is a Grafana template for a simple dashboard that displays a single metric, showcasing how to integrate metrics computed by the MCE into a complete dashboard.

## How it works

When importing the JSON into Grafana, it will ask for a connection to a ClickHouse DB. Once provided, the dashboard can be loaded.

This dashboard has three variables:

- `Application Name`: allows you to select only the sessions of a particular application, should you have more than one application monitored. Leaving it blank means that all sessions will be considered.
- `Session ID`: a dropdown list to select a session among the ones filtered (once the application name is applied).
- `Metric Name`: a text box where you fill in the name of the metric you want to see.

To assist with the selection of the `Metric Name`, once the session ID is selected, the first panel of the dashboard will provide the list of available metrics for that particular session.

Once the `Metric Name` is set, the second panel of the dashboard will display the value of the selected metric as a gauge. It assumes that the metric is a percentage value.

## Limitations

- The gauge visualization is designed for percentage values (0-100%)
- Requires metrics to be pre-computed by the MCE and stored in ClickHouse
- It currently does not support `PassiveEvalApp` and `PassiveEvalAgents` as the stored structure of these metrics is different at the moment.
