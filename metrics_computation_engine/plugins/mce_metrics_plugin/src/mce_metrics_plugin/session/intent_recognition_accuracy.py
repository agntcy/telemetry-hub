# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.entities.models.session import SessionEntity

# Co-located prompt for better readability and maintainability
INTENT_RECOGNITION_ACCURACY_PROMPT = """
    You are an evaluator of Intent Recognition Accuracy.

    You will be given a QUERY and a RESPONSE, and (optionally) a Reference Answer that gets a score of 3. Evaluate how well the RESPONSE demonstrates intent recognition accuracy.

    Here is the evaluation criteria to follow: (1) Does the response correctly identify the user's intent? (2) Does the response address the identified intent accurately? (3) Is the response appropriate for the identified intent?

    Scoring Rubric:
        1: the Assistant accurately identifies the user's intent and responds appropriately.
        0: the Assistant fails to identify the user's intent correctly.

    QUERY: {query} Optional Reference Answer (Score 3): {ground_truth} RESPONSE to evaluate: {response}
"""


class IntentRecognitionAccuracy(BaseMetric):
    """
    Measures how well the assistant recognizes and responds to user intents.
    """

    REQUIRED_PARAMETERS = {
        "IntentRecognitionAccuracy": ["input_query", "final_response"]
    }

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"
        self.description = (
            "Measures how well the assistant recognizes and responds to user intents."
        )

    @property
    def required_parameters(self) -> List[str]:
        return self.REQUIRED_PARAMETERS

    def supports_agent_computation(self) -> bool:
        """Returns True if this metric supports agent-level computation."""
        return True

    def validate_config(self) -> bool:
        return True

    def init_with_model(self, model) -> bool:
        self.jury = model
        return True

    def get_model_provider(self):
        return self.get_default_provider()

    def create_model(self, llm_config):
        return self.create_native_model(llm_config)

    async def compute(self, session: SessionEntity, **context):
        """Compute intent recognition accuracy at session level."""
        return await self._compute_session_level(session)

    async def _compute_session_level(self, session: SessionEntity):
        """Compute intent recognition accuracy at session level."""
        # Extract data directly from the session entity
        query = session.input_query
        response = session.final_response

        print("SESSION:", session.session_id)
        print("INPUT:", session.input_query)
        print("RESPONSE:", session.final_response)

        entities_involved = (
            [span.entity_name for span in session.agent_spans]
            if session.agent_spans
            else []
        )
        # TODO: Add ground truth lookup once dataset is available
        ground_truth = "No ground truth available"

        # Format the prompt
        prompt = INTENT_RECOGNITION_ACCURACY_PROMPT.format(
            query=query, response=response, ground_truth=ground_truth
        )

        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score=score,
                category="application",
                app_name=session.app_name,
                reasoning=reasoning,
                entities_involved=entities_involved,
                span_ids=[span.span_id for span in session.agent_spans],
                session_ids=[session.session_id],
            )

        return self._create_error_result(
            error_message="No model available",
            category="application",
            app_name=session.app_name,
            entities_involved=entities_involved,
            span_ids=[span.span_id for span in session.agent_spans],
            session_ids=[session.session_id],
        )

    async def compute_agent_level(self, session: SessionEntity):
        """Compute intent recognition accuracy for each agent in the session."""

        # Temporarily override aggregation level for agent computation
        original_level = self.aggregation_level
        self.aggregation_level = "agent"

        results = []

        try:
            # Check if session has agent_stats property
            if not hasattr(session, "agent_stats"):
                # Session doesn't have agent_stats - return empty list
                return []

            agent_stats = session.agent_stats
            if not agent_stats:
                # No agents found in session - return empty list
                return []

            for agent_name in agent_stats.keys():
                # Create AgentView for this specific agent
                agent_view = session.get_agent_view(agent_name)

                # Extract agent-specific input_query and final_response
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

                # TODO: Add ground truth lookup once dataset is available
                ground_truth = "No ground truth available"

                # Format the prompt for this agent
                prompt = INTENT_RECOGNITION_ACCURACY_PROMPT.format(
                    query=agent_input_query,
                    response=agent_final_response,
                    ground_truth=ground_truth,
                )

                entities_involved = [agent_name]
                agent_span_ids = [span.span_id for span in agent_view.all_spans]

                if self.jury:
                    score, reasoning = self.jury.judge(prompt, BinaryGrading)
                    result = self._create_success_result(
                        score=score,
                        category="agent",
                        app_name=session.app_name,
                        agent_id=agent_name,
                        reasoning=reasoning,
                        entities_involved=entities_involved,
                        span_ids=agent_span_ids,
                        session_ids=[session.session_id],
                    )
                    # Add agent-specific metadata
                    result.metadata.update(
                        {
                            "metric_type": "llm-as-a-judge",
                            "agent_id": agent_name,
                            "agent_input_query": agent_input_query,
                            "agent_final_response": agent_final_response,
                        }
                    )
                else:
                    result = self._create_error_result(
                        error_message="No model available",
                        category="agent",
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

            # Restore original aggregation level before returning
            self.aggregation_level = original_level
            return results

        except Exception as e:
            # Error handling for agent computation - restore level and re-raise
            self.aggregation_level = original_level
            raise e
