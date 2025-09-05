# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
from typing import List, Tuple, Dict, Any
from collections import defaultdict

from metrics_computation_engine.core.data_parser import parse_raw_spans
from metrics_computation_engine.dal.client import get_api_response
from metrics_computation_engine.models.span import SpanEntity
from metrics_computation_engine.models.session import SessionEntity
from metrics_computation_engine.models.requests import BatchConfig
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


def get_traces_by_session(session_id: str) -> List[SpanEntity]:
    raw_spans = get_api_response(
        f"/traces/session/{session_id}", params={"table_name": "traces_raw"}
    )

    return parse_raw_spans(raw_spans)


def get_traces_by_session_ids(
    session_ids: List[str],
) -> Tuple[List[SpanEntity], List[str]]:
    """
    Session traces retrieval by session ids.
    """
    _batch_size = int(os.getenv("SESSIONS_TRACES_MAX", "20"))
    all_traces_by_session_ids: Dict[str, List[Any]] = {}
    all_notfound_ids: List[str] = []
    # Process session_ids in chunks
    for i in range(0, len(session_ids), _batch_size):
        batch_session_ids = session_ids[i : i + _batch_size]
        _session_ids = ",".join(batch_session_ids)

        response = get_api_response(
            f"/traces/sessions/spans?session_ids={_session_ids}"
        )
        current_traces = response.get("data", {})
        current_notfound_ids = response.get("notfound_session_ids", []) or []

        # Aggregate results
        all_traces_by_session_ids.update(current_traces)
        all_notfound_ids.extend(current_notfound_ids)

    # Hack for return
    for session_id in all_traces_by_session_ids.keys():
        all_traces_by_session_ids[session_id] = parse_raw_spans(
            all_traces_by_session_ids[session_id]
        )
    return all_traces_by_session_ids, all_notfound_ids


# def get_all_session_ids(start_time: str, end_time: str):
#     response = get_api_response(
#         "/traces/sessions",
#         params={
#             "start_time": start_time,
#             "end_time": end_time,
#         },
#     )
#     return [session["id"] for session in response]


def get_all_session_ids(batch_config: BatchConfig) -> List[str]:
    """
    Session ids retrieval by using batch config parameters.
    """
    _max_sessions = int(os.getenv("PAGINATION_DEFAULT_MAX_SESSIONS", "50"))

    if batch_config.get_num_sessions():
        _max_sessions = batch_config.get_num_sessions()

    _limit_per_page = int(os.getenv("PAGINATION_LIMIT", "50"))
    _limit_per_page = min(_limit_per_page, _max_sessions)
    _page = 0
    all_session_ids = []

    params = {
        "start_time": batch_config.get_time_range().get_start(),
        "end_time": batch_config.get_time_range().get_end(),
        "limit": _limit_per_page,
        "page": _page,
    }
    if batch_config.has_app_name():
        params["name"] = batch_config.get_app_name()

    response = get_api_response("/traces/sessions", params=params)

    # Extract session IDs from current page
    logger.info(f"Page Session Ids: {response}")

    all_session_ids = [session["id"] for session in response.get("data", [])]

    while len(all_session_ids) < _max_sessions:
        # Adjust limit for the last page if we're close to _max_sessions
        remaining_sessions = _max_sessions - len(all_session_ids)
        params["limit"] = min(_limit_per_page, remaining_sessions)
        params["page"] = _page

        response = get_api_response("/traces/sessions", params=params)

        # Extract session IDs from current page
        logger.info(f"Page Session Ids: {response}")

        page_session_ids = [session["id"] for session in response.get("data", [])]
        all_session_ids.extend(page_session_ids)

        # Check if there are more pages and if we haven't reached our limit
        # if not response.get("has_next", False) or len(page_session_ids) == 0:
        #     break
        if len(page_session_ids) == 0:
            break

        # increment the pagination
        _page += 1

    if len(all_session_ids) == 0:
        return []

    # Return only up to _max_sessions
    # (in case the last page gave us more than needed)
    return all_session_ids[: min(_max_sessions, len(all_session_ids))]


def build_session_entities(spans: List[SpanEntity]) -> List[SessionEntity]:
    """
    Build SessionEntity objects from a list of SpanEntity objects.
    Groups spans by session_id and creates a SessionEntity for each session.

    Args:
        spans: List of SpanEntity objects

    Returns:
        List of SessionEntity objects, one per unique session_id
    """
    # Group spans by session_id
    sessions_data = defaultdict(list)

    for span in spans:
        if span.session_id:
            sessions_data[span.session_id].append(span)

    # Create SessionEntity objects
    session_entities = []
    for session_id, session_spans in sessions_data.items():
        # Sort spans by timestamp for consistent ordering
        sorted_spans = sorted(session_spans, key=lambda x: x.timestamp or "")

        session_entity = SessionEntity(session_id=session_id, spans=sorted_spans)
        session_entities.append(session_entity)

    return session_entities


def build_session_entities_from_dict(
    sessions_data: Dict[str, List[SpanEntity]],
) -> List[SessionEntity]:
    """
    Build SessionEntity objects from a dictionary mapping session_ids to spans.

    Args:
        sessions_data: Dictionary where keys are session_ids and values are lists of SpanEntity

    Returns:
        List of SessionEntity objects
    """
    session_entities = []

    for session_id, spans in sessions_data.items():
        if spans:  # Only create session if it has spans
            # Sort spans by timestamp for consistent ordering
            sorted_spans = sorted(spans, key=lambda x: x.timestamp or "")

            session_entity = SessionEntity(session_id=session_id, spans=sorted_spans)
            session_entities.append(session_entity)

    return session_entities


def update_traces_workflow(traces_module):
    """
    Update the traces module to support SessionEntity creation.
    This can be used to modify the existing get_traces_by_session_ids function.
    """

    def get_session_entities_by_session_ids(
        session_ids: List[str],
    ) -> List[SessionEntity]:
        """
        Enhanced version of get_traces_by_session_ids that returns SessionEntity objects.
        """
        # Use existing function to get spans
        all_traces_by_session_ids, all_notfound_ids = (
            traces_module.get_traces_by_session_ids(session_ids)
        )

        # Convert to SessionEntity objects
        session_entities = build_session_entities_from_dict(all_traces_by_session_ids)

        return session_entities, all_notfound_ids

    return get_session_entities_by_session_ids
