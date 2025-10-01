#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
SessionSet Printer Module

Contains utility functions for displaying SessionSet data in various formats.
These functions provide detailed views of sessions, execution trees, and statistics.
"""

import json
from typing import Optional
from .session_set import SessionSet


def print_execution_tree(execution_tree, max_depth: int = 3):
    """
    Print a detailed view of the execution tree structure.

    Args:
        execution_tree: ExecutionTree object containing traces and flows
        max_depth: Maximum depth to print (default: 3)
    """
    if not execution_tree:
        return

    print("\n" + "=" * 60)
    print("EXECUTION TREE DETAILS")
    print("=" * 60)

    for trace_id, roots in execution_tree.traces.items():
        print(f"\nTrace ID: {trace_id}")
        print("-" * 40)

        for root in roots:
            _print_tree_node(root, depth=0, max_depth=max_depth)


def _print_tree_node(node, depth: int = 0, max_depth: int = 3):
    """
    Recursively print tree nodes with proper indentation.

    Args:
        node: Tree node to print
        depth: Current depth level
        max_depth: Maximum depth to print
    """
    if depth > max_depth:
        print("  " * depth + "... (truncated)")
        return

    indent = "  " * depth
    span = node.span

    # Format span information
    span_info = f"{span.entity_type}:{span.entity_name}"
    if hasattr(span, "duration") and span.duration:
        span_info += f" ({span.duration:.1f}ms)"

    print(f"{indent}├─ {span_info}")

    # Print children
    for child in node.children:
        _print_tree_node(child, depth + 1, max_depth)


def print_session_summary(session_set: SessionSet):
    """
    Print a summary of sessions found in the SessionSet.

    Args:
        session_set: SessionSet object containing session data
    """
    print("\n" + "=" * 60)
    print(f"SESSION SUMMARY - {len(session_set.sessions)} sessions found")
    print("=" * 60)

    for i, session in enumerate(session_set.sessions, 1):
        print(f"\n[Session {i}] ID: {session.session_id}")
        print(f"  Time Range: {session.time_range}")
        print(f"  Total Spans: {session.total_spans}")

        # Show execution tree info if available
        if session.execution_tree:
            tree_stats = f"{len(session.execution_tree.traces)} traces, {session.execution_tree.total_spans} flows"
            print(f"  Execution Tree: {tree_stats}")

        # Show entity breakdown
        entity_counts = {}
        for span in session.spans:
            entity_type = span.entity_type
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

        print("  Entity Breakdown:")
        for entity_type, count in sorted(entity_counts.items()):
            print(f"    {entity_type}: {count}")


def print_statistics(session_set: SessionSet):
    """
    Print comprehensive statistics for the SessionSet.

    Args:
        session_set: SessionSet object containing session data
    """
    print("\n" + "=" * 80)
    print("SESSION SET STATISTICS")
    print("=" * 80)

    stats = session_set.stats
    stats_json = stats.model_dump()

    print(json.dumps(stats_json, indent=2))
    print("=" * 80)


def print_detailed_session_info(
    session_set: SessionSet, tree_depth: Optional[int] = None
):
    """
    Print detailed information about all sessions including execution trees.

    Args:
        session_set: SessionSet object containing session data
        tree_depth: Maximum depth for execution tree display (default: 3)
    """
    if tree_depth is None:
        tree_depth = 3

    print_session_summary(session_set)

    for session in session_set.sessions:
        if session.execution_tree:
            print(f"\n{'=' * 60}")
            print(f"EXECUTION TREE - Session: {session.session_id}")
            print("=" * 60)
            print_execution_tree(session.execution_tree, tree_depth)


# Convenience function that combines multiple display options
def display_session_set(
    session_set: SessionSet,
    show_summary: bool = True,
    show_trees: bool = False,
    show_statistics: bool = True,
    tree_depth: int = 3,
):
    """
    Display SessionSet information with configurable options.

    Args:
        session_set: SessionSet object to display
        show_summary: Whether to show session summary (default: True)
        show_trees: Whether to show execution trees (default: False)
        show_statistics: Whether to show statistics (default: True)
        tree_depth: Maximum depth for execution tree display (default: 3)
    """
    if show_summary:
        print_session_summary(session_set)

    if show_trees:
        for session in session_set.sessions:
            if session.execution_tree:
                print(f"\n{'=' * 60}")
                print(f"EXECUTION TREE - Session: {session.session_id}")
                print("=" * 60)
                print_execution_tree(session.execution_tree, tree_depth)

    if show_statistics:
        print_statistics(session_set)
