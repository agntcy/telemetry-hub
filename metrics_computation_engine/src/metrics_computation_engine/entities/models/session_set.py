# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import List, Dict, Set, Optional
from pydantic import BaseModel, Field
from collections import defaultdict

from .session import SessionEntity


class SessionSetAgentAggregateStats(BaseModel):
    """Aggregate statistics for agents across sessions."""

    avg_tool_calls: float = Field(
        default=0.0,
        description="Average number of tool calls per session for this agent",
    )
    avg_tool_fails: float = Field(
        default=0.0,
        description="Average number of failed tool calls per session for this agent",
    )
    avg_tool_total_tokens: float = Field(
        default=0.0, description="Average tool tokens per session for this agent"
    )
    avg_tool_duration: float = Field(
        default=0.0, description="Average tool duration per session for this agent (ms)"
    )
    avg_tool_duration_norm: float = Field(
        default=0.0,
        description="Average normalized tool duration per session for this agent",
    )
    avg_llm_calls: float = Field(
        default=0.0,
        description="Average number of LLM calls per session for this agent",
    )
    avg_llm_fails: float = Field(
        default=0.0,
        description="Average number of failed LLM calls per session for this agent",
    )
    avg_llm_total_tokens: float = Field(
        default=0.0, description="Average LLM tokens per session for this agent"
    )
    avg_llm_input_tokens: float = Field(
        default=0.0, description="Average LLM input tokens per session for this agent"
    )
    avg_llm_output_tokens: float = Field(
        default=0.0, description="Average LLM output tokens per session for this agent"
    )
    avg_llm_duration: float = Field(
        default=0.0, description="Average LLM duration per session for this agent (ms)"
    )
    avg_llm_duration_norm: float = Field(
        default=0.0,
        description="Average normalized LLM duration per session for this agent",
    )
    avg_duration: float = Field(
        default=0.0, description="Average total duration of the agent's activity per session (ms)"
    )
    avg_completion: float = Field(
        default=1.0, description="Average completion rate of the agent per session (1.0 = always completed)"
    )


class SessionSetAgentHistogramStats(BaseModel):
    """Histogram statistics for agents across sessions."""

    tool_calls: List[int] = Field(
        default_factory=list, description="Tool calls count per session for this agent"
    )
    tool_fails: List[int] = Field(
        default_factory=list,
        description="Tool failures count per session for this agent",
    )
    tool_total_tokens: List[int] = Field(
        default_factory=list, description="Tool tokens per session for this agent"
    )
    tool_duration: List[float] = Field(
        default_factory=list,
        description="Tool duration per session for this agent (ms)",
    )
    llm_calls: List[int] = Field(
        default_factory=list, description="LLM calls count per session for this agent"
    )
    llm_fails: List[int] = Field(
        default_factory=list,
        description="LLM failures count per session for this agent",
    )
    llm_total_tokens: List[int] = Field(
        default_factory=list, description="LLM tokens per session for this agent"
    )
    llm_input_tokens: List[int] = Field(
        default_factory=list, description="LLM input tokens per session for this agent"
    )
    llm_output_tokens: List[int] = Field(
        default_factory=list, description="LLM output tokens per session for this agent"
    )
    llm_duration: List[float] = Field(
        default_factory=list, description="LLM duration per session for this agent (ms)"
    )
    duration: List[float] = Field(
        default_factory=list, description="Total duration of the agent's activity per session (ms)"
    )
    completion: List[bool] = Field(
        default_factory=list, description="Completion status per session for this agent"
    )


class SessionSetStatsAggregate(BaseModel):
    """Aggregate section of session set statistics."""

    avg_tool_calls: float = Field(default=0.0)
    avg_tool_fails: float = Field(default=0.0)
    avg_tool_total_tokens: float = Field(default=0.0)
    avg_tool_duration: float = Field(default=0.0)
    avg_tool_duration_norm: float = Field(default=0.0)
    avg_llm_calls: float = Field(default=0.0)
    avg_llm_fails: float = Field(default=0.0)
    avg_llm_total_tokens: float = Field(default=0.0)
    avg_llm_input_tokens: float = Field(default=0.0)
    avg_llm_output_tokens: float = Field(default=0.0)
    avg_llm_duration: float = Field(default=0.0)
    avg_llm_duration_norm: float = Field(default=0.0)
    avg_graph_determinism: float = Field(default=0.0)
    avg_graph_dynamism: float = Field(default=0.0)
    avg_total_tokens: float = Field(default=0.0)
    avg_latency: float = Field(default=0.0)
    agents: Dict[str, SessionSetAgentAggregateStats] = Field(default_factory=dict)
    avg_completion: float = Field(default=1.0, description="Average completion rate across all sessions (1.0 = all completed)")


class SessionSetStatsHistogram(BaseModel):
    """Histogram section of session set statistics."""

    tool_calls: List[int] = Field(default_factory=list)
    tool_fails: List[int] = Field(default_factory=list)
    tool_total_tokens: List[int] = Field(default_factory=list)
    tool_duration: List[float] = Field(default_factory=list)
    llm_calls: List[int] = Field(default_factory=list)
    llm_fails: List[int] = Field(default_factory=list)
    llm_total_tokens: List[int] = Field(default_factory=list)
    llm_input_tokens: List[int] = Field(default_factory=list)
    llm_output_tokens: List[int] = Field(default_factory=list)
    llm_duration: List[float] = Field(default_factory=list)
    graph_determinism: List[float] = Field(default_factory=list)
    graph_dynamism: List[float] = Field(default_factory=list)
    total_tokens: List[int] = Field(default_factory=list)
    latency: List[float] = Field(default_factory=list)
    accuracy: List[float] = Field(default_factory=list)
    agents: Dict[str, SessionSetAgentHistogramStats] = Field(default_factory=dict)
    completion: List[bool] = Field(default_factory=list)


class SessionSetStatsMeta(BaseModel):
    """Meta section of session set statistics."""

    count: int = Field(default=0, description="Number of sessions in the set")
    session_ids: List[List[str]] = Field(
        default_factory=list, description="List of [session_id, app_name] pairs"
    )


class SessionSetStats(BaseModel):
    """Complete statistics structure for a session set."""

    aggregate: SessionSetStatsAggregate = Field(
        default_factory=SessionSetStatsAggregate
    )
    histogram: SessionSetStatsHistogram = Field(
        default_factory=SessionSetStatsHistogram
    )
    meta: SessionSetStatsMeta = Field(default_factory=SessionSetStatsMeta)


class SessionSet(BaseModel):
    sessions: List[SessionEntity]

    # Private cache for stats
    _cached_stats: Optional[SessionSetStats] = None
    _cache_hash: Optional[int] = None

    @property
    def session_ids(self) -> List[str]:
        return [session.session_id for session in self.sessions]

    @property
    def stats(self) -> SessionSetStats:
        """
        Calculate comprehensive statistics for the session set with caching.

        Returns:
            SessionSetStats object containing aggregate, histogram, and meta statistics
        """
        # Calculate hash of current sessions to detect changes
        current_hash = self._calculate_sessions_hash()

        # Return cached stats if nothing has changed
        if (
            self._cached_stats is not None
            and self._cache_hash is not None
            and current_hash == self._cache_hash
        ):
            return self._cached_stats

        # Compute fresh stats
        fresh_stats = self._compute_stats()

        # Cache the results
        self._cached_stats = fresh_stats
        self._cache_hash = current_hash

        return fresh_stats

    def _calculate_sessions_hash(self) -> int:
        """Calculate a hash based on sessions to detect changes."""
        if not self.sessions:
            return hash(())

        # Create a hash based on session IDs and key metrics that affect stats
        session_data = []
        for session in self.sessions:
            session_data.append(
                (
                    session.session_id,
                    len(session.spans),
                    session.total_llm_calls,
                    session.total_tool_calls,
                    session.duration,
                )
            )
        return hash(tuple(session_data))

    def _compute_stats(self) -> SessionSetStats:
        """
        Internal method to compute statistics (moved from the original stats property).
        """
        if not self.sessions:
            return SessionSetStats()

        # Initialize collections for calculations
        session_metrics = []
        agent_metrics = defaultdict(list)
        session_ids = []
        all_agent_names = set()

        # Collect metrics from each session
        for session in self.sessions:
            # Session-level metrics
            metrics = self._extract_session_metrics(session)
            session_metrics.append(metrics)

            # Use the session's actual app_name property instead of parsing the session_id
            app_name = session.app_name
            session_ids.append([session.session_id, app_name])

            # Agent-level metrics
            for agent_name, agent_stats in session.agent_stats.items():
                all_agent_names.add(agent_name)
                agent_metrics[agent_name].append(
                    self._extract_agent_metrics(agent_stats)
                )

        # Calculate aggregate statistics
        aggregate = self._calculate_aggregate_stats(session_metrics, agent_metrics)

        # Build histogram statistics
        histogram = self._build_histogram_stats(
            session_metrics, agent_metrics, all_agent_names
        )

        # Build meta statistics
        meta = SessionSetStatsMeta(count=len(self.sessions), session_ids=session_ids)

        return SessionSetStats(aggregate=aggregate, histogram=histogram, meta=meta)

    def _extract_session_metrics(self, session: SessionEntity) -> Dict:
        """Extract metrics from a single session."""
        # Calculate latency (session duration)
        latency = session.duration if session.duration is not None else 0.0

        # Determine completion status
        completion = session.completion

        # Calculate normalized durations (duration per call)
        tool_duration_norm = (
            (session.total_tools_duration / session.total_tool_calls)
            if session.total_tool_calls > 0
            else 0.0
        )
        llm_duration_norm = (
            (session.total_llm_duration / session.total_llm_calls)
            if session.total_llm_calls > 0
            else 0.0
        )

        # Extract graph metrics with defaults
        graph_determinism = (
            session.graph_determinism if session.graph_determinism is not None else 0.0
        )
        graph_dynamism = (
            session.graph_dynamism if session.graph_dynamism is not None else 0.0
        )

        return {
            "tool_calls": session.total_tool_calls,
            "tool_fails": session.tool_calls_failed,
            "tool_total_tokens": session.tool_total_tokens,
            "tool_duration": session.total_tools_duration,
            "tool_duration_norm": tool_duration_norm,
            "llm_calls": session.total_llm_calls,
            "llm_fails": session.llm_calls_failed,
            "llm_total_tokens": session.llm_total_tokens,
            "llm_input_tokens": session.llm_input_tokens,
            "llm_output_tokens": session.llm_output_tokens,
            "llm_duration": session.total_llm_duration,
            "llm_duration_norm": llm_duration_norm,
            "graph_determinism": graph_determinism,
            "graph_dynamism": graph_dynamism,
            "total_tokens": session.llm_total_tokens,  # Total tokens = LLM tokens for now
            "latency": latency,
            "completion": completion,
        }

    def _extract_agent_metrics(self, agent_stats) -> Dict:
        """Extract metrics from agent statistics."""
        # Calculate normalized durations
        tool_duration_norm = (
            (agent_stats.total_tools_duration / agent_stats.total_tool_calls)
            if agent_stats.total_tool_calls > 0
            else 0.0
        )
        llm_duration_norm = (
            (agent_stats.total_llm_duration / agent_stats.total_llm_calls)
            if agent_stats.total_llm_calls > 0
            else 0.0
        )

        return {
            "completion": agent_stats.completion,
            "duration": agent_stats.duration,
            "tool_calls": agent_stats.total_tool_calls,
            "tool_fails": agent_stats.tool_calls_failed,
            "tool_total_tokens": agent_stats.tool_total_tokens,
            "tool_duration": agent_stats.total_tools_duration,
            "tool_duration_norm": tool_duration_norm,
            "llm_calls": agent_stats.total_llm_calls,
            "llm_fails": agent_stats.llm_calls_failed,
            "llm_total_tokens": agent_stats.llm_total_tokens,
            "llm_input_tokens": agent_stats.llm_input_tokens,
            "llm_output_tokens": agent_stats.llm_output_tokens,
            "llm_duration": agent_stats.total_llm_duration,
            "llm_duration_norm": llm_duration_norm,
        }

    def _calculate_aggregate_stats(
        self, session_metrics: List[Dict], agent_metrics: Dict[str, List[Dict]]
    ) -> SessionSetStatsAggregate:
        """Calculate aggregate statistics from session metrics."""
        if not session_metrics:
            return SessionSetStatsAggregate()

        count = len(session_metrics)

        # Calculate session-level averages
        def avg(key: str) -> float:
            return sum(m[key] for m in session_metrics) / count

        # Calculate agent-level averages
        agents = {}
        for agent_name, metrics_list in agent_metrics.items():
            if metrics_list:
                agent_count = len(metrics_list)
                agents[agent_name] = SessionSetAgentAggregateStats(
                    avg_tool_calls=sum(m["tool_calls"] for m in metrics_list)
                    / agent_count,
                    avg_tool_fails=sum(m["tool_fails"] for m in metrics_list)
                    / agent_count,
                    avg_tool_total_tokens=sum(
                        m["tool_total_tokens"] for m in metrics_list
                    )
                    / agent_count,
                    avg_tool_duration=sum(m["tool_duration"] for m in metrics_list)
                    / agent_count,
                    avg_tool_duration_norm=sum(
                        m["tool_duration_norm"] for m in metrics_list
                    )
                    / agent_count,
                    avg_llm_calls=sum(m["llm_calls"] for m in metrics_list)
                    / agent_count,
                    avg_llm_fails=sum(m["llm_fails"] for m in metrics_list)
                    / agent_count,
                    avg_llm_total_tokens=sum(
                        m["llm_total_tokens"] for m in metrics_list
                    )
                    / agent_count,
                    avg_llm_input_tokens=sum(
                        m["llm_input_tokens"] for m in metrics_list
                    )
                    / agent_count,
                    avg_llm_output_tokens=sum(
                        m["llm_output_tokens"] for m in metrics_list
                    )
                    / agent_count,
                    avg_llm_duration=sum(m["llm_duration"] for m in metrics_list)
                    / agent_count,
                    avg_llm_duration_norm=sum(
                        m["llm_duration_norm"] for m in metrics_list
                    )
                    / agent_count,
                    avg_duration=sum(m["duration"] for m in metrics_list) / agent_count,
                    avg_completion=sum(1.0 if m["completion"] else 0.0 for m in metrics_list)
                    / agent_count,
                )

        return SessionSetStatsAggregate(
            avg_tool_calls=avg("tool_calls"),
            avg_tool_fails=avg("tool_fails"),
            avg_tool_total_tokens=avg("tool_total_tokens"),
            avg_tool_duration=avg("tool_duration"),
            avg_tool_duration_norm=avg("tool_duration_norm"),
            avg_llm_calls=avg("llm_calls"),
            avg_llm_fails=avg("llm_fails"),
            avg_llm_total_tokens=avg("llm_total_tokens"),
            avg_llm_input_tokens=avg("llm_input_tokens"),
            avg_llm_output_tokens=avg("llm_output_tokens"),
            avg_llm_duration=avg("llm_duration"),
            avg_llm_duration_norm=avg("llm_duration_norm"),
            avg_graph_determinism=avg("graph_determinism"),
            avg_graph_dynamism=avg("graph_dynamism"),
            avg_total_tokens=avg("total_tokens"),
            avg_latency=avg("latency"),
            agents=agents,
            avg_completion=avg("completion"),
        )

    def _build_histogram_stats(
        self,
        session_metrics: List[Dict],
        agent_metrics: Dict[str, List[Dict]],
        all_agent_names: Set[str],
    ) -> SessionSetStatsHistogram:
        """Build histogram statistics from session metrics."""
        if not session_metrics:
            return SessionSetStatsHistogram()

        # Session-level histograms
        def extract_values(key: str) -> List:
            return [m[key] for m in session_metrics]

        # Agent-level histograms
        agents = {}
        for agent_name in all_agent_names:
            metrics_list = agent_metrics.get(agent_name, [])
            if metrics_list:
                # Ensure we have the same number of values as sessions
                # Fill missing values with 0
                agent_values = {
                    "tool_calls": [],
                    "tool_fails": [],
                    "tool_total_tokens": [],
                    "tool_duration": [],
                    "llm_calls": [],
                    "llm_fails": [],
                    "llm_total_tokens": [],
                    "llm_input_tokens": [],
                    "llm_output_tokens": [],
                    "llm_duration": [],
                    "duration": [],
                    "completion": [],
                }

                # Map agent metrics to session order
                for i, _ in enumerate(session_metrics):
                    if i < len(metrics_list):
                        m = metrics_list[i]
                        for key in agent_values:
                            agent_values[key].append(m[key])
                    else:
                        # Fill missing sessions with 0
                        for key in agent_values:
                            agent_values[key].append(
                                0 if "duration" not in key else 0.0
                            )

                agents[agent_name] = SessionSetAgentHistogramStats(
                    tool_calls=agent_values["tool_calls"],
                    tool_fails=agent_values["tool_fails"],
                    tool_total_tokens=agent_values["tool_total_tokens"],
                    tool_duration=agent_values["tool_duration"],
                    llm_calls=agent_values["llm_calls"],
                    llm_fails=agent_values["llm_fails"],
                    llm_total_tokens=agent_values["llm_total_tokens"],
                    llm_input_tokens=agent_values["llm_input_tokens"],
                    llm_output_tokens=agent_values["llm_output_tokens"],
                    llm_duration=agent_values["llm_duration"],
                    duration=agent_values["duration"],
                    completion=agent_values["completion"],
                )

        return SessionSetStatsHistogram(
            tool_calls=extract_values("tool_calls"),
            tool_fails=extract_values("tool_fails"),
            tool_total_tokens=extract_values("tool_total_tokens"),
            tool_duration=extract_values("tool_duration"),
            llm_calls=extract_values("llm_calls"),
            llm_fails=extract_values("llm_fails"),
            llm_total_tokens=extract_values("llm_total_tokens"),
            llm_input_tokens=extract_values("llm_input_tokens"),
            llm_output_tokens=extract_values("llm_output_tokens"),
            llm_duration=extract_values("llm_duration"),
            graph_determinism=extract_values("graph_determinism"),
            graph_dynamism=extract_values("graph_dynamism"),
            total_tokens=extract_values("total_tokens"),
            latency=extract_values("latency"),
            accuracy=[],  # Empty for now, will be implemented later
            agents=agents,
            completion=extract_values("completion"),
        )

    def _extract_uuid_and_app_name(self, session_id: str) -> tuple[str, str]:
        """
        Extract UUID and app name from session_id with format: <app_name>_<uuid>

        Args:
            session_id: Session ID in format like "noa-moderator_4d798de1-e517-49f9-9a77-9f86a314d6b7"

        Returns:
            Tuple of (uuid, app_name)
        """
        if "_" in session_id:
            # Split on the last underscore to handle app names with underscores
            parts = session_id.rsplit("_", 1)
            if len(parts) == 2:
                app_name, uuid_part = parts
                return uuid_part, app_name

        # Fallback if format doesn't match expected pattern
        return session_id, "unknown-app"

    def invalidate_stats_cache(self) -> None:
        """
        Manually invalidate the stats cache.
        Call this if you modify sessions in-place.
        """
        self._cached_stats = None
        self._cache_hash = None

    def add_session(self, session: SessionEntity) -> None:
        """
        Add a session to the set and invalidate cache.

        Args:
            session: The session to add
        """
        self.sessions.append(session)
        self.invalidate_stats_cache()

    def remove_session(self, session_id: str) -> bool:
        """
        Remove a session by ID and invalidate cache.

        Args:
            session_id: The ID of the session to remove

        Returns:
            True if session was found and removed, False otherwise
        """
        for i, session in enumerate(self.sessions):
            if session.session_id == session_id:
                self.sessions.pop(i)
                self.invalidate_stats_cache()
                return True
        return False
