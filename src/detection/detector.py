"""YOLO detector wrapper.

`PPEDetector` loads the application's checkpoint and returns plain `Detection` objects, so the rest of the app
never touches Ultralytics result objects directly.

Which checkpoint: without an explicit `weights` path, the model registry in configs/settings.yaml decides
(`model.active`, with `model.fallback` loaded and logged if the active checkpoint is missing or incompatible;
see src/detection/model_registry.py). Every checkpoint is validated before use: detection task, the 12 class names
of configs/dataset.yaml in the same order, the architecture of its registry entry and, when a model card exists,
its SHA-256. An incompatible checkpoint is never loaded silently.

Class names are read from the checkpoint itself (model.names) and checked against the dataset configuration.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from src.detection.model_registry import (  # noqa: F401  (ModelNotFoundError / file_sha256 re-exported)
    IncompatibleModelError,
    ModelNotFoundError,
    ModelRegistry,
    file_sha256,
    load_validated,
)
from src.utils.paths import TRAINED_DIR, load_settings, project_path

log = logging.getLogger("siteguard.model")


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = round(self.confidence, 4)
        return d


def resolve_device(requested: str = "auto") -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "0"
    return "cpu"


class PPEDetector:
    """Thin, thread-safe wrapper around an Ultralytics YOLO detection model."""

    def __init__(
        self,
        weights: str | Path | None = None,
        device: str | None = None,
        confidence: float | None = None,
        iou: float | None = None,
        image_size: int | None = None,
        model_key: str | None = None,
        settings: dict | None = None,
    ) -> None:
        settings = settings or load_settings()
        inf = settings["inference"]
        self._explicit = weights is not None
        if self._explicit:  # a specific file (tools, tests): validated, no registry, no fallback
            self._order = []
            self.entry = None
            self.weights = project_path(weights)
        else:
            self._order = ModelRegistry.from_settings(settings).load_order(model_key)
            self.entry = self._order[0]
            self.weights = self.entry.weights
        self.model_key = self.entry.key if self.entry else None
        self.status = "not loaded"
        self.load_errors: list[str] = []
        self.identity: dict = {}
        self.device = resolve_device(device or inf["device"])
        self.confidence = float(confidence if confidence is not None else inf["confidence_threshold"])
        self.iou = float(iou if iou is not None else inf["iou_threshold"])
        self._image_size_override = image_size
        size = image_size or (self.entry.image_size if self.entry and self.entry.image_size else None) or inf["image_size"]
        self.image_size = int(size)
        self._model = None
        self._lock = threading.Lock()  # the webcam callback runs in another thread

    # ------------------------------------------------------------------ loading
    def load(self) -> "PPEDetector":
        if self._model is not None:
            return self
        if self._explicit:
            self._model, self.identity = load_validated(self.weights)
            self.status = "explicit weights"
            log.info("Model loaded: %s sha256=%s arch=%s imgsz=%s", self.weights, self.identity["sha256"][:16],
                     self.identity["architecture"], self.image_size)
            return self
        first_error: Exception | None = None
        for i, entry in enumerate(self._order):
            card = entry.card_data()
            try:
                self._model, self.identity = load_validated(entry.weights, entry.architecture,
                                                             card.get("checkpoint_sha256") if card else None)
            except (ModelNotFoundError, IncompatibleModelError) as exc:
                first_error = first_error or exc
                self.load_errors.append(f"{entry.key}: {exc}")
                log.warning("Model '%s' not used: %s", entry.key, exc)
                continue
            self.entry, self.weights, self.model_key = entry, entry.weights, entry.key
            if self._image_size_override is None and entry.image_size:
                self.image_size = int(entry.image_size)
            self.status = "active" if i == 0 else "fallback"
            (log.info if i == 0 else log.warning)(
                "Model %s: key=%s arch=%s sha256=%s imgsz=%s", "loaded" if i == 0 else "FALLBACK loaded", entry.key,
                self.identity["architecture"], self.identity["sha256"][:16], self.image_size)
            return self
        raise first_error

    @property
    def model(self):
        if self._model is None:
            self.load()
        return self._model

    @property
    def names(self) -> dict[int, str]:
        return {int(k): str(v) for k, v in self.model.names.items()}

    # ---------------------------------------------------------------- inference
    def detect(self, image_bgr: np.ndarray, confidence: float | None = None, image_size: int | None = None) -> list[Detection]:
        """Run the model on one BGR image (OpenCV format) and return detections."""
        if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.ndim != 3 or image_bgr.size == 0:
            raise ValueError("detect() expects a non-empty HxWx3 BGR numpy array")
        conf = self.confidence if confidence is None else float(confidence)
        imgsz = self.image_size if image_size is None else int(image_size)
        with self._lock:
            result = self.model.predict(
                image_bgr, conf=conf, iou=self.iou, imgsz=imgsz, device=self.device, verbose=False
            )[0]
        names = result.names
        detections: list[Detection] = []
        if result.boxes is None or len(result.boxes) == 0:
            return detections
        xyxy = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)
        for (x1, y1, x2, y2), c, k in zip(xyxy, confs, classes):
            detections.append(Detection(int(k), str(names[int(k)]), float(c), float(x1), float(y1), float(x2), float(y2)))
        return detections

    # --------------------------------------------------------------------- info
    def info(self) -> dict:
        """Model facts for the dashboard (path, checksum, classes, training source)."""
        data = {
            "model_key": self.model_key,
            "status": self.status,
            "weights": str(self.weights),
            "exists": self.weights.exists(),
            "device": self.device,
            "confidence": self.confidence,
            "image_size": self.image_size,
        }
        if self.load_errors:
            data["load_errors"] = list(self.load_errors)
        if not self.weights.exists():
            return data
        data["size_mb"] = round(self.weights.stat().st_size / 1e6, 2)
        data["sha256"] = (self.identity.get("sha256") or file_sha256(self.weights))[:16]
        data["architecture"] = self.identity.get("architecture")
        data["class_names"] = self.names
        card = self.entry.card_data() if self.entry else None
        if card:
            data["model_card"] = card
        elif self.weights.parent == TRAINED_DIR and (TRAINED_DIR / "MODEL_SOURCE.json").exists():
            data["source"] = json.loads((TRAINED_DIR / "MODEL_SOURCE.json").read_text(encoding="utf-8"))
        return data
