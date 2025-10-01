from typing import Literal, List, Union, Dict

# Import SpanEntity for type definitions
from .entities.models.span import SpanEntity

AggregationLevel = Literal["span", "session", "population"]

# Data type definitions for transformers
SpanListType = List[SpanEntity]
SpanDataType = Union[SpanEntity, SpanListType, Dict[str, SpanListType]]
