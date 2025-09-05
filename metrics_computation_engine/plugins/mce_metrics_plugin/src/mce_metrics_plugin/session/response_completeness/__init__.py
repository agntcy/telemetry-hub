"""
Intent Recognition Accuracy Plugin
A metric plugin that scores the accuracy of intent recognition from an LLM Agent
"""

from .response_completeness import ResponseCompleteness

__version__ = "0.1.0"
__all__ = ["ResponseCompleteness"]
