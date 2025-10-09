# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity

from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


class PassiveEvalAgents(BaseMetric):
    """
    Returns various stats for the agents for a given application.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return []

    def validate_config(self) -> bool:
        return True

    def create_model(self, llm_config):
        return self.create_no_model()

    def get_model_provider(self):
        return self.get_provider_no_model_needed()

    def init_with_model(self, model) -> bool:
        return True

    async def compute(self, session: SessionEntity, **context):
        try:
            # Extract context information
            if not context:
                logger.warning(
                    f"PassiveEvalAgents: No context provided for session {session.session_id}"
                )
                # Return early with error if no context
                return MetricResult(
                    metric_name=self.name,
                    value={},
                    aggregation_level=self.aggregation_level,
                    category="application",
                    app_name=session.app_name
                    if hasattr(session, "app_name")
                    else "unknown",
                    description="",
                    unit="",
                    reasoning="PassiveEvalAgents requires SessionSet stats context but none was provided",
                    span_id="",
                    session_id=[session.session_id],
                    source="native",
                    entities_involved=[],
                    edges_involved=[],
                    success=False,
                    metadata={},
                    error_message="No context provided",
                )

            session_set_stats = context.get("session_set_stats")
            session_index = context.get("session_index")
            app_name = session_set_stats.meta.session_ids[session_index][1]

            if session_set_stats is None or session_index is None:
                logger.warning(
                    f"PassiveEvalAgents: Missing required context data for session {session.session_id}"
                )
                return MetricResult(
                    metric_name=self.name,
                    value={},
                    aggregation_level=self.aggregation_level,
                    category="application",
                    app_name=session.app_name
                    if hasattr(session, "app_name")
                    else "unknown",
                    description="Passive evaluation statistics for the application",
                    unit="",
                    reasoning="PassiveEvalAgents requires session_set_stats and session_index in context",
                    span_id="",
                    session_id=[session.session_id],
                    source="native",
                    entities_involved=[],
                    edges_involved=[],
                    success=False,
                    metadata={},
                    error_message="Missing context data",
                )

            # Use the context data
            idx = session_index

            # for one session, we can have several agents
            _values = {}
            for _an, _anv in session_set_stats.histogram.agents.items():
                _values[_an] = {
                    "eval.agent.tool_calls": _anv.tool_calls[idx],
                    "eval.agent.tool_fails": _anv.tool_fails[idx],
                    "eval.agent.tool_cost": _anv.tool_total_tokens[idx],
                    "eval.agent.tool_duration": _anv.tool_duration[idx],
                    "eval.agent.llm_calls": _anv.llm_calls[idx],
                    "eval.agent.llm_fails": _anv.llm_fails[idx],
                    "eval.agent.llm_cost": _anv.llm_total_tokens[idx],
                    "eval.agent.llm_cost_input": _anv.llm_input_tokens[idx],
                    "eval.agent.llm_cost_output": _anv.llm_output_tokens[idx],
                    "eval.agent.llm_duration": _anv.llm_duration[idx],
                }

            _value = {
                "aggregation_level": "session",
                "category": "agents",
                "name": app_name,
                "agents": _values,
            }

            logger.debug(
                f"Prepared metric data for session {session.session_id}: {_value}"
            )

            return MetricResult(
                metric_name=self.name,
                value=_value,
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=session.app_name,
                description="Passive evaluation statistics for agents for the application",
                unit="dict_stats",
                reasoning="Statistics extracted from session data using SessionSet context",
                span_id="",
                session_id=[session.session_id],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={
                    "session_index": idx,
                },
                error_message=None,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                category="application",
                app_name=session.app_name
                if hasattr(session, "app_name")
                else "unknown",
                description="Passive evaluation statistics for the agents for the application",
                value={},
                unit="",
                reasoning="Error occurred while computing passive evaluation statistics",
                aggregation_level=self.aggregation_level,
                span_id="",
                session_id=[session.session_id]
                if hasattr(session, "session_id")
                else [],
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=str(e),
            )
