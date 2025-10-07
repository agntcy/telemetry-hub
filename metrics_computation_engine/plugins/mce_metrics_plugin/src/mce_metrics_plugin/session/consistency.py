# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Union
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading, MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.core.agent_role_detector import get_agent_role_and_skip_decision, AgentFilterMetadata
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

# Consistency
CONSISTENCY_PROMPT = """
    You are an evaluator of Consistency.

    You will be given multiple RESPONSES from different interactions. Evaluate the consistency in the RESPONSES.

    Here is the evaluation criteria to follow: (1) Are the responses consistent in the information they provide? (2) Do the responses avoid contradictions or conflicting statements? (3) Is the overall tone and style of the responses consistent?

    Scoring Rubric:
        1: the responses are fully consistent across all interactions.
        0: the responses are not consistent.

    RESPONSES to evaluate: {conversation}
"""


class Consistency(BaseMetric):
    REQUIRED_PARAMETERS = {"Consistency": ["conversation_data"]}

    def __init__(self, metric_name: Optional[str] = None, filter_coordinators: bool = True):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"
        self.description = "Evaluates consistency across multiple responses in a conversation by checking information consistency, absence of contradictions, and consistent tone/style. Returns 1 for fully consistent responses across interactions, or 0 for inconsistent responses."
        self.filter_coordinators = filter_coordinators

    @property
    def required_parameters(self) -> List[str]:
        return ["conversation_data"]

    def validate_config(self) -> bool:
        return True

    def supports_agent_computation(self) -> bool:
        """Consistency can be computed at agent level for individual agent consistency analysis."""
        return True

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    async def compute(self, session: SessionEntity, **context) -> Union[MetricResult, List[MetricResult]]:
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
        prompt = CONSISTENCY_PROMPT.format(conversation=conversation)

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            result = self._create_success_result(
                score=score,
                category="application",
                app_name=session.app_name,
                reasoning=reasoning,
                span_ids=agent_span_ids,
                entities_involved=entities_involved,
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
        Compute Consistency for each agent in the session.

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
                # Check if agent should be skipped based on role detection
                should_skip, role_metadata = get_agent_role_and_skip_decision(
                    session, agent_name, filter_coordinators=self.filter_coordinators
                )

                if should_skip:
                    # Skip this agent entirely - don't include in results
                    # Log the skip for debugging purposes
                    logger.info(f"Skipping agent '{agent_name}' for Consistency metric: {role_metadata.get('skip_reason', 'Detected as coordinator agent')}")
                    continue

                # Use SessionEntity-level cached conversation data
                # This leverages existing conversation extraction logic + execution tree filtering
                agent_conversation = session.get_agent_conversation_text(agent_name)

                if not agent_conversation:
                    # Skip agents with no conversation data
                    continue

                # Use the same prompt format as session-level
                prompt = CONSISTENCY_PROMPT.format(conversation=agent_conversation)

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

                # Ensure agent-level metadata including role detection info
                result.description = self.description
                result.aggregation_level = "agent"
                if not hasattr(result, 'metadata') or result.metadata is None:
                    result.metadata = {}
                # Handle both AgentFilterMetadata objects and plain dicts (for tests)
                role_dict = role_metadata.to_dict() if hasattr(role_metadata, 'to_dict') else role_metadata
                result.metadata.update({
                    "agent_id": agent_name,
                    "metric_type": "llm-as-a-judge",
                    "skipped": False,
                    **role_dict
                })
                results.append(result)

            except Exception as e:
                # Handle errors gracefully for individual agents
                import traceback

                # Log detailed error information for debugging
                logger.error(f"ERROR in consistency computation for agent {agent_name}:")
                logger.error(f"Exception type: {type(e).__name__}")
                logger.error(f"Exception message: {str(e)}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")

                # Also print to stdout for immediate visibility in tests
                print(f"\n=== CONSISTENCY ERROR DEBUG ===")
                print(f"Agent: {agent_name}")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                print(f"Traceback:\n{traceback.format_exc()}")
                print(f"===============================\n")

                result = self._create_error_result(
                    error_message=f"Error computing consistency for agent {agent_name}: {str(e)}",
                    category="agent",
                    app_name=session.app_name,
                    entities_involved=[agent_name],
                    span_ids=[],
                    session_ids=[session.session_id],
                )

                # Ensure agent-level metadata for error results too
                result.description = self.description
                result.aggregation_level = "agent"
                if not hasattr(result, 'metadata') or result.metadata is None:
                    result.metadata = {}
                result.metadata.update({
                    "agent_id": agent_name,
                    "metric_type": "llm-as-a-judge",
                    "skipped": False,
                    "error_in_processing": True
                })

                results.append(result)

        return results
