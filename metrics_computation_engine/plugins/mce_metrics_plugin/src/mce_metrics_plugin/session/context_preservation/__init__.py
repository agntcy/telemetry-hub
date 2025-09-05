"""
Groundedness Plugin
A metric plugin that scores the groundedness from an LLM Agent
"""

from .context_preservation import ContextPreservation

__version__ = "0.1.0"
__all__ = ["ContextPreservation"]
