# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""Server entry point for the Metrics Computation Engine."""

import os

import uvicorn
from dotenv import load_dotenv


def main():
    """Main entry point for the mce-server command."""
    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment variables
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    reload: bool = os.getenv("RELOAD", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "info").lower()

    print("Starting Metrics Computation Engine server...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log Level: {log_level}")

    # Start the server
    uvicorn.run(
        "metrics_computation_engine.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
