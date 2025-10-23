"""Settings loader for environment-driven configuration."""

from __future__ import annotations

import os

from metrics_computation_engine.mock_llm_proxy.config import MockLLMSettings


def load_settings_from_env() -> MockLLMSettings:
    """Load mock proxy settings from environment variables."""

    overrides = {}

    if host := os.getenv("MOCK_LLM_PROXY_HOST"):
        overrides["host"] = host

    if port := os.getenv("MOCK_LLM_PROXY_PORT"):
        overrides["port"] = int(port)

    if score := os.getenv("MOCK_LLM_PROXY_METRIC_SCORE"):
        overrides["mock_metric_score"] = float(score)

    if reasoning := os.getenv("MOCK_LLM_PROXY_REASONING"):
        overrides["mock_reasoning"] = reasoning

    if latency_min := os.getenv("MOCK_LLM_PROXY_LATENCY_MIN_MS"):
        overrides["response_latency_min_ms"] = float(latency_min)

    if latency_max := os.getenv("MOCK_LLM_PROXY_LATENCY_MAX_MS"):
        overrides["response_latency_max_ms"] = float(latency_max)

    return MockLLMSettings(**overrides)
