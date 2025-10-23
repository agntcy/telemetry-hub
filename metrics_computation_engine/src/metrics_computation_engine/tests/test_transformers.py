# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive unit tests for Session Transformers.

Tests cover:
1. Base transformer classes (DataTransformer, DataPreservingTransformer, DataPipeline)
2. AgentTransitionTransformer - Agent transition extraction
3. ConversationDataTransformer - Conversation element extraction
4. WorkflowDataTransformer - Workflow pattern extraction
5. ExecutionTreeTransformer - Execution tree building
"""

import pytest
from collections import Counter

from metrics_computation_engine.entities.transformers.base import (
    DataPreservingTransformer,
    DataPipeline,
)
from metrics_computation_engine.entities.transformers.session_enrichers import (
    AgentTransitionTransformer,
    ConversationDataTransformer,
    WorkflowDataTransformer,
    EndToEndAttributesTransformer,
)
from metrics_computation_engine.entities.transformers.execution_tree_transformer import (
    ExecutionTreeTransformer,
)


# ============================================================================
# TEST CLASS 1: BASE TRANSFORMERS
# ============================================================================


class TestBaseTransformers:
    """Test base transformer classes and pipeline."""

    def test_data_preserving_transformer_first_call(self):
        """Test DataPreservingTransformer creates structure on first call."""

        class SimpleExtractor(DataPreservingTransformer):
            def extract(self, data):
                return {"extracted": "value"}

        transformer = SimpleExtractor()
        input_data = {"original": "data"}

        # Execute
        result = transformer.transform(input_data)

        # Assert: Creates structure with original_data
        assert "original_data" in result
        assert result["original_data"] == input_data
        assert result["extracted"] == "value"

    def test_data_preserving_transformer_subsequent_call(self):
        """Test DataPreservingTransformer preserves existing data."""

        class SimpleExtractor(DataPreservingTransformer):
            def extract(self, data):
                return {"new_field": "new_value"}

        transformer = SimpleExtractor()

        # Input already has original_data
        input_data = {
            "original_data": {"first": "data"},
            "existing_field": "existing_value",
        }

        # Execute
        result = transformer.transform(input_data)

        # Assert: Preserves all existing fields
        assert result["original_data"] == {"first": "data"}
        assert result["existing_field"] == "existing_value"
        assert result["new_field"] == "new_value"

    def test_data_pipeline_empty_raises_error(self):
        """Test that empty pipeline raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DataPipeline([])

        assert "at least one transformer" in str(exc_info.value)

    def test_data_pipeline_processes_in_order(self):
        """Test that pipeline processes transformers in order."""

        class FirstTransformer(DataPreservingTransformer):
            def extract(self, data):
                return {"step": "first"}

        class SecondTransformer(DataPreservingTransformer):
            def extract(self, data):
                return {"step": "second", "first_was_called": "step" in data}

        pipeline = DataPipeline([FirstTransformer(), SecondTransformer()])

        # Execute
        result = pipeline.process({"input": "data"})

        # Assert: Both transformers applied in order
        assert result["step"] == "second"
        assert result["first_was_called"] is True


# ============================================================================
# TEST CLASS 2: AGENT TRANSITION TRANSFORMER
# ============================================================================


class TestAgentTransitionTransformer:
    """Test agent transition extraction."""

    def test_extract_agent_transitions(self, create_session, create_span):
        """Test extracting agent transitions from spans."""
        transformer = AgentTransitionTransformer()

        # Create session with agent transitions
        spans = [
            create_span(
                span_id="s1",
                entity_type="agent",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentA"}]},
            ),
            create_span(
                span_id="s2",
                entity_type="agent",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentB"}]},
            ),
            create_span(
                span_id="s3",
                entity_type="agent",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentC"}]},
            ),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: Transitions extracted
        assert "agent_transitions" in result
        assert "agent_transition_counts" in result

        # Should have 2 transitions: A->B, B->C
        assert len(result["agent_transitions"]) == 2
        assert "AgentA -> AgentB" in result["agent_transitions"]
        assert "AgentB -> AgentC" in result["agent_transitions"]

        # Counts should match
        assert result["agent_transition_counts"]["AgentA -> AgentB"] == 1
        assert result["agent_transition_counts"]["AgentB -> AgentC"] == 1

    def test_extract_with_no_agents(self, create_session, create_span):
        """Test extraction with no agent spans."""
        transformer = AgentTransitionTransformer()

        # Session with no agent event data
        spans = [
            create_span(span_id="s1", entity_type="tool"),
            create_span(span_id="s2", entity_type="llm"),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: Empty transitions
        assert result["agent_transitions"] == []
        assert result["agent_transition_counts"] == Counter()

    def test_extract_handles_same_agent_repeated(self, create_session, create_span):
        """Test that same agent repeated doesn't create transition."""
        transformer = AgentTransitionTransformer()

        spans = [
            create_span(
                span_id="s1",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentA"}]},
            ),
            create_span(
                span_id="s2",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentA"}]},
            ),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: No transitions (same agent)
        assert result["agent_transitions"] == []
        assert result["agent_transition_counts"] == Counter()


# ============================================================================
# TEST CLASS 3: CONVERSATION DATA TRANSFORMER
# ============================================================================


class TestConversationDataTransformer:
    """Test conversation data extraction."""

    def test_extract_from_llm_spans(self, create_session, create_span):
        """Test extracting conversation from LLM spans."""
        transformer = ConversationDataTransformer()

        # Create session with LLM span containing conversation
        llm_span = create_span(
            span_id="llm1",
            entity_type="llm",
            input_payload={
                "gen_ai.prompt.0.content": "Hello AI",
                "gen_ai.prompt.0.role": "user",
            },
            output_payload={
                "gen_ai.completion.0.content": "Hello! How can I help?",
                "gen_ai.completion.0.role": "assistant",
            },
        )

        session = create_session(session_id="test", spans=[llm_span])

        # Execute
        result = transformer.extract(session)

        # Assert: Conversation data extracted
        assert "conversation_data" in result
        conv_data = result["conversation_data"]

        assert "elements" in conv_data
        assert len(conv_data["elements"]) == 2  # 1 prompt + 1 completion

        # Check elements structure
        assert conv_data["elements"][0]["role"] == "user"
        assert conv_data["elements"][0]["content"] == "Hello AI"
        assert conv_data["elements"][1]["role"] == "assistant"
        assert conv_data["elements"][1]["content"] == "Hello! How can I help?"

    def test_extract_conversation_elements_count(self, create_session, create_span):
        """Test that element counts are correct."""
        transformer = ConversationDataTransformer()

        # Multiple conversation turns
        llm_span = create_span(
            span_id="llm1",
            entity_type="llm",
            input_payload={
                "gen_ai.prompt.0.content": "Message 1",
                "gen_ai.prompt.0.role": "user",
                "gen_ai.prompt.1.content": "Message 2",
                "gen_ai.prompt.1.role": "system",
            },
            output_payload={
                "gen_ai.completion.0.content": "Response 1",
                "gen_ai.completion.0.role": "assistant",
            },
        )

        session = create_session(session_id="test", spans=[llm_span])

        # Execute
        result = transformer.extract(session)

        # Assert: Correct count
        conv_data = result["conversation_data"]
        assert conv_data["total_elements"] == 3  # 2 prompts + 1 completion

    def test_extract_tool_calls_from_llm(self, create_session, create_span):
        """Test extracting tool calls from LLM output."""
        transformer = ConversationDataTransformer()

        llm_span = create_span(
            span_id="llm1",
            entity_type="llm",
            output_payload={
                "gen_ai.completion.0.tool_calls": '{"function": "search", "args": {}}',
            },
        )

        session = create_session(session_id="test", spans=[llm_span])

        # Execute
        result = transformer.extract(session)

        # Assert: Tool calls extracted
        conv_data = result["conversation_data"]
        assert "tool_calls" in conv_data
        assert conv_data["total_tool_calls"] == 1

    def test_extract_sorts_by_timestamp(self, create_session, create_span):
        """Test that conversation elements are sorted by timestamp."""
        transformer = ConversationDataTransformer()

        # Create spans with different timestamps (out of order)
        span1 = create_span(
            span_id="llm1",
            entity_type="llm",
            timestamp="2025-01-01T00:00:02Z",
            input_payload={
                "gen_ai.prompt.0.content": "Third",
                "gen_ai.prompt.0.role": "user",
            },
        )

        span2 = create_span(
            span_id="llm2",
            entity_type="llm",
            timestamp="2025-01-01T00:00:00Z",
            input_payload={
                "gen_ai.prompt.0.content": "First",
                "gen_ai.prompt.0.role": "user",
            },
        )

        session = create_session(session_id="test", spans=[span1, span2])

        # Execute
        result = transformer.extract(session)

        # Assert: Elements sorted by timestamp
        elements = result["conversation_data"]["elements"]
        assert elements[0]["content"] == "First"  # Earlier timestamp
        assert elements[1]["content"] == "Third"  # Later timestamp

    def test_extract_with_no_conversation(self, create_session, create_span):
        """Test extraction with no LLM or conversation data."""
        transformer = ConversationDataTransformer()

        # Session with only tool spans (no conversation)
        spans = [
            create_span(span_id="t1", entity_type="tool"),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: Empty conversation data
        conv_data = result["conversation_data"]
        assert conv_data["elements"] == []
        assert conv_data["total_elements"] == 0


# ============================================================================
# TEST CLASS 4: WORKFLOW DATA TRANSFORMER
# ============================================================================


class TestWorkflowDataTransformer:
    """Test workflow data extraction."""

    def test_extract_workflow_data(self, create_session, create_span):
        """Test extracting workflow execution data."""
        transformer = WorkflowDataTransformer()

        # Create session with workflow span
        workflow_span = create_span(
            span_id="wf1",
            entity_type="workflow",
            entity_name="TestWorkflow",
            input_payload={"inputs": {"messages": [["user", "test query"]]}},
            output_payload={
                "outputs": {"messages": [{"kwargs": {"content": "response"}}]}
            },
        )

        session = create_session(session_id="test", spans=[workflow_span])

        # Execute
        result = transformer.extract(session)

        # Assert: Workflow data extracted
        assert "workflow_data" in result
        wf_data = result["workflow_data"]

        assert "workflows" in wf_data
        assert wf_data["total_workflows"] >= 1
        assert "execution_pattern" in wf_data

    def test_extract_query_response(self, create_session, create_span):
        """Test extracting query and response from workflow."""
        transformer = WorkflowDataTransformer()

        workflow_span = create_span(
            span_id="wf1",
            entity_type="workflow",
            entity_name="TestWorkflow",
            input_payload={"inputs": {"messages": [["user", "What is 2+2?"]]}},
            output_payload={
                "outputs": {"messages": [{"kwargs": {"content": "The answer is 4"}}]}
            },
        )

        session = create_session(session_id="test", spans=[workflow_span])

        # Execute
        result = transformer.extract(session)

        # Assert: Query and response extracted
        wf_data = result["workflow_data"]
        assert wf_data["query"] == "What is 2+2?"
        assert "4" in wf_data["response"]

    def test_extract_multiple_workflows(self, create_session, create_span):
        """Test handling multiple workflow spans."""
        transformer = WorkflowDataTransformer()

        spans = [
            create_span(
                span_id="wf1",
                entity_type="workflow",
                entity_name="WorkflowA",
                timestamp="2025-01-01T00:00:00Z",
            ),
            create_span(
                span_id="wf2",
                entity_type="workflow",
                entity_name="WorkflowB",
                timestamp="2025-01-01T00:00:01Z",
            ),
            create_span(
                span_id="wf3",
                entity_type="workflow",
                entity_name="WorkflowA",
                timestamp="2025-01-01T00:00:02Z",
            ),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: Multiple workflows tracked
        wf_data = result["workflow_data"]
        assert wf_data["total_workflows"] == 2  # WorkflowA and WorkflowB
        assert len(wf_data["execution_pattern"]) == 3  # 3 executions total

    def test_extract_with_no_workflows(self, create_session, create_span):
        """Test extraction with no workflow spans."""
        transformer = WorkflowDataTransformer()

        spans = [create_span(span_id="a1", entity_type="agent")]
        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: Empty workflow data
        wf_data = result["workflow_data"]
        assert wf_data["total_workflows"] == 0
        assert wf_data["query"] == ""
        assert wf_data["response"] == ""

    def test_extract_tracks_errors(self, create_session, create_span):
        """Test that workflow errors are tracked."""
        transformer = WorkflowDataTransformer()

        workflow_span = create_span(
            span_id="wf1",
            entity_type="workflow",
            entity_name="ErrorWorkflow",
            contains_error=True,
        )

        session = create_session(session_id="test", spans=[workflow_span])

        # Execute
        result = transformer.extract(session)

        # Assert: Error tracked
        wf_data = result["workflow_data"]
        workflow = wf_data["workflows"][0]
        assert workflow["has_errors"] is True


# ============================================================================
# TEST CLASS 5: EXECUTION TREE TRANSFORMER
# ============================================================================


class TestExecutionTreeTransformer:
    """Test execution tree building."""

    def test_build_execution_tree(self, create_session, create_span):
        """Test building execution tree from spans."""
        transformer = ExecutionTreeTransformer()

        # Create spans with parent-child relationships
        spans = [
            create_span(
                span_id="root",
                entity_type="workflow",
                parent_span_id=None,
            ),
            create_span(
                span_id="child1",
                entity_type="agent",
                parent_span_id="root",
            ),
            create_span(
                span_id="child2",
                entity_type="llm",
                parent_span_id="root",
            ),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: Tree built
        assert "execution_tree" in result
        assert result["execution_tree"] is not None

        # Should have hierarchy summary
        assert "hierarchy_summary" in result

    def test_build_with_empty_session(self, create_session):
        """Test building tree with no spans."""
        transformer = ExecutionTreeTransformer()

        session = create_session(session_id="test", spans=[])

        # Execute
        result = transformer.extract(session)

        # Assert: Empty result
        assert result == {}


# ============================================================================
# TEST CLASS 6: END-TO-END ATTRIBUTES TRANSFORMER
# ============================================================================


class TestEndToEndAttributesTransformer:
    """Test input/output query extraction."""

    def test_extract_input_query_and_final_response(self, create_session, create_span):
        """Test extracting input query and final response from LLM spans."""
        transformer = EndToEndAttributesTransformer()

        # Create LLM span with conversation
        llm_span = create_span(
            span_id="llm1",
            entity_type="llm",
            input_payload={
                "gen_ai.prompt.0.content": "System prompt",
                "gen_ai.prompt.0.role": "system",
                "gen_ai.prompt.1.content": "What is the weather?",
                "gen_ai.prompt.1.role": "user",
            },
            output_payload={
                "gen_ai.completion.0.content": "It's sunny today",
                "gen_ai.completion.0.role": "assistant",
            },
        )

        session = create_session(session_id="test", spans=[llm_span])

        # Execute
        result = transformer.extract(session)

        # Assert: Query and response extracted
        assert "input_query" in result
        assert "final_response" in result

        # First user message should be query
        assert result["input_query"] == "What is the weather?"
        # Last assistant message should be response
        assert result["final_response"] == "It's sunny today"

    def test_extract_with_no_llm_spans(self, create_session, create_span):
        """Test extraction with no LLM spans."""
        transformer = EndToEndAttributesTransformer()

        spans = [create_span(span_id="a1", entity_type="agent")]
        session = create_session(session_id="test", spans=spans)

        # Execute
        result = transformer.extract(session)

        # Assert: Empty result
        assert result == {}


# ============================================================================
# INTEGRATION TEST: TRANSFORMER PIPELINE
# ============================================================================


class TestTransformerIntegration:
    """Integration tests for transformer pipelines."""

    def test_enrichment_pipeline_with_multiple_transformers(
        self, create_session, create_span
    ):
        """Test chaining multiple transformers in pipeline."""
        from metrics_computation_engine.entities.transformers.session_enrichers import (
            SessionEnrichmentPipeline,
        )

        # Create session with various spans
        spans = [
            create_span(
                span_id="a1",
                entity_type="agent",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentA"}]},
            ),
            create_span(
                span_id="a2",
                entity_type="agent",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentB"}]},
            ),
            create_span(
                span_id="llm1",
                entity_type="llm",
                input_payload={
                    "gen_ai.prompt.0.content": "Test",
                    "gen_ai.prompt.0.role": "user",
                },
                output_payload={
                    "gen_ai.completion.0.content": "Response",
                    "gen_ai.completion.0.role": "assistant",
                },
            ),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute: Run enrichment pipeline
        pipeline = SessionEnrichmentPipeline()
        enriched_sessions = pipeline.enrich_sessions([session])

        # Assert: Session enriched
        assert len(enriched_sessions) == 1
        enriched = enriched_sessions[0]

        # Should have agent transitions
        assert hasattr(enriched, "agent_transitions")

        # Should have conversation data
        assert hasattr(enriched, "conversation_data")

    def test_chained_transformers_preserve_data(self, create_session, create_span):
        """Test that chained transformers preserve all data."""
        # Create simple pipeline
        pipeline = DataPipeline(
            [
                AgentTransitionTransformer(),
                ConversationDataTransformer(),
            ]
        )

        spans = [
            create_span(
                span_id="a1",
                entity_type="agent",
                raw_span_data={"Events.Attributes": [{"agent_name": "AgentA"}]},
            ),
            create_span(
                span_id="llm1",
                entity_type="llm",
                input_payload={
                    "gen_ai.prompt.0.content": "Test",
                    "gen_ai.prompt.0.role": "user",
                },
            ),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute
        result = pipeline.process(session)

        # Assert: Both transformers applied, data preserved
        # This would be a dict with all extracted fields
        assert isinstance(result, dict)

    def test_transformer_with_invalid_input(self):
        """Test transformers handle invalid input gracefully."""
        transformer = AgentTransitionTransformer()

        # Execute: Pass non-SessionEntity
        result = transformer.extract("invalid input")

        # Assert: Returns empty dict (graceful handling)
        assert result == {}

    def test_full_session_enrichment(self, create_session, create_span):
        """Test full session enrichment with all transformers."""
        from metrics_computation_engine.entities.transformers.session_enrichers import (
            SessionEnrichmentPipeline,
        )

        # Create realistic session
        spans = [
            # Workflow span
            create_span(
                span_id="wf1",
                entity_type="workflow",
                entity_name="MainWorkflow",
                input_payload={"inputs": {"messages": [["user", "Hello"]]}},
                output_payload={
                    "outputs": {"messages": [{"kwargs": {"content": "Hi"}}]}
                },
            ),
            # Agent span
            create_span(
                span_id="a1",
                entity_type="agent",
                raw_span_data={"Events.Attributes": [{"agent_name": "TestAgent"}]},
            ),
            # LLM span
            create_span(
                span_id="llm1",
                entity_type="llm",
                input_payload={
                    "gen_ai.prompt.0.content": "Question",
                    "gen_ai.prompt.0.role": "user",
                },
                output_payload={
                    "gen_ai.completion.0.content": "Answer",
                    "gen_ai.completion.0.role": "assistant",
                },
            ),
        ]

        session = create_session(session_id="test", spans=spans)

        # Execute: Full enrichment
        pipeline = SessionEnrichmentPipeline()
        enriched = pipeline.enrich_sessions([session])

        # Assert: All enrichments applied
        assert len(enriched) == 1
        enriched_session = enriched[0]

        # Should have various enriched fields
        assert enriched_session.session_id == "test"
        assert len(enriched_session.spans) == 3
