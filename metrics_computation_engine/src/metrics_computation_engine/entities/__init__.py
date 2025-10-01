# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Entities package for OpenTelemetry trace inspection.

This package provides data models and processing logic for inspecting
and analyzing OpenTelemetry traces with session-based aggregation.
"""

# Import these modules only when specifically needed to avoid circular imports
# from .models.span import SpanEntity
# from .models.session import SessionEntity
# from .models.session_set import SessionSet
# from .core.data_parser import parse_raw_spans
# from .core.session_aggregator import SessionAggregator
# from .transformers.session_enrichers import (
#     ConversationDataTransformer,
#     WorkflowDataTransformer,
#     ToolUsageTransformer,
#     SessionEnrichmentPipeline
# )

__all__ = [
    "SpanEntity",
    "SessionEntity",
    "SessionSet",
    "parse_raw_spans",
    "SessionAggregator",
    "ConversationDataTransformer",
    "WorkflowDataTransformer",
    "ToolUsageTransformer",
    "SessionEnrichmentPipeline",
]
