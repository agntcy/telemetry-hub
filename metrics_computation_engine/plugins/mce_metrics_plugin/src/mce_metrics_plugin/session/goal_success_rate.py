# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading, MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity

GOAL_SUCCESS_RATE_PROMPT = """
    You are an evaluator of Goal Success Rate.

    You will be given a QUERY and a RESPONSE, and (optionally) a Reference Answer that gets a score of 1. Evaluate how well the RESPONSE demonstrates Goal Success Rate.

    The QUERY contains the GOAL that the user is requesting the assistant to achieve.

    Here is the evaluation criteria to follow: (1) Does the response correctly correspond to what the user has asked for in the goal? (2) Does the response fulfill all expectations specified in the goal? (3) If the assistant is not able to achieve the goal, does it state the reasons for why it cannot?

    Scoring Rubric:
        1: the response is accurate and correspond to what the user asked for in the goal.
        0: the Assistant fails to achieve the goal specified by the user.

    QUERY: {query} Optional Reference Answer (Score 1): {ground_truth} RESPONSE to evaluate: {response}
"""


class GoalSuccessRate(BaseMetric):
    REQUIRED_PARAMETERS = {"GoalSuccessRate": ["input_query", "final_response"]}

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"
        self.description = "Measures the rate at which the assistant successfully achieves the input's goal as extracted from traces."

    @property
    def required_parameters(self) -> List[str]:
        return self.REQUIRED_PARAMETERS

    def validate_config(self) -> bool:
        return True

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    def supports_agent_computation(self) -> bool:
        """Indicates that this metric supports agent-level computation."""
        return True

    async def compute(self, session: SessionEntity, **context) -> MetricResult:
        # Session-level computation (existing logic)
        query = session.input_query
        response = session.final_response

        entities_involved = (
            [span.entity_name for span in session.agent_spans]
            if session.agent_spans
            else []
        )
        ground_truth = "No ground truth available"  # TODO: Add dataset lookup

        prompt = GOAL_SUCCESS_RATE_PROMPT.format(
            query=query, response=response, ground_truth=ground_truth
        )

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score=score,
                reasoning=reasoning,
                category="application",
                description=self.description,
                app_name=session.app_name,
                entities_involved=entities_involved,
                span_ids=[span.span_id for span in session.llm_spans],
                session_ids=[session.session_id],
            )

        return self._create_error_result(
            error_message="No model available",
            category="application",
            description=self.description,
            app_name=session.app_name,
            entities_involved=entities_involved,
            span_ids=[span.span_id for span in session.llm_spans],
            session_ids=[session.session_id],
        )

    async def compute_agent_level(self, session: SessionEntity) -> List[MetricResult]:
        """
        Compute goal success rate for each individual agent in the session.

        Returns a list of MetricResult objects, one per agent found.
        Each result contains the goal success rate for that specific agent.
        """
        # Temporarily override aggregation level for agent computation
        original_level = self.aggregation_level
        self.aggregation_level = "agent"

        try:
            # Check if session has agent_stats property
            if not hasattr(session, "agent_stats"):
                # Session doesn't have agent_stats - return empty list
                return []

            agent_stats = session.agent_stats
            if not agent_stats:
                # No agents found in session - return empty list
                return []

            # Create individual results for each agent
            results = []

            for agent_name in agent_stats.keys():
                agent_view = session.get_agent_view(agent_name)

                # Get agent-specific input_query and final_response from AgentView
                agent_input_query = agent_view.input_query
                agent_final_response = agent_view.final_response

                if not agent_input_query or not agent_final_response:
                    # Create error result for agents without complete query/response data
                    entities_involved = [agent_name] if agent_name else []
                    agent_span_ids = [span.span_id for span in agent_view.all_spans]

                    result = self._create_error_result(
                        error_message=f"Agent '{agent_name}' missing input_query or final_response data",
                        category="agent",
                        description=self.description,
                        app_name=session.app_name,
                        entities_involved=entities_involved,
                        span_ids=agent_span_ids,
                        session_ids=[session.session_id],
                    )
                    # Add metadata to the result after creation
                    result.metadata.update(
                        {
                            "metric_type": "llm-as-a-judge",
                            "agent_id": agent_name,
                            "agent_input_query": agent_input_query,
                            "agent_final_response": agent_final_response,
                        }
                    )

                    results.append(result)
                    continue

                ground_truth = "No ground truth available"  # TODO: Add dataset lookup

                prompt = GOAL_SUCCESS_RATE_PROMPT.format(
                    query=agent_input_query,
                    response=agent_final_response,
                    ground_truth=ground_truth,
                )

                entities_involved = [agent_name] if agent_name else []
                agent_span_ids = [span.span_id for span in agent_view.all_spans]

                if self.jury:
                    score, reasoning = self.jury.judge(prompt, BinaryGrading)
                    result = self._create_success_result(
                        score=score,
                        reasoning=f"{reasoning}",
                        description=self.description,
                        category="agent",
                        app_name=session.app_name,
                        agent_id=agent_name,
                        entities_involved=entities_involved,
                        span_ids=agent_span_ids,
                        session_ids=[session.session_id],
                    )
                else:
                    result = self._create_error_result(
                        error_message="No model available",
                        description=self.description,
                        category="agent",
                        app_name=session.app_name,
                        entities_involved=entities_involved,
                        span_ids=agent_span_ids,
                        session_ids=[session.session_id],
                    )

                # Set agent-specific fields
                result.metadata = {
                    "metric_type": "llm-as-a-judge",
                    "agent_id": agent_name,
                    "agent_input_query": agent_input_query,
                    "agent_final_response": agent_final_response,
                }

                results.append(result)

            # Restore original aggregation level before returning
            self.aggregation_level = original_level
            return results

        except Exception as e:
            # Error handling for agent computation - restore level and re-raise
            self.aggregation_level = original_level
            raise e
