# Metric Computation Engine - Plugin

Creating plugin for the MCE allows to easily add metrics to the MCE, without having to fork the whole repo.
We provide some examples of plugins that are  in the `plugins/` folder.

# Plugin Development Guide

This guide explains how to create plugins that are automatically discovered by the MCE metrics listing system.

## Plugin Entry Points

For plugins to be automatically discovered by the MCE, they must define proper entry points in their `pyproject.toml` file, following this structure:

```toml
[project.entry-points."metrics_computation_engine.plugins"]
MetricName = "path.in.module:MetricClass"
```

A dummy example plugin is provided in the `example_plugin/` folder. It contains a single metric, called `SpanCounter`. If you look at the `pyproject.toml` for this plugin, you will see that the entry-point is defined as:

```toml
[project.entry-points."metrics_computation_engine.plugins"]
SpanCounter = "span_counter:SpanCounter"
```

This tells the system:
- **Entry point name**: `SpanCounter` (how it appears in listings)
- **Package**: `span_counter` (the Python package name)
- **Class**: `SpanCounter` (the metric class to load)

## Plugin Requirements

Your plugin class must:

1. **Inherit from BaseMetric**:
   ```python
   from metrics_computation_engine.metrics.base import BaseMetric

   class YourPlugin(BaseMetric):
       pass
   ```

2. **Define the required attributes**:
   ```python
   def __init__(self, jury=None, dataset=None):
       super().__init__(jury=jury, dataset=dataset)
       self.name = "YourPluginName"
       self.aggregation_level = "session"  # or "span"
   ```

3. **Implement the required methods**:
   ```python
   @property
   def required_parameters(self) -> List[str]:
       return []  # List of required parameters

   def validate_config(self) -> bool:
       return True  # Validation logic

   async def compute(self, data):
       # Your computation logic
       return MetricResult(...)
   ```

# Installation Options

There are two main options to install a plugin to be used with the MCE.

## Method 1: As a pacakge
Assuming that the plugin comes as a wheel package, you can simply install the package on your system and it will be detected by the MCE.

`uv pip install plugin-package.whl`

## Method 2: From source code

You can run the following snippet to install the plugin in your virtual env, where you have the MCE running:
`uv pip install path/to/plugin/root/folder`

## Uninstalling

To uninstall a plugin, simply uninstall the package.

## Check plugins installation with the MCE

List available metrics from the cli.
```bash
uv run --env-file .env  mce-cli list-metrics
```
