"""Shared constants for metrics computation engine."""

from __future__ import annotations
from typing import Dict


# Base mapping of BinaryGrading metric scores to human-readable labels. Include
# both first-party metrics and supported third-party adapters.
BINARY_GRADING_LABELS: Dict[str, Dict[int, str]] = {
    "ComponentConflictRate": {0: "not_conflicted", 1: "conflicted"},
    "Consistency": {0: "not_consistent", 1: "consistent"},
    "ContextPreservation": {0: "context_not_preserved", 1: "context_preserved"},
    "GoalSuccessRate": {0: "goal_not_achieved", 1: "goal_achieved"},
    "Groundedness": {0: "not_grounded", 1: "grounded"},
    "InformationRetention": {0: "information_not_retained", 1: "information_retained"},
    "IntentRecognitionAccuracy": {0: "intent_not_recognized", 1: "intent_recognized"},
    "ResponseCompleteness": {0: "response_not_complete", 1: "response_complete"},
    "WorkflowCohesionIndex": {0: "workflow_not_cohesive", 1: "workflow_cohesive"},
    "TaskDelegationAccuracy": {0: "delegation_not_accurate", 1: "delegation_accurate"},
    "ToolUtilizationAccuracy": {0: "tool_usage_incorrect", 1: "tool_usage_correct"},
    "Hallucination": {0: "not_hallucinated", 1: "hallucinated"},
    "AnswerRelevancyMetric": {0: "not_relevant", 1: "relevant"},
    "RoleAdherenceMetric": {0: "role_not_adherent", 1: "role_adherent"},
    "TaskCompletionMetric": {0: "task_not_completed", 1: "task_completed"},
    "ConversationCompletenessMetric": {
        0: "conversation_not_complete",
        1: "conversation_complete",
    },
    "BiasMetric": {0: "not_biased", 1: "biased"},
    "GroundednessMetric": {0: "not_grounded", 1: "grounded"},
    "TonalityMetric": {0: "tone_not_aligned", 1: "tone_aligned"},
    "ToxicityMetric": {0: "not_toxic", 1: "toxic"},
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

__all__ = ["BINARY_GRADING_LABELS", "DEEPEVAL_METRICS"]
