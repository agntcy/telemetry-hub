# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Optional

from litellm import acompletion, completion
from deepeval.models.base_model import DeepEvalBaseLLM
from pydantic import BaseModel
import instructor

from metrics_computation_engine.logger import setup_logger


logger = setup_logger(__name__)


class LiteLLMModel(DeepEvalBaseLLM):
    def __init__(
        self,
        model="gpt-5",
        api_key=None,
        base_url=None,
        temperature: Optional[float] = 1,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature

        self.client = instructor.from_litellm(completion)

    def _build_kwargs(self, messages: list, schema: BaseModel) -> dict:
        """Build kwargs for litellm, handling model-specific parameter support."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "response_model": schema,
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        # Safety-net: ask litellm to silently drop any params that
        # a given model does not support, rather than raising
        # UnsupportedParamsError.
        kwargs["drop_params"] = True

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url

        return kwargs

    def load_model(self):
        return self.model

    def generate(self, prompt: str, schema: BaseModel) -> BaseModel:
        messages = [{"content": prompt, "role": "user"}]
        kwargs = self._build_kwargs(messages, schema)

        response = self.client.chat.completions.create(**kwargs)
        return response

    async def a_generate(self, prompt: str, schema: BaseModel) -> BaseModel:
        client = instructor.from_litellm(acompletion)

        messages = [{"content": prompt, "role": "user"}]
        kwargs = self._build_kwargs(messages, schema)

        response = await client.chat.completions.create(**kwargs)
        return response

    def get_model_name(self):
        return self.model
