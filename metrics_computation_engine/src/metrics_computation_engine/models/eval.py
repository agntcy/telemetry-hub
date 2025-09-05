# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


@dataclass
class MetricResult:
    """Result of a metric computation"""

    metric_name: str
    description: str
    value: Union[float, int, str, Dict[str, Any]]
    reasoning: str
    unit: str
    aggregation_level: str
    span_id: List[str]
    session_id: List[str]
    source: str
    entities_involved: List[str]
    edges_involved: List[str]
    success: bool
    metadata: Dict[str, Any]
    # timestamp: datetime
    error_message: Optional[str] = None


class BinaryGrading(BaseModel):
    """
    A Pydantic model for grading responses based on a specific scoring rubric.

    Attributes:
    -----------
    feedback : str
        Detailed feedback that assesses the quality of the response based on the given score rubric.
        The feedback should leverage on CoT reasoning.

    score : int
        The final evaluation as a score of 0 or 1.
    """

    score_reasoning: str = Field(
        title="Feedback",
        description="""Provide concise feedback on all responses at once (≤100 words) assessing quality per the rubric. """,
    )
    metric_score: int = Field(
        title="Score",
        description="""Provide the final evaluation as a score of 1 or 0. You should strictly refer to the given score rubric.""",
        ge=0,
        le=1,
    )
