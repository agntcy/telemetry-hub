# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from litellm import acompletion, completion
from deepeval.models.base_model import DeepEvalBaseLLM
from pydantic import BaseModel
import instructor


class LiteLLMModel(DeepEvalBaseLLM):
    def __init__(
        self,
        model="gpt-4o",
        api_key=None,
        base_url=None,
        temperature=0.0,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature

        self.client = instructor.from_litellm(completion)

    def load_model(self):
        return self.model

    def generate(self, prompt: str, schema: BaseModel) -> BaseModel:
        messages = [{"content": prompt, "role": "user"}]

        # Prepare kwargs for litellm
        kwargs = {
            "model": self.model,
            "messages": messages,
            "response_model": schema,
            "temperature": self.temperature,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            print(e)
            response = schema.model_construct()

        return response

    async def a_generate(self, prompt: str, schema: BaseModel) -> BaseModel:
        client = instructor.from_litellm(acompletion)

        messages = [{"content": prompt, "role": "user"}]

        # Prepare kwargs for litellm
        kwargs = {
            "model": self.model,
            "messages": messages,
            "response_model": schema,
            "temperature": self.temperature,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url

        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            print(e)
            response = schema.model_construct()

        return response

    def get_model_name(self):
        return self.model
