# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, List
from datetime import datetime, timedelta, timezone

from metrics_computation_engine.core.data_parser import parse_raw_spans
from metrics_computation_engine.dal.client import get_api_response
from metrics_computation_engine.models.span import SpanEntity


def get_traces_by_session(session_id: str) -> List[SpanEntity]:
    raw_spans = get_api_response(
        f"/traces/session/{session_id}", params={"table_name": "traces_raw"}
    )
    return parse_raw_spans(raw_spans)


def get_traces_by_time(start_time: str, end_time: str) -> Dict[str, List[SpanEntity]]:
    session_ids = get_all_session_ids(start_time, end_time)
    traces_by_session: Dict[str, List[SpanEntity]] = {}

    for session_id in session_ids:
        session_traces = get_traces_by_session(session_id)
        traces_by_session[session_id] = session_traces

    return traces_by_session


# Time in ISO 8601 UTC format (e.g. 2023-06-25T15:04:05Z)
def get_all_session_ids(start_time: str, end_time: str):
    response = get_api_response(
        "/traces/sessions",
        params={
            "start_time": start_time,
            "end_time": end_time,
        },
    )
    return [session["id"] for session in response]


# get last n sessions using get_all_session_ids and then picking the last n sessions
def get_last_n_sessions_with_traces(n: int) -> Dict[str, List[SpanEntity]]:
    # Use a generous time window (e.g., past 30 days); adjust as needed
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=30)

    start_time_str = start_time.isoformat().replace("+00:00", "Z")
    end_time_str = end_time.isoformat().replace("+00:00", "Z")

    session_ids = get_all_session_ids(
        start_time=start_time_str,
        end_time=end_time_str,
    )

    traces_by_session: Dict[str, List[SpanEntity]] = {}

    if len(session_ids) == 0:
        return traces_by_session

    # pick the latest n sessions or all of them if n > len(session_ids)
    last_n_sessions = session_ids[0 : min(n, len(session_ids))]

    for session_id in last_n_sessions:
        traces_by_session[session_id] = get_traces_by_session(session_id)

    return traces_by_session
