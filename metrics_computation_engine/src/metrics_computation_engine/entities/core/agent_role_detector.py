# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Agent Role Detector - Behavioral analysis for agent role classification

This module provides application-agnostic agent role detection based on behavioral patterns.
It's designed to be computed once per agent and reused across multiple metrics to avoid
redundant analysis.

Detects functional roles:
- Coordinators: Task routing, workflow management, delegation
- Processors: Information processing, computation, tool usage
- Mixed: Agents with both coordination and processing responsibilities
- Unknown: Unclear patterns (conservative default)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class AgentBehavior:
    """Encapsulates behavioral characteristics of an agent"""

    agent_name: str
    total_spans: int
    llm_calls: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    tools_used: List[str]
    conversation_length: int
    coordination_signals: int
    processing_signals: int
    json_signals: int
    assistant_responses: int
    avg_response_length: float
    short_response_ratio: float


@dataclass
class AgentRoleAnalysis:
    """Complete role analysis result for an agent"""

    agent_name: str
    behavior: AgentBehavior
    detected_role: str  # 'coordinator', 'processor', 'mixed', 'unknown'
    coordinator_score: int
    processor_score: int
    confidence: float
    analysis_timestamp: Optional[str] = None


@dataclass
class AgentFilterMetadata:
    """Structured metadata returned by agent role filtering decisions"""

    filtering_enabled: bool
    detected_role: str
    skip_reason: str
    analysis_failed: bool = False
    coordinator_score: Optional[int] = None
    processor_score: Optional[int] = None
    confidence: Optional[float] = None
    tool_calls: Optional[int] = None
    coordination_signals: Optional[int] = None
    processing_signals: Optional[int] = None

    def __getitem__(self, key: str):
        """Support dictionary-style access for backward compatibility"""
        return getattr(self, key, None)

    def get(self, key: str, default=None):
        """Support dict.get() method for backward compatibility"""
        return getattr(self, key, default)

    def to_dict(self) -> Dict:
        """Convert to dict for backward compatibility"""
        return {
            "filtering_enabled": self.filtering_enabled,
            "detected_role": self.detected_role,
            "skip_reason": self.skip_reason,
            "analysis_failed": self.analysis_failed,
            "coordinator_score": self.coordinator_score,
            "processor_score": self.processor_score,
            "confidence": self.confidence,
            "tool_calls": self.tool_calls,
            "coordination_signals": self.coordination_signals,
            "processing_signals": self.processing_signals,
        }


class AgentRoleDetector:
    """
    Detects functional agent roles based on behavioral analysis.

    This class is designed to be used as a singleton or cached instance
    to avoid redundant computation of role analysis across metrics.
    """

    # Pattern definitions for role detection
    COORDINATION_PATTERNS = [
        "next",
        "finish",
        "delegate",
        "route",
        "assign",
        "worker",
        "task",
        "supervisor",
        "coordinator",
        "orchestrator",
        "manager",
        "dispatch",
        "workflow",
        "control",
        "manage",
    ]

    PROCESSING_PATTERNS = [
        "calculate",
        "compute",
        "analyze",
        "process",
        "research",
        "find",
        "search",
        "generate",
        "create",
        "write",
        "code",
        "execute",
        "run",
        "solve",
        "build",
        "implement",
        "develop",
    ]

    JSON_PATTERNS = ["{", "}", '"next"', '"finish"', '"action"', '"response"']

    COMPUTATIONAL_TOOL_KEYWORDS = [
        "repl",
        "python",
        "code",
        "execute",
        "compute",
        "calculator",
        "terminal",
        "bash",
        "shell",
        "sql",
        "database",
    ]

    def __init__(self):
        # Cache for role analyses to avoid recomputation
        self._role_cache: Dict[str, AgentRoleAnalysis] = {}

    def analyze_agent_behavior(
        self, session, agent_name: str
    ) -> Optional[AgentBehavior]:
        """
        Analyze an agent's behavioral patterns from session data.

        Args:
            session: SessionEntity containing the agent's activity
            agent_name: Name of the agent to analyze

        Returns:
            AgentBehavior object or None if agent not found
        """
        agent_stats = session.agent_stats.get(agent_name)
        if not agent_stats:
            logger.warning(f"No stats found for agent: {agent_name}")
            return None

        try:
            # Get basic stats
            agent_spans = session._get_spans_for_agent(agent_name)
            conversation = session.get_agent_conversation_text(agent_name)

            # Analyze conversation patterns
            conversation_lower = conversation.lower()

            coordination_signals = sum(
                1
                for pattern in self.COORDINATION_PATTERNS
                if pattern in conversation_lower
            )
            processing_signals = sum(
                1
                for pattern in self.PROCESSING_PATTERNS
                if pattern in conversation_lower
            )
            json_signals = sum(
                1 for pattern in self.JSON_PATTERNS if pattern in conversation
            )

            # Response analysis
            lines = [line.strip() for line in conversation.split("\n") if line.strip()]
            assistant_responses = [
                line for line in lines if line.startswith("Assistant:")
            ]

            avg_response_length = (
                sum(len(resp) for resp in assistant_responses)
                / len(assistant_responses)
                if assistant_responses
                else 0
            )

            short_responses = sum(1 for resp in assistant_responses if len(resp) < 100)
            short_response_ratio = (
                short_responses / len(assistant_responses) if assistant_responses else 0
            )

            return AgentBehavior(
                agent_name=agent_name,
                total_spans=len(agent_spans),
                llm_calls=agent_stats.total_llm_calls,
                tool_calls=agent_stats.total_tool_calls,
                input_tokens=agent_stats.llm_input_tokens,
                output_tokens=agent_stats.llm_output_tokens,
                tools_used=agent_stats.unique_tool_names,
                conversation_length=len(conversation),
                coordination_signals=coordination_signals,
                processing_signals=processing_signals,
                json_signals=json_signals,
                assistant_responses=len(assistant_responses),
                avg_response_length=avg_response_length,
                short_response_ratio=short_response_ratio,
            )

        except Exception as e:
            import traceback

            logger.error(f"Error analyzing behavior for agent {agent_name}: {str(e)}")
            logger.error(f"Full traceback in role detector:\n{traceback.format_exc()}")

            logger.error("=== ROLE DETECTOR ERROR DEBUG ===")
            logger.error(f"Agent: {agent_name}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            logger.error("=================================")

            return None

    def classify_agent_role(
        self, behavior: AgentBehavior
    ) -> Tuple[str, Dict[str, int]]:
        """
        Classify agent role based on behavioral analysis.

        Args:
            behavior: AgentBehavior object with analyzed patterns

        Returns:
            Tuple of (role, scores_dict) where role is one of:
            'coordinator', 'processor', 'mixed', 'unknown'
        """
        coordinator_score = 0
        processor_score = 0

        # Strong processor indicators (tool usage is decisive)
        if behavior.tool_calls > 0:
            processor_score += 4

        # Check for computational tools (strong processor signal)
        computational_tools = any(
            keyword in tool.lower()
            for tool in behavior.tools_used
            for keyword in self.COMPUTATIONAL_TOOL_KEYWORDS
        )
        if computational_tools:
            processor_score += 3

        # Coordination indicators
        if behavior.coordination_signals >= 3:
            coordinator_score += 3
        elif behavior.coordination_signals >= 1:
            coordinator_score += 1

        # Short responses with no tools suggest coordination role
        if (
            behavior.short_response_ratio > 0.8
            and behavior.tool_calls == 0
            and behavior.coordination_signals >= 2
        ):
            coordinator_score += 3

        # Processing indicators
        if behavior.processing_signals >= 3:
            processor_score += 2
        elif behavior.processing_signals >= 1:
            processor_score += 1

        # Response complexity suggests information processing
        if behavior.avg_response_length > 200:
            processor_score += 2
        elif behavior.avg_response_length > 100:
            processor_score += 1

        # Token usage patterns (high output suggests content generation)
        if behavior.output_tokens > behavior.input_tokens:
            processor_score += 1

        scores = {
            "coordinator_score": coordinator_score,
            "processor_score": processor_score,
        }

        # Classification logic
        if processor_score >= 4 and processor_score > coordinator_score:
            return "processor", scores
        elif coordinator_score >= 4 and coordinator_score > processor_score:
            return "coordinator", scores
        elif abs(coordinator_score - processor_score) <= 1:
            return "mixed", scores
        else:
            return "unknown", scores

    def get_agent_role_analysis(
        self, session, agent_name: str, use_cache: bool = True
    ) -> Optional[AgentRoleAnalysis]:
        """
        Get complete role analysis for an agent, with caching support.

        Args:
            session: SessionEntity containing the agent's activity
            agent_name: Name of the agent to analyze
            use_cache: Whether to use cached results if available

        Returns:
            AgentRoleAnalysis object or None if analysis fails
        """
        # Create cache key based on session and agent
        cache_key = f"{session.session_id}_{agent_name}"

        # Return cached result if available and requested
        if use_cache and cache_key in self._role_cache:
            logger.debug(f"Using cached role analysis for agent: {agent_name}")
            return self._role_cache[cache_key]

        # Perform analysis
        behavior = self.analyze_agent_behavior(session, agent_name)
        if not behavior:
            return None

        role, scores = self.classify_agent_role(behavior)

        # Calculate confidence based on score difference
        total_score = scores["coordinator_score"] + scores["processor_score"]
        score_diff = abs(scores["coordinator_score"] - scores["processor_score"])
        confidence = score_diff / max(total_score, 1.0) if total_score > 0 else 0.0

        analysis = AgentRoleAnalysis(
            agent_name=agent_name,
            behavior=behavior,
            detected_role=role,
            coordinator_score=scores["coordinator_score"],
            processor_score=scores["processor_score"],
            confidence=confidence,
        )

        # Cache the result
        if use_cache:
            self._role_cache[cache_key] = analysis
            logger.debug(f"Cached role analysis for agent: {agent_name}")

        return analysis

    def should_skip_coordinator_agent(
        self, analysis: AgentRoleAnalysis
    ) -> Tuple[bool, str]:
        """
        Determine if a coordinator agent should be skipped for metrics that focus on information processing.

        Args:
            analysis: AgentRoleAnalysis object

        Returns:
            Tuple of (should_skip: bool, reason: str)
        """
        role = analysis.detected_role
        behavior = analysis.behavior

        if role == "coordinator":
            return (
                True,
                "Coordinator agents focus on task routing/workflow management, not information processing",
            )

        if role == "processor":
            return False, "Processor agents handle information and should be evaluated"

        if role == "mixed":
            # For mixed agents, check processing activity level
            processing_activity = (
                behavior.processing_signals >= 2
                or behavior.tool_calls >= 2
                or behavior.avg_response_length >= 150
            )
            if processing_activity:
                return False, "Mixed agent with significant processing activity"
            else:
                return (
                    True,
                    "Mixed agent with minimal processing activity (coordination-focused)",
                )

        # For unknown role, default to not skipping (conservative approach)
        return False, "Unknown role - evaluating conservatively"

    def clear_cache(self):
        """Clear the role analysis cache"""
        self._role_cache.clear()
        logger.debug("Cleared agent role analysis cache")


# Global instance for reuse across metrics
_global_detector = None


def get_agent_role_detector() -> AgentRoleDetector:
    """
    Get the global agent role detector instance.

    This ensures role analysis is computed once per agent per session
    and reused across multiple metrics.
    """
    global _global_detector
    if _global_detector is None:
        _global_detector = AgentRoleDetector()
    return _global_detector


def get_agent_role_and_skip_decision(
    session, agent_name: str, filter_coordinators: bool = True, use_cache: bool = True
) -> Tuple[bool, AgentFilterMetadata]:
    """
    Convenience function to get role classification and skip decision for coordinator filtering.

    Args:
        session: SessionEntity
        agent_name: Name of the agent to analyze
        filter_coordinators: Whether to enable coordinator filtering
        use_cache: Whether to use cached role analysis

    Returns:
        Tuple of (should_skip_agent: bool, metadata: AgentFilterMetadata)
    """
    # If filtering is disabled, never skip
    if not filter_coordinators:
        return False, AgentFilterMetadata(
            filtering_enabled=False,
            detected_role="unknown",
            skip_reason="Coordinator filtering disabled",
        )

    detector = get_agent_role_detector()

    analysis = detector.get_agent_role_analysis(
        session, agent_name, use_cache=use_cache
    )
    if not analysis:
        return False, AgentFilterMetadata(
            filtering_enabled=True,
            detected_role="unknown",
            skip_reason="Could not analyze agent behavior - evaluating conservatively",
            analysis_failed=True,
        )

    should_skip, reason = detector.should_skip_coordinator_agent(analysis)

    metadata = AgentFilterMetadata(
        filtering_enabled=True,
        detected_role=analysis.detected_role,
        coordinator_score=analysis.coordinator_score,
        processor_score=analysis.processor_score,
        confidence=analysis.confidence,
        skip_reason=reason,
        tool_calls=analysis.behavior.tool_calls,
        coordination_signals=analysis.behavior.coordination_signals,
        processing_signals=analysis.behavior.processing_signals,
        analysis_failed=False,
    )

    return should_skip, metadata
