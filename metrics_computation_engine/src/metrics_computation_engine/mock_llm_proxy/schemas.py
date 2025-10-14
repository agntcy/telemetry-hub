"""Pydantic schemas mirroring a subset of the LiteLLM API surface."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResponseFormat(BaseModel):
    """Subset of the OpenAI response_format schema supported by LiteLLM."""

    type: str = Field(default="text")


class ChatCompletionMessage(BaseModel):
    role: str
    content: str


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatCompletionMessage
    finish_reason: str = Field(default="stop")


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    created: int
    object: str = Field(default="chat.completion")
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage
    provider: str = Field(default="mock-litellm")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MockChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
    response_format: Optional[ResponseFormat] = None
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = None
    extra_body: Dict[str, Any] = Field(default_factory=dict)
    custom_llm_provider: Optional[str] = None
