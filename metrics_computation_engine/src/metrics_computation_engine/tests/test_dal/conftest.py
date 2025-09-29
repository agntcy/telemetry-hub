#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Pytest configuration and fixtures for dal tests.
"""

import pytest
import json
import logging
from pathlib import Path
from typing import Dict, List

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "local" / "data"


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("unit_test")


@pytest.fixture
def api_noa_2_data() -> List[Dict]:
    """Load api_noa_2.json test data."""
    file_path = TEST_DATA_DIR / "api_noa_2.json"
    with open(file_path, "r") as f:
        return json.load(f)


@pytest.fixture
def gls_linear_data() -> List[Dict]:
    """Load gls_linear.json test data."""
    file_path = TEST_DATA_DIR / "gls_linear.json"
    with open(file_path, "r") as f:
        return json.load(f)


@pytest.fixture
def api_noa_2_file_path() -> str:
    """Provide path to api_noa_2.json file."""
    return str(TEST_DATA_DIR / "api_noa_2.json")


@pytest.fixture
def gls_linear_file_path() -> str:
    """Provide path to gls_linear.json file."""
    return str(TEST_DATA_DIR / "gls_linear.json")


@pytest.fixture
def sample_trace_data() -> List[Dict]:
    """Provide minimal sample trace data for unit tests."""
    return [
        {
            "Timestamp": "2025-09-10T14:26:57.794657Z",
            "TraceId": "test-trace-1",
            "SpanId": "test-span-1",
            "ParentSpanId": "",
            "SpanName": "test_agent.agent",
            "SpanKind": "Server",
            "ServiceName": "test-service",
            "ResourceAttributes": {"service.name": "test-service"},
            "SpanAttributes": {
                "session_id": "test-session-1",
                "agent_id": "test-agent",
            },
        },
        {
            "Timestamp": "2025-09-10T14:26:58.794657Z",
            "TraceId": "test-trace-1",
            "SpanId": "test-span-2",
            "ParentSpanId": "test-span-1",
            "SpanName": "test_tool.tool",
            "SpanKind": "Client",
            "ServiceName": "test-service",
            "ResourceAttributes": {"service.name": "test-service"},
            "SpanAttributes": {
                "session_id": "test-session-1",
                "agent_id": "test-agent",
            },
        },
    ]


# Configure pytest
def pytest_configure(config):
    """Configure pytest."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@pytest.fixture
def real_session_set(logger, api_noa_2_file_path):
    """Provide a real SessionSet loaded from actual data."""
    from metrics_computation_engine.dal import ApiClient

    client = ApiClient(logger=logger)
    return client.load_session_set_from_file(api_noa_2_file_path)


@pytest.fixture
def sample_session_set(sample_trace_data, logger):
    """Provide a sample SessionSet for testing."""
    from metrics_computation_engine.entities.models.session_set import SessionSet
    from metrics_computation_engine.entities.models.session import SessionEntity

    # Create a simple SessionSet for testing
    # Note: In reality, SessionSets are created by the ApiClient processing pipeline
    # For testing, we create a minimal valid structure
    sessions = []

    session = SessionEntity(
        session_id="test-session-1",
        spans=[],
        total_spans=0,
        duration=0.0,
        agent_transitions=None,
        agent_transition_counts=None,
        conversation_elements=None,
        tool_calls=None,
        user_input=None,
        final_response=None,
    )
    sessions.append(session)

    return SessionSet(sessions=sessions)


@pytest.fixture
def sample_session_with_tree(sample_session_set):
    """Provide a session that has an execution tree."""
    # Return the first session, assuming it might have an execution tree
    if sample_session_set.sessions:
        session = sample_session_set.sessions[0]
        # Create a proper ExecutionTree mock
        from metrics_computation_engine.entities.models.execution_tree import (
            ExecutionTree,
        )

        session.execution_tree = ExecutionTree(traces={}, all_nodes={}, total_spans=0)
        return session

    # Create a mock session with execution tree if needed
    from metrics_computation_engine.entities.models.session import SessionEntity
    from metrics_computation_engine.entities.models.execution_tree import ExecutionTree

    session = SessionEntity(
        session_id="test_session_with_tree",
        spans=[],
        total_spans=0,
        duration=0.0,
        agent_transitions=None,
        agent_transition_counts=None,
        conversation_elements=None,
        tool_calls=None,
        user_input=None,
        final_response=None,
    )

    # Create a proper ExecutionTree mock
    session.execution_tree = ExecutionTree(traces={}, all_nodes={}, total_spans=0)

    return session


@pytest.fixture
def sample_session_without_tree(sample_session_set):
    """Provide a session that does not have an execution tree."""
    # Create a session without execution tree
    from metrics_computation_engine.entities.models.session import SessionEntity

    session = SessionEntity(
        session_id="test_session_without_tree",
        spans=[],
        total_spans=0,
        duration=0.0,
        agent_transitions=None,
        agent_transition_counts=None,
        conversation_elements=None,
        tool_calls=None,
        user_input=None,
        final_response=None,
    )

    # Ensure no execution tree
    session.execution_tree = None

    return session
