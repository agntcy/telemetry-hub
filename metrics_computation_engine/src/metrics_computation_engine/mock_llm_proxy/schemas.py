"""Pydantic schemas mirroring the OpenAI Chat Completion API.

Reference: https://platform.openai.com/docs/api-reference/chat/create
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ResponseFormat(BaseModel):
    """OpenAI response_format schema."""

    type: str = Field(default="text")
    json_schema: Optional[Dict[str, Any]] = None


class FunctionDefinition(BaseModel):
    """Function definition within a tool."""

    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ToolDefinition(BaseModel):
    """Tool definition for OpenAI tool calling."""

    type: str = "function"
    function: FunctionDefinition


class ToolChoice(BaseModel):
    """Tool choice specification."""

    type: str = "function"
    function: Dict[str, str]


class FunctionCall(BaseModel):
    """Function call within a tool call."""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """Tool call in a message response."""

    id: str
    type: str = "function"
    function: FunctionCall


class ChatCompletionMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


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
    messages: List[Dict[str, Any]]
    response_format: Optional[ResponseFormat] = None
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = None
    extra_body: Dict[str, Any] = Field(default_factory=dict)
    custom_llm_provider: Optional[str] = None
    # Tool calling
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[Union[str, ToolChoice]] = None
