#!/usr/bin/env python3
"""
Comprehensive test for opik adapter with actual metric computation.
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

# Import the OpikMetricAdapter
import sys
sys.path.append('plugins/adapters/opik_adapter/src')
from mce_opik_adapter.adapter import OpikMetricAdapter


def create_test_spans_for_hallucination() -> List[SpanEntity]:
    """Create test spans specifically for hallucination detection."""
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
                'gen_ai.prompt.0.content': 'What is the capital of France?'
            },
            output_payload={
                'gen_ai.completion.0.role': 'assistant',
                'gen_ai.completion.0.content': 'The capital of France is London.'  # Clearly hallucinated answer
            },
            raw_span_data={}
        )
    ]


async def test_opik_hallucination_metric():
    """Test opik hallucination metric with actual computation."""

    print("\n🧪 Testing OpikMetricAdapter with Hallucination metric computation...")

    # Check if LLM credentials are available
    if not os.getenv("LLM_API_KEY"):
        print("⚠️  LLM_API_KEY not set - skipping full computation test")
        return

    try:
        # Create adapter instance for Hallucination metric
        adapter = OpikMetricAdapter('Hallucination')
        print("✅ OpikMetricAdapter for Hallucination created")

        # Set up registry
        registry = MetricRegistry()
        registry.register_metric(OpikMetricAdapter, 'Hallucination')
        print("✅ Hallucination metric registered")

        # Create test data with hallucinated content
        spans = create_test_spans_for_hallucination()
        aggregator = SessionAggregator()
        session = aggregator.create_session_from_spans('test_session', spans)
        sessions_set = SessionSet(sessions=[session])
        print("✅ Test session with hallucinated content created")

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

        # Look for hallucination metric results
        span_metrics = results.get('span_metrics', [])
        hallucination_results = [m for m in span_metrics if m.metric_name == 'Hallucination']

        if hallucination_results:
            print(f"\n🎯 Hallucination Metric Results:")
            for result in hallucination_results:
                print(f"  - Success: {result.success}")
                print(f"  - Value: {result.value}")
                print(f"  - Reasoning: {result.reasoning}")
                if result.error_message:
                    print(f"  - Error: {result.error_message}")
        else:
            print("⚠️  No hallucination metric results found")

        print("\n🎉 Opik adapter computation test completed!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(test_opik_hallucination_metric())