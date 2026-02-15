# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading, MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.core.agent_role_detector import (
    get_agent_role_and_skip_decision,
)
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

# Co-located prompt for better readability and maintainability
GROUNDEDNESS_PROMPT = """
    You are an evaluator of Groundedness Evaluate how well each response is grounded in verifiable data and avoids speculation or hallucinations.

    Here is the evaluation criteria to follow: (1) Is the response based on verifiable information from the provided data, knowledge bases, or tool outputs? (2) Does the response avoid speculation, hallucinations, or misleading statements? (3) Is the factual accuracy of the response maintained throughout the conversation?

    Scoring Rubric:
        1: Response by the system is fully grounded by the context available through the tools and conversation.
        0: There are details in the response that are not grounded by the context available through tools and conversation.

    CONVERSATION: {conversation}
"""


class Groundedness(BaseMetric):
    REQUIRED_PARAMETERS = {"Groundedness": ["conversation_data"]}

    def __init__(
        self, metric_name: Optional[str] = None, filter_coordinators: bool = True
    ):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"
        self.description = "Evaluates how well each response is grounded in verifiable data and avoids speculation or hallucinations by checking if responses are based on verifiable information, avoid speculation/hallucinations, and maintain factual accuracy. Returns 1 for fully grounded responses, or 0 for responses with ungrounded details."
        self.filter_coordinators = filter_coordinators

    @property
    def required_parameters(self) -> List[str]:
        return ["conversation_data"]

    def validate_config(self) -> bool:
        return True

    def supports_agent_computation(self) -> bool:
        """Groundedness can be computed at agent level for individual agent grounding analysis."""
        return True

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    async def compute(self, session: SessionEntity, **context) -> MetricResult:
        """
        Compute groundedness using pre-populated SessionEntity data.

        Args:
            session: SessionEntity with pre-computed conversation data
            **context: Additional context
        """
        # Session-level computation (incorporating main branch improvements)
        try:
            if self.jury:
                # Use pre-computed conversation data from SessionEntity (compatible with both formats)
                conversation = ""
                if session.conversation_data:
                    # Try both "elements" (main branch) and "conversation" (agent branch) formats
                    #                    if "elements" in session.conversation_data:
                    #                        conversation = session.conversation_data["elements"]
                    #                    elif "conversation" in session.conversation_data:
                    #                        conversation = session.conversation_data["conversation"]
                    conversation = session.get_conversation_data_without_images()
                    if "elements" in conversation:
                        conversation = conversation["elements"]
                    elif "conversation" in conversation:
                        conversation = conversation["conversation"]

                # Format conversation properly (main branch improvement)
                conversation_str = (
                    json.dumps(conversation, indent=2)
                    if isinstance(conversation, list)
                    else conversation
                )

                prompt = GROUNDEDNESS_PROMPT.format(conversation=conversation_str)
                score, reasoning = self.jury.judge(prompt, BinaryGrading)
                # Get relevant span IDs for metadata
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

                result = self._create_success_result(
                    score=score,
                    reasoning=reasoning,
                    category="application",
                    app_name=session.app_name,
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
                entities_involved=[],
                span_ids=[],
                session_ids=[session.session_id],
            )

        except Exception as e:
            return self._create_error_result(
                error_message=str(e),
                category="application",
                app_name=session.app_name,
                entities_involved=[],
                span_ids=[],
                session_ids=[session.session_id],
            )

    async def compute_agent_level(self, session: SessionEntity) -> List[MetricResult]:
        """
        Compute Groundedness for each agent in the session.

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
                    logger.info(
                        f"Skipping agent '{agent_name}' for Groundedness metric: {role_metadata.get('skip_reason', 'Detected as coordinator agent')}"
                    )
                    continue

                # Use SessionEntity-level cached conversation data
                # This leverages existing conversation extraction logic + execution tree filtering
                agent_conversation = session.get_agent_conversation_text(agent_name)

                if not agent_conversation:
                    # Skip agents with no conversation data
                    logger.info(
                        f"Skipping agent '{agent_name}' for Groundedness metric: no conversation data available"
                    )
                    continue

                # Use the same prompt format as session-level
                prompt = GROUNDEDNESS_PROMPT.format(conversation=agent_conversation)

                # Get agent-specific spans for metadata (reuses existing span collection)
                agent_spans = session._get_spans_for_agent(agent_name)
                agent_span_ids = [span.span_id for span in agent_spans]

                if self.jury:
                    score, reasoning = self.jury.judge(prompt, BinaryGrading)
                    result = self._create_success_result(
                        score=score,
                        category="agent",
                        agent_id=agent_name,
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
                if not hasattr(result, "metadata") or result.metadata is None:
                    result.metadata = {}
                # Handle both AgentFilterMetadata objects and plain dicts (for tests)
                role_dict = (
                    role_metadata.to_dict()
                    if hasattr(role_metadata, "to_dict")
                    else role_metadata
                )
                result.metadata.update(
                    {
                        "agent_id": agent_name,
                        "metric_type": "llm-as-a-judge",
                        "skipped": False,
                        **role_dict,
                    }
                )
                results.append(result)

            except Exception as e:
                # Handle errors gracefully for individual agents
                import traceback

                # Log detailed error information for debugging
                logger.error(
                    f"ERROR in groundedness computation for agent {agent_name}:"
                )
                logger.error(f"Exception type: {type(e).__name__}")
                logger.error(f"Exception message: {str(e)}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")

                result = self._create_error_result(
                    error_message=f"Error computing groundedness for agent {agent_name}: {str(e)}",
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
                result.metadata.update(
                    {
                        "agent_id": agent_name,
                        "metric_type": "llm-as-a-judge",
                        "skipped": False,
                        "error_in_processing": True,
                    }
                )

                results.append(result)

        return results
