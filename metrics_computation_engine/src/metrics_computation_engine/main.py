# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""Main FastAPI application for the Metrics Computation Engine."""

from datetime import datetime
import uvicorn
import os
import logging

from fastapi import FastAPI, HTTPException

from metrics_computation_engine.dal.api_client import (
    get_api_client,
    get_all_session_ids,
    get_traces_by_session_ids,
    traces_processor,
)

from metrics_computation_engine.models.requests import MetricsConfigRequest
from metrics_computation_engine.processor import MetricsProcessor
from metrics_computation_engine.registry import MetricRegistry
from metrics_computation_engine.util import (
    format_return,
    get_metric_class,
    get_all_available_metrics,
)
from metrics_computation_engine.entities.models.session_set import SessionSet
from metrics_computation_engine.entities.models.session_set_printer import (
    print_session_summary,
)
from metrics_computation_engine.model_handler import ModelHandler

from metrics_computation_engine.logger import setup_logger

logger = setup_logger(__name__)

# initialize the dal api client
get_api_client(logger=logger)

# TODO: we should create a class to hold the app and other global level variables (model_handler)
# ========== FastAPI App ==========
app = FastAPI(
    title="Metrics Computation Engine",
    description=("MCE service for computing metrics on AI agent performance data"),
    version="0.1.0",
)

model_handler = None


def start_server(host: str, port: int, reload: bool, log_level: str, workers: int = 1):
    global model_handler
    logger.debug("Starting server...")
    model_handler = ModelHandler()

    if reload:
        # USe import chain to avoid reloading issues
        uvicorn.run(
            "metrics_computation_engine.main:app",
            host=host,
            port=port,
            reload=True,
            log_level=log_level,
        )
    else:
        # Use app object when reload=false
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,
            log_level=log_level,
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

    # ensure the request is valid
    if not config.validate():
        logger.error("Request validation failed")
        raise HTTPException(status_code=400, detail="Invalid request configuration.")

    if model_handler is None:
        logger.warning("missing model_handler, creating it.")
        model_handler = ModelHandler()
    try:
        # Get session IDs
        logger.info(f"Is Batch: {config.is_batch_request()}")
        if config.is_batch_request():
            batch_config = config.get_batch_config()
            session_ids = get_all_session_ids(batch_config=batch_config)
        else:
            session_ids = config.get_session_ids()
        if logger.isEnabledFor(logging.DEBUG):  # DEBUG level
            logger.debug(f"Session IDs: {session_ids}")

        try:
            traces_by_session, notfound_session_ids = get_traces_by_session_ids(
                session_ids
            )

            # Log any sessions that weren't found
            if notfound_session_ids:
                logger.warning(f"Sessions not found: {notfound_session_ids}")

            # Build SessionEntity objects and create mapping
            if logger.isEnabledFor(logging.DEBUG):  # DEBUG level
                logger.debug("Building sessions_set")
            sessions_set = traces_processor(traces_by_session)
        except Exception as e:
            # No more fallback - old endpoint deprecated
            logger.error(f"Batched endpoint failed ({e})")
            sessions_set = SessionSet(sessions=[], stats=None)

        logger.info(print_session_summary(sessions_set))

        # if logger.isEnabledFor(logging.DEBUG):  # DEBUG level
        #     logger.debug(f"Session IDs Content Found: {list(sessions_set.values())}")
        # Configure LLM
        llm_config = config.llm_judge_config
        if llm_config.LLM_API_KEY == "sk-...":
            llm_config.LLM_BASE_MODEL_URL = os.getenv(
                "LLM_BASE_MODEL_URL", "https://api.openai.com/v1"
            )
            llm_config.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4-turbo")
            llm_config.LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-...")

        llm_config.NUM_LLM_RETRIES = int(os.getenv("NUM_LLM_RETRIES", str(llm_config.NUM_LLM_RETRIES)))

        logger.info(f"LLM Judge using - URL: {llm_config.LLM_BASE_MODEL_URL}")
        logger.info(f"LLM Judge using - Model: {llm_config.LLM_MODEL_NAME}")

        # Register metrics
        registry = MetricRegistry()
        failed_registry_metrics = []
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
                        "session_id": [],
                        "span_id": [],
                        "app_name": [],
                        "error_message": str(e),
                        "metadata": {},
                    }
                )

        logger.info(f"Registered Metrics: {registry.list_metrics()}")

        # Process metrics with structured session data
        processor = MetricsProcessor(
            registry=registry, model_handler=model_handler, llm_config=llm_config
        )

        # Get computation levels from config
        computation_levels = config.get_computation_levels()
        logger.info(f"Computation levels: {computation_levels}")

        results = await processor.compute_metrics(sessions_set, computation_levels)
        results.setdefault("failed_metrics", [])
        results["failed_metrics"].extend(failed_registry_metrics)

        # Implement caching of results here
        if (
            os.getenv("METRICS_CACHE_ENABLED", "false").lower() == "true"
            or config.should_write_to_db()
        ):
            logger.info("Caching required")
            get_api_client().cache_metrics(results)

        logger.info(f"Failed metrics: {results['failed_metrics']}")
        return {
            "metrics": registry.list_metrics(),
            "results": format_return(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
