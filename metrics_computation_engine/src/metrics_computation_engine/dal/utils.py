# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import asdict, is_dataclass


def sanitize_metric(metric):
    if isinstance(metric, dict):
        return {k: sanitize_metric(v) for k, v in metric.items()}
    elif isinstance(metric, list):
        return [sanitize_metric(v) for v in metric]
    elif isinstance(metric, BaseException):
        return str(metric)
    else:
        return metric


def format_metric_payload(metric, app_id, app_name, trace_id):
    if is_dataclass(metric):
        metric = asdict(metric)
    metric = sanitize_metric(metric)

    session_ids = metric.get("session_id", [])
    span_ids = metric.get("span_id", [])

    session_id = (
        session_ids[0]
        if isinstance(session_ids, list) and session_ids
        else "default_session_id"
    )
    span_id = (
        span_ids[0] if isinstance(span_ids, list) and span_ids else "default_span_id"
    )
    trace_id = trace_id or "default_trace_id"
    app_id = app_id or "default_app_id"
    app_name = app_name or "default_app_name"

    return {
        "app_id": app_id,
        "app_name": app_name,
        "metrics": metric,
        "session_id": session_id,
        "span_id": span_id,
        "trace_id": trace_id,
    }
