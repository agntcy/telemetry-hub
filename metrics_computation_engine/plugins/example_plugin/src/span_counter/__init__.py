"""
Span Counter Plugin
A metric plugin that counts the number of spans in a session.
"""

from .span_counter import SpanCounter

__version__ = "0.1.0"
__all__ = ["SpanCounter"]
