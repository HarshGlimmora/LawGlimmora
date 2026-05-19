"""Loguru setup. Call configure_logging() once at app startup.

Two outputs:

  * stderr — always on. Coloured in dev, plain in prod (Render's log
    viewer doesn't render ANSI colour codes well).
  * Rotating file sink — only when SETTINGS.log_file is set. In production
    it is None by default, so we rely on Render's captured stdout/stderr
    rather than writing to ephemeral disk.
"""
from __future__ import annotations

import sys

from loguru import logger

from config.settings import SETTINGS

_configured = False


_DEV_STDERR_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | "
    "<cyan>{name}</cyan> | {message}"
)
_PROD_STDERR_FORMAT = (
    "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} {level: <7} {name} | {message}"
)
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | "
    "{name}:{function}:{line} | {message}"
)


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level=SETTINGS.log_level,
        format=_DEV_STDERR_FORMAT if SETTINGS.is_dev else _PROD_STDERR_FORMAT,
        colorize=SETTINGS.is_dev,
        backtrace=SETTINGS.is_dev,
        diagnose=SETTINGS.is_dev,
    )

    if SETTINGS.log_file is not None:
        SETTINGS.log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            SETTINGS.log_file,
            level=SETTINGS.log_level,
            rotation="2 MB",
            retention=5,
            encoding="utf-8",
            format=_FILE_FORMAT,
        )

    _configured = True


def get_logger(name: str):
    configure_logging()
    return logger.bind(scope=name)
