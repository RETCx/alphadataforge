import logging
import sys


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create and return a logger with a consistent format for the library.

    Usage:
        from alphadataforge.utils.logger import setup_logger
        logger = setup_logger(__name__)
        logger.info("message")

    End-users can control verbosity via:
        logging.getLogger("alphadataforge").setLevel(logging.DEBUG)
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when modules are re-imported
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger
