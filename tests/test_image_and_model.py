"""Invalid image handling, model loading and detection output format."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from src.detection.detector import Detection
from src.detection.image_processor import InvalidImageError, decode_image_bytes, load_image


def test_rejects_unsupported_extension():
    with pytest.raises(InvalidImageError, match="Unsupported"):
        decode_image_bytes(b"GIF89a....", "animation.gif")


def test_rejects_empty_file():
    with pytest.raises(InvalidImageError, match="empty"):
        decode_image_bytes(b"", "photo.jpg")


def test_rejects_corrupted_bytes():
    with pytest.raises(InvalidImageError, match="decoded"):
        decode_image_bytes(b"this is not a jpeg" * 50, "photo.jpg")


def test_rejects_missing_file(tmp_path):
    with pytest.raises(InvalidImageError, match="not found"):
        load_image(tmp_path / "missing.jpg")


def test_decodes_valid_png():
    img = np.zeros((40, 60, 3), np.uint8)
    img[:, :, 2] = 255
    ok, buf = cv2.imencode(".png", img)
    out = decode_image_bytes(buf.tobytes(), "red.png")
    assert out.shape == (40, 60, 3)
    assert out[0, 0, 2] == 255


def test_model_loads_with_dataset_class_names(detector):
    names = detector.names
    assert len(names) == 12
    assert names[0] == "helmet" and names[5] == "Person" and names[11] == "no_vest"
    assert detector.model.task == "detect"


def test_detection_output_format(detector, sample_val_image):
    img = load_image(sample_val_image)
    detections = detector.detect(img)
    assert isinstance(detections, list)
    assert len(detections) > 0, "trained model found nothing on a validation image"
    h, w = img.shape[:2]
    for d in detections:
        assert isinstance(d, Detection)
        assert d.class_name == detector.names[d.class_id]
        assert detector.confidence <= d.confidence <= 1.0
        assert -1 <= d.x1 < d.x2 <= w + 1 and -1 <= d.y1 < d.y2 <= h + 1


def test_detect_rejects_bad_input(detector):
    with pytest.raises(ValueError):
        detector.detect(np.zeros((0, 0, 3), np.uint8))
    with pytest.raises(ValueError):
        detector.detect(None)
