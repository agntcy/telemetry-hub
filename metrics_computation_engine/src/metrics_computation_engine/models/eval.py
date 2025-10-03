# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


@dataclass
class MetricResult:
    """Result of a metric computation"""

    metric_name: str
    value: Union[float, int, str, Dict[str, Any]]
    aggregation_level: str
    category: str
    app_name: str
    agent_id: Optional[str] = None
    description: str = ""
    reasoning: str = ""
    unit: str = ""
    span_id: List[str] = field(default_factory=list)
    session_id: List[str] = field(default_factory=list)
    source: str = ""
    entities_involved: List[str] = field(default_factory=list)
    edges_involved: List[str] = field(default_factory=list)
    success: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    # timestamp: datetime
    error_message: Optional[str] = None
    from_cache: bool = False


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
