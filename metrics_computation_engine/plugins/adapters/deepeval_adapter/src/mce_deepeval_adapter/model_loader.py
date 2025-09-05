from typing import Any

try:
    from deepeval.models import GPTModel
except ImportError:
    raise ImportError(
        "DeepEval is not installed. Please install it with: pip install deepeval"
    )

from metrics_computation_engine.models.requests import LLMJudgeConfig


MODEL_PROVIDER_NAME = "deepeval"


def load_model(llm_config: LLMJudgeConfig) -> Any:
    """
    Load a DeepEval model from the given LLM configuration.

    Args:
        llm_config: LLMJudgeConfig containing model configuration

    Returns:
        Configured DeepEval model

    Raises:
        ImportError: If deepeval is not installed
        ValueError: If required configuration is missing
    """
    # Validate required configuration
    if not llm_config.LLM_MODEL_NAME:
        raise ValueError("LLM_MODEL_NAME is required for DeepEval models")
    if not llm_config.LLM_API_KEY:
        raise ValueError("LLM_API_KEY is required for DeepEval models")

    # For now, we support only GPTModel
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
) -> GPTModel:
    """
    Load a GPT model for DeepEval.

    Args:
        llm_model_name: Name of the model to load
        llm_api_key: API key for the model
        llm_base_url: Base URL for the model API

    Returns:
        Configured GPTModel instance
    """
    model = GPTModel(
        model=llm_model_name,
        _openai_api_key=llm_api_key,
        base_url=llm_base_url,
        temperature=0.0,
    )
    return model
