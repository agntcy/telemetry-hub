# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""Server entry point for the Metrics Computation Engine."""

import os

from dotenv import load_dotenv

from metrics_computation_engine.logger import setup_logger
from metrics_computation_engine.main import start_server


logger = setup_logger(__name__)


def main():
    """Main entry point for the mce-server command."""
    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment variables
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    reload: bool = os.getenv("RELOAD", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "info").lower()
    # fail fast if bad env variables format
    pagination_limit = int(os.getenv("PAGINATION_LIMIT", "50"))
    pagination_max_sessions = int(os.getenv("PAGINATION_DEFAULT_MAX_SESSIONS", "50"))
    sessions_traces_max = int(os.getenv("SESSIONS_TRACES_MAX", "20"))
    workers = int(os.getenv("WORKERS", "2"))

    logger.info("Starting Metrics Computation Engine server...")
    logger.info("Host: %s", host)
    logger.info("Port: %s", port)
    logger.info("Reload: %s", reload)
    logger.info("Log Level: %s", log_level)
    logger.info("Pagination Limit: %s", pagination_limit)
    logger.info(
        "Pagination Default Max Sessions: %s", pagination_max_sessions
    )
    logger.info("Sessions Traces Max: %s", sessions_traces_max)
    logger.info("Workers: %s", workers)

    # Start the server
    start_server(
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        workers=workers,
    )


if __name__ == "__main__":
    main()
