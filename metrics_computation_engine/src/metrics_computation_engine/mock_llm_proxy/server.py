"""Mock LLM server for testing DeepEval and Opik metrics without using real tokens.

Reference: https://platform.openai.com/docs/api-reference/chat/create
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from metrics_computation_engine.mock_llm_proxy.config import MockLLMSettings
from metrics_computation_engine.mock_llm_proxy.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionResponse,
    ChatCompletionUsage,
    FunctionCall,
    MockChatCompletionRequest,
    ToolCall,
)


# =============================================================================
# DEEPEVAL: Schema resolution for tool calling
# DeepEval uses `instructor` library which sends tool calls with JSON schemas.
# Schemas use $ref to reference nested types in $defs (e.g., Verdict, Statement).
# =============================================================================


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    """[DEEPEVAL] Resolve $ref references like '#/$defs/ToxicityVerdict'."""
    if not ref.startswith("#/"):
        return {"type": "string"}

    path_parts = ref[2:].split("/")
    current = root_schema

    for part in path_parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return {"type": "string"}

    return current if isinstance(current, dict) else {"type": "string"}


def _generate_mock_value(
    schema: dict[str, Any],
    settings: MockLLMSettings,
    root_schema: dict[str, Any] | None = None,
) -> Any:
    """[DEEPEVAL] Generate mock values matching JSON schema from instructor."""
    if root_schema is None:
        root_schema = schema

    # [DEEPEVAL] Resolve $ref to nested types in $defs
    if "$ref" in schema:
        resolved = _resolve_ref(schema["$ref"], root_schema)
        return _generate_mock_value(resolved, settings, root_schema)

    # [DEEPEVAL] Handle enum - verdict fields require "yes"/"no", not arbitrary strings
    if "enum" in schema:
        return schema["enum"][0] if schema["enum"] else settings.mock_reasoning

    # [DEEPEVAL] Handle anyOf - Pydantic uses this for Optional[str] fields
    if "anyOf" in schema:
        return _generate_mock_value(schema["anyOf"][0], settings, root_schema)

    schema_type = schema.get("type", "string")

    # [DEEPEVAL] Handle type unions like ["string", "null"] for Optional fields
    if isinstance(schema_type, list):
        schema_type = next((t for t in schema_type if t != "null"), "string")

    if schema_type == "string":
        return settings.mock_reasoning
    elif schema_type == "null":
        return None
    elif schema_type == "array":
        items_schema = schema.get("items", {"type": "string"})
        return [_generate_mock_value(items_schema, settings, root_schema)]
    elif schema_type == "object":
        return {
            name: _generate_mock_value(prop, settings, root_schema)
            for name, prop in schema.get("properties", {}).items()
        }
    return settings.mock_reasoning


def _build_tool_response(
    request: MockChatCompletionRequest, settings: MockLLMSettings
) -> ToolCall:
    """[DEEPEVAL] Build tool call response for instructor-based structured outputs."""
    tool = request.tools[0]
    parameters = tool.function.parameters or {}

    mock_args = {
        name: _generate_mock_value(prop, settings, parameters)
        for name, prop in parameters.get("properties", {}).items()
    }

    return ToolCall(
        id=f"call_{uuid.uuid4().hex[:24]}",
        type="function",
        function=FunctionCall(
            name=tool.function.name,
            arguments=json.dumps(mock_args),
        ),
    )


# =============================================================================
# OPIK: JSON detection for prompt-based JSON responses
# Opik does NOT use tool calling. It sends prompts asking for JSON output
# and expects a text response containing {"score": ..., "reason": ...}.
# =============================================================================


def _is_json_expected(messages: list[dict[str, Any]]) -> bool:
    """[OPIK] Detect if prompt expects JSON based on message content."""
    indicators = ["json", "JSON"]
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        if content and any(ind in content for ind in indicators):
            return True
    return False


# =============================================================================
# SHARED: Response building and FastAPI app
# =============================================================================


def _build_response(
    request: MockChatCompletionRequest, settings: MockLLMSettings
) -> ChatCompletionResponse:
    """Build the chat completion response."""
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason = "stop"

    if request.tools:
        # [DEEPEVAL] Tool calling via instructor
        tool_calls = [_build_tool_response(request, settings)]
        finish_reason = "tool_calls"
    elif _is_json_expected(request.messages):
        # [OPIK] JSON in text response
        content = json.dumps(
            {
                "score": settings.mock_metric_score,
                "reason": settings.mock_reasoning,
            }
        )
    else:
        content = settings.mock_reasoning

    return ChatCompletionResponse(
        id=f"chatcmpl-mock-{uuid.uuid4().hex}",
        model=request.model,
        created=int(time.time()),
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                ),
                finish_reason=finish_reason,
            )
        ],
        usage=ChatCompletionUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def create_app(settings: MockLLMSettings | None = None) -> FastAPI:
    """Create the mock LLM FastAPI application."""
    app = FastAPI(title="Mock LLM Proxy", version="0.1.0")
    app.state.settings = settings or MockLLMSettings()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat/completions")
    async def chat_completions(request: MockChatCompletionRequest) -> JSONResponse:
        if request.stream:
            raise HTTPException(status_code=400, detail="Streaming not supported.")

        settings: MockLLMSettings = app.state.settings
        await asyncio.sleep(settings.response_latency_min_ms / 1000.0)

        response = _build_response(request, settings)
        return JSONResponse(content=response.model_dump())

    return app


__all__ = ["create_app"]
