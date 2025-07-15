# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import os

import pandas as pd

from metrics_computation_engine.metrics.span import (
    ToolUtilizationAccuracy,
)
from metrics_computation_engine.metrics.session import (
    AgentToAgentInteractions,
)
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry


async def main():
    data = json.load(open("./data/otel_traces.json", "r"))
    data_df = pd.DataFrame(data)

    llm_config = {
        "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        "LLM_MODEL_NAME": os.environ["LLM_MODEL_NAME"],
        "LLM_BASE_MODEL_URL": os.environ.get("LLM_BASE_MODEL_URL", ""),
        "CUSTOM_API_KEY": os.environ.get("CUSTOM_API_KEY", ""),
    }

    registry = MetricRegistry()
    registry.register_metric(ToolUtilizationAccuracy)  # Span level: Uses LLM-as-a-Judge
    registry.register_metric(AgentToAgentInteractions)  # Session Level
    print(registry.list_metrics())

    processor = MetricsProcessor(registry, llm_config=llm_config)
    results = await processor.compute_metrics(data_df)
    print(results)


asyncio.run(main())
