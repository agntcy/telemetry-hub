# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""Main FastAPI application for the Metrics Computation Engine."""

from datetime import datetime
import uvicorn
import os

from fastapi import FastAPI, HTTPException

from metrics_computation_engine.dal.traces import (
    get_all_session_ids,
    get_traces_by_session,
    get_traces_by_session_ids,
)
from metrics_computation_engine.dal.metrics import write_metrics
from metrics_computation_engine.dal.sessions import build_session_entities_from_dict
from metrics_computation_engine.models.requests import MetricsConfigRequest
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.util import (
    format_return,
    get_metric_class,
    get_all_available_metrics,
)

from metrics_computation_engine.model_handler import ModelHandler

from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

# ========== FastAPI App ==========
app = FastAPI(
    title="Metrics Computation Engine",
    description=("MCE service for computing metrics on AI agent performance data"),
    version="0.1.0",
)

model_handler = None


def start_server(host: str, port: int, reload: bool, log_level: str, workers: int):
    global model_handler
    model_handler = ModelHandler()
    uvicorn.run(
        "metrics_computation_engine.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        workers=workers,
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Metrics Computation Engine",
        "version": "0.1.0",
        "endpoints": {
            "compute_metrics": "/compute_metrics",
            "health": "/health",
            "list_metrics": "/metrics",
            "status": "/status",
        },
    }


@app.get("/metrics")
async def list_metrics():
    """
    List all available metrics in the system.
    Returns:
        dict: Dictionary containing all available metrics with their metadata
    """
    try:
        metrics = get_all_available_metrics()

        # Separate native and plugin metrics
        native_metrics = {
            k: v for k, v in metrics.items() if v.get("source") == "native"
        }
        plugin_metrics = {
            k: v for k, v in metrics.items() if v.get("source") == "plugin"
        }

        return {
            "total_metrics": len(metrics),
            "native_metrics": len(native_metrics),
            "plugin_metrics": len(plugin_metrics),
            "metrics": {"native": native_metrics, "plugins": plugin_metrics},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing metrics: {str(e)}")


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
    global model_handler
    if model_handler is None:
        logger.info("Warning: missing model_handler, creating it.")
        model_handler = ModelHandler()
    try:
        # Get session IDs
        logger.info(f"Is Batch: {config.is_batch_request()}")
        if config.is_batch_request():
            batch_config = config.get_batch_config()
            session_ids = get_all_session_ids(batch_config=batch_config)
        else:
            session_ids = config.get_session_ids()

        # ensure the request is valid
        if not config.validate():
            raise HTTPException(
                status_code=400, detail="Invalid request configuration."
            )

        # Try batched approach first, fallback to sequential if endpoint doesn't exist
        try:
            traces_by_session, notfound_session_ids = get_traces_by_session_ids(
                session_ids
            )

            # Log any sessions that weren't found
            if notfound_session_ids:
                logger.warning(f"Sessions not found: {notfound_session_ids}")

            # Build SessionEntity objects and create mapping
            session_entities = build_session_entities_from_dict(traces_by_session)
            sessions_data = {entity.session_id: entity for entity in session_entities}

        except Exception as e:
            # Fallback to sequential approach if batched endpoint fails (404)
            logger.warning(
                f"Batched endpoint failed ({e}), falling back to sequential processing"
            )
            traces_by_session = {}

            for session_id in session_ids:
                try:
                    spans = get_traces_by_session(session_id)
                    if spans:
                        traces_by_session[session_id] = spans
                except Exception as session_error:
                    logger.error(
                        f"Failed to get traces for session {session_id}: {session_error}"
                    )

            # Build SessionEntity objects and create mapping
            if traces_by_session:
                session_entities = build_session_entities_from_dict(traces_by_session)
                sessions_data = {
                    entity.session_id: entity for entity in session_entities
                }
            else:
                sessions_data = {}

        logger.info(f"Session IDs Found: {list(sessions_data.keys())}")
        # Configure LLM
        llm_config = config.llm_judge_config
        if llm_config.LLM_API_KEY == "sk-...":
            llm_config.LLM_BASE_MODEL_URL = os.getenv(
                "LLM_BASE_MODEL_URL", "https://api.openai.com/v1"
            )
            llm_config.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4-turbo")
            llm_config.LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-...")

        logger.info(f"LLM Judge using - URL: {llm_config.LLM_BASE_MODEL_URL}")
        logger.info(f"LLM Judge using - Model: {llm_config.LLM_MODEL_NAME}")

        failed_registry_metrics = []

        # Register metrics
        registry = MetricRegistry()
        for metric in config.metrics:
            try:
                metric_cls, metric_name = get_metric_class(metric)
                logger.info(f"Metric Name: {metric_name} - {metric_cls}")
                registry.register_metric(
                    metric_class=metric_cls, metric_name=metric_name
                )
            except Exception as e:
                logger.error(f"Error: {e}")
                failed_registry_metrics.append(
                    {
                        "metric_name": metric,
                        "aggregation_level": "unknown",
                        "error_message": str(e),
                        "metadata": {},
                    }
                )

        logger.info(f"Registered Metrics: {registry.list_metrics()}")

        # Process metrics with structured session data
        processor = MetricsProcessor(
            registry, model_handler=model_handler, llm_config=llm_config
        )
        results = await processor.compute_metrics(sessions_data)
        results.setdefault("failed_metrics", [])
        results["failed_metrics"].extend(failed_registry_metrics)
        write_metrics(results)
        return {
            "metrics": registry.list_metrics(),
            "results": format_return(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
