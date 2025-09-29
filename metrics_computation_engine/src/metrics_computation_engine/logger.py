# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import logging


def setup_logger(
    name: str,
    level: int = os.getenv("LOG_LEVEL", logging.INFO),
    formatter_str: str = "%(asctime)s.%(msecs)03d %(levelname)9s [%(filename)25s:%(lineno)4d - %(funcName)20s] [%(threadName)s] %(message)s",
) -> logging.Logger:
    """
    Set up a logger with the specified name, level, and formatter.

    Parameters
    ----------
    name : str
        Name of the logger.
    level : int, optional
        Logging level (default is `logging.INFO`).
    formatter_str : str, optional
        Formatter string (default is
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ).

    Returns
    -------
    logger : logging.Logger
        Configured logger.
    """
    logger = logging.getLogger(name)
    logger.setLevel(os.environ.get("LOG_LEVEL", level).upper())

    ch = logging.StreamHandler()
    ch.setLevel(os.environ.get("LOG_LEVEL", level).upper())

    formatter = logging.Formatter(formatter_str)
    ch.setFormatter(formatter)

    if not logger.handlers:  # Avoid adding multiple handlers to the logger
        logger.addHandler(ch)
        logger.propagate = False

    return logger
