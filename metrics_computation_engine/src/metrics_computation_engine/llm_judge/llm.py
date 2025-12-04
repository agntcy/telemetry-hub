# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from litellm import completion


class LLMClient:
    """Handles individual LLM model configuration and querying."""

    def __init__(
        self,
        model_config: Dict[str, Any],
    ):
        self.model = model_config.get("LLM_MODEL_NAME", "")
        self.api_base = model_config["LLM_BASE_MODEL_URL"]
        self.api_key = model_config["LLM_API_KEY"]
        self.api_version = model_config.get("api_version", "")
        self.custom_llm_provider = self._determine_provider()
        self.num_retries = int(model_config.get("NUM_LLM_RETRIES", 3))

    def _determine_provider(self) -> Optional[str]:
        """Determine the custom LLM provider based on configuration."""
        """Determine the custom LLM provider based on configuration."""
        if self.api_version is None or len(self.api_version) == 0:
            return "openai"
        return None

    def query(self, messages: List[Dict[str, str]], **kwargs) -> Any:
        """Execute a query against this LLM."""

        # TODO: Temp, top_p, and seed can be used to roughly control
        # determinism of LLM outputs. However, it is found that different
        # providers do not offer configuration of these params.
        # To simplify usage, we will leave this out for now but worth
        # revisiting in the future.
        return completion(
            model=self.model,
            api_base=self.api_base,
            api_version=self.api_version,
            api_key=self.api_key,
            messages=messages,
            # temperature=0.0,
            # top_p=0.0,
            # seed=42,
            custom_llm_provider=self.custom_llm_provider,
            num_retries=self.num_retries,
            **kwargs,
        )
