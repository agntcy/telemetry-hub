# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import logging
from typing import Union


def _normalize_log_level(level: Union[int, str]) -> int:
    """
    Normalize log level to integer format.

    Parameters
    ----------
    level : Union[int, str]
        Log level as string (e.g., 'INFO', 'DEBUG', '20', '10') or integer (e.g., 20, 10)

    Returns
    -------
    int
        Logging level as integer
    """
    if isinstance(level, str):
        # Try to parse as integer first (for numeric strings like "20", "30")
        try:
            return int(level)
        except ValueError:
            # If not numeric, treat as level name (e.g., 'INFO', 'DEBUG')
            return getattr(logging, level.upper(), logging.INFO)
    return level


def setup_logger(
    name: str,
    level: Union[int, str] = None,
    formatter_str: str = "%(asctime)s.%(msecs)03d %(levelname)9s [%(filename)25s:%(lineno)4d - %(funcName)20s] [%(threadName)s] %(message)s",
) -> logging.Logger:
    """
    Set up a logger with the specified name, level, and formatter.

    Parameters
    ----------
    name : str
        Name of the logger.
    level : Union[int, str], optional
        Logging level as string ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        or integer (10, 20, 30, 40, 50). If None, defaults to LOG_LEVEL env var or INFO.
    formatter_str : str, optional
        Formatter string for log messages.

    Returns
    -------
    logger : logging.Logger
        Configured logger.
    """
    # Determine the effective log level
    if level is not None:
        effective_level = _normalize_log_level(level)
    else:
        env_level = os.getenv("LOG_LEVEL", "INFO")
        effective_level = _normalize_log_level(env_level)

    logger = logging.getLogger(name)
    logger.setLevel(effective_level)

    ch = logging.StreamHandler()
    ch.setLevel(effective_level)

    formatter = logging.Formatter(formatter_str)
    ch.setFormatter(formatter)

    if not logger.handlers:  # Avoid adding multiple handlers to the logger
        logger.addHandler(ch)
        logger.propagate = False

    return logger
