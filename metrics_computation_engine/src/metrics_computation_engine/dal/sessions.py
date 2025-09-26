# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import ast
from typing import Dict, List
from collections import Counter

from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.models.session import (
    SessionEntity,
    ConversationElement,
    ToolCall,
)
from metrics_computation_engine.transformers import (
    DataPipeline,
    EntityFilter,
    ConversationDataExtractor,
)
from metrics_computation_engine.logger import setup_logger
from metrics_computation_engine.dal.annotations import (
    get_annotations_results_by_session,
)

logger = setup_logger(__name__)


def build_session_entity(session_id: str, spans: List[SpanEntity]) -> SessionEntity:
    """
    Build a SessionEntity with the essential computed fields that metrics actually use.
    """
    session = SessionEntity(session_id=session_id, spans=spans)

    populate_timing(session)
    populate_entity_spans(session)

    populate_app_name(session)

    populate_conversation_data(session)
    populate_agent_interactions(session)

    populate_conversation_elements(session)
    populate_tool_calls(session)

    populate_e2e_attributes(session)
    populate_ground_truth(session)

    return session


def build_session_entities_from_dict(
    sessions_data: Dict[str, List[SpanEntity]],
) -> List[SessionEntity]:
    """Build SessionEntity objects from a dictionary mapping session_ids to spans."""
    session_entities = []

    for session_id, spans in sessions_data.items():
        sorted_spans = sorted(spans, key=lambda x: x.timestamp or "")
        session_entity = build_session_entity(session_id, sorted_spans)
        session_entities.append(session_entity)

    return session_entities


def populate_app_name(session: SessionEntity) -> None:
    if len(session.spans) > 0:
        session.app_name = session.spans[0].app_name


def populate_timing(session: SessionEntity) -> None:
    """Compute session start and end times from spans."""
    if not session.spans:
        return

    start_times = [float(span.start_time) for span in session.spans if span.start_time]
    end_times = [float(span.end_time) for span in session.spans if span.end_time]

    if start_times:
        session.start_time = str(min(start_times))
    if end_times:
        session.end_time = str(max(end_times))


def populate_e2e_attributes(session: SessionEntity) -> None:
    if not session.llm_spans:
        return

    # Use the latest invocation of the LLM which should maintain the whole chat history, use to extract the query and final responses respectively
    from datetime import datetime

    latest_span = max(
        session.llm_spans, key=lambda x: datetime.fromisoformat(x.timestamp)
    ).input_payload
    indexes = {
        int(key.split(".")[2])
        for key in latest_span.keys()
        if key.startswith("gen_ai.prompt.")
    }

    input_query, final_response = None, None
    for i in indexes:
        if (
            f"gen_ai.prompt.{i}.role" in latest_span.keys()
            and latest_span[f"gen_ai.prompt.{i}.role"].lower() == "system"
        ):
            continue
        if f"gen_ai.prompt.{i}.content" in latest_span.keys():
            if not input_query:
                input_query = latest_span[f"gen_ai.prompt.{i}.content"]
            final_response = latest_span[f"gen_ai.prompt.{i}.content"]

    session.input_query = str(input_query)
    session.final_response = str(final_response)


def populate_ground_truth(session: SessionEntity) -> None:
    session.ground_truth = get_annotations_results_by_session(session.session_id)


def populate_entity_spans(session: SessionEntity) -> None:
    """Populate entity-specific spans using filters."""
    agent_filter = EntityFilter(["agent"])
    llm_filter = EntityFilter(["llm"])
    tool_filter = EntityFilter(["tool"])  # Add this line

    session.agent_spans = agent_filter.transform(session.spans)
    session.tool_spans = tool_filter.transform(session.spans)
    session.llm_spans = llm_filter.transform(session.spans)


def populate_conversation_data(session: SessionEntity) -> None:
    """Extract conversation data using the transformer pipeline."""
    if not session.agent_spans:
        session.conversation_data = {"conversation": ""}
        return

    pipeline = DataPipeline(
        [
            EntityFilter(["agent"]),
            ConversationDataExtractor(["agent"]),
        ]
    )

    result = pipeline.process(session.spans)
    session.conversation_data = {"conversation": result.get("conversation", "")}


def populate_agent_interactions(session: SessionEntity) -> None:
    """Compute agent-to-agent transitions and counts."""
    agent_events = []

    # Extract agent events from spans with Events.Attributes (same logic as original)
    for span in session.spans:
        if (
            hasattr(span, "raw_span_data")
            and span.raw_span_data
            and (
                span.raw_span_data.get("Events.Attributes")
                or span.raw_span_data.get("EventsAttributes")
            )
        ):
            events = span.raw_span_data.get(
                "Events.Attributes"
            ) or span.raw_span_data.get("EventsAttributes", [])
            if (
                len(events) > 0
                and isinstance(events[0], dict)
                and "agent_name" in events[0]
            ):
                agent_name = events[0]["agent_name"]
                agent_events.append((span.span_id, agent_name))

    if not agent_events:
        session.agent_transitions = []
        session.agent_transition_counts = Counter()
        return

    # Extract just the agent names for transition analysis
    agent_names = [event[1] for event in agent_events]

    # Compute transitions (same logic as original)
    transitions = []
    for i in range(len(agent_names) - 1):
        if agent_names[i] != agent_names[i + 1]:
            transition = f"{agent_names[i]} -> {agent_names[i + 1]}"
            transitions.append(transition)

    session.agent_transitions = transitions
    session.agent_transition_counts = Counter(transitions)


def populate_conversation_elements(session: SessionEntity) -> None:
    """Extract structured conversation elements for DeepEval metrics."""
    if not session.llm_spans:
        logger.info("No llm spans available!")
        session.conversation_elements = []
        return

    # Find the main conversation span (same logic as DeepEval adapter)
    main_conversation_span = (
        session.llm_spans[-2] if len(session.llm_spans) >= 2 else session.llm_spans[-1]
    )

    input_payload = main_conversation_span.input_payload
    output_payload = main_conversation_span.output_payload

    if not input_payload or not output_payload:
        session.conversation_elements = []
        return

    conversation_elements = []

    # Extract conversation turns from input payload
    num_turns = len(
        set(
            [
                message_key.split(".")[2]
                for message_key in input_payload.keys()
                if "gen_ai.prompt" in message_key
            ]
        )
    )

    for n in range(num_turns):
        role_key = f"gen_ai.prompt.{n}.role"
        content_key = f"gen_ai.prompt.{n}.content"

        if role_key in input_payload:
            role = input_payload[role_key]

            if content_key in input_payload:
                content = input_payload[content_key]
            else:
                # Handle case where content is split across multiple keys
                content_segments = [
                    f"{k.split('.')[-1]}:{input_payload[k]}"
                    for k in input_payload.keys()
                    if f"gen_ai.prompt.{n}" in k and "role" not in k
                ]
                content = "\n".join(content_segments)

            conversation_elements.append(
                ConversationElement(role=role, content=content)
            )

    # Add the final response
    if (
        "gen_ai.completion.0.role" in output_payload
        and "gen_ai.completion.0.content" in output_payload
    ):
        conversation_elements.append(
            ConversationElement(
                role=output_payload["gen_ai.completion.0.role"],
                content=output_payload["gen_ai.completion.0.content"],
            )
        )

    session.conversation_elements = conversation_elements


def populate_tool_calls(session: SessionEntity) -> None:
    """Extract structured tool call data for DeepEval metrics."""
    if not session.tool_spans:
        session.tool_calls = []
        return

    tool_calls = []

    for span in session.tool_spans:
        # Skip spans that don't have the required payload data
        if not span.input_payload or "input_str" not in span.input_payload:
            continue
        if not span.tool_definition or "description" not in span.tool_definition:
            continue
        if not span.output_payload or "output" not in span.output_payload:
            continue

        name = span.entity_name
        try:
            input_parameters = ast.literal_eval(span.input_payload["input_str"])
        except (ValueError, SyntaxError):
            continue

        description = span.tool_definition["description"]
        output = span.output_payload["output"]["kwargs"]

        tool_calls.append(
            ToolCall(
                name=name,
                description=description,
                input_parameters=input_parameters,
                output=output,
            )
        )

    session.tool_calls = tool_calls
