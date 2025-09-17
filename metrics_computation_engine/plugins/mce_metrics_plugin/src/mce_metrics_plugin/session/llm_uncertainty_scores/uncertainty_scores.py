import logging
import math
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from pydantic import BaseModel

from metrics_computation_engine.metrics.base import BaseMetric
from metrics_computation_engine.models.eval import MetricResult
from metrics_computation_engine.models.requests import LLMJudgeConfig
from metrics_computation_engine.models.session import SessionEntity
from metrics_computation_engine.models.span import SpanEntity
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

    async def compute(self, data: Any):
        data = self._check_data_type(data=data)
        self.session_id = data.session_id
        single_session_spans = data.spans
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
            description="",
            value=value,
            reasoning="",
            unit="",
            aggregation_level=self.aggregation_level,
            category="session",
            app_name=data.app_name,
            span_id=list(log_probs.keys()),
            session_id=[self.session_id],
            source="MCE",
            entities_involved=[],
            edges_involved=[],
            success=success,
            metadata={k: [x.model_dump() for x in v] for k, v in log_probs.items()},
            error_message=error_message,
        )

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

    def compute_uncertainty_score(
        self, log_probs_mapping: SpanToLogProbMapping
    ) -> float:
        log_probs = get_all_log_probs_from_mapping(log_probs_mapping=log_probs_mapping)
        return log_to_prob(min(log_probs))


class LLMMaximumConfidence(LLMUncertaintyScoresBase):
    def __init__(self, metric_name: str = "Maximum Confidence"):
        super().__init__(metric_name=metric_name)

    def compute_uncertainty_score(
        self, log_probs_mapping: SpanToLogProbMapping
    ) -> float:
        log_probs = get_all_log_probs_from_mapping(log_probs_mapping=log_probs_mapping)
        return log_to_prob(max(log_probs))


class LLMAverageConfidence(LLMUncertaintyScoresBase):
    def __init__(self, metric_name: str = "Average Confidence"):
        super().__init__(metric_name=metric_name)

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
