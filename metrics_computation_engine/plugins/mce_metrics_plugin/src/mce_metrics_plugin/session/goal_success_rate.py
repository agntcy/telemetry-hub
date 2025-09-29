# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import BinaryGrading
from metrics_computation_engine.entities.models.session import SessionEntity

GOAL_SUCCESS_RATE_PROMPT = """
    You are an evaluator of Goal Success Rate.

    You will be given a QUERY and a RESPONSE, and (optionally) a Ground Truth. If the RESPONSE to evaluate matches the Ground Truth, then the score should be a 1. The RESPONSE can alternatively score a goal of 1 by satisfying all of the evaluation critieria. Evaluate how well the RESPONSE demonstrates Goal Success Rate.

    The QUERY contains the GOAL that the user is requesting the assistant to achieve.

    Here is the evaluation criteria to follow: (1) Does the response correctly correspond to what the user has asked for in the goal? (2) Does the response fulfill all expectations specified in the goal? (3) If the assistant is not able to achieve the goal, does it state the reasons for why it cannot?

    Scoring Rubric:
        1: the response is accurate and correspond to what the user asked for in the goal.
        0: the Assistant fails to achieve the goal specified by the user.

    QUERY: {query}
    GROUND TRUTH EXPECTED RESPONSE: {ground_truth}
    RESPONSE to evaluate: {response}
"""


class GoalSuccessRate(BaseMetric):
    REQUIRED_PARAMETERS = {"GoalSuccessRate": ["input_query", "final_response"]}

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

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

    async def compute(self, session: SessionEntity):
        query = session.input_query
        response = session.final_response

        entities_involved = (
            [span.entity_name for span in session.agent_spans]
            if session.agent_spans
            else []
        )
        ground_truth = session.ground_truth
        prompt = GOAL_SUCCESS_RATE_PROMPT.format(
            query=query, response=response, ground_truth=ground_truth
        )
        
        if self.jury:
            score, reasoning = self.jury.judge(prompt, BinaryGrading)
            return self._create_success_result(
                score=score,
                reasoning=reasoning,
                category="application",
                app_name=session.app_name,
                entities_involved=entities_involved,
                span_ids=[span.span_id for span in session.llm_spans],
                session_ids=[session.session_id],
            )

        return self._create_error_result(
            error_message="No model available",
            category="application",
            app_name=session.app_name,
            entities_involved=entities_involved,
            span_ids=[span.span_id for span in session.llm_spans],
            session_ids=[session.session_id],
        )
