# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Hierarchical tree structures for representing span execution flows.
"""

from typing import Dict, List, Any
from pydantic import BaseModel, ConfigDict
from ..models.span import SpanEntity


class SpanNode(BaseModel):
    """
    Represents a node in the execution tree.
    """

    span: SpanEntity
    children: List["SpanNode"] = []
    depth: int = 0
    trace_id: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ExecutionTree(BaseModel):
    """
    Represents the complete execution tree for a session.
    Contains multiple trace trees and provides navigation methods.
    """

    traces: Dict[str, List[SpanNode]] = {}  # trace_id -> list of root nodes
    all_nodes: Dict[str, SpanNode] = {}  # span_id -> node (for quick lookup)
    total_spans: int = 0

    def get_roots_by_entity_type(self, entity_type: str) -> List[SpanNode]:
        """Get all root nodes of a specific entity type."""
        roots = []
        for trace_roots in self.traces.values():
            for root in trace_roots:
                if root.span.entity_type == entity_type:
                    roots.append(root)
        return roots

    def get_execution_paths(self) -> List[List[SpanNode]]:
        """Get all execution paths from root to leaf nodes."""
        paths = []

        def traverse_path(node: SpanNode, current_path: List[SpanNode]):
            current_path.append(node)
            if not node.children:
                # Leaf node - complete path
                paths.append(current_path.copy())
            else:
                for child in node.children:
                    traverse_path(child, current_path)
            current_path.pop()

        for trace_roots in self.traces.values():
            for root in trace_roots:
                traverse_path(root, [])

        return paths

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution tree."""
        total_flows = sum(self._count_flows(roots) for roots in self.traces.values())

        return {
            "total_traces": len(self.traces),
            "total_flows": total_flows,
            "trace_details": {
                trace_id: {
                    "root_count": len(roots),
                    "flow_count": self._count_flows(roots),
                }
                for trace_id, roots in self.traces.items()
            },
        }

    def get_total_flows(self) -> int:
        """Get the total number of flows across all traces."""
        return sum(self._count_flows(roots) for roots in self.traces.values())

    def _count_flows(self, nodes: List[SpanNode]) -> int:
        """Count the total number of nodes in a list of root nodes."""
        count = 0
        for node in nodes:
            count += 1 + self._count_flows(node.children)
        return count

    def _analyze_flow(self, node: SpanNode, depth: int = 0) -> Dict[str, Any]:
        """Recursively analyze the flow structure."""
        flow = {
            "entity": f"{node.span.entity_type}:{node.span.entity_name}",
            "span_id": node.span.span_id,
            "depth": depth,
            "children_count": len(node.children),
            "children": [],
        }

        for child in node.children:
            flow["children"].append(self._analyze_flow(child, depth + 1))

        return flow

    def _analyze_entity_hierarchy(self, node: SpanNode, hierarchy: Dict[str, Any]):
        """Analyze parent-child relationships between entity types."""
        parent_type = node.span.entity_type

        if parent_type not in hierarchy:
            hierarchy[parent_type] = {"contains": set(), "count": 0}

        hierarchy[parent_type]["count"] += 1

        for child in node.children:
            child_type = child.span.entity_type
            hierarchy[parent_type]["contains"].add(child_type)
            self._analyze_entity_hierarchy(child, hierarchy)


def build_execution_tree(spans: List[SpanEntity]) -> ExecutionTree:
    """
    Build a hierarchical execution tree from a list of spans.

    Args:
        spans: List of SpanEntity objects

    Returns:
        ExecutionTree representing the hierarchical structure
    """
    if not spans:
        return ExecutionTree()

    # Create nodes for all spans
    nodes: Dict[str, SpanNode] = {}
    for span in spans:
        nodes[span.span_id] = SpanNode(span=span, trace_id=span.trace_id or "unknown")

    # Build parent-child relationships
    roots_by_trace: Dict[str, List[SpanNode]] = {}

    for span in spans:
        node = nodes[span.span_id]
        trace_id = span.trace_id or "unknown"

        if span.parent_span_id and span.parent_span_id in nodes:
            # This span has a parent
            parent_node = nodes[span.parent_span_id]
            parent_node.children.append(node)
            node.depth = parent_node.depth + 1
        else:
            # This is a root node (no parent or parent not found)
            if trace_id not in roots_by_trace:
                roots_by_trace[trace_id] = []
            roots_by_trace[trace_id].append(node)

    # Sort children by timestamp for consistent ordering
    def sort_children_by_timestamp(node: SpanNode):
        node.children.sort(key=lambda child: child.span.timestamp or "")
        for child in node.children:
            sort_children_by_timestamp(child)

    for trace_roots in roots_by_trace.values():
        # Sort roots by timestamp
        trace_roots.sort(key=lambda node: node.span.timestamp or "")
        for root in trace_roots:
            sort_children_by_timestamp(root)

    return ExecutionTree(traces=roots_by_trace, all_nodes=nodes, total_spans=len(spans))


# Update SpanNode to handle forward references
SpanNode.model_rebuild()
