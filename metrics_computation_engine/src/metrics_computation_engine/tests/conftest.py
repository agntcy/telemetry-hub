# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Shared pytest configuration and fixtures for all MCE tests.
"""

import pytest
import logging
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock

from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.session_set import SessionSet
from metrics_computation_engine.model_handler import ModelHandler
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.metrics.base import CustomBaseMetric
from metrics_computation_engine.models.eval import MetricResult


# ============================================================================
# LOGGING FIXTURES
# ============================================================================


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_processor")


# ============================================================================
# MOCK MODEL & HANDLER FIXTURES
# ============================================================================


@pytest.fixture
def mock_llm_config():
    """Provide a mock LLMJudgeConfig for testing."""
    return LLMJudgeConfig(
        LLM_API_KEY="test-api-key",
        LLM_BASE_MODEL_URL="https://test.example.com",
        LLM_MODEL_NAME="test-model",
    )


@pytest.fixture
def mock_model_handler():
    """Provide a mock ModelHandler that returns mock models."""
    handler = MagicMock(spec=ModelHandler)

    # Mock get_or_create_model to return a mock model
    async def mock_get_or_create_model(provider, llm_config):
        mock_model = MagicMock()
        mock_model.name = "mock-model"
        return mock_model

    handler.get_or_create_model = AsyncMock(side_effect=mock_get_or_create_model)

    # Mock set_model
    async def mock_set_model(provider, llm_config, model):
        return True

    handler.set_model = AsyncMock(side_effect=mock_set_model)

    return handler


@pytest.fixture
def mock_registry():
    """Provide an empty MetricRegistry for testing."""
    return MetricRegistry()


# ============================================================================
# SPAN ENTITY FIXTURES
# ============================================================================


@pytest.fixture
def create_span():
    """Factory fixture to create SpanEntity objects."""

    def _create_span(
        entity_type: str = "agent",
        span_id: str = "span-1",
        entity_name: str = "test-entity",
        app_name: str = "test-app",
        session_id: str = "session-1",
        contains_error: bool = False,
        agent_id: Optional[str] = None,
        timestamp: str = "2025-01-01T00:00:00Z",
        parent_span_id: Optional[str] = None,
        trace_id: str = "trace-1",
        start_time: str = "1704067200.0",
        end_time: str = "1704067201.0",
        duration: float = 1000.0,
        raw_span_data: Optional[Dict] = None,
        input_payload: Optional[Dict] = None,
        output_payload: Optional[Dict] = None,
        **kwargs,
    ) -> SpanEntity:
        """Create a SpanEntity for testing."""
        return SpanEntity(
            entity_type=entity_type,
            span_id=span_id,
            entity_name=entity_name,
            app_name=app_name,
            session_id=session_id,
            contains_error=contains_error,
            timestamp=timestamp,
            parent_span_id=parent_span_id,
            trace_id=trace_id,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            agent_id=agent_id,
            raw_span_data=raw_span_data if raw_span_data is not None else {},
            input_payload=input_payload,
            output_payload=output_payload,
            **kwargs,
        )

    return _create_span


@pytest.fixture
def sample_spans(create_span):
    """Provide a list of sample spans for testing."""
    return [
        create_span(entity_type="agent", span_id="span-1", entity_name="AgentA"),
        create_span(entity_type="agent", span_id="span-2", entity_name="AgentB"),
        create_span(entity_type="tool", span_id="span-3", entity_name="tool_search"),
        create_span(entity_type="llm", span_id="span-4", entity_name="gpt-4"),
    ]


# ============================================================================
# SESSION ENTITY FIXTURES
# ============================================================================


@pytest.fixture
def create_session():
    """Factory fixture to create SessionEntity objects."""

    def _create_session(
        session_id: str = "session-1",
        spans: Optional[List[SpanEntity]] = None,
        app_name: str = "test-app",
        **kwargs,
    ) -> SessionEntity:
        """Create a SessionEntity for testing."""
        if spans is None:
            spans = []

        return SessionEntity(
            session_id=session_id,
            spans=spans,
            app_name=app_name,
            total_spans=len(spans),
            duration=1000.0,
            **kwargs,
        )

    return _create_session


@pytest.fixture
def empty_session(create_session):
    """Provide an empty SessionEntity (no spans)."""
    return create_session(session_id="empty-session", spans=[])


@pytest.fixture
def sample_session(create_session, sample_spans):
    """Provide a SessionEntity with sample spans."""
    return create_session(
        session_id="sample-session", spans=sample_spans, app_name="test-app"
    )


@pytest.fixture
def session_with_agent_transitions(create_session, create_span):
    """Provide a SessionEntity with agent transition data."""
    from collections import Counter

    # Create spans with raw_span_data manually
    span1 = create_span(entity_type="agent", span_id="span-1", entity_name="AgentA")
    span1.raw_span_data = {"Events.Attributes": [{"agent_name": "A"}]}

    span2 = create_span(entity_type="agent", span_id="span-2", entity_name="AgentB")
    span2.raw_span_data = {"Events.Attributes": [{"agent_name": "B"}]}

    span3 = create_span(entity_type="agent", span_id="span-3", entity_name="AgentC")
    span3.raw_span_data = {"Events.Attributes": [{"agent_name": "C"}]}

    spans = [span1, span2, span3]

    session = create_session(
        session_id="session-with-transitions",
        spans=spans,
        agent_transitions=["A -> B", "B -> C"],
        agent_transition_counts=Counter({"A -> B": 1, "B -> C": 1}),
    )

    return session


# ============================================================================
# SESSION SET FIXTURES
# ============================================================================


@pytest.fixture
def create_session_set():
    """Factory fixture to create SessionSet objects."""

    def _create_session_set(
        sessions: Optional[List[SessionEntity]] = None,
    ) -> SessionSet:
        """Create a SessionSet for testing."""
        if sessions is None:
            sessions = []

        return SessionSet(sessions=sessions)

    return _create_session_set


@pytest.fixture
def empty_session_set(create_session_set):
    """Provide an empty SessionSet (no sessions)."""
    return create_session_set(sessions=[])


@pytest.fixture
def sample_session_set(create_session_set, sample_session):
    """Provide a SessionSet with one sample session."""
    return create_session_set(sessions=[sample_session])


@pytest.fixture
def multi_session_set(create_session_set, create_session, create_span):
    """Provide a SessionSet with multiple sessions."""
    # Session 1: 2 agent spans, 1 tool span
    session1_spans = [
        create_span(entity_type="agent", span_id="s1-span1", session_id="session-1"),
        create_span(entity_type="agent", span_id="s1-span2", session_id="session-1"),
        create_span(entity_type="tool", span_id="s1-span3", session_id="session-1"),
    ]
    session1 = create_session(session_id="session-1", spans=session1_spans)

    # Session 2: 2 agent spans, 2 tool spans
    session2_spans = [
        create_span(entity_type="agent", span_id="s2-span1", session_id="session-2"),
        create_span(entity_type="agent", span_id="s2-span2", session_id="session-2"),
        create_span(entity_type="tool", span_id="s2-span3", session_id="session-2"),
        create_span(entity_type="tool", span_id="s2-span4", session_id="session-2"),
    ]
    session2 = create_session(session_id="session-2", spans=session2_spans)

    return create_session_set(sessions=[session1, session2])


# ============================================================================
# MOCK METRIC CLASSES FOR TESTING
# ============================================================================


class MockSpanMetric(CustomBaseMetric):
    """Simple span-level metric for testing (no LLM needed)."""

    aggregation_level = "span"

    # Require tool entity type for testing entity filtering
    required = {"entity_type": ["tool"]}

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__(metric_name or "MockSpanMetric")
        self.call_count = 0

    def init_with_model(self, model: Any) -> bool:
        """No model needed for this test metric."""
        return True

    def get_model_provider(self) -> Optional[str]:
        """No model needed."""
        return None

    def create_model(self, llm_config) -> Any:
        """No model needed."""
        return None

    async def compute(self, data: SpanEntity, **context) -> MetricResult:
        """Simple computation - just count calls."""
        self.call_count += 1

        return MetricResult(
            metric_name=self.name,
            value=1.0,
            aggregation_level=self.aggregation_level,
            category="test",
            app_name=data.app_name,
            span_id=[data.span_id],
            session_id=[data.session_id],
            success=True,
            metadata={"test": True},
        )


class MockSessionMetric(CustomBaseMetric):
    """Simple session-level metric for testing (no LLM needed)."""

    aggregation_level = "session"
    REQUIRED_PARAMETERS = {"MockSessionMetric": ["agent_transitions"]}

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__(metric_name or "MockSessionMetric")
        self.call_count = 0

    def init_with_model(self, model: Any) -> bool:
        """No model needed for this test metric."""
        return True

    def get_model_provider(self) -> Optional[str]:
        """No model needed."""
        return None

    def create_model(self, llm_config) -> Any:
        """No model needed."""
        return None

    async def compute(self, data: SessionEntity, **context) -> MetricResult:
        """Simple computation - just count calls."""
        self.call_count += 1

        return MetricResult(
            metric_name=self.name,
            value=len(data.agent_transitions) if data.agent_transitions else 0,
            aggregation_level=self.aggregation_level,
            category="test",
            app_name=data.app_name,
            session_id=[data.session_id],
            success=True,
            metadata={"test": True},
        )


class MockPopulationMetric(CustomBaseMetric):
    """Simple population-level metric for testing."""

    aggregation_level = "population"

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__(metric_name or "MockPopulationMetric")
        self.call_count = 0

    def init_with_model(self, model: Any) -> bool:
        """No model needed for this test metric."""
        return True

    def get_model_provider(self) -> Optional[str]:
        """No model needed."""
        return None

    def create_model(self, llm_config) -> Any:
        """No model needed."""
        return None

    async def compute(self, data: SessionSet, **context) -> MetricResult:
        """Simple computation - count sessions."""
        self.call_count += 1

        return MetricResult(
            metric_name=self.name,
            value=len(data.sessions),
            aggregation_level=self.aggregation_level,
            category="test",
            app_name="test-app",
            session_id=[s.session_id for s in data.sessions],
            success=True,
            metadata={"test": True},
        )


class FailingMetric(CustomBaseMetric):
    """Metric that intentionally fails for error testing."""

    aggregation_level = "session"

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__(metric_name or "FailingMetric")

    def init_with_model(self, model: Any) -> bool:
        """Initialize successfully."""
        return True

    def get_model_provider(self) -> Optional[str]:
        """No model needed."""
        return None

    def create_model(self, llm_config) -> Any:
        """No model needed."""
        return None

    async def compute(self, data: Any, **context) -> MetricResult:
        """Intentionally raise an error."""
        raise ValueError("Intentional test failure for error handling")


class FailingInitMetric(CustomBaseMetric):
    """Metric that fails during initialization."""

    aggregation_level = "session"

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__(metric_name or "FailingInitMetric")

    def init_with_model(self, model: Any) -> bool:
        """Fail initialization."""
        return False

    def get_model_provider(self) -> Optional[str]:
        """No model needed."""
        return None

    def create_model(self, llm_config) -> Any:
        """No model needed."""
        return None

    async def compute(self, data: Any, **context) -> MetricResult:
        """Should never be called."""
        raise RuntimeError("This should never be called!")


# ============================================================================
# METRIC CLASS FIXTURES
# ============================================================================


@pytest.fixture
def mock_span_metric_class():
    """Provide MockSpanMetric class."""
    return MockSpanMetric


@pytest.fixture
def mock_session_metric_class():
    """Provide MockSessionMetric class."""
    return MockSessionMetric


@pytest.fixture
def mock_population_metric_class():
    """Provide MockPopulationMetric class."""
    return MockPopulationMetric


@pytest.fixture
def failing_metric_class():
    """Provide FailingMetric class."""
    return FailingMetric


@pytest.fixture
def failing_init_metric_class():
    """Provide FailingInitMetric class."""
    return FailingInitMetric


# ============================================================================
# INVALID METRIC CLASS FOR REGISTRY TESTING
# ============================================================================


class InvalidMetric:
    """A class that does NOT inherit from BaseMetric - for testing validation."""

    def __init__(self):
        self.name = "InvalidMetric"

    def some_method(self):
        """Just a regular method."""
        return "not a metric"


@pytest.fixture
def invalid_metric_class():
    """Provide a class that doesn't inherit from BaseMetric."""
    return InvalidMetric


# ============================================================================
# DATA PARSER TEST FIXTURES
# ============================================================================


@pytest.fixture
def api_noa_2_data():
    """Load real trace data from api_noa_2.json."""
    import json
    from pathlib import Path

    test_data_dir = Path(__file__).parent / "local" / "data"
    file_path = test_data_dir / "api_noa_2.json"

    with open(file_path, "r") as f:
        return json.load(f)


@pytest.fixture
def sample_llm_span_raw():
    """Provide a real LLM span from api_noa_2.json."""
    return {
        "Timestamp": "2025-08-05T15:40:10.05080697Z",
        "TraceId": "78c23cf39c9b08cc62623b1c75ae3e6a",
        "SpanId": "4fd34aedfd53f8e3",
        "ParentSpanId": "1e870e56cc5e6a4c",
        "TraceState": "",
        "SpanName": "ChatOpenAI.chat",
        "SpanKind": "Client",
        "ServiceName": "noa-moderator",
        "ResourceAttributes": {"service.name": "noa-moderator"},
        "ScopeName": "opentelemetry.instrumentation.langchain",
        "ScopeVersion": "0.40.8",
        "SpanAttributes": {
            "agent_id": "moderator-agent.invoke",
            "deployment.environment": "o11y-for-ai-outshift",
            "gen_ai.completion.0.content": '{"messages": [{"type": "RequestToSpeak", "author": "noa-moderator", "target": "noa-web-surfer-assistant", "message": "What is the current time in Paris?"}]}',
            "gen_ai.completion.0.role": "assistant",
            "gen_ai.prompt.0.content": "You are a moderator agent",
            "gen_ai.prompt.0.role": "system",
            "gen_ai.prompt.1.content": "What time is it in Paris?",
            "gen_ai.prompt.1.role": "user",
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.request.temperature": "0",
            "gen_ai.response.id": "chatcmpl-test123",
            "gen_ai.response.model": "gpt-4o-2024-08-06",
            "gen_ai.system": "Langchain",
            "gen_ai.usage.cache_read_input_tokens": "0",
            "gen_ai.usage.completion_tokens": "48",
            "gen_ai.usage.prompt_tokens": "1404",
            "ioa_observe.workflow.name": "moderator-agent.invoke",
            "ioa_start_time": "1754408410.050816",
            "llm.request.type": "chat",
            "llm.usage.total_tokens": "1452",
            "session.id": "noa-moderator_4d798de1-e517-49f9-9a77-9f86a314d6b7",
            "traceloop.workflow.name": "RunnableSequence",
        },
        "Duration": 1459444226,
        "StatusCode": "Unset",
        "StatusMessage": "",
    }


@pytest.fixture
def sample_task_span_raw():
    """Provide a real task span from api_noa_2.json."""
    return {
        "Timestamp": "2025-08-05T15:40:10.050109221Z",
        "TraceId": "78c23cf39c9b08cc62623b1c75ae3e6a",
        "SpanId": "209df09e17aef3d1",
        "ParentSpanId": "1e870e56cc5e6a4c",
        "TraceState": "",
        "SpanName": "ChatPromptTemplate.task",
        "SpanKind": "Internal",
        "ServiceName": "noa-moderator",
        "ResourceAttributes": {"service.name": "noa-moderator"},
        "ScopeName": "",
        "ScopeVersion": "",
        "SpanAttributes": {
            "agent_id": "moderator-agent.invoke",
            "deployment.environment": "o11y-for-ai-outshift",
            "ioa_observe.workflow.name": "moderator-agent.invoke",
            "ioa_start_time": "1754408410.0501182",
            "session.id": "noa-moderator_4d798de1-e517-49f9-9a77-9f86a314d6b7",
            "traceloop.entity.input": '{"inputs": {"query": "test"}}',
            "traceloop.entity.name": "ChatPromptTemplate",
            "traceloop.entity.output": '{"outputs": {"result": "processed"}}',
            "traceloop.span.kind": "task",
            "traceloop.workflow.name": "RunnableSequence",
        },
        "Duration": 520038,
        "StatusCode": "Unset",
        "StatusMessage": "",
    }


@pytest.fixture
def sample_workflow_span_raw():
    """Provide a real workflow span."""
    return {
        "Timestamp": "2025-08-05T15:40:10.049910495Z",
        "TraceId": "78c23cf39c9b08cc62623b1c75ae3e6a",
        "SpanId": "1e870e56cc5e6a4c",
        "ParentSpanId": "84660700939efc15",
        "TraceState": "",
        "SpanName": "RunnableSequence.workflow",
        "SpanKind": "Internal",
        "ServiceName": "noa-moderator",
        "ResourceAttributes": {"service.name": "noa-moderator"},
        "ScopeName": "",
        "ScopeVersion": "",
        "SpanAttributes": {
            "agent_id": "moderator-agent.invoke",
            "ioa_observe.workflow.name": "moderator-agent.invoke",
            "ioa_start_time": "1754408410.0499318",
            "session.id": "noa-moderator_4d798de1-e517-49f9-9a77-9f86a314d6b7",
            "traceloop.entity.input": '{"query": "test query"}',
            "traceloop.entity.output": '{"response": "test response"}',
            "traceloop.workflow.name": "RunnableSequence",
        },
        "Duration": 2306869659,
        "StatusCode": "Unset",
        "StatusMessage": "",
    }


@pytest.fixture
def sample_agent_span_raw():
    """Provide a real agent span."""
    return {
        "Timestamp": "2025-08-05T15:40:10.123456Z",
        "TraceId": "test-trace-agent",
        "SpanId": "agent-span-123",
        "ParentSpanId": None,
        "SpanName": "test_agent.agent",
        "SpanKind": "Internal",
        "ServiceName": "test-app",
        "ResourceAttributes": {"service.name": "test-app"},
        "ScopeName": "",
        "ScopeVersion": "",
        "SpanAttributes": {
            "agent_id": "test-agent-id",
            "ioa_observe.entity.name": "test_agent",
            "ioa_observe.entity.input": '{"task": "do something"}',
            "ioa_observe.entity.output": '{"result": "done"}',
            "session.id": "test-session-123",
            "ioa_start_time": "1754408410.123",
        },
        "Duration": 1000000000,  # 1 second
        "StatusCode": "Unset",
        "StatusMessage": "",
    }


@pytest.fixture
def sample_graph_span_raw():
    """Provide a real graph span."""
    return {
        "Timestamp": "2025-08-05T15:40:10.123456Z",
        "TraceId": "test-trace-graph",
        "SpanId": "graph-span-123",
        "ParentSpanId": None,
        "SpanName": "test_graph.graph",
        "SpanKind": "Internal",
        "ServiceName": "test-app",
        "ResourceAttributes": {"service.name": "test-app"},
        "ScopeName": "",
        "ScopeVersion": "",
        "SpanAttributes": {
            "ioa_observe.workflow.name": "test-graph",
            "session.id": "test-session-123",
            "ioa_start_time": "1754408410.123",
            "traceloop.entity.input": '{"nodes": ["A", "B"]}',
            "traceloop.entity.output": '{"edges": ["A->B"]}',
        },
        "Duration": 500000000,
        "StatusCode": "Unset",
        "StatusMessage": "",
    }


@pytest.fixture
def sample_tool_span_raw():
    """Provide a real tool span."""
    return {
        "Timestamp": "2025-08-05T15:40:10.123456Z",
        "TraceId": "test-trace-tool",
        "SpanId": "tool-span-123",
        "ParentSpanId": "parent-123",
        "SpanName": "search_tool.tool",
        "SpanKind": "Client",
        "ServiceName": "test-app",
        "ResourceAttributes": {"service.name": "test-app"},
        "SpanAttributes": {
            "traceloop.entity.name": "search_tool",
            "ioa_observe.entity.name": "search_tool",
            "traceloop.entity.input": '{"query": "test search"}',
            "traceloop.entity.output": '{"results": ["item1", "item2"]}',
            "session.id": "test-session-123",
            "ioa_start_time": "1754408410.123",
        },
        "Duration": 250000000,
    }
