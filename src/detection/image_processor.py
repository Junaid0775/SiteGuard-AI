"""Image loading, validation and single-image inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from src.compliance.compliance_analyzer import ComplianceAnalyzer, ComplianceResult
from src.detection.annotate import draw_compliance
from src.detection.detector import Detection, PPEDetector

SUPPORTED_IMAGE_TYPES = ("jpg", "jpeg", "png", "bmp", "webp")
MAX_IMAGE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_IMAGE_SIDE = 8000


class InvalidImageError(ValueError):
    """The file is not a supported, decodable image."""


def decode_image_bytes(data: bytes, filename: str = "upload") -> np.ndarray:
    """Decode uploaded bytes into a BGR image, with clear errors for bad input."""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext and ext not in SUPPORTED_IMAGE_TYPES:
        raise InvalidImageError(f"Unsupported file type '.{ext}'. Supported: {', '.join(SUPPORTED_IMAGE_TYPES)}")
    if not data:
        raise InvalidImageError("The file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidImageError(f"Image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise InvalidImageError("The file could not be decoded as an image (corrupted or not an image).")
    if max(img.shape[:2]) > MAX_IMAGE_SIDE:
        raise InvalidImageError(f"Image side longer than {MAX_IMAGE_SIDE} px is not supported.")
    return img


def load_image(path: str | Path) -> np.ndarray:
    path = Path(path)
    if not path.exists():
        raise InvalidImageError(f"File not found: {path}")
    return decode_image_bytes(path.read_bytes(), path.name)


def encode_jpeg(image_bgr: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


@dataclass
class ImageInspection:
    image: np.ndarray
    detections: list[Detection]
    compliance: ComplianceResult
    annotated: np.ndarray

    def detection_rows(self) -> list[dict]:
        return [
            {"Class": d.class_name, "Confidence": round(d.confidence, 3), "x1": int(d.x1), "y1": int(d.y1), "x2": int(d.x2), "y2": int(d.y2)}
            for d in sorted(self.detections, key=lambda d: (d.class_name, -d.confidence))
        ]

    def class_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.detections:
            counts[d.class_name] = counts.get(d.class_name, 0) + 1
        return counts


def inspect_image(
    image_bgr: np.ndarray,
    detector: PPEDetector,
    analyzer: ComplianceAnalyzer,
    confidence: float | None = None,
    image_size: int | None = None,
) -> ImageInspection:
    detections = detector.detect(image_bgr, confidence=confidence, image_size=image_size)
    compliance = analyzer.analyze(detections)
    annotated = draw_compliance(image_bgr, compliance)
    return ImageInspection(image_bgr, detections, compliance, annotated)
