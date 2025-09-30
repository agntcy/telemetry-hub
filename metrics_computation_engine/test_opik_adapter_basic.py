#!/usr/bin/env python3
"""
Basic test script to verify opik adapter functionality after import fixes.
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
try:
    import sys
    sys.path.append('plugins/adapters/opik_adapter/src')
    from mce_opik_adapter.adapter import OpikMetricAdapter
    OPIK_AVAILABLE = True
    print("✅ OpikMetricAdapter imported successfully")
except ImportError as e:
    OPIK_AVAILABLE = False
    print(f"❌ OpikMetricAdapter import failed: {e}")


def create_test_spans() -> List[SpanEntity]:
    """Create test spans for opik adapter testing."""
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
                'gen_ai.completion.0.content': 'The capital of France is Paris.'
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
                'gen_ai.prompt.0.content': 'Tell me about elephants.'
            },
            output_payload={
                'gen_ai.completion.0.role': 'assistant',
                'gen_ai.completion.0.content': 'Elephants are large mammals that can fly and breathe underwater.'  # Hallucinated content
            },
            raw_span_data={}
        )
    ]


async def test_opik_adapter():
    """Test basic opik adapter functionality."""
    if not OPIK_AVAILABLE:
        print("❌ Skipping test - OpikMetricAdapter not available")
        return

    print("\n🧪 Testing OpikMetricAdapter basic functionality...")

    try:
        # Create adapter instance
        adapter = OpikMetricAdapter('Hallucination')
        print("✅ OpikMetricAdapter instance created successfully")

        # Test metric registry
        registry = MetricRegistry()
        registry.register_metric(OpikMetricAdapter, 'Hallucination')
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

        print("\n🎉 All basic opik adapter tests passed!")
        print("Note: Full computation test skipped (requires opik installation and LLM credentials)")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(test_opik_adapter())