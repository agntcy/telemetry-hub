# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Type definitions for the entities package.
"""

from typing import Union, List, Dict
from .models.span import SpanEntity

# Type alias for data that can be processed by transformers
SpanDataType = Union[SpanEntity, List[SpanEntity], Dict[str, List[SpanEntity]]]
