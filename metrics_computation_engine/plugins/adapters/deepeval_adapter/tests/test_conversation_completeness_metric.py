import os

import pytest

from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import ConversationElement
from metrics_computation_engine.entities.models.session_set import SessionSet
from metrics_computation_engine.entities.core.session_aggregator import SessionAggregator
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry

# Import the DeepEvalMetricAdapter directly from the plugin system
from mce_deepeval_adapter.adapter import DeepEvalMetricAdapter


def create_session_from_spans(spans):
    """Helper function to create a session entity from spans using the new SessionAggregator API."""
    if not spans:
        raise ValueError("No spans provided")

    aggregator = SessionAggregator()
    session_id = spans[0].session_id
    session = aggregator.create_session_from_spans(session_id, spans)

    # Manually populate conversation elements for deepeval adapter compatibility
    conversation_elements = []
    for span in spans:
        if span.entity_type == "llm":
            # Extract conversation from input payload
            if span.input_payload:
                for key, value in span.input_payload.items():
                    if key.startswith("gen_ai.prompt") and ".content" in key:
                        role_key = key.replace(".content", ".role")
                        role = span.input_payload.get(role_key, "user")
                        conversation_elements.append(ConversationElement(
                            role=role,
                            content=value
                        ))

            # Extract conversation from output payload
            if span.output_payload:
                for key, value in span.output_payload.items():
                    if key.startswith("gen_ai.completion") and ".content" in key:
                        role_key = key.replace(".content", ".role")
                        role = span.output_payload.get(role_key, "assistant")
                        conversation_elements.append(ConversationElement(
                            role=role,
                            content=value
                        ))

    # Set conversation elements on session
    session.conversation_elements = conversation_elements

    return session


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
                app_name="test_app",
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
                app_name="test_app",
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

    session_entity = create_session_from_spans(spans)
    sessions_set = SessionSet(sessions=[session_entity])

    results = await processor.compute_metrics(sessions_set)

    # Validate result shape and value
    session_metrics = results.get("session_metrics", [])

    assert len(session_metrics) == 1, (
        f"Expected exactly 1 session metric, got {len(session_metrics)}"
    )
    cc = session_metrics[0]  # Only metric we registered
    assert (
        cc.metric_name == "ConversationCompletenessMetric"
    )  # Verify it's the expected metric
    assert isinstance(cc.value, float)
    assert 0.0 <= cc.value <= 1.0
    assert cc.success is True
