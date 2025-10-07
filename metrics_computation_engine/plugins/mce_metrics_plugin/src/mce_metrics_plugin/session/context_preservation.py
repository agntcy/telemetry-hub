# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Union
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading, MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity

# Context Preservation
CONTEXT_PRESERVATION_PROMPT = """
    You are an evaluator of Context Preservation.

    Evaluate the given response based on its ability to understand and address the provided input. You will be given a CONVERSATION.

    Here is the evaluation criteria to follow: (1) Does the response accurately understand and address the given input? (2) Is the response relevant and logically structured? (3) Does the response provide useful or insightful information?

    Scoring Rubric:
        1: The response is highly relevant, well-structured, and insightful.
        0: The response is irrelevant, unclear, or fails to address the input effectively.

    CONVERSATION to evaluate: {conversation}
"""


class ContextPreservation(BaseMetric):
    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"
        self.description = "Measures how well responses maintain conversation context by evaluating accurate understanding of input, relevance and logical structure of responses, and provision of useful insights. Returns 1 for highly relevant, well-structured, and insightful responses, or 0 for irrelevant, unclear, or ineffective responses."

    @property
    def required_parameters(self) -> List[str]:
        return ["conversation_data"]

    def validate_config(self) -> bool:
        return True

    def supports_agent_computation(self) -> bool:
        """Context Preservation can be computed at agent level for individual agent performance analysis."""
        return True

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    async def compute(
        self, session: SessionEntity, **context
    ) -> Union[MetricResult, List[MetricResult]]:
        # Check if this is agent computation
        if context.get("agent_computation", False):
            return self._compute_agent_level(session)

        # Session-level computation (existing logic)
        conversation = (
            session.conversation_data.get("conversation", "")
            if session.conversation_data
            else ""
        )
        agent_span_ids = (
            [span.span_id for span in session.agent_spans]
            if session.agent_spans
            else []
        )

        entities_involved = (
            [span.entity_name for span in session.agent_spans]
            if session.agent_spans
            else []
        )
        prompt = CONTEXT_PRESERVATION_PROMPT.format(conversation=conversation)

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            result = self._create_success_result(
                score=score,
                category="application",
                app_name=session.app_name,
                reasoning=reasoning,
                entities_involved=entities_involved,
                span_ids=agent_span_ids,
                session_ids=[session.session_id],
            )

            # Override description with static metric description
            result.description = self.description
            return result

        return self._create_error_result(
            error_message="No model available",
            category="application",
            app_name=session.app_name,
            entities_involved=entities_involved,
            span_ids=agent_span_ids,
            session_ids=[session.session_id],
        )

    def _compute_agent_level(self, session: SessionEntity) -> List[MetricResult]:
        """
        Compute Context Preservation for each agent in the session.

        Uses session-level caching for agent conversation data to optimize performance
        when multiple conversation-based metrics are computed.

        Args:
            session: SessionEntity containing agent data and execution tree

        Returns:
            List of MetricResult objects, one per agent
        """
        results = []

        # Get agents from session stats (leverages existing agent identification)

        if not session.agent_stats:
            return results

        for agent_name in session.agent_stats.keys():
            try:
                # Use SessionEntity-level cached conversation data
                # This leverages existing conversation extraction logic + execution tree filtering
                agent_conversation = session.get_agent_conversation_text(agent_name)

                if not agent_conversation:
                    # Skip agents with no conversation data
                    continue

                # Use the same prompt format as session-level
                prompt = CONTEXT_PRESERVATION_PROMPT.format(
                    conversation=agent_conversation
                )

                # Get agent-specific spans for metadata (reuses existing span collection)
                agent_spans = session._get_spans_for_agent(agent_name)
                agent_span_ids = [span.span_id for span in agent_spans]

                if self.jury:
                    score, reasoning = self.jury.judge(prompt, BinaryGrading)
                    result = self._create_success_result(
                        score=score,
                        category="agent",
                        app_name=session.app_name,
                        reasoning=reasoning,
                        entities_involved=[agent_name],
                        span_ids=agent_span_ids,
                        session_ids=[session.session_id],
                    )

                else:
                    result = self._create_error_result(
                        error_message="No model available",
                        category="agent",
                        app_name=session.app_name,
                        entities_involved=[agent_name],
                        span_ids=agent_span_ids,
                        session_ids=[session.session_id],
                    )

                # Ensure agent-level metadata
                result.description = self.description
                result.aggregation_level = "agent"
                if not hasattr(result, "metadata") or result.metadata is None:
                    result.metadata = {}
                result.metadata["agent_id"] = agent_name
                result.metadata["metric_type"] = "llm-as-a-judge"
                results.append(result)

            except Exception as e:
                # Handle errors gracefully for individual agents
                result = self._create_error_result(
                    error_message=f"Error computing context preservation for agent {agent_name}: {str(e)}",
                    category="agent",
                    app_name=session.app_name,
                    entities_involved=[agent_name],
                    span_ids=[],
                    session_ids=[session.session_id],
                )

                # Ensure agent-level metadata for error results too
                result.description = self.description
                result.aggregation_level = "agent"
                if not hasattr(result, "metadata") or result.metadata is None:
                    result.metadata = {}
                result.metadata["agent_id"] = agent_name
                result.metadata["metric_type"] = "llm-as-a-judge"

                results.append(result)

        return results
