# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Dict, List, Optional

from mce_ragas_adapter.metric_test_case_creation import (
    AbstractTestCaseCalculator,
    RagasMultiTurnTestCase,
)
from pydantic import BaseModel, ConfigDict, Field

from metrics_computation_engine.types import AggregationLevel


class MetricRequirements(BaseModel):
    entity_type: List[str]
    aggregation_level: AggregationLevel
    required_input_parameters: List[str]


class MetricConfiguration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    metric_name: str
    test_case_calculator: AbstractTestCaseCalculator
    requirements: MetricRequirements
    metric_class_arguments: Optional[Dict[str, Any]] = Field(default=None)
    mode_support: Optional[List[str]] = Field(default=None)  # For precision/recall/f1


def build_metric_configuration_map() -> Dict[str, MetricConfiguration]:
    confs: List[MetricConfiguration] = build_metric_configurations()
    return {conf.metric_name: conf for conf in confs}


def build_metric_configurations() -> List[MetricConfiguration]:
    return [
        MetricConfiguration(
            metric_name="TopicAdherenceScore",
            test_case_calculator=RagasMultiTurnTestCase(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="session",
                required_input_parameters=["conversation_elements"],
            ),
            mode_support=["precision", "recall", "f1"],
        ),
        # Future RAGAS metrics can be added here following the same pattern
        # When adding single-turn metrics, create a new test case calculator class
    ]
