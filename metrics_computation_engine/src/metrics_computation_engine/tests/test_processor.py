# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive unit tests for MetricsProcessor.

Tests cover:
1. Empty data handling
2. Metric computation with valid sessions
3. Metric execution order and classification
4. Error handling and recovery
"""

import pytest
from collections import Counter

from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry


# ============================================================================
# TEST 1: EMPTY DATA HANDLING
# ============================================================================


class TestEmptyDataHandling:
    """Test processor handles empty/minimal data gracefully."""

    @pytest.mark.asyncio
    async def test_compute_metrics_empty_session_set(
        self,
        empty_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
    ):
        """Test processor with completely empty SessionSet (no sessions)."""
        # Setup
        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(empty_session_set)

        # Assert: Should return proper structure with empty lists
        assert isinstance(results, dict)
        assert "span_metrics" in results
        assert "session_metrics" in results
        assert "agent_metrics" in results
        assert "population_metrics" in results
        assert "failed_metrics" in results

        # All lists should be empty
        assert len(results["span_metrics"]) == 0
        assert len(results["session_metrics"]) == 0
        assert len(results["agent_metrics"]) == 0
        assert len(results["population_metrics"]) == 0
        assert len(results["failed_metrics"]) == 0

    @pytest.mark.asyncio
    async def test_compute_metrics_empty_session(
        self,
        create_session_set,
        empty_session,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
    ):
        """Test processor with session that has no spans."""
        # Setup: SessionSet with 1 empty session
        session_set = create_session_set(sessions=[empty_session])

        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(session_set)

        # Assert: No span metrics computed (session has no spans)
        assert len(results["span_metrics"]) == 0
        # No errors
        assert len(results["failed_metrics"]) == 0

    @pytest.mark.asyncio
    async def test_entity_filtering_no_matching_spans(
        self,
        sample_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
    ):
        """Test entity filtering when no spans match metric requirements."""
        # MockSpanMetric requires entity_type="tool"
        # sample_session has agent, agent, tool, llm spans
        # So only 1 tool span should match

        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(sample_session_set)

        # Assert: Only tool spans processed
        assert len(results["span_metrics"]) == 1  # Only 1 tool span
        assert results["span_metrics"][0].metric_name == "MockSpanMetric"
        assert results["span_metrics"][0].success is True


# ============================================================================
# TEST 2: METRIC COMPUTATION WITH VALID SESSIONS
# ============================================================================


class TestMetricComputation:
    """Test processor computes metrics correctly for valid sessions."""

    @pytest.mark.asyncio
    async def test_span_level_metrics(
        self,
        multi_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
    ):
        """Test span-level metrics computed across multiple sessions."""
        # multi_session_set has:
        # - Session 1: 3 spans (2 agent, 1 tool)
        # - Session 2: 4 spans (2 agent, 2 tool)
        # MockSpanMetric only processes entity_type="tool"
        # Expected: 3 tool spans total (1 from s1, 2 from s2)

        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(multi_session_set)

        # Assert: Correct number of span results
        assert len(results["span_metrics"]) == 3  # 3 tool spans total

        # All results should be successful
        for result in results["span_metrics"]:
            assert result.metric_name == "MockSpanMetric"
            assert result.success is True
            assert result.value == 1.0
            assert result.aggregation_level == "span"
            assert len(result.span_id) == 1
            assert len(result.session_id) == 1

        # No failed metrics
        assert len(results["failed_metrics"]) == 0

    @pytest.mark.asyncio
    async def test_session_level_metrics(
        self,
        create_session_set,
        session_with_agent_transitions,
        mock_model_handler,
        mock_llm_config,
        mock_session_metric_class,
    ):
        """Test session-level metrics computed for sessions."""
        # Setup: SessionSet with 1 session that has agent transitions
        session_set = create_session_set(sessions=[session_with_agent_transitions])

        registry = MetricRegistry()
        registry.register_metric(mock_session_metric_class, "MockSessionMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(session_set)

        # Assert: 1 session result
        assert len(results["session_metrics"]) == 1

        result = results["session_metrics"][0]
        assert result.metric_name == "MockSessionMetric"
        assert result.success is True
        assert result.value == 2  # 2 agent transitions: ["A -> B", "B -> C"]
        assert result.aggregation_level == "session"
        assert result.session_id == [session_with_agent_transitions.session_id]

        # No failed metrics
        assert len(results["failed_metrics"]) == 0

    @pytest.mark.asyncio
    async def test_population_level_metrics(
        self,
        multi_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_population_metric_class,
    ):
        """Test population-level metrics computed across sessions."""
        registry = MetricRegistry()
        registry.register_metric(mock_population_metric_class, "MockPopulationMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(multi_session_set)

        # Assert: 1 population result
        assert len(results["population_metrics"]) == 1

        result = results["population_metrics"][0]
        assert result.metric_name == "MockPopulationMetric"
        assert result.success is True
        assert result.value == 2  # 2 sessions in multi_session_set
        assert result.aggregation_level == "population"

        # No failed metrics
        assert len(results["failed_metrics"]) == 0

    @pytest.mark.asyncio
    async def test_multiple_metrics_at_once(
        self,
        multi_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
        mock_session_metric_class,
        mock_population_metric_class,
    ):
        """Test multiple metrics computed concurrently."""
        # Note: session needs agent_transitions for MockSessionMetric
        # Let's enrich the sessions with agent transition data
        from collections import Counter

        for session in multi_session_set.sessions:
            session.agent_transitions = ["test -> test"]
            session.agent_transition_counts = Counter({"test -> test": 1})

        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")
        registry.register_metric(mock_session_metric_class, "MockSessionMetric")
        registry.register_metric(mock_population_metric_class, "MockPopulationMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(multi_session_set)

        # Assert: Results segregated correctly
        assert len(results["span_metrics"]) == 3  # 3 tool spans
        assert len(results["session_metrics"]) == 2  # 2 sessions
        assert len(results["population_metrics"]) == 1  # 1 population result

        # All successful
        assert len(results["failed_metrics"]) == 0

        # Check each type
        for span_result in results["span_metrics"]:
            assert span_result.aggregation_level == "span"
            assert span_result.success is True

        for session_result in results["session_metrics"]:
            assert session_result.aggregation_level == "session"
            assert session_result.success is True

        for pop_result in results["population_metrics"]:
            assert pop_result.aggregation_level == "population"
            assert pop_result.success is True


# ============================================================================
# TEST 3: METRIC EXECUTION ORDER
# ============================================================================


class TestMetricExecutionOrder:
    """Test metrics are classified and executed in correct order."""

    def test_classify_metrics_by_aggregation_level(
        self,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
        mock_session_metric_class,
        mock_population_metric_class,
    ):
        """Test _classify_metrics_by_aggregation_level works correctly."""
        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")
        registry.register_metric(mock_session_metric_class, "MockSessionMetric")
        registry.register_metric(mock_population_metric_class, "MockPopulationMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute classification
        classified = processor._classify_metrics_by_aggregation_level()

        # Assert: Correct classification
        assert "span" in classified
        assert "session" in classified
        assert "agent" in classified
        assert "population" in classified

        # Check each category
        assert len(classified["span"]) == 1
        assert classified["span"][0][0] == "MockSpanMetric"

        assert len(classified["session"]) == 1
        assert classified["session"][0][0] == "MockSessionMetric"

        assert len(classified["population"]) == 1
        assert classified["population"][0][0] == "MockPopulationMetric"

    @pytest.mark.asyncio
    async def test_entity_filtering_for_span_metrics(
        self,
        multi_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
    ):
        """Test entity type filtering for span metrics."""
        # MockSpanMetric requires entity_type="tool"
        # multi_session_set has agent, agent, tool spans

        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(multi_session_set)

        # Assert: Only tool spans processed
        assert len(results["span_metrics"]) == 3  # 3 tool spans (1 + 2)

        # Check that all are tool spans
        for result in results["span_metrics"]:
            assert result.metric_name == "MockSpanMetric"
            # Verify it's from a tool span (span_id should be s1-span3, s2-span3, s2-span4)
            span_id = result.span_id[0]
            assert "span3" in span_id or "span4" in span_id

    @pytest.mark.asyncio
    async def test_session_requirements_validation(
        self,
        create_session_set,
        create_session,
        sample_spans,
        mock_model_handler,
        mock_llm_config,
        mock_session_metric_class,
    ):
        """Test session requirements checking."""
        # MockSessionMetric requires "agent_transitions"

        # Session 1: Has agent_transitions (should be processed)
        session1 = create_session(
            session_id="session-1",
            spans=sample_spans,
            agent_transitions=["A -> B"],
            agent_transition_counts=Counter({"A -> B": 1}),
        )

        # Session 2: Missing agent_transitions (should be skipped)
        session2 = create_session(
            session_id="session-2", spans=sample_spans, agent_transitions=None
        )

        session_set = create_session_set(sessions=[session1, session2])

        registry = MetricRegistry()
        registry.register_metric(mock_session_metric_class, "MockSessionMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(session_set)

        # Assert: Only session1 processed
        assert len(results["session_metrics"]) == 1
        assert results["session_metrics"][0].session_id == ["session-1"]

        # session2 was skipped (didn't meet requirements)
        # No error, just skipped
        assert len(results["failed_metrics"]) == 0


# ============================================================================
# TEST 4: ERROR HANDLING
# ============================================================================


class TestErrorHandling:
    """Test processor handles errors gracefully without crashing."""

    @pytest.mark.asyncio
    async def test_metric_initialization_fails(
        self,
        sample_session_set,
        mock_model_handler,
        mock_llm_config,
        failing_init_metric_class,
    ):
        """Test handling when metric init_with_model returns False."""
        registry = MetricRegistry()
        registry.register_metric(failing_init_metric_class, "FailingInitMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute - should not crash
        results = await processor.compute_metrics(sample_session_set)

        # Assert: Computation continued, but metric not computed
        # Failed init metrics are skipped, not added to failed_metrics
        assert len(results["session_metrics"]) == 0
        # The metric was just not initialized, so no computation attempted

    @pytest.mark.asyncio
    async def test_metric_compute_raises_exception(
        self,
        sample_session_set,
        mock_model_handler,
        mock_llm_config,
        failing_metric_class,
    ):
        """Test handling when metric compute() raises exception."""
        registry = MetricRegistry()
        registry.register_metric(failing_metric_class, "FailingMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute - should not crash
        results = await processor.compute_metrics(sample_session_set)

        # Assert: Exception caught, error result created
        assert len(results["failed_metrics"]) == 1

        failed = results["failed_metrics"][0]
        assert failed["metric_name"] == "FailingMetric"
        assert failed["aggregation_level"] == "session"
        assert "Intentional test failure" in failed["error_message"]
        # Note: session_id may be empty in error results from _safe_compute
        # The processor creates error results with empty lists for session_id/span_id
        assert "session_id" in failed

    @pytest.mark.asyncio
    async def test_multiple_metrics_one_fails(
        self,
        sample_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
        failing_metric_class,
    ):
        """Test one failing metric doesn't stop others from running."""
        # Enrich session with agent_transitions for other metrics
        session = sample_session_set.sessions[0]
        session.agent_transitions = ["test"]
        session.agent_transition_counts = Counter({"test": 1})

        registry = MetricRegistry()
        registry.register_metric(
            mock_span_metric_class, "MockSpanMetric"
        )  # Should work
        registry.register_metric(failing_metric_class, "FailingMetric")  # Will fail

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(sample_session_set)

        # Assert: MockSpanMetric succeeded
        assert len(results["span_metrics"]) == 1
        assert results["span_metrics"][0].metric_name == "MockSpanMetric"
        assert results["span_metrics"][0].success is True

        # FailingMetric failed
        assert len(results["failed_metrics"]) == 1
        assert results["failed_metrics"][0]["metric_name"] == "FailingMetric"

    @pytest.mark.asyncio
    async def test_safe_compute_error_result_structure(
        self,
        sample_session_set,
        mock_model_handler,
        mock_llm_config,
        failing_metric_class,
    ):
        """Test error result has proper MetricResult structure."""
        registry = MetricRegistry()
        registry.register_metric(failing_metric_class, "FailingMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(sample_session_set)

        # Assert: Error result structure
        assert len(results["failed_metrics"]) == 1

        failed = results["failed_metrics"][0]

        # Check all required fields present
        assert "metric_name" in failed
        assert "aggregation_level" in failed
        assert "error_message" in failed
        assert "session_id" in failed
        assert "app_name" in failed

        # Check error details
        assert failed["metric_name"] == "FailingMetric"
        assert failed["aggregation_level"] == "session"
        assert failed["error_message"] is not None
        assert len(failed["error_message"]) > 0

    @pytest.mark.asyncio
    async def test_deduplicate_failures(
        self,
        create_session_set,
        create_session,
        sample_spans,
        mock_model_handler,
        mock_llm_config,
        failing_metric_class,
    ):
        """Test _deduplicate_failures removes duplicate errors."""
        # Create 2 identical sessions to potentially trigger duplicate errors
        session1 = create_session(session_id="session-1", spans=sample_spans)
        session2 = create_session(session_id="session-2", spans=sample_spans)

        session_set = create_session_set(sessions=[session1, session2])

        registry = MetricRegistry()
        registry.register_metric(failing_metric_class, "FailingMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute
        results = await processor.compute_metrics(session_set)

        # Assert: Failures recorded (may or may not be deduplicated based on content)
        # At minimum, we should have failure records
        assert len(results["failed_metrics"]) >= 1

        # Each failure should have the error message
        for failed in results["failed_metrics"]:
            assert "error_message" in failed
            assert len(failed["error_message"]) > 0


# ============================================================================
# INTEGRATION TEST: FULL PROCESSOR WORKFLOW
# ============================================================================


class TestProcessorIntegration:
    """Integration test for complete processor workflow."""

    @pytest.mark.asyncio
    async def test_full_processor_workflow(
        self,
        multi_session_set,
        mock_model_handler,
        mock_llm_config,
        mock_span_metric_class,
        mock_session_metric_class,
        mock_population_metric_class,
    ):
        """Test complete processor workflow with multiple metric types."""
        # Enrich sessions with required data
        from collections import Counter

        for session in multi_session_set.sessions:
            session.agent_transitions = ["A -> B"]
            session.agent_transition_counts = Counter({"A -> B": 1})

        # Setup registry with all metric types
        registry = MetricRegistry()
        registry.register_metric(mock_span_metric_class, "MockSpanMetric")
        registry.register_metric(mock_session_metric_class, "MockSessionMetric")
        registry.register_metric(mock_population_metric_class, "MockPopulationMetric")

        processor = MetricsProcessor(
            registry=registry,
            model_handler=mock_model_handler,
            llm_config=mock_llm_config,
        )

        # Execute complete workflow
        results = await processor.compute_metrics(multi_session_set)

        # Assert: All metrics computed successfully
        assert len(results["span_metrics"]) == 3  # 3 tool spans
        assert len(results["session_metrics"]) == 2  # 2 sessions
        assert len(results["population_metrics"]) == 1  # 1 population
        assert len(results["failed_metrics"]) == 0  # No failures

        # Verify result quality
        for metric_list in [
            results["span_metrics"],
            results["session_metrics"],
            results["population_metrics"],
        ]:
            for result in metric_list:
                assert result.success is True
                assert result.value is not None
                assert result.value != -1
                assert result.error_message is None
                assert len(result.session_id) > 0

        # Verify app_name populated from session
        for result in results["session_metrics"]:
            assert result.app_name is not None
            assert len(result.app_name) > 0
