# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Union
from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.entities.models.session import SessionEntity

from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


class CyclesCount(BaseMetric):
    """
    Counts contiguous cycles in agent and tool interactions.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "session"

    @property
    def required_parameters(self) -> List[str]:
        return ["Events.Attributes"]

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

    def count_contiguous_cycles(self, seq, min_cycle_len=2):
        n = len(seq)
        cycle_count = 0
        i = 0
        while i < n:
            found_cycle = False
            for k in range(min_cycle_len, (n - i) // 2 + 1):
                if seq[i : i + k] == seq[i + k : i + 2 * k]:
                    cycle_count += 1
                    found_cycle = True
                    i += k
                    break
            if not found_cycle:
                i += 1
        return cycle_count

    async def compute(self, session: SessionEntity, **context) -> Union[MetricResult, List[MetricResult]]:
        # Extract nested context if present
        actual_context = context.get('context', context)
        is_agent_computation = actual_context.get("agent_computation", False) if actual_context else False

        # Check if this is agent-level computation
        if is_agent_computation:
            return await self._compute_agent_level(session)

        # Session-level computation (existing logic)
        try:
            # Get agent and tool spans, extract entity names
            # agent_tool_spans = []
            # if session.agent_spans:
            #     agent_tool_spans.extend(session.agent_spans)
            # if session.tool_spans:
            #     agent_tool_spans.extend(session.tool_spans)
            # Sort by timestamp to maintain order
            # agent_tool_spans.sort(key=lambda x: x.timestamp or "")

            agent_tool_spans = [
                span for span in session.spans if span.entity_type in ["agent", "tool"]
            ]
            events = [span.entity_name for span in agent_tool_spans]
            cycle_count = self.count_contiguous_cycles(events)

            span_ids = [span.span_id for span in agent_tool_spans]

            result = self._create_success_result(
                score=cycle_count,
                category="application",
                app_name=session.app_name,
                reasoning="Count of contiguous cycles in agent and tool interactions",
                span_ids=span_ids,
                session_ids=[session.session_id]
            )

            # Override specific fields for cycles count
            result.description = "Count of contiguous cycles in agent and tool interactions"
            result.unit = "cycles"
            result.metadata = {
                "span_ids": span_ids,
                "event_sequence": events,
                "total_events": len(events),
            }

            return result

        except Exception as e:
            print(f"DEBUG: Exception in session-level computation: {e}")
            import traceback
            traceback.print_exc()

            result = self._create_error_result(
                category="application",
                app_name=session.app_name if hasattr(session, "app_name") else "unknown",
                error_message=str(e),
                session_ids=[session.session_id] if hasattr(session, "session_id") else []
            )

            # Override specific fields for cycles count
            result.description = "Failed to calculate cycles count"
            result.unit = "cycles"

            return result

    async def _compute_agent_level(self, session: SessionEntity) -> List[MetricResult]:
        """
        Compute cycles count for each individual agent in the session.

        Returns a list of MetricResult objects, one per agent found.
        Each result contains the cycles count for that specific agent.
        """
        # Temporarily override aggregation level for agent computation
        original_level = self.aggregation_level
        self.aggregation_level = "agent"

        try:
            # Check if session has agent_stats property
            if not hasattr(session, 'agent_stats'):
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

                # Get agent and tool spans for this specific agent
                agent_tool_spans = [
                    span for span in agent_view.all_spans
                    if span.entity_type in ["agent", "tool"]
                ]

                # Extract entity names and compute cycles
                events = [span.entity_name for span in agent_tool_spans if span.entity_name]
                cycle_count = self.count_contiguous_cycles(events)
                span_ids = [span.span_id for span in agent_tool_spans]

                # Create individual result for this agent
                result = self._create_success_result(
                    score=cycle_count,
                    category="application",
                    app_name=session.app_name,
                    reasoning=f"Cycles count for agent '{agent_name}': {cycle_count} cycles found in {len(events)} events",
                    span_ids=span_ids,
                    session_ids=[session.session_id]
                )

                # Set agent-specific fields
                result.description = f"Cycles count for agent '{agent_name}'"
                result.unit = "cycles"
                result.metadata = {
                    "agent_id": agent_name,
                    "agent_span_ids": span_ids,
                    "agent_event_sequence": events,
                    "agent_total_events": len(events)
                }

                results.append(result)

            # Restore original aggregation level before returning
            self.aggregation_level = original_level
            return results

        except Exception as e:
            # Error handling for agent computation - restore level and re-raise
            self.aggregation_level = original_level
            raise e
