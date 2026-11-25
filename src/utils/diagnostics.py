"""Isolation helpers for diagnostic and benchmark scripts (camera-quality Fix 6, 2026-11-23).

Diagnostic runs (replays, benchmarks, audits) must never write into production evidence storage
(events.evidence_dir, normally outputs/evidence/). EventManager honours SITEGUARD_EVIDENCE_DIR; this helper points it
at a fresh temporary folder for the current process unless a non-production folder is already configured.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.utils.paths import load_settings, project_path


def production_evidence_dir() -> Path:
    return project_path(load_settings()["events"]["evidence_dir"]).resolve()


def use_temporary_evidence_dir(prefix: str = "siteguard-diagnostic-evidence-") -> Path:
    """Redirect evidence written by this process to a temporary folder and return it."""
    current = os.environ.get("SITEGUARD_EVIDENCE_DIR")
    if current and Path(current).resolve() != production_evidence_dir():
        return Path(current)
    path = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["SITEGUARD_EVIDENCE_DIR"] = str(path)
    return path
