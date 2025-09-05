"""
Intent Recognition Accuracy Plugin
A metric plugin that scores the accuracy of intent recognition from an LLM Agent
"""

from .workflow_cohesion_index import WorkflowCohesionIndex

__version__ = "0.1.0"
__all__ = ["WorkflowCohesionIndex"]
