from typing import Any, Dict, List, Optional

from mce_opik_adapter.metric_test_case_creation import (
    AbstractTestCaseCalculator,
    OpikHallucinationTestCase,
)
from pydantic import BaseModel, Field

from metrics_computation_engine.types import AggregationLevel


class MetricRequirements(BaseModel):
    entity_type: List[str]
    aggregation_level: AggregationLevel
    required_input_parameters: List[str]


class MetricConfiguration(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    metric_name: str
    test_case_calculator: AbstractTestCaseCalculator
    requirements: MetricRequirements
    metric_class_arguments: Optional[Dict[str, Any]] = Field(default=None)


def build_metric_configuration_map() -> Dict[str, MetricConfiguration]:
    confs: List[MetricConfiguration] = build_metric_configurations()
    return {conf.metric_name: conf for conf in confs}


def build_metric_configurations() -> List[MetricConfiguration]:
    return [
        MetricConfiguration(
            metric_name="Hallucination",
            test_case_calculator=OpikHallucinationTestCase(),
            requirements=MetricRequirements(
                entity_type=["llm"],
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
        )
    ]
