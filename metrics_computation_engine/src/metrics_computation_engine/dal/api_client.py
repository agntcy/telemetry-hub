#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Standalone DAL reader / writer interface
"""

import json
import logging
import os
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from pydantic_settings import BaseSettings

# Import entities for SessionSet processing
from metrics_computation_engine.entities.models.session_set import SessionSet
from metrics_computation_engine.entities.core.trace_processor import (
    TraceProcessor,
    create_pseudo_grouped_sessions_from_file,
)
from metrics_computation_engine.models.eval import MetricResult
from .utils import format_metric_payload

# Load environment variables
load_dotenv()


def check_metrics_conditions(list_of_json_objects: list) -> bool:
    """
    Analyzes a list of JSON objects to check if any object's 'metrics' attribute
    matches specific conditions.

    Used conditionally to decide whether to skip writing metrics for a session.
    Returns True if:
    - 'metrics.aggregation_level' is set AND
    - 'metrics.category' is set AND
    - 'metrics.name' is set

    Otherwise, returns False.

    Args:
        list_of_json_objects (list): A list of dictionaries (representing JSON objects).

    Returns:
        bool: True if any object meets the conditions, False otherwise.
    """
    for obj in list_of_json_objects:
        if isinstance(obj, dict) and "metrics" in obj:
            metrics = obj["metrics"]
            if isinstance(metrics, dict):
                aggregation_level = metrics.get("aggregation_level", None)
                category = metrics.get("category", None)
                name = metrics.get("name", None)

                # Condition
                if (
                    aggregation_level is not None
                    and category is not None
                    and name is not None
                ):
                    return True
    return False


class ApiClientConfig(BaseSettings):
    """Configuration for API access."""

    type: str = "API"
    base_url: str = "http://localhost:8000"
    api_limit: int = 50
    verify_ssl: bool = True
    base_writer_url: str = "http://localhost:8000"
    verify_writer_ssl: bool = True
    uri_session: str = "/traces/session/"
    uri_sessions: str = "/traces/sessions"
    uri_sessions_spans: str = "/traces/sessions/spans"
    uri_session_metric: str = "/metrics/session"
    uri_span_metric: str = "/metrics/span"
    uri_population_metric: Optional[str] = None  # None means not implemented


class ApiClient:
    """
    Standalone API client for file and API operations.

    This class provides a simplified interface that works independently
    without requiring the full DAL infrastructure.
    """

    def __init__(
        self, devlimit: Optional[int] = None, logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the API client.

        Args:
            devlimit: Maximum number of sessions to retrieve (-1 for no limit)
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.devlimit = devlimit or -1
        self.trace_processor = TraceProcessor()

        # Setup API configuration
        self._api_config = self._setup_api_config()

    def _setup_api_config(self) -> Optional[ApiClientConfig]:
        """Setup API configuration from environment variables and extra_config.yaml."""
        try:
            # Load base URL from environment
            base_url = os.environ.get("API_BASE_URL")
            if not base_url:
                self.logger.debug(
                    "No API base URL configured, API operations will be unavailable"
                )
                return None

            # Load all environment configuration
            config_params = {
                "base_url": os.environ.get("API_BASE_URL", "http://localhost"),
                "type": "API",
                "verify_ssl": os.environ.get("API_VERIFY_SSL", "true").lower()
                == "true",
                "base_writer_url": os.environ.get("WRITER_API_BASE_URL", base_url),
                "verify_writer_ssl": os.environ.get(
                    "WRITER_API_VERIFY_SSL", "true"
                ).lower()
                == "true",
            }

            config = ApiClientConfig(**config_params)

            self.logger.debug(f"API configuration loaded: {config}")
            return config

        except Exception as e:
            self.logger.warning(f"Could not setup API configuration: {e}")
            return None

    def _get_api_request(
        self, endpoint: str, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Make a GET API request for the specified endpoint."""
        if not self._api_config:
            raise ValueError("API configuration not available")

        url = f"{self._api_config.base_url.rstrip('/')}{endpoint}"

        # Add authentication headers if available
        headers = {}
        auth_header = os.environ.get("DB_ADAPTER_TYPE_API_HEADERS")
        if auth_header:
            try:
                headers.update(json.loads(auth_header))
            except json.JSONDecodeError:
                self.logger.warning("Invalid JSON in API headers environment variable")

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                verify=self._api_config.verify_ssl,
                timeout=30,
            )
            response.raise_for_status()

            return response.json()

        except requests.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse API response: {e}")
            raise

    def _post_api_request(self, endpoint: str, data: Dict[str, Any] = None) -> int:
        """Make a POST API request to the specified endpoint."""
        if not self._api_config:
            raise ValueError("API configuration not available")

        url = f"{self._api_config.base_url.rstrip('/')}{endpoint}"

        # Add authentication headers if available
        headers = {"Content-Type": "application/json"}
        auth_header = os.environ.get("DB_ADAPTER_TYPE_API_HEADERS")
        if auth_header:
            try:
                headers.update(json.loads(auth_header))
            except json.JSONDecodeError:
                self.logger.warning("Invalid JSON in API headers environment variable")

        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                verify=self._api_config.verify_ssl,
                timeout=30,
            )
            response.raise_for_status()

            return response.status_code

        except requests.RequestException as e:
            self.logger.error(f"API POST request failed: {e}")
            raise

    def get_traces_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load traces from a local JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            List of trace dictionaries
        """
        self.logger.info(f"Loading traces from file: {file_path}")

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path_obj, "r") as f:
            try:
                # Try to load as JSON array first
                data = json.load(f)
                if isinstance(data, list):
                    traces = data
                else:
                    traces = [data]
            except json.JSONDecodeError:
                # Try as JSON Lines format
                f.seek(0)
                traces = []
                for line in f:
                    line = line.strip()
                    if line:
                        traces.append(json.loads(line))

        self.logger.info(f"Loaded {len(traces)} trace records from file")
        return traces

    def get_session_spans(self, session_id: str) -> tuple[List[Dict], List[str]]:
        """
        Get session for a specific session ID.

        Returns:
            A tuple containing:
            - A list of spans as dicts
            - A list of not found session IDs
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Getting session details for {session_id=}")

        response = self._get_api_request(
            self._api_config.uri_sessions_spans + f"?session_ids={session_id}"
        )

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"API response: {response}")

        if response is None:
            self.logger.warning(
                f"No response retrieved from API for session {session_id}"
            )
            return [], [session_id]

        # Handle not found session IDs
        not_found_session_ids = (
            response.get("notfound_session_ids", []) if response else []
        )
        # Handle case where notfound_session_ids is None
        if not_found_session_ids is None:
            not_found_session_ids = []

        # Check if data exists and contains the requested session
        data = response.get("data", {}) if response else {}
        if not data or session_id not in data:
            # If session not found, add to not found list if not already there
            if session_id not in not_found_session_ids:
                not_found_session_ids.append(session_id)
            return [], not_found_session_ids

        _spans = data.get(session_id, [])

        # Handle case where _spans is None
        if _spans is None:
            _spans = []

        # Process spans if they exist
        for _s in _spans:
            if _s is None:
                continue

            _id = _s["SpanAttributes"].get(
                "session.id", _s["SpanAttributes"].get("execution.id")
            )
            _s["sessionId"] = _id
            _timestamp = datetime.fromisoformat(_s["Timestamp"])
            _s["startTime"] = _timestamp.timestamp()
            _s["duration"] = _s["Duration"] * 0.000001
            _s["statusCode"] = (
                2 if _s["StatusCode"] in ["Error", "STATUS_CODE_ERROR"] else 0
            )
            span_kind = _s["SpanAttributes"].get("traceloop.span.kind", "")
            _s["FrameworkSpanKind"] = str(span_kind).upper()
        return _spans, not_found_session_ids

    def _get_spans_by_session_ids_batch(
        self, session_ids: List[str]
    ) -> tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
        """
        Session spans retrieval by session ids using batch processing.

        Args:
            session_ids: List of session IDs to retrieve spans for

        Returns:
            A tuple containing:
            - Dictionary mapping session IDs to span lists
            - List of not found session IDs
        """
        _batch_size = int(os.getenv("SESSIONS_TRACES_MAX", "20"))
        all_sessions: Dict[str, List[Dict[str, Any]]] = {}
        all_not_found_ids: List[str] = []

        # Process session_ids in chunks
        for i in range(0, len(session_ids), _batch_size):
            batch_session_ids = session_ids[i : i + _batch_size]
            _session_ids = ",".join(batch_session_ids)

            self.logger.info(
                f"Retrieving spans for batch {i // _batch_size + 1}: {len(batch_session_ids)} sessions"
            )

            try:
                response = self._get_api_request(
                    self._api_config.uri_sessions_spans + f"?session_ids={_session_ids}"
                )

                if response is None:
                    self.logger.warning(
                        f"No response retrieved from API for batch: {batch_session_ids}"
                    )
                    all_not_found_ids.extend(batch_session_ids)
                    continue

                # Get current batch results
                current_sessions = response.get("data", {})
                current_not_found_ids = response.get("notfound_session_ids", []) or []

                # Process and aggregate results
                for session_id, spans in current_sessions.items():
                    if spans is None:
                        spans = []

                    # Process spans (same logic as get_session_spans)
                    for _s in spans:
                        if _s is None:
                            continue

                        _id = _s["SpanAttributes"].get(
                            "session.id", _s["SpanAttributes"].get("execution.id")
                        )
                        _s["sessionId"] = _id
                        _timestamp = datetime.fromisoformat(_s["Timestamp"])
                        _s["startTime"] = _timestamp.timestamp()
                        _s["duration"] = _s["Duration"] * 0.000001
                        _s["statusCode"] = (
                            2
                            if _s["StatusCode"] in ["Error", "STATUS_CODE_ERROR"]
                            else 0
                        )
                        span_kind = _s["SpanAttributes"].get("traceloop.span.kind", "")
                        _s["FrameworkSpanKind"] = str(span_kind).upper()

                    all_sessions[session_id] = spans

                # Aggregate not found IDs
                all_not_found_ids.extend(current_not_found_ids)

                self.logger.info(
                    f"Batch {i // _batch_size + 1}: Retrieved {len(current_sessions)} sessions, {len(current_not_found_ids)} not found"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to retrieve spans for batch {batch_session_ids}: {e}"
                )
                # Add entire batch to not found on error
                all_not_found_ids.extend(batch_session_ids)

        self.logger.info(
            f"Total spans retrieval: {len(all_sessions)} sessions retrieved, {len(all_not_found_ids)} not found"
        )
        return all_sessions, all_not_found_ids

    def _get_all_session_ids_paginated(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> List[str]:
        """
        Session ids retrieval with pagination logic.

        Args:
            start_time: Start time in ISO format
            end_time: End time in ISO format
            prefix: App prefix filter

        Returns:
            List of session IDs retrieved across all pages
        """
        # Get max sessions limit - use devlimit if set, otherwise use environment or default
        if self.devlimit > 0:
            _max_sessions = self.devlimit
        else:
            _max_sessions = int(os.getenv("PAGINATION_DEFAULT_MAX_SESSIONS", "50"))

        # Get limit per page from environment or use a reasonable default
        _limit_per_page = int(os.getenv("PAGINATION_LIMIT", "50"))
        _limit_per_page = min(_limit_per_page, _max_sessions)
        _page = 0
        all_session_ids = []

        while len(all_session_ids) < _max_sessions:
            # Adjust limit for the current page if we're close to _max_sessions
            remaining_sessions = _max_sessions - len(all_session_ids)
            current_limit = min(_limit_per_page, remaining_sessions)

            params = {
                "limit": current_limit,
                "page": _page,
            }
            if start_time:
                params["start_time"] = start_time
            if end_time:
                params["end_time"] = end_time
            if prefix:
                params["name"] = prefix

            # Make API request for current page
            endpoint = self._api_config.uri_sessions
            response = self._get_api_request(endpoint, params)

            # Extract session IDs from current page
            self.logger.info(f"Page {_page} Session Ids response: {response}")

            page_session_ids = [
                session.get("id")
                for session in response.get("data", [])
                if session.get("id")
            ]
            all_session_ids.extend(page_session_ids)

            # Check if there are no more results on this page
            if len(page_session_ids) == 0:
                self.logger.info(
                    f"No more session IDs found on page {_page}, stopping pagination"
                )
                break

            # Increment the pagination for next iteration
            _page += 1
            self.logger.info(
                f"Retrieved {len(page_session_ids)} session IDs from page {_page - 1}, total so far: {len(all_session_ids)}"
            )

        if len(all_session_ids) == 0:
            return []

        # Return only up to _max_sessions
        # (in case the last page gave us more than needed)
        final_session_ids = all_session_ids[: min(_max_sessions, len(all_session_ids))]
        self.logger.info(
            f"Returning {len(final_session_ids)} session IDs (max: {_max_sessions})"
        )
        return final_session_ids

    def get_population_set(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        prefix: Optional[str] = None,
        session_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
        """
        Get population set from file or API.

        Args:
            eval_uuid: Evaluation UUID (unused in simplified version)
            start_time: Start time in ISO format
            end_time: End time in ISO format
            prefix: App prefix filter
            session_id: Specific session ID to retrieve
            file_path: If provided, load from local file instead of API

        Returns:
            A tuple containing:
            - Dictionary mapping session IDs to trace lists
            - List of not found session IDs (empty for file-based operations)
        """
        # Handle file loading
        if file_path:
            traces = self.get_traces_from_file(file_path)
            # Convert to session format expected by trace_inspector
            sessions = {}
            for i, trace in enumerate(traces):
                # Use existing session_id if available, otherwise generate one
                sess_id = trace.get("session_id", f"file_session_{i}")
                if sess_id not in sessions:
                    sessions[sess_id] = []
                sessions[sess_id].append(trace)

            self.logger.info(f"Loaded {len(sessions)} sessions from file")
            return sessions, []  # No not found IDs for file operations

        # Handle API loading
        if not self._api_config:
            raise ValueError(
                "API configuration not available and no file_path provided"
            )

        # First, we retrieve session IDs with pagination
        self.logger.info("Loading session ids from remote API")

        try:
            if session_id:
                # Get specific session
                session_ids = [session_id]
                self.logger.info("Retrieved 1 specific session id from API")
            else:
                # Get multiple sessions using pagination
                session_ids = self._get_all_session_ids_paginated(
                    start_time, end_time, prefix
                )
                self.logger.info(
                    f"Retrieved {len(session_ids)} session ids from API using pagination"
                )
        except Exception as e:
            self.logger.error(f"Failed to retrieve data from API: {e}")
            raise

        # Second, we retrieve spans for all session ids using batch processing
        if not session_ids:
            self.logger.info("No session IDs to process")
            return {}, []

        self.logger.info(
            f"Retrieving spans for {len(session_ids)} sessions using batch processing"
        )
        sessions, all_not_found_ids = self._get_spans_by_session_ids_batch(session_ids)

        return sessions, all_not_found_ids

    def load_session_set_from_file(self, file_path: str) -> SessionSet:
        """
        Load traces from a file and return a processed SessionSet.

        Args:
            file_path: Path to the trace file

        Returns:
            Processed SessionSet with enriched data
        """
        self.logger.info(f"Loading session set from file: {file_path}")

        # Get raw traces from file
        raw_traces = self.get_traces_from_file(file_path)

        self.logger.info(f"Processing {len(raw_traces)} raw trace records from file")

        # Create pseudo-grouped sessions for file data to match API structure
        grouped_sessions = create_pseudo_grouped_sessions_from_file(raw_traces)

        self.logger.info(f"Grouped traces into {len(grouped_sessions)} sessions")

        # Use the optimized grouped processing
        session_set = self.trace_processor.process_grouped_sessions(grouped_sessions)

        self.logger.info("Session enrichment completed")

        return session_set

    def get_session_metrics(self, session_id: str) -> SessionSet:
        """
        Retrieve Metrics.

        Args:
            session_id: The ID of the session to retrieve metrics for

        Returns:
            Processed SessionSet with enriched data
        """
        self.logger.info(f"Retrieving metrics for {session_id=}")
        _uri_get_metrics = (
            f"{self._api_config.uri_session_metric.rstrip('/')}/{session_id}"
        )

        metrics = self._get_api_request(endpoint=_uri_get_metrics)
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"API response for metrics: {len(metrics)=}")
        """if check_metrics_conditions(data):
            self.logger.warning(f'Skipping metrics write for {session[0]=} as metrics already exist')
            break"""
        return metrics

    def cache_metrics(self, results: Dict[str, List[MetricResult]]):
        """
        Cache metrics results.

        Args:
            results: The metrics results to cache
        """
        self.logger.info("Caching metrics results")
        # Implement caching logic here
        for metric_category, metric_results in results.items():
            metric_category = metric_category.split("_")[0].lower()
            if metric_category not in ["session", "span"] and len(metric_results) > 0:
                self.logger.warning(
                    f"⚠️ Skipping {metric_category}: endpoint not implemented."
                )
                continue
            for r in metric_results:
                assert isinstance(r, MetricResult)

                if r.from_cache is True:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(
                            f"Skip {r.metric_name} {r.session_id=}: from_cache=True"
                        )
                    continue

                metric_data = format_metric_payload(
                    metric=r, app_id="", app_name=r.app_name, trace_id=""
                )

                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(
                        f"Prepared metric data for {metric_data['session_id']=}: {metric_data}"
                    )
                # select the endpoint
                _endpoint = self._api_config.uri_session_metric
                if metric_category == "span ":
                    _endpoint = self._api_config.uri_span_metric

                # run the query
                status = self._post_api_request(
                    endpoint=_endpoint, data=metric_data
                )
                self.logger.info(
                    f"write {metric_category} metrics {metric_data['session_id']=}: {status}"
                )


# Global instance for reuse
_global_api_client = None


def get_api_client(
    devlimit: Optional[int] = None, logger: Optional[logging.Logger] = None
) -> "ApiClient":
    """
    Get or create a global ApiClient instance to avoid repeated initialization.
    """
    global _global_api_client
    if _global_api_client is None:
        _global_api_client = ApiClient(devlimit=devlimit, logger=logger)
    return _global_api_client


def reset_api_client():
    """
    Reset the global ApiClient instance. Useful for testing or configuration changes.
    """
    global _global_api_client
    _global_api_client = None


# Standalone functions for backward compatibility with main.py
def get_all_session_ids(batch_config) -> List[str]:
    """
    Get all session IDs using batch config parameters.
    This function provides backward compatibility with the existing API.
    """
    api_client = get_api_client()

    # Convert batch_config to parameters
    start_time = (
        batch_config.get_time_range().get_start()
        if batch_config.has_time_range()
        else None
    )
    end_time = (
        batch_config.get_time_range().get_end()
        if batch_config.has_time_range()
        else None
    )
    prefix = batch_config.get_app_name() if batch_config.has_app_name() else None

    # Get population set and extract session IDs
    sessions_data, _ = api_client.get_population_set(
        start_time=start_time, end_time=end_time, prefix=prefix
    )

    session_ids = list(sessions_data.keys())

    # Apply session limit if specified
    if batch_config.has_num_sessions():
        max_sessions = batch_config.get_num_sessions()
        session_ids = session_ids[:max_sessions]

    return session_ids


def get_traces_by_session_ids(
    session_ids: List[str],
) -> tuple[Dict[str, List[Any]], List[str]]:
    """
    Get traces for multiple session IDs.
    Returns (traces_by_session_dict, notfound_session_ids).
    """
    api_client = get_api_client()
    return api_client._get_spans_by_session_ids_batch(session_ids)


def get_traces_by_session(session_id: str) -> List[Any]:
    """
    Get traces for a single session ID.
    """
    api_client = get_api_client()
    spans, not_found = api_client.get_session_spans(session_id)
    return spans


def traces_processor(grouped_sessions: Dict[str, List[Any]]) -> SessionSet:
    """
    Get a TraceProcessor instance.
    """
    api_client = get_api_client()
    return api_client.trace_processor.process_grouped_sessions(grouped_sessions)
