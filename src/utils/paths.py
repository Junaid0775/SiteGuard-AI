"""Central path handling for SiteGuard AI.

Every other module asks this file where things live, so that the project works
no matter which folder a command is started from.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# SiteGuard-AI/ (this file is SiteGuard-AI/src/utils/paths.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = PROJECT_ROOT / "configs"
DATASET_CONFIG = CONFIG_DIR / "dataset.yaml"
SETTINGS_CONFIG = CONFIG_DIR / "settings.yaml"

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
PRETRAINED_DIR = MODELS_DIR / "pretrained"
TRAINED_DIR = MODELS_DIR / "trained"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
DOCS_DIR = PROJECT_ROOT / "docs"

# Generated dataset files (resolved YAMLs and split lists) live here.
GENERATED_DATA_DIR = DATA_DIR / "generated"
VIEWPOINT_CSV = DATA_DIR / "viewpoint_metadata.csv"

# Keep Ultralytics' own settings file and fonts inside the project instead of
# the user's global Library folder. Must be set before `import ultralytics`.
ULTRALYTICS_CONFIG_DIR = PROJECT_ROOT / ".ultralytics"
os.environ.setdefault("YOLO_CONFIG_DIR", str(ULTRALYTICS_CONFIG_DIR))


def configure_ultralytics() -> None:
    """Disable anonymous usage analytics and point Ultralytics at project folders."""
    from ultralytics import settings  # imported here so YOLO_CONFIG_DIR is already set

    settings.update(
        {
            "sync": False,  # no anonymous telemetry
            "runs_dir": str(EXPERIMENTS_DIR),
            "weights_dir": str(PRETRAINED_DIR),
        }
    )


def project_path(relative: str | Path) -> Path:
    """Turn a path from a config file into an absolute path inside the project."""
    p = Path(relative).expanduser()
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    """Load configs/settings.yaml (cached; call load_settings.cache_clear() to reload)."""
    return load_yaml(SETTINGS_CONFIG)


def load_dataset_config() -> dict[str, Any]:
    return load_yaml(DATASET_CONFIG)


def source_dataset_dir() -> Path:
    """Absolute path of the ORIGINAL construction-ppe dataset (read-only).

    The environment variable SITEGUARD_DATASET_DIR overrides the config value,
    which is useful if the dataset is stored somewhere else on another machine.
    """
    override = os.environ.get("SITEGUARD_DATASET_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return project_path(load_dataset_config()["source_dataset"])


def mirror_dataset_dir() -> Path:
    """Absolute path of the symlink mirror used for training (see dataset_tools)."""
    return project_path(load_dataset_config()["mirror_dir"])


def class_names() -> dict[int, str]:
    """The 12-class mapping from configs/dataset.yaml, with integer keys."""
    names = load_dataset_config()["names"]
    return {int(k): str(v) for k, v in names.items()}


def ensure_output_dirs() -> None:
    for d in (
        OUTPUTS_DIR / "images",
        OUTPUTS_DIR / "videos",
        OUTPUTS_DIR / "reports",
        OUTPUTS_DIR / "evidence",
        GENERATED_DATA_DIR,
        EXPERIMENTS_DIR,
        PRETRAINED_DIR,
        TRAINED_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
