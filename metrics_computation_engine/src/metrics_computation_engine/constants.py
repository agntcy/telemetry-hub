"""Shared constants for metrics computation engine."""

from __future__ import annotations
from typing import Dict


# Base mapping of BinaryGrading metric scores to human-readable labels. Include
# both first-party metrics and supported third-party adapters.
BINARY_GRADING_LABELS: Dict[str, Dict[int, str]] = {
    "ComponentConflictRate": {0: "conflict_detected", 1: "conflict_free"},
    "Consistency": {0: "inconsistent", 1: "consistent"},
    "ContextPreservation": {0: "context_not_preserved", 1: "context_preserved"},
    "GoalSuccessRate": {0: "goal_failed", 1: "goal_achieved"},
    "Groundedness": {0: "not_grounded", 1: "grounded"},
    "InformationRetention": {0: "information_lost", 1: "information_retained"},
    "IntentRecognitionAccuracy": {0: "intent_missed", 1: "intent_recognized"},
    "ResponseCompleteness": {0: "response_incomplete", 1: "response_complete"},
    "WorkflowCohesionIndex": {0: "workflow_fragmented", 1: "workflow_cohesive"},
    "TaskDelegationAccuracy": {0: "delegation_inaccurate", 1: "delegation_accurate"},
    "ToolUtilizationAccuracy": {0: "tool_usage_incorrect", 1: "tool_usage_correct"},
    "Hallucination": {0: "no_hallucination_detected", 1: "hallucination_detected"},
    "AnswerRelevancyMetric": {0: "answer_irrelevant", 1: "answer_relevant"},
    "RoleAdherenceMetric": {0: "role_deviation", 1: "role_adherent"},
    "TaskCompletionMetric": {0: "task_incomplete", 1: "task_completed"},
    "ConversationCompletenessMetric": {
        0: "conversation_incomplete",
        1: "conversation_complete",
    },
    "BiasMetric": {0: "not_bias", 1: "bias_detected"},
    "GroundednessMetric": {0: "not_grounded", 1: "grounded"},
    "TonalityMetric": {0: "tone_mismatch", 1: "tone_aligned"},
    "ToxicityMetric": {0: "non_toxic", 1: "toxic"},
    "GeneralStructureAndStyleMetric": {
        0: "structure_not_met",
        1: "structure_met",
    },
}


# TODO: not sure if this will be needed in the future
# _BINARY_GRADING_PROVIDER_ALIASES: Dict[str, list[str]] = {
#     "Hallucination": ["opik.Hallucination"],
#     "AnswerRelevancyMetric": ["deepeval.AnswerRelevancyMetric"],
#     "RoleAdherenceMetric": ["deepeval.RoleAdherenceMetric"],
#     "TaskCompletionMetric": ["deepeval.TaskCompletionMetric"],
#     "ConversationCompletenessMetric": ["deepeval.ConversationCompletenessMetric"],
#     "BiasMetric": ["deepeval.BiasMetric"],
#     "GroundednessMetric": ["deepeval.GroundednessMetric"],
#     "TonalityMetric": ["deepeval.TonalityMetric"],
#     "ToxicityMetric": ["deepeval.ToxicityMetric"],
#     "GeneralStructureAndStyleMetric": ["deepeval.GeneralStructureAndStyleMetric"],
# }


DEEPEVAL_METRICS = [
    "AnswerRelevancyMetric",
    "RoleAdherenceMetric",
    "TaskCompletionMetric",
    "ConversationCompletenessMetric",
    "BiasMetric",
    "GroundednessMetric",
    "TonalityMetric",
    "ToxicityMetric",
    "GeneralStructureAndStyleMetric",
]

__all__ = [
    "BINARY_GRADING_LABELS",
    "DEEPEVAL_METRICS"
]
