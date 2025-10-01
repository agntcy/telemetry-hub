# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import pytest
from collections import Counter
from metrics_computation_engine.metrics.session.agent_to_agent_interactions import (
    AgentToAgentInteractions,
)
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.transformers.session_enrichers import (
    AgentTransitionTransformer,
)


def enrich_session_with_agent_transitions(session_entity):
    """Helper to enrich session with agent transition data."""
    transformer = AgentTransitionTransformer()
    enrichment_data = transformer.extract(session_entity)

    # Update the session with the enrichment data
    session_entity.agent_transitions = enrichment_data.get("agent_transitions")
    session_entity.agent_transition_counts = enrichment_data.get(
        "agent_transition_counts"
    )

    return session_entity


@pytest.mark.asyncio
async def test_agent_to_agent_interactions():
    metric = AgentToAgentInteractions()

    # Case 1: No Events.Attributes
    span1 = SpanEntity(
        entity_type="agent",
        span_id="1",
        entity_name="AgentA",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": []},
    )

    session_entity = SessionEntity(session_id=span1.session_id, spans=[span1])
    session_entity = enrich_session_with_agent_transitions(session_entity)
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == Counter()

    # Case 2: Different agent transitions
    span2 = SpanEntity(
        entity_type="agent",
        span_id="2",
        entity_name="AgentB",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "A"}]},
    )
    span3 = SpanEntity(
        entity_type="agent",
        span_id="3",
        entity_name="AgentC",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "B"}]},
    )
    span4 = SpanEntity(
        entity_type="agent",
        span_id="4",
        entity_name="AgentD",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "C"}]},
    )
    session_entity = SessionEntity(
        session_id=span2.session_id, spans=[span2, span3, span4]
    )
    session_entity = enrich_session_with_agent_transitions(session_entity)
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == Counter(
        {
            "A -> B": 1,
            "B -> C": 1,
        }
    )

    # Case 3: Same agent repeated (no transition)
    span5 = SpanEntity(
        entity_type="agent",
        span_id="5",
        entity_name="AgentX",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "Z"}]},
    )
    span6 = SpanEntity(
        entity_type="agent",
        span_id="6",
        entity_name="AgentX",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": [{"agent_name": "Z"}]},
    )
    session_entity = SessionEntity(session_id=span5.session_id, spans=[span5, span6])
    session_entity = enrich_session_with_agent_transitions(session_entity)
    result = await metric.compute(session_entity)
    assert result.success
    assert result.value == Counter()  # No transition Z -> Z

    # Case 4: None values in Events.Attributes are handled gracefully (robustness test)
    broken_span = SpanEntity(
        entity_type="agent",
        span_id="7",
        entity_name="AgentFail",
        app_name="example_app",
        contains_error=False,
        timestamp="",
        parent_span_id=None,
        trace_id="t1",
        session_id="s1",
        start_time=None,
        end_time=None,
        raw_span_data={"Events.Attributes": None},  # Invalid type
    )
    session_entity = SessionEntity(session_id=span2.session_id, spans=[broken_span])
    session_entity = enrich_session_with_agent_transitions(session_entity)
    result = await metric.compute(session_entity)
    assert result.success  # Now gracefully handles invalid data
    assert result.value == Counter()  # Returns empty counter instead of -1
    assert result.error_message is None  # No error message
