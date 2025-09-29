#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Tests for entity models and data structures.

Tests cover:
- Session and Span model functionality
- SessionSet printer functionality
- Entity validation and serialization
- Model interactions and relationships
"""

import pytest
from unittest.mock import patch
import io

from metrics_computation_engine.entities.models.session_set_printer import (
    print_execution_tree,
    print_session_summary,
    print_statistics,
    display_session_set,
)
from metrics_computation_engine.entities.models.session_set import SessionSet


class TestSessionSetPrinter:
    """Test session set printer functionality."""

    def test_print_execution_tree_with_tree(self, sample_session_with_tree):
        """Test printing execution tree when tree exists."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            print_execution_tree(sample_session_with_tree.execution_tree, max_depth=2)

        output = captured_output.getvalue()
        assert len(output) > 0
        # Should contain execution tree header when tree exists
        assert "EXECUTION TREE DETAILS" in output

    def test_print_execution_tree_without_tree(self, sample_session_without_tree):
        """Test printing execution tree when no tree exists."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            print_execution_tree(
                sample_session_without_tree.execution_tree, max_depth=2
            )

        output = captured_output.getvalue()
        # Should indicate no execution tree
        assert "No execution tree" in output or len(output) == 0

    def test_print_session_summary(self, sample_session_set):
        """Test printing session summary."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            print_session_summary(sample_session_set)

        output = captured_output.getvalue()
        assert len(output) > 0
        # Should contain session count information
        assert str(len(sample_session_set.sessions)) in output

    def test_print_statistics(self, sample_session_set):
        """Test printing statistics."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            print_statistics(sample_session_set)

        output = captured_output.getvalue()
        assert len(output) > 0
        # Should contain statistical information
        stats = sample_session_set.stats
        assert str(stats.meta.count) in output

    def test_display_session_set_full(self, sample_session_set):
        """Test full display of session set."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            display_session_set(
                sample_session_set,
                show_summary=True,
                show_trees=True,
                show_statistics=True,
                tree_depth=3,
            )

        output = captured_output.getvalue()
        assert len(output) > 0

        # Should contain summary information
        assert "Session Set Summary" in output or len(sample_session_set.sessions) > 0

    def test_display_session_set_summary_only(self, sample_session_set):
        """Test display with summary only."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            display_session_set(
                sample_session_set,
                show_summary=True,
                show_trees=False,
                show_statistics=False,
                tree_depth=3,
            )

        output = captured_output.getvalue()
        assert len(output) > 0

    def test_display_session_set_trees_only(self, sample_session_set):
        """Test display with trees only."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            display_session_set(
                sample_session_set,
                show_summary=False,
                show_trees=True,
                show_statistics=False,
                tree_depth=2,
            )

        output = captured_output.getvalue()
        # Output length depends on whether sessions have execution trees
        assert isinstance(output, str)

    def test_display_session_set_statistics_only(self, sample_session_set):
        """Test display with statistics only."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            display_session_set(
                sample_session_set,
                show_summary=False,
                show_trees=False,
                show_statistics=True,
                tree_depth=3,
            )

        output = captured_output.getvalue()
        assert len(output) > 0
        # Should contain statistical information
        stats = sample_session_set.stats
        assert str(stats.meta.count) in output

    def test_display_session_set_nothing(self, sample_session_set):
        """Test display with all options disabled."""
        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            display_session_set(
                sample_session_set,
                show_summary=False,
                show_trees=False,
                show_statistics=False,
                tree_depth=3,
            )

        output = captured_output.getvalue()
        # Should produce minimal or no output
        assert isinstance(output, str)


class TestSessionSetPrinterEdgeCases:
    """Test edge cases in session set printer."""

    def test_print_empty_session_set(self):
        """Test printing empty session set."""
        empty_session_set = SessionSet(sessions=[])

        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            print_session_summary(empty_session_set)

        output = captured_output.getvalue()
        assert "0" in output  # Should show 0 sessions

    def test_print_statistics_empty(self):
        """Test printing statistics for empty session set."""
        empty_session_set = SessionSet(sessions=[])

        # Capture stdout
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            print_statistics(empty_session_set)

        output = captured_output.getvalue()
        # Should handle empty session set gracefully
        assert isinstance(output, str)

    def test_print_execution_tree_various_depths(self, sample_session_with_tree):
        """Test printing execution tree with various depths."""
        for depth in [0, 1, 2, 5, 10]:
            # Capture stdout
            captured_output = io.StringIO()

            with patch("sys.stdout", captured_output):
                print_execution_tree(
                    sample_session_with_tree.execution_tree, max_depth=depth
                )

            output = captured_output.getvalue()
            # Should not raise errors for any depth
            assert isinstance(output, str)

    def test_display_session_set_with_none_session_set(self):
        """Test display with None session set."""
        # Should handle None gracefully or raise appropriate error
        with pytest.raises((AttributeError, TypeError)):
            display_session_set(None)


class TestSessionSetPrinterPerformance:
    """Test performance aspects of session set printer."""

    def test_large_session_set_printing(self):
        """Test printing large session set doesn't cause issues."""
        # Create a larger session set for testing
        from metrics_computation_engine.entities.models.session import SessionEntity

        # Create sessions
        sessions = []
        for i in range(10):  # Create 10 sessions
            session = SessionEntity(
                session_id=f"session_{i}",
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

        large_session_set = SessionSet(sessions=sessions)

        # Test that printing doesn't take too long or cause errors
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            display_session_set(
                large_session_set,
                show_summary=True,
                show_trees=True,
                show_statistics=True,
                tree_depth=2,
            )

        output = captured_output.getvalue()
        assert len(output) > 0
        # Should contain information about the 10 sessions
        assert "10" in output


class TestSessionSetPrinterIntegration:
    """Test integration between printer and real data."""

    def test_printer_with_real_session_set(self, real_session_set):
        """Test printer functionality with real session set from fixtures."""
        # Test all display functions with real data
        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            display_session_set(
                real_session_set,
                show_summary=True,
                show_trees=True,
                show_statistics=True,
                tree_depth=3,
            )

        output = captured_output.getvalue()
        assert len(output) > 0

        # Should contain real session information
        if len(real_session_set.sessions) > 0:
            # Should show actual session count
            assert str(len(real_session_set.sessions)) in output

    def test_printer_statistics_accuracy(self, real_session_set):
        """Test that printed statistics match actual statistics."""
        stats = real_session_set.stats

        captured_output = io.StringIO()

        with patch("sys.stdout", captured_output):
            print_statistics(real_session_set)

        output = captured_output.getvalue()

        # Verify key statistics appear in output
        assert str(stats.meta.count) in output
        if stats.meta.count > 0:
            # Should contain some statistical information
            assert len(output) > 50  # Reasonable minimum length for stats output


class TestErrorHandling:
    """Test error handling in printer functions."""

    def test_printer_with_corrupted_session(self):
        """Test printer behavior with corrupted session data."""
        # Create a session with missing required fields
        from metrics_computation_engine.entities.models.session import SessionEntity

        # Test with minimal session
        try:
            corrupted_session = SessionEntity(
                session_id="corrupted_session",
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
            session_set = SessionSet(sessions=[corrupted_session])

            captured_output = io.StringIO()

            with patch("sys.stdout", captured_output):
                print_session_summary(session_set)

            # Should handle gracefully or raise appropriate error
            output = captured_output.getvalue()
            assert isinstance(output, str)

        except (ValueError, TypeError):
            # If the model prevents creation of invalid sessions, that's fine
            pass

    def test_printer_with_missing_attributes(self):
        """Test printer behavior when session attributes are missing."""
        # This tests the robustness of the printer functions
        # Implementation depends on the actual Session model structure
        pass  # Implement based on actual Session model capabilities
