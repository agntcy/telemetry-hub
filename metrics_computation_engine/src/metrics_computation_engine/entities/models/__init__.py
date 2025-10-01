# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Data models for OpenTelemetry trace inspection.
"""

# Import these modules only when specifically needed to avoid circular imports
from .span import SpanEntity
from .session import SessionEntity
from .session_set import SessionSet
from .execution_tree import ExecutionTree, SpanNode, build_execution_tree

__all__ = [
    "SpanEntity",
    "SessionEntity",
    "SessionSet",
    "ExecutionTree",
    "SpanNode",
    "build_execution_tree",
]
