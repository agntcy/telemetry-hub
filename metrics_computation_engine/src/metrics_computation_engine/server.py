# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""Server entry point for the Metrics Computation Engine."""

import os

from dotenv import load_dotenv

from metrics_computation_engine.main import start_server


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

    print("Starting Metrics Computation Engine server...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log Level: {log_level}")
    print(f"Pagination Limit: {pagination_limit}")
    print(f"Pagination Default Max Sessions: {pagination_max_sessions}")
    print(f"Sessions Traces Max {sessions_traces_max}")

    # Start the server
    start_server(host=host, port=port, reload=reload, log_level=log_level)


if __name__ == "__main__":
    main()
