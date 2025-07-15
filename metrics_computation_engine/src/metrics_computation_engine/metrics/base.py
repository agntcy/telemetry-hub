# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from metrics_computation_engine.llm_judge.jury import Jury


class BaseMetric(ABC):
    """Base class for generic metric"""

    def __init__(self, jury: Optional[Jury] = None, dataset: Optional[Dict] = None):
        self.jury = jury
        self.dataset = dataset

    @abstractmethod
    async def compute(self, data: Any):
        """Compute the metric for given data"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the plugin configuration"""
        pass

    @property
    @abstractmethod
    def required_parameters(self) -> List[str]:
        """Return list of required parameters for this metric"""
        pass
