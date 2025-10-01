# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from itertools import combinations
from typing import List, Optional

import networkx as nx

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult


class TaskCompletionEfficiency(BaseMetric):
    """
    Collects the Agent to Agent Interactions counts throughout a trace.
    """

    def __init__(self, metric_name: Optional[str] = None):
        super().__init__()
        if metric_name is None:
            metric_name = self.__class__.__name__
        self.name = metric_name
        self.aggregation_level = "population"

    @property
    def required_parameters(self) -> List[str]:
        return ["Events.Attributes"]

    def validate_config(self) -> bool:
        return True

    def create_model(self, llm_config):
        return self.create_no_model()

    def get_model_provider(self):
        return self.get_provider_no_model_needed()

    def init_with_model(self, model) -> bool:
        return True

    async def compute(self, data):
        app_name = None
        if len(data.sessions) > 0:
            app_name = next(iter(data.sessions)).app_name

        try:
            graphs = []
            for eid in data.execution_id.unique():
                # TODO: Latency =
                pass

            nx_graphs = []
            for edges in graphs:
                G = nx.DiGraph()
                G.add_edges_from(edges)
                nx_graphs.append(G)

            # Calculate pairwise edit distances
            edit_distances = []
            for g1, g2 in combinations(nx_graphs, 2):
                # For small graphs, simple edge difference can work
                edges1 = set(g1.edges())
                edges2 = set(g2.edges())
                edit_distance = len(edges1.symmetric_difference(edges2))
                edit_distances.append(edit_distance)

            variance = -1
            error_message = None
            if edit_distances:
                variance = sum(edit_distances) / len(edit_distances)
            if len(edit_distances) == 0:
                error_message = "Not enough executions to compute variance."

            # TODO: MCE allows you to query multi sessions from multiple apps, we may want to constrain this OR allow population level metrics to list involved app_names
            return MetricResult(
                metric_name=self.name,
                description="",
                value=variance,
                unit="",
                aggregation_level=self.aggregation_level,
                category="application",
                source_name=app_name,
                span_id=[],
                session_id=list(data.execution_id.unique()),
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=True,
                metadata={},
                error_message=error_message,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="",
                value=-1,
                unit="",
                aggregation_level=self.aggregation_level,
                category="application",
                source_name=app_name,
                span_id="",
                session_id=list(data.execution_id.unique()),
                source="native",
                entities_involved=[],
                edges_involved=[],
                success=False,
                metadata={},
                error_message=e,
            )
