# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Union
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity


class ToolErrorRate(BaseMetric):
    """
    Calculates the percentage of tool spans that resulted in an error.
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

    def supports_agent_computation(self) -> bool:
        """Indicates that this metric supports agent-level computation."""
        return True

    async def compute(
        self, session: SessionEntity, **context
    ) -> Union[MetricResult, List[MetricResult]]:
        # Extract nested context if present
        actual_context = context.get("context", context)
        is_agent_computation = (
            actual_context.get("agent_computation", False) if actual_context else False
        )

        # Check if this is agent-level computation
        if is_agent_computation:
            return await self._compute_agent_level(session)

        # Session-level computation (existing logic)
        try:
            tool_spans = session.tool_spans if session.tool_spans else []
            total_tool_calls = len(tool_spans)

            error_spans = [span for span in tool_spans if span.contains_error]
            total_tool_errors = len(error_spans)
            error_span_ids = [span.span_id for span in error_spans]

            tool_error_rate = (
                (total_tool_errors / total_tool_calls) * 100 if total_tool_calls else 0
            )

            result = self._create_success_result(
                score=tool_error_rate,
                category="application",
                app_name=session.app_name,
                reasoning="",
                span_ids=error_span_ids,
                session_ids=[session.session_id],
            )

            # Override specific fields for tool error rate
            result.description = "Percentage of tool spans that encountered errors"
            result.unit = "%"
            result.metadata = {
                "total_tool_calls": total_tool_calls,
                "total_tool_errors": total_tool_errors,
                "all_tool_span_ids": [span.span_id for span in tool_spans],
            }

            return result

        except Exception as e:
            print(f"DEBUG: Exception in session-level computation: {e}")
            import traceback

            traceback.print_exc()

            result = self._create_error_result(
                category="application",
                app_name=session.app_name
                if hasattr(session, "app_name")
                else "unknown",
                error_message=str(e),
                session_ids=[session.session_id]
                if hasattr(session, "session_id")
                else [],
            )

            # Override specific fields for tool error rate
            result.description = "Failed to calculate tool error rate"
            result.unit = "%"

            return result

    async def _compute_agent_level(self, session: SessionEntity) -> List[MetricResult]:
        """
        Compute tool error rate for each individual agent in the session.

        Returns a list of MetricResult objects, one per agent found.
        Each result contains the tool error rate for that specific agent.
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

                agent_tool_calls = agent_view.total_tool_calls
                agent_tool_errors = agent_view.total_tool_errors
                agent_error_rate = agent_view.tool_error_rate
                agent_error_span_ids = [
                    span.span_id for span in agent_view.error_tool_spans
                ]

                # Create individual result for this agent
                result = self._create_success_result(
                    score=agent_error_rate,
                    category="application",
                    app_name=session.app_name,
                    reasoning=f"Tool error rate for agent '{agent_name}': {agent_tool_errors} errors out of {agent_tool_calls} tool calls",
                    span_ids=agent_error_span_ids,
                    session_ids=[session.session_id],
                )

                # Set agent-specific fields
                result.description = f"Tool error rate for agent '{agent_name}'"
                result.unit = "%"
                result.metadata = {
                    "agent_id": agent_name,
                    "agent_tool_calls": agent_tool_calls,
                    "agent_tool_errors": agent_tool_errors,
                    "agent_error_span_ids": agent_error_span_ids,
                    "agent_tool_names": agent_view.unique_tool_names,
                }

                results.append(result)

            # Restore original aggregation level before returning
            self.aggregation_level = original_level
            return results

        except Exception as e:
            # Error handling for agent computation - restore level and re-raise
            self.aggregation_level = original_level
            raise e
