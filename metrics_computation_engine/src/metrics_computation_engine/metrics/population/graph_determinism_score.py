# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from itertools import combinations
from typing import List, Optional

import networkx as nx

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult


class GraphDeterminismScore(BaseMetric):
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
        print("DATA")
        print(len(data.values()))

        if len(data.values()) > 0:
            app_name = next(iter(data.values())).app_name
        try:
            graphs = []
            entities_involved = []
            for session_id, session_entity in data.items():
                filtered_events = []
                for span in session_entity.spans:
                    if span.entity_type in ["agent", "tool"]:
                        filtered_events.append(span.entity_name)
                        entities_involved.append(span.entity_name)
                edges = []
                for i in range(len(filtered_events) - 1):
                    edges.append((filtered_events[i], filtered_events[i + 1]))

                graphs.append(edges)

            # Create NetworkX graphs
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
            elif len(nx_graphs) < 2:
                error_message = "Not enough executions to compute variance (need at least 2 sessions)."
            else:
                error_message = "No valid graph transitions found in any session."

            # TODO: MCE allows you to query multi sessions from multiple apps, we may want to constrain this OR allow population level metrics to list involved app_names
            return MetricResult(
                metric_name=self.name,
                description="Measures variance in execution paths across sessions",
                value=variance,
                reasoning=f"Computed edit distance variance across {len(nx_graphs)} graphs with {len(edit_distances)} pairwise comparisons",
                unit="average_edit_distance",
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=app_name,
                span_id=[],
                session_id=list(data.keys()),
                source="native",
                entities_involved=list(set(entities_involved)),
                edges_involved=[],
                success=error_message is None,
                metadata={
                    "total_graphs": len(nx_graphs),
                    "pairwise_comparisons": len(edit_distances),
                    "edit_distances": edit_distances if edit_distances else [],
                },
                error_message=error_message,
            )

        except Exception as e:
            return MetricResult(
                metric_name=self.name,
                description="Measures variance in execution paths across sessions",
                value=-1,
                reasoning=f"Error occurred during computation: {str(e)}",
                unit="average_edit_distance",
                aggregation_level=self.aggregation_level,
                category="application",
                app_name=app_name,
                span_id=[],
                session_id=list(data.keys()) if data else [],
                source="native",
                entities_involved=list(set(entities_involved)),
                edges_involved=[],
                success=False,
                metadata={},
                error_message=str(e),
            )
