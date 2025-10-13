# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import math
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from pydantic import BaseModel

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.entities.models.session import SessionEntity
from metrics_computation_engine.entities.models.span import SpanEntity
from metrics_computation_engine.types import AggregationLevel
from metrics_computation_engine.util import setup_logger

logger = setup_logger(__name__, level=logging.INFO)


class TokenModel(BaseModel):
    token: str
    logprob: float
    bytes: Optional[List[int]] = None


class LogProbsModel(BaseModel):
    token_logprob: TokenModel
    top_logprobs: List[TokenModel]


SpanToLogProbMapping = Dict[str, List[LogProbsModel]]


class LLMUncertaintyScoresBase(BaseMetric):
    def __init__(self, metric_name: str):
        super().__init__()
        self.name: str = metric_name
        self.aggregation_level: AggregationLevel = "session"
        self.session_id: Optional[str] = None

    def supports_agent_computation(self) -> bool:
        """Indicates that this metric supports agent-level computation."""
        return True

    async def compute(self, session: SessionEntity, **context):
        # Session-level computation (existing logic)
        return await self._compute_session_level(session)

    async def _compute_session_level(self, session: SessionEntity):
        """Compute uncertainty score for the entire session."""
        session = self._check_data_type(data=session)
        self.session_id = session.session_id
        single_session_spans = session.spans
        log_probs = get_log_probs(single_session_spans=single_session_spans)
        if log_probs:
            try:
                value = self.compute_uncertainty_score(log_probs_mapping=log_probs)
                success = True
                error_message = None
            except Exception as e:
                value = -1
                success = False
                error_message = str(e)
        else:
            value = -1
            success = False
            error_message = "No logprobs found"

        return MetricResult(
            metric_name=self.name,
            value=value,
            aggregation_level=self.aggregation_level,
            category="session",
            app_name=session.app_name,
            description="",
            reasoning="",
            unit="MCE",
            span_id=list(log_probs.keys()),
            session_id=[self.session_id],
            source="",
            entities_involved=[],
            edges_involved=[],
            success=success,
            metadata={k: [x.model_dump() for x in v] for k, v in log_probs.items()},
            error_message=error_message,
        )

    async def compute_agent_level(self, session: SessionEntity) -> List[MetricResult]:
        """
        Compute uncertainty score for each individual agent in the session.

        Returns a list of MetricResult objects, one per agent found.
        Each result contains the uncertainty score for that specific agent.
        """
        # Temporarily override aggregation level for agent computation
        original_level = self.aggregation_level
        self.aggregation_level = "agent"

        try:
            # Check if session has agent_stats property
            if not hasattr(session, "agent_stats"):
                # Session doesn't have agent_stats - return empty list
                self.aggregation_level = original_level
                return []

            agent_stats = session.agent_stats
            if not agent_stats:
                # No agents found in session - return empty list
                self.aggregation_level = original_level
                return []

            # Create individual results for each agent
            results = []

            for agent_name in agent_stats.keys():
                agent_view = session.get_agent_view(agent_name)

                # Get agent-specific spans from AgentView
                agent_spans = agent_view.all_spans

                if not agent_spans:
                    # Create error result for agents without spans
                    entities_involved = [agent_name] if agent_name else []

                    result = MetricResult(
                        metric_name=self.name,
                        value=-1,
                        aggregation_level=self.aggregation_level,
                        category="agent",
                        app_name=session.app_name,
                        agent_id=agent_name,
                        description="",
                        reasoning="",
                        unit="MCE",
                        span_id=[],
                        session_id=[session.session_id],
                        source="",
                        entities_involved=entities_involved,
                        edges_involved=[],
                        success=False,
                        metadata={"agent_id": agent_name},
                        error_message=f"Agent '{agent_name}' has no spans to process",
                    )

                    results.append(result)
                    continue

                # Get log probs for this agent's spans
                log_probs = get_log_probs(single_session_spans=agent_spans)

                if log_probs:
                    try:
                        value = self.compute_uncertainty_score(
                            log_probs_mapping=log_probs
                        )
                        success = True
                        error_message = None
                    except Exception as e:
                        value = -1
                        success = False
                        error_message = str(e)
                else:
                    value = -1
                    success = False
                    error_message = f"No logprobs found for agent '{agent_name}'"

                entities_involved = [agent_name] if agent_name else []
                agent_span_ids = [span.span_id for span in agent_spans]

                result = MetricResult(
                    metric_name=self.name,
                    value=value,
                    aggregation_level=self.aggregation_level,
                    category="agent",
                    app_name=session.app_name,
                    agent_id=agent_name,
                    description="",
                    reasoning="",
                    unit="MCE",
                    span_id=agent_span_ids,
                    session_id=[session.session_id],
                    source="",
                    entities_involved=entities_involved,
                    edges_involved=[],
                    success=success,
                    metadata={
                        "agent_id": agent_name,
                        "logprobs": {
                            k: [x.model_dump() for x in v] for k, v in log_probs.items()
                        }
                        if log_probs
                        else {},
                    },
                    error_message=error_message,
                )

                results.append(result)

            # Restore original aggregation level before returning
            self.aggregation_level = original_level
            return results

        except Exception as e:
            # Error handling for agent computation - restore level and re-raise
            self.aggregation_level = original_level
            raise e

    def init_with_model(self, model: Any) -> bool:
        return True

    def create_model(self, llm_config: LLMJudgeConfig) -> Any:
        return None

    def get_model_provider(self) -> Optional[str]:
        return None

    def validate_config(self) -> bool:
        return True

    @property
    def required_parameters(self) -> List[str]:
        return ["conversation_data"]

    @abstractmethod
    def compute_uncertainty_score(
        self, log_probs_mapping: SpanToLogProbMapping
    ) -> float:
        pass

    @staticmethod
    def _check_data_type(data: Any) -> SessionEntity:
        if not isinstance(data, SessionEntity):
            raise TypeError("Data must be a SessionEntity instance")
        return data


class LLMMinimumConfidence(LLMUncertaintyScoresBase):
    def __init__(self, metric_name: str = "Minimum Confidence"):
        super().__init__(metric_name=metric_name)
        self.description = "Calculates the minimum confidence score from LLM log probabilities across all tokens in the session or agent."

    def compute_uncertainty_score(
        self, log_probs_mapping: SpanToLogProbMapping
    ) -> float:
        log_probs = get_all_log_probs_from_mapping(log_probs_mapping=log_probs_mapping)
        return log_to_prob(min(log_probs))


class LLMMaximumConfidence(LLMUncertaintyScoresBase):
    def __init__(self, metric_name: str = "Maximum Confidence"):
        super().__init__(metric_name=metric_name)
        self.description = "Calculates the maximum confidence score from LLM log probabilities across all tokens in the session or agent."

    def compute_uncertainty_score(
        self, log_probs_mapping: SpanToLogProbMapping
    ) -> float:
        log_probs = get_all_log_probs_from_mapping(log_probs_mapping=log_probs_mapping)
        return log_to_prob(max(log_probs))


class LLMAverageConfidence(LLMUncertaintyScoresBase):
    def __init__(self, metric_name: str = "Average Confidence"):
        super().__init__(metric_name=metric_name)
        self.description = "Calculates the average confidence score from LLM log probabilities across all tokens in the session or agent."

    def compute_uncertainty_score(
        self, log_probs_mapping: SpanToLogProbMapping
    ) -> float:
        avg_per_span: List[float] = []
        for record_list in log_probs_mapping.values():
            span_log_probs = [record.token_logprob.logprob for record in record_list]
            span_average_confidence = calculate_mean(numbers=span_log_probs)
            avg_per_span.append(span_average_confidence)
        session_avg = calculate_mean(numbers=avg_per_span)
        score = log_to_prob(logprob=session_avg)
        return score


def calculate_mean(numbers: List[float]) -> float:
    return float(pd.Series(numbers).mean())


def log_to_prob(logprob: float) -> float:
    return math.exp(logprob)


def get_log_probs(single_session_spans: List[SpanEntity]) -> SpanToLogProbMapping:
    res_dict: SpanToLogProbMapping = dict()
    for span in single_session_spans:
        output_payload = span.output_payload
        span_id = span.span_id
        try:
            res = find_key_value_in_nested_structure(
                data=output_payload, target_key="logprobs"
            )
        except Exception as e:
            logger.warning(
                f"Error occurred while processing span {span_id} with message {str(e)}"
            )
            continue
        if res is None:
            continue
        try:
            content = res["content"]
        except Exception as e:
            logger.warning(
                f"Error occurred while processing span {span_id} with message {str(e)}"
            )
            continue
        else:
            res_list = []
            for token_dict in content:
                token = token_dict["token"]
                token_bytes = token_dict["bytes"]
                logprob = token_dict["logprob"]
                top_logprobs = token_dict["top_logprobs"]
                token_logprob = TokenModel(
                    bytes=token_bytes, logprob=logprob, token=token
                )
                token_top_logprobs = [
                    TokenModel.model_validate(lp) for lp in top_logprobs
                ]
                token_log_prob = LogProbsModel(
                    token_logprob=token_logprob,
                    top_logprobs=token_top_logprobs,
                )
                res_list.append(token_log_prob)
                res_dict[span_id] = res_list
    return res_dict


def get_all_log_probs_from_mapping(
    log_probs_mapping: SpanToLogProbMapping,
) -> List[float]:
    log_probs = []
    for record_list in log_probs_mapping.values():
        for record in record_list:
            logprob = record.token_logprob.logprob
            log_probs.append(logprob)
    return log_probs


def find_key_value_in_nested_structure(
    data: Union[List[Any], Dict[str, Any]], target_key: str
) -> Any:
    """
    Recursively searches for a target_key within a nested dictionary or list
    and returns the value associated with the first occurrence of the key.
    Args:
        data: The nested dictionary, list, or primitive value to search.
        target_key: The string key to search for.
    Returns:
        The value associated with the target_key if found, otherwise None.
    """
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for value in data.values():
            result = find_key_value_in_nested_structure(
                data=value, target_key=target_key
            )
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_key_value_in_nested_structure(
                data=item, target_key=target_key
            )
            if result is not None:
                return result
    return None
