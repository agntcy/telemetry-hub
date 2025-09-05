# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Any

# Import logger from MCE following the standard pattern
from metrics_computation_engine.logger import setup_logger

MODEL_PROVIDER_NAME = "ragas"

# Set up logger using MCE's standard pattern
logger = setup_logger(__name__)


def load_model(llm_config) -> Any:
    """
    Entry point for MCE plugin system to load RAGAS-compatible models.

    This function serves as the standardized interface between the Metrics
    Computation Engine and the RAGAS adapter plugin. It extracts configuration
    parameters and delegates to the specialized RAGAS model loader.

    Args:
        llm_config: LLMJudgeConfig instance containing:
            - LLM_MODEL_NAME: OpenAI model identifier
            - LLM_API_KEY: Authentication token
            - LLM_BASE_MODEL_URL: API endpoint URL

    Returns:
        LangchainLLMWrapper: RAGAS model instance

    Raises:
        ImportError: If RAGAS dependencies are missing
        RuntimeError: If model initialization fails
    """
    return load_ragas_model(
        llm_model_name=llm_config.LLM_MODEL_NAME,
        llm_api_key=llm_config.LLM_API_KEY,
        llm_base_url=llm_config.LLM_BASE_MODEL_URL,
    )


def load_ragas_model(
    llm_model_name: str,
    llm_api_key: str,
    llm_base_url: str,
) -> Any:
    """
    Create a RAGAS-compatible LLM model with uvloop compatibility.

    RAGAS unconditionally calls nest_asyncio.apply() during import, which conflicts
    with uvloop (used by FastAPI/uvicorn). This function implements a conditional
    approach similar to DeepEval's strategy to avoid the conflict.

    Also handles GitPython import issues in RAGAS v0.3.2.

    Args:
        llm_model_name: OpenAI model name (e.g., 'gpt-4o', 'gpt-3.5-turbo')
        llm_api_key: API key for the LLM service
        llm_base_url: Base URL for the LLM API endpoint

    Returns:
        LangchainLLMWrapper: RAGAS-compatible model wrapper

    Raises:
        ImportError: If RAGAS or LangChain dependencies are not available
        RuntimeError: If model creation fails due to configuration issues

    Note:
        This function temporarily patches nest_asyncio.apply() to prevent
        uvloop conflicts. The original function is always restored.
    """
    import asyncio
    import os

    # Set git environment variable to suppress git errors in RAGAS
    original_git_refresh = os.environ.get("GIT_PYTHON_REFRESH")
    os.environ["GIT_PYTHON_REFRESH"] = "quiet"

    # Import and store original nest_asyncio function
    import nest_asyncio

    original_apply = nest_asyncio.apply

    def _conditional_nest_asyncio_apply():
        """
        Conditionally apply nest_asyncio only when an event loop is already running.

        This prevents the "Can't patch loop of type <class 'uvloop.Loop'>" error
        that occurs when RAGAS tries to unconditionally patch the event loop.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Only apply when we're inside a running loop
                original_apply()
                logger.debug("Applied nest_asyncio due to running event loop")
            # If no loop is running, nest_asyncio is not needed
        except Exception as exc:
            # If we can't determine loop state, don't apply to avoid conflicts
            logger.debug(f"Skipped nest_asyncio application: {exc}")

    # Temporarily replace with conditional version
    nest_asyncio.apply = _conditional_nest_asyncio_apply

    try:
        # Import RAGAS components (this triggers the conditional nest_asyncio)
        from ragas.llms import LangchainLLMWrapper
        from langchain_openai import ChatOpenAI

        # Create base LangChain ChatOpenAI model
        base_llm = ChatOpenAI(
            model=llm_model_name,
            api_key=llm_api_key,
            base_url=llm_base_url,
            temperature=0.0,  # Deterministic evaluation
            timeout=30,  # Reasonable timeout for evaluation
            max_retries=2,  # Limited retries for production
        )

        # Wrap in RAGAS-required LangchainLLMWrapper
        evaluator_llm = LangchainLLMWrapper(base_llm)

        logger.info(f"Successfully created RAGAS model: {llm_model_name}")
        return evaluator_llm

    except ImportError as exc:
        logger.error(f"Failed to import RAGAS dependencies: {exc}")
        raise ImportError(
            "RAGAS or LangChain dependencies not available. "
            "Install with: pip install ragas langchain-openai"
        ) from exc

    except Exception as exc:
        logger.error(f"Failed to create RAGAS model: {exc}")
        raise RuntimeError(f"RAGAS model creation failed: {exc}") from exc

    finally:
        # Always restore the original nest_asyncio.apply function
        nest_asyncio.apply = original_apply

        # Restore original git environment variable
        if original_git_refresh is not None:
            os.environ["GIT_PYTHON_REFRESH"] = original_git_refresh
        elif "GIT_PYTHON_REFRESH" in os.environ:
            del os.environ["GIT_PYTHON_REFRESH"]
