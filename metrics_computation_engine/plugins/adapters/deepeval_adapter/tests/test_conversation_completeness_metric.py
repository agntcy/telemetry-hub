# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os

import pytest

from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict

# Import the DeepEvalMetricAdapter directly from the plugin system
from mce_deepeval_adapter.adapter import DeepEvalMetricAdapter


@pytest.mark.asyncio
async def test_conversation_completeness_metric():
    """Test ConversationCompletenessMetric end-to-end using env-provided LLM creds."""

    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY not set; skipping DeepEval metric test")

    # Build minimal session containing at least two llm spans (adapter uses [-2])
    spans = [
        SpanEntity(
            entity_type="llm",
            span_id="1",
            entity_name="assistant",
            contains_error=False,
            timestamp="2024-01-01T10:00:00Z",
            parent_span_id=None,
            trace_id="trace1",
            session_id="session1",
            start_time=None,
            end_time=None,
            input_payload={
                "gen_ai.prompt.0.role": "user",
                "gen_ai.prompt.0.content": "What is 2+2?",
            },
            output_payload={
                "gen_ai.completion.0.role": "assistant",
                "gen_ai.completion.0.content": "4",
            },
            raw_span_data={},
        ),
        SpanEntity(
            entity_type="llm",
            span_id="2",
            entity_name="assistant",
            contains_error=False,
            timestamp="2024-01-01T10:01:00Z",
            parent_span_id=None,
            trace_id="trace1",
            session_id="session1",
            start_time=None,
            end_time=None,
            input_payload={
                "gen_ai.prompt.0.role": "user",
                "gen_ai.prompt.0.content": "Thanks!",
            },
            output_payload={
                "gen_ai.completion.0.role": "assistant",
                "gen_ai.completion.0.content": "You're welcome.",
            },
            raw_span_data={},
        ),
    ]

    # Compute via processor so model is constructed via ModelHandler
    registry = MetricRegistry()
    # Create an instance of the adapter with the specific metric name
    adapter_instance = DeepEvalMetricAdapter("ConversationCompletenessMetric")
    registry.register_metric(
        adapter_instance.__class__, "ConversationCompletenessMetric"
    )

    # Explicitly set LLM config from environment variables
    llm_config = LLMJudgeConfig(
        LLM_API_KEY=os.getenv("LLM_API_KEY", ""),
        LLM_BASE_MODEL_URL=os.getenv("LLM_BASE_MODEL_URL", ""),
        LLM_MODEL_NAME=os.getenv("LLM_MODEL_NAME", ""),
    )

    model_handler = ModelHandler()
    processor = MetricsProcessor(
        registry=registry,
        model_handler=model_handler,
        llm_config=llm_config,
    )

    traces_by_session = {spans[0].session_id: spans}
    session_entities = build_session_entities_from_dict(traces_by_session)
    sessions_data = {entity.session_id: entity for entity in session_entities}

    results = await processor.compute_metrics(sessions_data)

    # Validate result shape and value
    session_metrics = results.get("session_metrics", [])

    assert (
        len(session_metrics) == 1
    ), f"Expected exactly 1 session metric, got {len(session_metrics)}"
    cc = session_metrics[0]  # Only metric we registered
    assert (
        cc.metric_name == "ConversationCompletenessMetric"
    )  # Verify it's the expected metric
    assert isinstance(cc.value, float)
    assert 0.0 <= cc.value <= 1.0
    assert cc.success is True
