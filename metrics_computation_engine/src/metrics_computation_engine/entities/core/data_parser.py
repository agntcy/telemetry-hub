# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List

from ..models.span import SpanEntity


def safe_parse_json(value: str | None) -> dict | None:
    try:
        return json.loads(value) if value else None
    except Exception:
        return None


# TODO: use LaaJ to detect error-like patterns in output payloads
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


def detect_span_format(span: Dict) -> str:
    """
    Detect if span is in Jaeger or standard format.
    
    Returns:
        "jaeger" if Jaeger format detected
        "standard" if standard format detected
        "unknown" otherwise
    """
    if "operationName" in span and "tags" in span:
        return "jaeger"
    elif "SpanName" in span and "SpanAttributes" in span:
        return "standard"
    return "unknown"


def convert_jaeger_to_standard(span: Dict) -> Dict:
    """
    Convert Jaeger format span to standard format.
    
    Jaeger format uses:
    - operationName -> SpanName
    - tags -> SpanAttributes
    - serviceName -> ServiceName
    - spanId -> SpanId
    - parentId -> ParentSpanId
    - traceId -> TraceId
    - startTime -> Timestamp and ioa_start_time attribute
    - durationMicros -> Duration (converted to nanoseconds)
    """
    converted = span.copy()
    
    # Map Jaeger field names to standard field names
    if "operationName" in span:
        converted["SpanName"] = span["operationName"]
        
    if "tags" in span:
        attrs = span["tags"].copy()
        
        # Add traceId as session.id if not already present
        # This ensures trace grouping works correctly
        if "session.id" not in attrs and "execution.id" not in attrs:
            if "traceId" in span:
                attrs["session.id"] = span["traceId"]
        
        converted["SpanAttributes"] = attrs
        
    if "serviceName" in span:
        converted["ServiceName"] = span["serviceName"]
        
    if "spanId" in span:
        converted["SpanId"] = span["spanId"]
        
    if "parentId" in span:
        converted["ParentSpanId"] = span["parentId"]
        
    if "traceId" in span:
        converted["TraceId"] = span["traceId"]
    
    # Handle Jaeger timestamp format
    if "startTime" in span:
        start_time_str = span["startTime"]
        converted["Timestamp"] = start_time_str
        
        # Convert ISO 8601 timestamps to float for ioa_start_time
        try:
            if 'T' in start_time_str and 'Z' in start_time_str:
                dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                start_time_float = dt.timestamp()
            else:
                start_time_float = float(start_time_str)
            
            # Add ioa_start_time to attributes
            if "SpanAttributes" not in converted:
                converted["SpanAttributes"] = {}
            converted["SpanAttributes"]["ioa_start_time"] = str(start_time_float)
        except Exception:
            # If conversion fails, store as-is
            if "SpanAttributes" not in converted:
                converted["SpanAttributes"] = {}
            converted["SpanAttributes"]["ioa_start_time"] = start_time_str
    
    # Convert duration from microseconds to nanoseconds
    if "durationMicros" in span:
        duration_micros = span["durationMicros"]
        converted["Duration"] = duration_micros * 1000  # Convert to nanoseconds
    
    return converted


def app_name(span: Dict) -> str:
    """
    Extract the application name from session spans.

    Looks for common attributes that might contain the app name.
    Returns a default value if not found.
    """
    # Check for common app name attributes in spans
    # First, check raw span data for ServiceName
    if span.get("ServiceName", None):
        service_name = str(span.get("ServiceName", None))
        if service_name and service_name != "unknown":
            return service_name

    # Then check ResourceAttributes for service.name
    if span.get("ResourceAttributes", None):
        resource_attrs = span.get("ResourceAttributes", None)
        if isinstance(resource_attrs, dict) and resource_attrs.get("service.name"):
            service_name = str(resource_attrs["service.name"])
            if service_name and service_name != "unknown":
                return service_name

    # Check span attributes for app name patterns
    attrs = span.get("SpanAttributes", {})
    if attrs:
        # Common patterns for app names
        for attr_key in [
            "app.name",
            "service.name",
            "application.name",
            "traceloop.workflow.name",
        ]:
            if attrs.get(attr_key, None):
                return str(attrs[attr_key])

        # Check for workflow names that might indicate app
        workflow_name = attrs.get("ioa_workflow.name", None)
        if workflow_name:
            return str(workflow_name)

    # Default fallback
    return "unknown-app"


def parse_raw_spans(raw_spans: List[Dict[str, Any]]) -> List[SpanEntity]:
    """
    Parse raw span data into SpanEntity objects using DataFrame optimization.

    This implementation uses pandas for efficient vectorized operations,
    particularly beneficial for larger datasets.
    
    Supports both standard and Jaeger span formats with automatic detection
    and conversion.
    """
    if not raw_spans:
        return []

    # Detect format and convert Jaeger spans to standard format if needed
    converted_spans = []
    for span in raw_spans:
        span_format = detect_span_format(span)
        if span_format == "jaeger":
            converted_spans.append(convert_jaeger_to_standard(span))
        else:
            converted_spans.append(span)

    # Convert to DataFrame for vectorized operations
    df = pd.DataFrame(converted_spans)

    # Extract and normalize span attributes, maintaining index alignment
    attrs_list = df["SpanAttributes"].fillna({}).tolist()
    attrs_df = pd.json_normalize(attrs_list)
    attrs_df.index = df.index  # Ensure index alignment

    # Entity type detection using masks
    span_names = df["SpanName"].fillna("").astype(str).str.lower()
    entity_type_masks = {
        "llm": span_names.str.endswith(".chat"),
        "tool": span_names.str.endswith(".tool"),
        "agent": span_names.str.endswith(".agent"),
        "workflow": span_names.str.endswith(".workflow"),
        "graph": span_names.str.endswith(".graph"),
        "task": span_names.str.endswith(".task"),
    }

    # Create entity_type column
    df["entity_type"] = None
    for entity_type, mask in entity_type_masks.items():
        df.loc[mask, "entity_type"] = entity_type

    # Enhanced detection for different frameworks (Autogen, etc.)
    # Detect Autogen agents - patterns like "autogen process MultimodalWebSurfer_..."
    autogen_agent_mask = span_names.str.contains("autogen process", na=False)
    df.loc[autogen_agent_mask, "entity_type"] = "agent"

    # Detect Autogen workflows - patterns like "autogen create group_topic_..."
    autogen_workflow_mask = span_names.str.contains("autogen create", na=False)
    df.loc[autogen_workflow_mask, "entity_type"] = "workflow"

    # Additional logic: detect agent-related TASK spans
    # Look for task spans that contain agent information
    task_mask = df["entity_type"] == "task"
    if task_mask.any():
        # Check for agent patterns in task span names or attributes
        task_indices = df[task_mask].index
        for idx in task_indices:
            span_name = str(df.loc[idx, "SpanName"])  # Ensure string conversion
            # Check if task name contains agent name pattern (e.g., "website_selector_agent.task")
            if ".task" in span_name:
                base_name = span_name.replace(".task", "")
                if "agent" in base_name:
                    # This is an agent task - check if we have the corresponding agent span
                    agent_span_name = base_name + ".agent"
                    if (
                        not df["SpanName"]
                        .astype(str)
                        .str.contains(agent_span_name, regex=False)
                        .any()
                    ):
                        # No corresponding agent span found, keep this as task
                        continue

            # Check for agent information in attributes
            if idx in attrs_df.index:
                attrs = attrs_df.loc[idx]
                # Look for agent path patterns
                entity_path = str(attrs.get("traceloop.entity.path", ""))
                if "agent" in entity_path.lower():
                    # This task is agent-related but keep it as task for hierarchy
                    continue

    # Filter only valid entity types
    valid_mask = df["entity_type"].notna()
    df_filtered = df[valid_mask].copy()
    attrs_filtered = attrs_df[valid_mask].copy()

    if df_filtered.empty:
        return []

    # Configuration for payload processing
    PAYLOAD_CONFIG = {
        "llm": {
            "entity_name_key": "gen_ai.response.model",
            "input_prefix": "gen_ai.prompt",
            "output_prefix": "gen_ai.completion",
            "custom_output_processing": True,
        },
        "tool": {
            "entity_name_key": "traceloop.entity.name",
            "input_key": "traceloop.entity.input",
            "output_key": "traceloop.entity.output",
            "custom_output_processing": False,
        },
        "agent": {
            "entity_name_key": "ioa_observe.entity.name",
            "input_key": "ioa_observe.entity.input",
            "output_key": "ioa_observe.entity.output",
            "custom_output_processing": False,
        },
        "workflow": {
            "entity_name_key": "ioa_observe.workflow.name",
            "input_key": "traceloop.entity.input",
            "output_key": "traceloop.entity.output",
            "custom_output_processing": False,
        },
        "graph": {
            "entity_name_key": "ioa_observe.workflow.name",
            "input_key": "traceloop.entity.input",
            "output_key": "traceloop.entity.output",
            "custom_output_processing": False,
        },
        "task": {
            "entity_name_key": "traceloop.entity.name",
            "input_key": "traceloop.entity.input",
            "output_key": "traceloop.entity.output",
            "custom_output_processing": False,
        },
    }

    # Extract tool definitions for LLM spans
    tool_definitions_by_name = _extract_tool_definitions(
        attrs_filtered, df_filtered["entity_type"] == "llm"
    )

    span_entities = []

    # Process each row with proper index handling
    for idx in df_filtered.index:
        input_payload = None
        output_payload = None
        extra_attrs = None

        row = df_filtered.loc[idx]
        attrs = (
            attrs_filtered.loc[idx].dropna().to_dict()
            if idx in attrs_filtered.index
            else {}
        )
        entity_type = row["entity_type"]
        config = PAYLOAD_CONFIG[entity_type]

        # Extract entity name
        entity_name = attrs.get(config["entity_name_key"], "unknown")
        agent_id = attrs.get("agent_id", None)

        # Special handling for Autogen agent names
        if entity_type == "agent" and entity_name == "unknown":
            span_name = row.get("SpanName", "")
            if "autogen process" in span_name:
                # Extract agent name from patterns like:
                # "autogen process MultimodalWebSurfer_01f41b74-66dd-4438-a040-ac36c58253b6.(01f41b74-66dd-4438-a040-ac36c58253b6)-A"
                # -> "MultimodalWebSurfer"
                import re

                match = re.search(r"autogen process (\w+)_", span_name)
                if match:
                    entity_name = match.group(1)
                else:
                    # Fallback: try to extract just after "autogen process "
                    parts = span_name.replace("autogen process ", "").split("_")
                    if parts and parts[0]:
                        entity_name = parts[0]

        # Extract payloads based on entity type
        if entity_type == "llm":
            input_payload, output_payload, extra_attrs = _process_llm_payloads(attrs)
        else:
            input_payload = _process_generic_payload(attrs.get(config["input_key"]))
            output_payload = _process_generic_payload(attrs.get(config["output_key"]))

            # Special handling for workflow output
            if entity_type == "workflow" and isinstance(output_payload, str):
                output_payload = {"value": output_payload}

        # Get tool definition if applicable
        tool_definition = (
            tool_definitions_by_name.get(entity_name) if entity_type == "tool" else None
        )

        # Calculate timing
        start_time_str = attrs.get("ioa_start_time")
        duration_ns = row.get("Duration")
        end_time_str = _calculate_end_time(start_time_str, duration_ns)
        duration_ms = _calculate_duration_ms(start_time_str, end_time_str, duration_ns)

        # Determine error status
        contains_error = _check_error_status(attrs, output_payload)

        # Ensure payloads are dictionaries
        input_payload = _ensure_dict_payload(input_payload)
        output_payload = _ensure_dict_payload(output_payload)

        # Enhance raw_span_data with backward compatibility fields
        raw_span_dict = row.to_dict()
        
        # Add backward compatibility for adapters expecting old field names
        # This ensures both Jaeger and standard field names are available
        if "SpanAttributes" in raw_span_dict and "tags" not in raw_span_dict:
            raw_span_dict["tags"] = raw_span_dict["SpanAttributes"]
        if "SpanName" in raw_span_dict and "operationName" not in raw_span_dict:
            raw_span_dict["operationName"] = raw_span_dict["SpanName"]
        if "ServiceName" in raw_span_dict and "serviceName" not in raw_span_dict:
            raw_span_dict["serviceName"] = raw_span_dict["ServiceName"]
        if "SpanId" in raw_span_dict and "spanId" not in raw_span_dict:
            raw_span_dict["spanId"] = raw_span_dict["SpanId"]
        if "ParentSpanId" in raw_span_dict and "parentId" not in raw_span_dict:
            raw_span_dict["parentId"] = raw_span_dict["ParentSpanId"]
        if "TraceId" in raw_span_dict and "traceId" not in raw_span_dict:
            raw_span_dict["traceId"] = raw_span_dict["TraceId"]
        
        span_entity = SpanEntity(
            entity_type=entity_type,
            span_id=row.get("SpanId", ""),
            entity_name=entity_name,
            app_name=app_name(row),
            agent_id=agent_id,
            input_payload=input_payload,
            output_payload=output_payload,
            message=attrs.get("traceloop.entity.message"),
            tool_definition=tool_definition,
            contains_error=contains_error,
            timestamp=row.get("Timestamp", ""),
            parent_span_id=row.get("ParentSpanId")
            if pd.notna(row.get("ParentSpanId"))
            else None,
            trace_id=row.get("TraceId"),
            session_id=attrs.get("session.id") or attrs.get("execution.id"),
            start_time=start_time_str,
            end_time=end_time_str,
            duration=duration_ms,
            attrs=extra_attrs,
            raw_span_data=raw_span_dict,
        )

        span_entities.append(span_entity)

    return span_entities


def _extract_tool_definitions(
    attrs_df: pd.DataFrame, llm_mask: pd.Series
) -> Dict[str, Dict[str, Any]]:
    """Extract tool definitions from LLM spans."""
    tool_definitions = {}

    if not llm_mask.any():
        return tool_definitions

    llm_attrs = attrs_df[llm_mask]

    for idx, attrs in llm_attrs.iterrows():
        attrs_dict = attrs.dropna().to_dict()
        i = 0
        while f"llm.request.functions.{i}.name" in attrs_dict:
            name = attrs_dict.get(f"llm.request.functions.{i}.name")
            description = attrs_dict.get(f"llm.request.functions.{i}.description")
            parameters = safe_parse_json(
                attrs_dict.get(f"llm.request.functions.{i}.parameters")
            )

            if name and name not in tool_definitions:
                tool_definitions[name] = {
                    "description": description,
                    "parameters": parameters,
                }
            i += 1

    return tool_definitions


def _process_llm_payloads(
    attrs: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Process LLM-specific input and output payloads + extra attributes"""
    # Input payload: all gen_ai.prompt fields
    input_payload = {
        key: attrs[key] for key in attrs if key.startswith("gen_ai.prompt")
    }

    # Output payload: all gen_ai.completion fields with JSON parsing
    output_payload = {}
    for key in attrs:
        if key.startswith("gen_ai.completion"):
            value = attrs[key]
            if isinstance(value, str):
                parsed_value = safe_parse_json(value)
                output_payload[key] = (
                    parsed_value if parsed_value is not None else value
                )
            else:
                output_payload[key] = value

    # extrac specific LLM attributes
    extra = {}
    # example: gpt-4o
    extra["model_name"] = attrs.get("gen_ai.request.model", None)
    # example: gpt-4o-2024-06-13
    extra["model_name_response"] = attrs.get("gen_ai.response.model", None)

    extra["model_temperature"] = attrs.get("gen_ai.request.temperature", None)
    extra["cache_tokens"] = attrs.get("gen_ai.usage.cache_read_input_tokens", None)
    extra["input_tokens"] = attrs.get("gen_ai.usage.prompt_tokens", None)
    extra["output_tokens"] = attrs.get("gen_ai.usage.completion_tokens", None)
    extra["total_tokens"] = attrs.get("llm.usage.total_tokens", None)
    return input_payload, output_payload, extra


def _process_generic_payload(raw_payload: Any) -> Dict[str, Any] | None:
    """Process generic payload (tool, agent, workflow)."""
    if raw_payload is None:
        return None

    parsed = (
        safe_parse_json(raw_payload) if isinstance(raw_payload, str) else raw_payload
    )

    # If parsing failed but we have a string, wrap it
    if parsed is None and raw_payload is not None:
        return {"value": raw_payload}

    return parsed


def _calculate_end_time(start_time_str: str | None, duration_ns: Any) -> str | None:
    """Calculate end time from start time and duration."""
    if start_time_str and duration_ns:
        try:
            start_time_float = float(start_time_str)
            return str(start_time_float + float(duration_ns) / 1e9)
        except (ValueError, TypeError):
            return None
    return None


def _calculate_duration_ms(
    start_time_str: str | None, end_time_str: str | None, duration_ns: Any
) -> float | None:
    """Calculate duration in milliseconds from available timing information."""
    # Method 1: Use duration_ns directly if available
    if duration_ns:
        try:
            return float(duration_ns) / 1e6  # Convert nanoseconds to milliseconds
        except (ValueError, TypeError):
            pass

    # Method 2: Calculate from start_time and end_time
    if start_time_str and end_time_str:
        try:
            start_time_float = float(start_time_str)
            end_time_float = float(end_time_str)
            return (
                end_time_float - start_time_float
            ) * 1000  # Convert seconds to milliseconds
        except (ValueError, TypeError):
            pass

    return None


def _check_error_status(
    attrs: Dict[str, Any], output_payload: Dict[str, Any] | None
) -> bool:
    """Check if span contains error indicators."""
    # Check explicit error attribute
    if attrs.get("traceloop.entity.error"):
        return True

    # Check for error patterns in output
    if isinstance(output_payload, dict) and contains_error_like_pattern(output_payload):
        return True

    return False


def _ensure_dict_payload(payload: Any) -> Dict[str, Any] | None:
    """Ensure payload is a dictionary or None."""
    if payload is None:
        return None

    if isinstance(payload, dict):
        return payload

    # Convert non-dict types to dict with 'value' key
    return {"value": payload}
