# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
from typing import Any, Dict, List, Optional, Type, Union

from deepeval.metrics import AnswerRelevancyMetric
from deepeval.metrics import (
    BaseConversationalMetric as DeepEvalBaseConversationalMetric,
)
from deepeval.metrics import BaseMetric as DeepEvalBaseMetric
from deepeval.metrics import (
    BiasMetric,
    ConversationCompletenessMetric,
    GEval,
    RoleAdherenceMetric,
    TaskCompletionMetric,
    ToxicityMetric,
)
from deepeval.test_case import LLMTestCaseParams
from mce_deepeval_adapter.geval_criteria import (
    COHERENCE_CRITERIA,
    CRITERIA_CORRECTNESS,
    CRITERIA_GENERAL_STRUCTURE,
    EVALUATION_STEPS_GROUNDEDNESS,
    EVALUATION_STEPS_TONALITY,
)
from mce_deepeval_adapter.metric_test_case_creation import (
    AbstractTestCaseCalculator,
    DeepEvalTestCaseConversational,
    DeepEvalTestCaseLLM,
    DeepEvalTestCaseLLMWithTools,
    LLMAnswerCorrectnessTestCase,
    LLMGeneralStructureAndStyleTestCase,
    LLMAnswerRelevancyTestCase,
)
from pydantic import BaseModel, ConfigDict, Field

from metrics_computation_engine.types import AggregationLevel


SPAN_ENTITY_TYPE_ALLOWLIST_ENV = "MCE_SPAN_METRIC_ENTITY_TYPE_ALLOWLIST"
_SUPPORTED_SPAN_ENTITY_TYPES = {"llm", "agent", "workflow", "tool", "graph", "task"}
_ALLOWLIST_ENABLED_METRICS = {
    AnswerRelevancyMetric.__name__,
    BiasMetric.__name__,
    ToxicityMetric.__name__,
}


def _entity_types_for(metric_name: str, default: List[str]) -> List[str]:
    """Resolve entity types for selected span metrics from env allowlist."""
    if metric_name not in _ALLOWLIST_ENABLED_METRICS:
        return default

    raw_allowlist = os.getenv(SPAN_ENTITY_TYPE_ALLOWLIST_ENV, "").strip()
    if not raw_allowlist:
        return default

    parsed = [item.strip().lower() for item in raw_allowlist.split(",") if item.strip()]
    parsed = [item for item in parsed if item in _SUPPORTED_SPAN_ENTITY_TYPES]
    return parsed or default


class MetricRequirements(BaseModel):
    entity_type: List[str]
    aggregation_level: AggregationLevel
    required_input_parameters: List[str]


class MetricConfiguration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    metric_name: str
    test_case_calculator: AbstractTestCaseCalculator
    requirements: MetricRequirements
    metric_class: Union[
        Type[DeepEvalBaseMetric], Type[DeepEvalBaseConversationalMetric]
    ]
    metric_class_arguments: Optional[Dict[str, Any]] = Field(default=None)


def build_metric_configuration_map() -> Dict[str, MetricConfiguration]:
    confs: List[MetricConfiguration] = build_metric_configurations()
    return {conf.metric_name: conf for conf in confs}


def build_metric_configurations() -> List[MetricConfiguration]:
    return [
        MetricConfiguration(
            metric_name=AnswerRelevancyMetric.__name__,
            test_case_calculator=LLMAnswerRelevancyTestCase(),
            requirements=MetricRequirements(
                entity_type=_entity_types_for(AnswerRelevancyMetric.__name__, ["llm"]),
                aggregation_level="span",
                required_input_parameters=["input_query", "final_response"],
            ),
            metric_class=AnswerRelevancyMetric,
        ),
        MetricConfiguration(
            metric_name=RoleAdherenceMetric.__name__,
            test_case_calculator=DeepEvalTestCaseConversational(),
            requirements=MetricRequirements(
                entity_type=["llm", "tool"],
                aggregation_level="session",
                required_input_parameters=["conversation_elements"],
            ),
            metric_class=RoleAdherenceMetric,
        ),
        MetricConfiguration(
            metric_name=TaskCompletionMetric.__name__,
            test_case_calculator=DeepEvalTestCaseLLMWithTools(),
            requirements=MetricRequirements(
                entity_type=["llm", "tool"],
                aggregation_level="session",
                required_input_parameters=["tool_calls, input_query, final_response"],
            ),
            metric_class=TaskCompletionMetric,
        ),
        MetricConfiguration(
            metric_name=ConversationCompletenessMetric.__name__,
            test_case_calculator=DeepEvalTestCaseConversational(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="session",
                required_input_parameters=["conversation_elements"],
            ),
            metric_class=ConversationCompletenessMetric,
        ),
        MetricConfiguration(
            metric_name=BiasMetric.__name__,
            test_case_calculator=DeepEvalTestCaseLLM(),
            requirements=MetricRequirements(
                entity_type=_entity_types_for(BiasMetric.__name__, ["llm"]),
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
            metric_class=BiasMetric,
        ),
        MetricConfiguration(
            metric_name="CoherenceMetric",
            test_case_calculator=DeepEvalTestCaseLLM(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
            metric_class=GEval,
            metric_class_arguments=dict(
                name="Coherence",
                criteria=COHERENCE_CRITERIA,
                evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            ),
        ),
        MetricConfiguration(
            metric_name="GroundednessMetric",
            test_case_calculator=DeepEvalTestCaseLLM(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
            metric_class=GEval,
            metric_class_arguments=dict(
                name="Groundedness",
                evaluation_steps=EVALUATION_STEPS_GROUNDEDNESS,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
            ),
        ),
        MetricConfiguration(
            metric_name="TonalityMetric",
            test_case_calculator=DeepEvalTestCaseLLM(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
            metric_class=GEval,
            metric_class_arguments=dict(
                name="Tonality",
                evaluation_steps=EVALUATION_STEPS_TONALITY,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
            ),
        ),
        MetricConfiguration(
            metric_name=ToxicityMetric.__name__,
            test_case_calculator=DeepEvalTestCaseLLM(),
            requirements=MetricRequirements(
                entity_type=_entity_types_for(ToxicityMetric.__name__, ["llm"]),
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
            metric_class=ToxicityMetric,
        ),
        MetricConfiguration(
            metric_name="AnswerCorrectnessMetric",
            test_case_calculator=LLMAnswerCorrectnessTestCase(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
            metric_class=GEval,
            metric_class_arguments=dict(
                name="AnswerCorrectness",
                criteria=CRITERIA_CORRECTNESS,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                    LLMTestCaseParams.EXPECTED_OUTPUT,
                ],
            ),
        ),
        MetricConfiguration(
            metric_name="GeneralStructureAndStyleMetric",
            test_case_calculator=LLMGeneralStructureAndStyleTestCase(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
            metric_class=GEval,
            metric_class_arguments=dict(
                name="GeneralStructureAndStyle",
                criteria=CRITERIA_GENERAL_STRUCTURE,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
            ),
        ),
    ]
