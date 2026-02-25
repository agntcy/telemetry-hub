# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from mce_opik_adapter.metric_test_case_creation import (
    AbstractTestCaseCalculator,
    OpikHallucinationTestCase,
    OpikSpanTestCase,
)
from pydantic import BaseModel, ConfigDict, Field

from metrics_computation_engine.types import AggregationLevel


SPAN_ENTITY_TYPE_ALLOWLIST_ENV = "MCE_SPAN_METRIC_ENTITY_TYPE_ALLOWLIST"
_SUPPORTED_SPAN_ENTITY_TYPES = {"llm", "agent", "workflow", "tool", "graph", "task"}
_ALLOWLIST_ENABLED_METRICS = {"Hallucination", "Sentiment"}
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_configured_entity_types() -> List[str]:
    raw_allowlist = os.getenv(SPAN_ENTITY_TYPE_ALLOWLIST_ENV, "").strip()
    if not raw_allowlist:
        return []

    requested = [item.strip().lower() for item in raw_allowlist.split(",") if item.strip()]
    parsed = [item for item in requested if item in _SUPPORTED_SPAN_ENTITY_TYPES]
    dropped = sorted({item for item in requested if item not in _SUPPORTED_SPAN_ENTITY_TYPES})
    if dropped:
        logger.warning(
            "Ignoring unsupported values in %s: %s. Supported values: %s",
            SPAN_ENTITY_TYPE_ALLOWLIST_ENV,
            ", ".join(dropped),
            ", ".join(sorted(_SUPPORTED_SPAN_ENTITY_TYPES)),
        )

    return parsed


def _entity_types_for(metric_name: str, default: List[str]) -> List[str]:
    """Resolve entity types for selected span metrics from env allowlist."""
    if metric_name not in _ALLOWLIST_ENABLED_METRICS:
        return default

    parsed = _get_configured_entity_types()
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
                entity_type=_entity_types_for("Hallucination", ["llm"]),
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
        ),
        MetricConfiguration(
            metric_name="Sentiment",
            test_case_calculator=OpikSpanTestCase(),
            requirements=MetricRequirements(
                entity_type=_entity_types_for("Sentiment", ["llm"]),
                aggregation_level="span",
                required_input_parameters=["input_payload", "output_payload"],
            ),
        ),
    ]
