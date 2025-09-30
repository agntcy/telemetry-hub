#!/usr/bin/env python3
"""
Basic test script to verify ragas adapter functionality after import fixes.
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
try:
    import sys
    sys.path.append('plugins/adapters/ragas_adapter/src')
    from mce_ragas_adapter.adapter import RagasAdapter
    RAGAS_AVAILABLE = True
    print("✅ RagasAdapter imported successfully")
except ImportError as e:
    RAGAS_AVAILABLE = False
    print(f"❌ RagasAdapter import failed: {e}")


def create_test_spans() -> List[SpanEntity]:
    """Create test spans for ragas adapter testing."""
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
                'gen_ai.completion.0.content': 'The capital of France is Paris, a beautiful city known for its landmarks like the Eiffel Tower.'
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
                'gen_ai.prompt.0.content': 'Tell me about the weather today.'
            },
            output_payload={
                'gen_ai.completion.0.role': 'assistant',
                'gen_ai.completion.0.content': 'I don\'t have access to real-time weather data, but I can help you find weather information from reliable sources.'
            },
            raw_span_data={}
        )
    ]


async def test_ragas_adapter():
    """Test basic ragas adapter functionality."""
    if not RAGAS_AVAILABLE:
        print("❌ Skipping test - RagasAdapter not available")
        return

    print("\n🧪 Testing RagasAdapter basic functionality...")

    try:
        # Check what metrics are available
        from mce_ragas_adapter.metric_configuration import build_metric_configuration_map
        config_map = build_metric_configuration_map()
        available_metrics = list(config_map.keys())
        print(f"✅ Available RAGAS metrics: {available_metrics}")

        if not available_metrics:
            print("⚠️  No RAGAS metrics configured")
            return

        # Use the first available metric
        metric_name = available_metrics[0]
        adapter = RagasAdapter(metric_name)
        print(f"✅ RagasAdapter instance created for '{metric_name}'")

        # Test metric registry
        registry = MetricRegistry()
        registry.register_metric(RagasAdapter, metric_name)
        print("✅ Metric registered in registry successfully")

        # Create test data
        spans = create_test_spans()
        aggregator = SessionAggregator()
        session = aggregator.create_session_from_spans('test_session', spans)
        sessions_set = SessionSet(sessions=[session])
        print("✅ Test session created successfully")

        # Test configuration
        llm_config = LLMJudgeConfig(
            LLM_API_KEY=os.getenv('LLM_API_KEY', 'test_key'),
            LLM_BASE_MODEL_URL=os.getenv('LLM_BASE_MODEL_URL', 'https://api.openai.com/v1'),
            LLM_MODEL_NAME=os.getenv('LLM_MODEL_NAME', 'gpt-4o-mini'),
        )
        print("✅ LLM config created successfully")

        # Test processor creation (without actually running compute which requires real LLM)
        model_handler = ModelHandler()
        processor = MetricsProcessor(registry=registry, model_handler=model_handler, llm_config=llm_config)
        print("✅ MetricsProcessor created successfully")

        print("\n🎉 All basic ragas adapter tests passed!")
        print("Note: Full computation test skipped (requires RAGAS installation and LLM credentials)")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(test_ragas_adapter())