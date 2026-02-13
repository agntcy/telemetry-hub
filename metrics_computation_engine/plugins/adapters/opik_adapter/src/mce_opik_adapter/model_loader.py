# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any, Optional
from opik.evaluation import models
from metrics_computation_engine.models.requests import LLMJudgeConfig

MODEL_PROVIDER_NAME = "opik"


def load_model(llm_config: LLMJudgeConfig) -> Any:
    # For now, we support only LiteLLMChatModel
    model = load_gpt_model(
        llm_model_name=llm_config.LLM_MODEL_NAME,
        llm_api_key=llm_config.LLM_API_KEY,
        llm_base_url=llm_config.LLM_BASE_MODEL_URL,
    )
    return model


def load_gpt_model(
    llm_model_name: str,
    llm_api_key: str,
    llm_base_url: str,
    temperature: Optional[float] = 1.0,
) -> models.LiteLLMChatModel:
    kwargs = {
        "model_name": llm_model_name,
        "base_url": llm_base_url,
        "api_key": llm_api_key,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    model = models.LiteLLMChatModel(**kwargs)
    return model
