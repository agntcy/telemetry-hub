# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Any, Dict, List

from metrics_computation_engine.models.span import SpanEntity


def safe_parse_json(value: str | None) -> dict | None:
    try:
        return json.loads(value) if value else None
    except Exception:
        return None


def contains_error_like_pattern(output_dict: dict) -> bool:
    # Flatten the dictionary and look for error-indicative values
    def extract_strings(d):
        if isinstance(d, dict):
            for v in d.values():
                yield from extract_strings(v)
        elif isinstance(d, list):
            for v in d:
                yield from extract_strings(v)
        elif isinstance(d, str):
            yield d.lower()

    for value in extract_strings(output_dict):
        if any(e in value for e in ["traceback", "exception", "httperror"]):
            return True
    return False


def parse_raw_spans(raw_spans: List[Dict[str, Any]]) -> List[SpanEntity]:
    span_entities: List[SpanEntity] = []
    tool_definitions_by_name: Dict[str, Dict[str, Any]] = {}

    for span in raw_spans:
        attrs = span.get("SpanAttributes", {})

        span_name = span.get("SpanName", "").lower()
        if span_name.endswith(".chat"):
            entity_type = "llm"
        elif span_name.endswith(".tool"):
            entity_type = "tool"
        elif span_name.endswith(".agent"):
            entity_type = "agent"
        else:
            entity_type = None

        if entity_type not in {"agent", "tool", "llm"}:
            continue

        if entity_type == "llm":
            i = 0
            while f"llm.request.functions.{i}.name" in attrs:
                name = attrs.get(f"llm.request.functions.{i}.name")
                description = attrs.get(f"llm.request.functions.{i}.description")
                parameters = safe_parse_json(
                    attrs.get(f"llm.request.functions.{i}.parameters")
                )

                if name and name not in tool_definitions_by_name:
                    tool_definitions_by_name[name] = {
                        "description": description,
                        "parameters": parameters,
                    }

                i += 1

        if entity_type == "tool":
            entity_name = attrs.get("traceloop.entity.name", "unknown")
        elif entity_type == "llm":
            entity_name = attrs.get("gen_ai.response.model", "unknown")
        elif entity_type == "agent":
            entity_name = attrs.get("ioa_observe.entity.name", "unknown")
        else:
            entity_name = "unknown"

        tool_definition = (
            tool_definitions_by_name.get(entity_name) if entity_type == "tool" else None
        )

        start_time_str = attrs.get("ioa_start_time")
        duration_ns = span.get("Duration")

        if start_time_str and duration_ns:
            try:
                start_time_float = float(start_time_str)
                end_time_str = str(start_time_float + duration_ns / 1e9)
            except Exception:
                end_time_str = None
        else:
            end_time_str = None

        # output_payload logic for LLM
        if entity_type == "llm":
            output_payload = {
                key: attrs[key] for key in attrs if key.startswith("gen_ai.completion")
            }
        elif entity_type == "agent":
            output_payload = safe_parse_json(attrs.get("ioa_observe.entity.output"))
        elif entity_type == "tool":
            output_payload = safe_parse_json(attrs.get("traceloop.entity.output"))
        else:
            output_payload = None

        # input_payload logic for LLM
        if entity_type == "llm":
            input_payload = {
                key: attrs[key] for key in attrs if key.startswith("gen_ai.prompt")
            }
        elif entity_type == "agent":
            input_payload = safe_parse_json(attrs.get("ioa_observe.entity.input"))
        elif entity_type == "tool":
            input_payload = safe_parse_json(attrs.get("traceloop.entity.input"))
        else:
            input_payload = None

        # Determine contains_error
        contains_error = bool(attrs.get("traceloop.entity.error"))
        if not contains_error and isinstance(output_payload, dict):
            if contains_error_like_pattern(output_payload):
                contains_error = True

        span_entity = SpanEntity(
            entity_type=entity_type,
            span_id=span.get("SpanId", ""),
            entity_name=entity_name,
            input_payload=input_payload,
            output_payload=output_payload,
            message=attrs.get("traceloop.entity.message"),
            tool_definition=tool_definition,
            contains_error=contains_error,
            timestamp=span.get("Timestamp", ""),
            parent_span_id=span.get("ParentSpanId"),
            trace_id=span.get("TraceId"),
            session_id=attrs.get("session.id") or attrs.get("execution.id"),
            start_time=start_time_str,
            end_time=end_time_str,
            raw_span_data=span,
        )

        span_entities.append(span_entity)

    return span_entities
