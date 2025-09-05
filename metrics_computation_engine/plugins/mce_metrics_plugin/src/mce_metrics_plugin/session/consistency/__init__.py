"""
Groundedness Plugin
A metric plugin that scores the groundedness from an LLM Agent
"""

from .consistency import Consistency

__version__ = "0.1.0"
__all__ = ["Consistency"]
