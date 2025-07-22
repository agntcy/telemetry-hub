import logging


def setup_logger(
    name: str,
    level: int = logging.INFO,
    formatter_str: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> logging.Logger:
    """
    Set up a logger with the specified name, level, and formatter.
    Parameters
    ----------
    name : str
        Name of the logger.
    level : int, optional
        Logging level (default is `logging.DEBUG`).
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
    logger.setLevel(level)

    ch = logging.StreamHandler()
    ch.setLevel(level)

    formatter = logging.Formatter(formatter_str)
    ch.setFormatter(formatter)

    if not logger.handlers:  # Avoid adding multiple handlers to the logger
        logger.addHandler(ch)
        logger.propagate = False

    return logger
