# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Base classes for data transformers and pipelines.

This module provides the foundational infrastructure for the pipeline pattern
with data preservation to ensure original data remains accessible.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Dict


class DataTransformer(ABC):
    """Base class for data transformers in pipeline processing."""

    @abstractmethod
    def transform(self, data: Any) -> Any:
        """Transform the input data and return the transformed result."""
        pass


class DataPreservingTransformer(DataTransformer):
    """
    Base class that preserves original data by default.

    This transformer ensures that original data is always available
    to subsequent transformers in the pipeline.
    """

    def transform(self, data):
        if isinstance(data, dict) and "original_data" in data:
            # Already structured - preserve everything
            result = data.copy()
            extracted = self.extract(data)
            if extracted and isinstance(extracted, dict):
                result.update(extracted)
            return result
        else:
            # First transformation - create structure
            extracted = self.extract(data)
            if extracted and isinstance(extracted, dict):
                return {
                    "original_data": data,  # Preserve original
                    **extracted,
                }
            else:
                return {"original_data": data}

    @abstractmethod
    def extract(self, data) -> Dict[str, Any]:
        """Override this method instead of transform to implement extraction logic."""
        pass


class DataPipeline:
    """
    Pipeline that processes data through a sequence of transformers.

    Each transformer in the pipeline receives the output of the previous
    transformer and produces input for the next one.
    """

    def __init__(self, transformers: List[DataTransformer]):
        self.transformers = transformers
        self._validate_pipeline()

    def _validate_pipeline(self):
        """Basic validation that pipeline has transformers."""
        if not self.transformers:
            raise ValueError("Pipeline must have at least one transformer")

    def process(self, data):
        """Process data through all transformers in sequence."""
        result = data
        for transformer in self.transformers:
            result = transformer.transform(result)
        return result

    def add_transformer(self, transformer: DataTransformer):
        """Add a transformer to the end of the pipeline."""
        self.transformers.append(transformer)
        return self

    def insert_transformer(self, index: int, transformer: DataTransformer):
        """Insert a transformer at a specific position in the pipeline."""
        self.transformers.insert(index, transformer)
        return self
