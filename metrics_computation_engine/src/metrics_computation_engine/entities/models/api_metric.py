# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Metric structure as used in DAL / API Layer.
"""

from pydantic import BaseModel
from typing import Dict


class ApiMetric(BaseModel):
    """
    Base class for API Layer Metric entity.
    """

    app_id: str
    app_name: str
    session_id: str
    metrics: Dict = {}
    span_id: str = None
    trace_id: str = None
