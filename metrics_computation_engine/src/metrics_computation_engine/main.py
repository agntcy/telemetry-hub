# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""Main FastAPI application for the Metrics Computation Engine."""

import os
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, HTTPException

from metrics_computation_engine.dal.traces import (
    get_all_session_ids,
    get_traces_by_session,
    get_last_n_sessions_with_traces,
)
from metrics_computation_engine.models.requests import MetricsConfigRequest
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.util import (
    format_return,
    get_metric_class,
)

from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

# ========== FastAPI App ==========
app = FastAPI(
    title="Metrics Computation Engine",
    description=(
        "A FastAPI-based service for computing metrics on AI agent performance data"
    ),
    version="0.1.0",
)


def set_batch_mode(num_sessions=None, time_range=None, app_name=None):
    """Set batch mode configuration."""
    modes = [num_sessions, time_range, app_name]
    if sum(x is not None for x in modes) != 1:
        raise ValueError("Specify exactly one batch_mode parameter.")
    if num_sessions:
        return {"num_sessions": num_sessions}
    if time_range:
        return {"time_range": time_range}
    if app_name:
        return {"app_name": app_name}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Metrics Computation Engine",
        "version": "0.1.0",
        "endpoints": {
            "compute_metrics": "/compute_metrics",
            "health": "/health",
        },
    }


@app.get("/status")
async def status():
    """
    Health check endpoint to verify the app is alive.

    Returns:
        dict: Status information including timestamp
    """
    return {
        "status": "ok",
        "message": "Metric Computation Engine is running",
        "timestamp": datetime.now().isoformat(),
        "service": "metrics_computation_engine",
    }


@app.post("/compute_metrics")
async def compute_metrics(config: MetricsConfigRequest):
    """Compute metrics based on the provided configuration."""
    try:
        traces_by_session: Dict[str, List] = {}

        batch_config = config.batch_config
        if batch_config:
            if batch_config.num_sessions is not None:
                session_ids = get_last_n_sessions_with_traces(batch_config.num_sessions)
            elif batch_config.time_range is not None:
                time_range = batch_config.time_range
                session_ids = get_all_session_ids(
                    start_time=time_range.start, end_time=time_range.end
                )
            elif batch_config.app_name is not None:
                raise HTTPException(
                    status_code=501,
                    detail="app_name batch mode not yet implemented",
                )
            else:
                raise HTTPException(
                    status_code=400, detail="Invalid batch_mode parameter."
                )

            for session_id in session_ids:
                traces_by_session[session_id] = get_traces_by_session(session_id)
        else:
            raise HTTPException(status_code=400, detail="batch_mode is required.")

        llm_judge_config = config.llm_judge_config

        # TODO: Awkward for now but the idea is to still show the example parameters in the FastAPI docs. If the user's request payload maintains the dummy credential values, then check the environmental variables for default LLM config.
        if llm_judge_config.LLM_API_KEY == "sk-...":
            llm_judge_config.LLM_BASE_MODEL_URL = os.getenv(
                "LLM_BASE_MODEL_URL", "https://api.openai.com/v1"
            )
            llm_judge_config.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4-turbo")
            llm_judge_config.LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-...")

        logger.info(f"LLM Judge using - URL: {llm_judge_config.LLM_BASE_MODEL_URL}")
        logger.info(f"LLM Judge using - Model: {llm_judge_config.LLM_MODEL_NAME}")

        registry = MetricRegistry()
        for metric in config.metrics:
            registry.register_metric(get_metric_class(metric))

        processor = MetricsProcessor(registry, llm_config=llm_judge_config.model_dump())
        results = await processor.compute_metrics(traces_by_session)

        return {
            "metrics": registry.list_metrics(),
            "results": format_return(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
