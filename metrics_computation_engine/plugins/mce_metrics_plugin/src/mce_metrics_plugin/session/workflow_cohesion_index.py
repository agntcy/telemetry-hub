# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Union

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading, MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.core.agent_role_detector import get_agent_role_and_skip_decision, AgentFilterMetadata
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

WORKFLOW_COHESION_INDEX_PROMPT = """
    You are an evaluator of Workflow Cohesion.

    You will be given multiple RESPONSES describing different components of a workflow. Evaluate how well these components integrate and function cohesively as a unified system.

    Here is the evaluation criteria to follow: (1) Do the components interact smoothly without unnecessary friction or gaps? (2) Is there a logical flow between different parts of the workflow? (3) Does the workflow maintain consistency and efficiency across all stages?

    Scoring Rubric:
        1: the workflow is highly cohesive, with seamless integration among components and a logical, efficient flow.
        0: the workflow lacks cohesion, with poor integration, inconsistencies, or significant inefficiencies.

    RESPONSES to evaluate: {conversation}
"""


class WorkflowCohesionIndex(BaseMetric):
    """
    Measures how well different components work together as a cohesive workflow.
    """

    REQUIRED_PARAMETERS = {"WorkflowCohesionIndex": ["conversation_data"]}

    def __init__(self, metric_name: Optional[str] = None, filter_coordinators: bool = True):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"
        self.description = "Measures how well different components work together as a cohesive workflow by evaluating component integration, logical flow, consistency, and efficiency. Returns 1 for highly cohesive workflows with seamless integration, or 0 for workflows lacking cohesion with poor integration or inefficiencies."
        self.filter_coordinators = filter_coordinators

    @property
    def required_parameters(self) -> List[str]:
        return ["conversation_data"]

    def validate_config(self) -> bool:
        return True

    def supports_agent_computation(self) -> bool:
        """WorkflowCohesionIndex can be computed at agent level for individual agent cohesion analysis."""
        return True

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    async def compute(self, session: SessionEntity, **context) -> Union[MetricResult, List[MetricResult]]:
        """
        Compute workflow cohesion index using pre-populated SessionEntity data.

        Args:
            session: SessionEntity with pre-computed conversation data
            **context: Additional context, including agent_computation flag
        """
        # Check if this is agent computation
        if context.get("agent_computation", False):
            return self._compute_agent_level(session)

        # Session-level computation (existing logic)
        if not session.conversation_data:
            return self._create_error_result(
                error_message="No conversation data found for workflow cohesion evaluation",
                category="application",
                app_name=session.app_name,
                entities_involved=[],
                span_ids=[],
                session_ids=[session.session_id],
            )

        # Handle both string and dictionary conversation data
        conversation = (
            session.conversation_data.get("conversation", "")
            if isinstance(session.conversation_data, dict)
            else str(session.conversation_data)
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
        prompt = WORKFLOW_COHESION_INDEX_PROMPT.format(conversation=conversation)

        if self.jury:
            try:
                jury_result = self.jury.judge(prompt, BinaryGrading)
                if jury_result is None:
                    return self._create_error_result(
                        error_message="Invalid binary grading result from model",
                        category="application",
                        app_name=session.app_name,
                        entities_involved=list(set(entities_involved)),
                        span_ids=agent_span_ids,
                        session_ids=[session.session_id],
                    )

                score, reasoning = jury_result
                result = self._create_success_result(
                    score=score,
                    category="application",
                    app_name=session.app_name,
                    reasoning=reasoning,
                    entities_involved=list(set(entities_involved)),
                    span_ids=agent_span_ids,
                    session_ids=[session.session_id],
                )

                # Override description with static metric description
                result.description = self.description
                return result
            except Exception as e:
                return self._create_error_result(
                    error_message=f"Error during workflow cohesion evaluation: {str(e)}",
                    category="application",
                    app_name=session.app_name,
                    entities_involved=list(set(entities_involved)),
                    span_ids=agent_span_ids,
                    session_ids=[session.session_id],
                )

        return self._create_error_result(
            error_message="No model available",
            category="application",
            app_name=session.app_name,
            entities_involved=list(set(entities_involved)),
            span_ids=agent_span_ids,
            session_ids=[session.session_id],
        )

    def _compute_agent_level(self, session: SessionEntity) -> List[MetricResult]:
        """
        Compute Workflow Cohesion Index for each agent in the session.

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
                    logger.info(f"Skipping agent '{agent_name}' for Workflow Cohesion Index metric: {role_metadata.get('skip_reason', 'Detected as coordinator agent')}")
                    continue

                # Use SessionEntity-level cached conversation data
                # This leverages existing conversation extraction logic + execution tree filtering
                agent_conversation = session.get_agent_conversation_text(agent_name)

                if not agent_conversation:
                    # Skip agents with no conversation data
                    continue

                # Use the same prompt format as session-level
                prompt = WORKFLOW_COHESION_INDEX_PROMPT.format(conversation=agent_conversation)

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
                logger.error(f"ERROR in workflow cohesion index computation for agent {agent_name}:")
                logger.error(f"Exception type: {type(e).__name__}")
                logger.error(f"Exception message: {str(e)}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")

                # Also print to stdout for immediate visibility in tests
                print(f"\n=== WORKFLOW COHESION INDEX ERROR DEBUG ===")
                print(f"Agent: {agent_name}")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                print(f"Traceback:\n{traceback.format_exc()}")
                print(f"==========================================\n")

                result = self._create_error_result(
                    error_message=f"Error computing workflow cohesion index for agent {agent_name}: {str(e)}",
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
