"""Simple logging setup shared by scripts and the app."""

from __future__ import annotations

import logging
from pathlib import Path

_CONFIGURED = False


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> logging.Logger:
    """Configure the root 'siteguard' logger once and return it."""
    global _CONFIGURED
    logger = logging.getLogger("siteguard")
    if not _CONFIGURED:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)
        logger.setLevel(level)
        _CONFIGURED = True
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(fh)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"siteguard.{name}")
