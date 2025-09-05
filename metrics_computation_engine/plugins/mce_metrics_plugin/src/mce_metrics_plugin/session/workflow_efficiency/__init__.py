"""
Workflow Efficiency Plugin
A metric plugin that scores the accuracy of intent recognition from an LLM Agent
"""

from .workflow_efficiency import WorkflowEfficiency

__version__ = "0.1.0"
__all__ = ["WorkflowEfficiency"]
