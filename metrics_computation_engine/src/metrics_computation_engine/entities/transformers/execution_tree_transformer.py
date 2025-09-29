# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Execution tree transformer for building hierarchical span relationships.
"""

from typing import Dict, Any
from .base import DataPreservingTransformer
from ..models.session import SessionEntity
from ..models.execution_tree import build_execution_tree


class ExecutionTreeTransformer(DataPreservingTransformer):
    """
    Builds a hierarchical execution tree showing parent-child relationships between spans.
    Uses trace_id and parent_span_id to construct the tree structure.
    """

    def extract(self, session: SessionEntity) -> Dict[str, Any]:
        """Build execution tree from session spans."""
        if not isinstance(session, SessionEntity) or not session.spans:
            return {}

        # Build the execution tree
        execution_tree = build_execution_tree(session.spans)

        # Get hierarchy summary for easy access
        hierarchy_summary = execution_tree.get_summary()

        return {
            "execution_tree": execution_tree,
            "hierarchy_summary": hierarchy_summary,
        }
