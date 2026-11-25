"""Application model registry: which checkpoint SiteGuard uses, how it is validated, and the safe fallback.

configs/settings.yaml:

    model:
      active: yolo26n_baseline          # registry key the application loads
      fallback: yolo26n_baseline        # loaded (with a logged warning) if the active model is missing or incompatible
      registry:
        yolo26n_baseline:
          weights: models/trained/best.pt
          architecture: yolo26n          # must match the checkpoint's YAML (yolo26n.yaml)
          image_size: 640                # the model's deployment inference size (one size for image, video, live)
          card: null                     # optional model card JSON; its checkpoint_sha256 must match the file
      trained_weights: models/trained/best.pt   # legacy key; used only when no registry is configured

The environment variable SITEGUARD_MODEL overrides `active` (for a rollback without editing files).
A checkpoint is never loaded silently if it is incompatible: the file must exist, its SHA-256 must equal the model
card (when a card is given), the task must be detection, its 12 class names must equal configs/dataset.yaml in the
same order, and its architecture must match the registry entry.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.paths import class_names, configure_ultralytics, project_path


class ModelNotFoundError(FileNotFoundError):
    """Raised when a checkpoint file does not exist."""


class IncompatibleModelError(ValueError):
    """Raised when a checkpoint exists but must not be used (corrupt, wrong task, classes, architecture or hash)."""


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ModelEntry:
    key: str
    weights: Path
    architecture: str | None = None
    image_size: int | None = None
    card: Path | None = None
    description: str = ""

    def card_data(self) -> dict[str, Any] | None:
        if self.card is None or not self.card.exists():
            return None
        return json.loads(self.card.read_text(encoding="utf-8"))


class ModelRegistry:
    def __init__(self, entries: dict[str, ModelEntry], active: str, fallback: str | None) -> None:
        if active not in entries:
            raise KeyError(f"Active model '{active}' is not in the registry ({sorted(entries)})")
        if fallback is not None and fallback not in entries:
            raise KeyError(f"Fallback model '{fallback}' is not in the registry ({sorted(entries)})")
        self.entries, self.active, self.fallback = entries, active, fallback

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "ModelRegistry":
        m = settings["model"]
        reg = m.get("registry") or {}
        if not reg:  # legacy configuration: a single checkpoint
            e = ModelEntry("default", project_path(m["trained_weights"]))
            return cls({"default": e}, "default", None)
        entries = {
            k: ModelEntry(k, project_path(v["weights"]), v.get("architecture"), v.get("image_size"),
                          project_path(v["card"]) if v.get("card") else None, v.get("description", ""))
            for k, v in reg.items()
        }
        active = os.environ.get("SITEGUARD_MODEL") or m.get("active") or next(iter(entries))
        return cls(entries, active, m.get("fallback"))

    def get(self, key: str) -> ModelEntry:
        if key not in self.entries:
            raise KeyError(f"Model '{key}' is not in the registry ({sorted(self.entries)})")
        return self.entries[key]

    def load_order(self, key: str | None = None) -> list[ModelEntry]:
        first = self.get(key or self.active)
        order = [first]
        if self.fallback and self.fallback != first.key:
            order.append(self.entries[self.fallback])
        return order


def load_validated(weights: Path, architecture: str | None = None, expected_sha256: str | None = None):
    """Load an Ultralytics checkpoint only if it is compatible. Returns (model, identity dict)."""
    if not weights.exists():
        raise ModelNotFoundError(f"Trained model not found at {weights}. Run: .venv/bin/python -m src.training.train")
    sha = file_sha256(weights)
    if expected_sha256 and sha != expected_sha256:
        raise IncompatibleModelError(f"{weights.name}: SHA-256 {sha[:16]}... does not match its model card ({expected_sha256[:16]}...)")
    configure_ultralytics()
    from ultralytics import YOLO

    try:
        model = YOLO(str(weights))
    except Exception as exc:  # corrupt or foreign file
        raise IncompatibleModelError(f"{weights.name} cannot be loaded as a YOLO checkpoint: {exc}") from exc
    if model.task != "detect":
        raise IncompatibleModelError(f"{weights.name}: expected a detection model, got task '{model.task}'")
    names = {int(k): str(v) for k, v in model.names.items()}
    expected = class_names()
    if names != expected:
        raise IncompatibleModelError(f"{weights.name}: class mapping {names} differs from configs/dataset.yaml {expected}")
    yaml_file = str((getattr(model.model, "yaml", None) or {}).get("yaml_file", ""))
    arch = Path(yaml_file).stem if yaml_file else None
    if architecture and arch != architecture:
        raise IncompatibleModelError(f"{weights.name}: architecture '{arch}' does not match the registry entry '{architecture}'")
    return model, {"sha256": sha, "architecture": arch, "classes": len(names)}
