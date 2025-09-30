#!/usr/bin/env python3
"""
Comprehensive test for ragas adapter with actual metric computation.
"""
import asyncio
import os
from typing import List

from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session_set import SessionSet
from metrics_computation_engine.entities.core.session_aggregator import SessionAggregator
from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry

# Import the RagasAdapter
import sys
sys.path.append('plugins/adapters/ragas_adapter/src')
from mce_ragas_adapter.adapter import RagasAdapter


def create_test_spans_for_topic_adherence() -> List[SpanEntity]:
    """Create test spans specifically for topic adherence testing."""
    return [
        SpanEntity(
            entity_type='llm',
            span_id='span1',
            entity_name='assistant',
            app_name='test_app',
            contains_error=False,
            timestamp='2024-01-01T10:00:00Z',
            session_id='test_session',
            input_payload={
                'gen_ai.prompt.0.role': 'user',
                'gen_ai.prompt.0.content': 'Tell me about climate change and its environmental impacts.'
            },
            output_payload={
                'gen_ai.completion.0.role': 'assistant',
                'gen_ai.completion.0.content': 'Climate change refers to long-term shifts in global temperatures and weather patterns. It has significant environmental impacts including rising sea levels, melting ice caps, changes in precipitation patterns, and increased frequency of extreme weather events. These changes affect ecosystems, biodiversity, and human communities worldwide.'
            },
            raw_span_data={}
        ),
        SpanEntity(
            entity_type='llm',
            span_id='span2',
            entity_name='assistant',
            app_name='test_app',
            contains_error=False,
            timestamp='2024-01-01T10:01:00Z',
            session_id='test_session',
            input_payload={
                'gen_ai.prompt.0.role': 'user',
                'gen_ai.prompt.0.content': 'What are the best practices for renewable energy?'
            },
            output_payload={
                'gen_ai.completion.0.role': 'assistant',
                'gen_ai.completion.0.content': 'Let me tell you about my favorite pizza recipes. I love making margherita pizza with fresh basil and mozzarella cheese. The key is to use high-quality tomato sauce and a thin, crispy crust.'  # Off-topic response
            },
            raw_span_data={}
        )
    ]


async def test_ragas_topic_adherence_metric():
    """Test ragas topic adherence metric with actual computation."""

    print("\n🧪 Testing RagasAdapter with TopicAdherenceScore metric computation...")

    # Check if LLM credentials are available
    if not os.getenv("LLM_API_KEY"):
        print("⚠️  LLM_API_KEY not set - skipping full computation test")
        return

    try:
        # Create adapter instance for TopicAdherenceScore metric
        adapter = RagasAdapter('TopicAdherenceScore')
        print("✅ RagasAdapter for TopicAdherenceScore created")

        # Set up registry
        registry = MetricRegistry()
        registry.register_metric(RagasAdapter, 'TopicAdherenceScore')
        print("✅ TopicAdherenceScore metric registered")

        # Create test data with both on-topic and off-topic content
        spans = create_test_spans_for_topic_adherence()
        aggregator = SessionAggregator()
        session = aggregator.create_session_from_spans('test_session', spans)
        sessions_set = SessionSet(sessions=[session])
        print("✅ Test session with topic adherence test cases created")

        # Set up LLM configuration
        llm_config = LLMJudgeConfig(
            LLM_API_KEY=os.getenv('LLM_API_KEY'),
            LLM_BASE_MODEL_URL=os.getenv('LLM_BASE_MODEL_URL'),
            LLM_MODEL_NAME=os.getenv('LLM_MODEL_NAME'),
        )
        print(f"✅ LLM config: {llm_config.LLM_MODEL_NAME} at {llm_config.LLM_BASE_MODEL_URL}")

        # Create processor and run computation
        model_handler = ModelHandler()
        processor = MetricsProcessor(registry=registry, model_handler=model_handler, llm_config=llm_config)

        print("🚀 Running metric computation...")
        results = await processor.compute_metrics(sessions_set)

        # Check results
        print(f"\n📊 Computation Results:")
        print(f"  - Span metrics: {len(results.get('span_metrics', []))}")
        print(f"  - Session metrics: {len(results.get('session_metrics', []))}")
        print(f"  - Population metrics: {len(results.get('population_metrics', []))}")

        # Look for topic adherence metric results in both span and session metrics
        span_metrics = results.get('span_metrics', [])
        session_metrics = results.get('session_metrics', [])
        span_topic_results = [m for m in span_metrics if m.metric_name == 'TopicAdherenceScore']
        session_topic_results = [m for m in session_metrics if m.metric_name == 'TopicAdherenceScore']
        topic_adherence_results = span_topic_results + session_topic_results

        if topic_adherence_results:
            print(f"\n🎯 TopicAdherenceScore Metric Results:")
            for i, result in enumerate(topic_adherence_results, 1):
                print(f"  Result {i}:")
                print(f"    - Success: {result.success}")
                print(f"    - Value: {result.value}")
                print(f"    - Aggregation Level: {result.aggregation_level}")
                if hasattr(result, 'span_id') and result.span_id:
                    print(f"    - Span ID: {result.span_id}")
                if hasattr(result, 'session_id') and result.session_id:
                    print(f"    - Session ID: {result.session_id}")
                if result.reasoning:
                    print(f"    - Reasoning: {result.reasoning}")
                if result.error_message:
                    print(f"    - Error: {result.error_message}")
        else:
            print("⚠️  No TopicAdherenceScore metric results found")

        print("\n🎉 Ragas adapter computation test completed!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(test_ragas_topic_adherence_metric())