"""ASGI application that emulates a LiteLLM-compatible chat completion API."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from metrics_computation_engine.mock_llm_proxy.config import MockLLMSettings
from metrics_computation_engine.mock_llm_proxy.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionResponse,
    ChatCompletionUsage,
    MockChatCompletionRequest,
)


def _count_tokens(messages: list[ChatCompletionMessage]) -> int:
    """Very rough token estimator based on whitespace-delimited words."""

    if not messages:
        return 0

    joined = " ".join(message.content for message in messages)
    return max(len(joined.split()), 1)


def _build_response_content(
    request: MockChatCompletionRequest, settings: MockLLMSettings
) -> str:
    """Generate the assistant content payload based on the requested format."""

    if request.response_format and request.response_format.type == "json_object":
        payload = {
            "metric_score": settings.mock_metric_score,
            "score_reasoning": settings.mock_reasoning,
        }
        return json.dumps(payload)

    return settings.mock_reasoning


def _build_chat_completion(
    request: MockChatCompletionRequest, settings: MockLLMSettings
) -> ChatCompletionResponse:
    """Create a ChatCompletionResponse mirroring LiteLLM/OpenAI shape."""

    prompt_tokens = _count_tokens(request.messages)
    response_content = _build_response_content(request, settings)
    assistant_message = ChatCompletionMessage(
        role="assistant", content=response_content
    )
    completion_tokens = _count_tokens([assistant_message])

    choice = ChatCompletionChoice(
        index=0,
        message=assistant_message,
        finish_reason="stop",
    )

    usage = ChatCompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )

    response = ChatCompletionResponse(
        id=f"chatcmpl-mock-{uuid.uuid4().hex}",
        model=request.model,
        created=int(time.time()),
        choices=[choice],
        usage=usage,
        metadata={
            "mock": True,
            "api_base": request.api_base,
            "api_version": request.api_version,
            "custom_llm_provider": request.custom_llm_provider,
        },
    )

    return response


def get_settings(app: FastAPI) -> MockLLMSettings:
    return app.state.settings  # type: ignore[return-value]


def create_app(settings: MockLLMSettings | None = None) -> FastAPI:
    """Instantiate the FastAPI application with the supplied settings."""

    app = FastAPI(title="Mock LiteLLM Proxy", version="0.1.0")
    app.state.settings = settings or MockLLMSettings()

    async def _get_settings() -> MockLLMSettings:
        return get_settings(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat/completions")
    async def chat_completions(
        request: MockChatCompletionRequest, settings: MockLLMSettings = Depends(_get_settings)
    ) -> JSONResponse:
        if request.stream:
            raise HTTPException(status_code=400, detail="Streaming responses are not supported by the mock proxy.")

        response = _build_chat_completion(request, settings)
        return JSONResponse(content=response.model_dump())

    return app


__all__ = ["create_app"]


