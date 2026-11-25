"""Draw detections and compliance results onto an image (OpenCV, BGR colours).

Camera-quality Fix 4 (2026-11-23): overlay legibility. Box coordinates, colours, label texts and the drawn classes are
unchanged; only the drawing style changed:
* line thickness and font size scale with the image's SHORT side and have readable minimums (small live frames such as
  480x270 used to get 1-px item boxes and a 0.32 font that video compression made unreadable);
* every box gets a thin dark outline under its coloured line, so it stays visible on bright or busy backgrounds;
* labels are kept inside the image (shifted left / placed below or inside the box when there is no room above) and use
  a slightly translucent background so they do not completely hide the worker or PPE underneath.
Previous version: experiments/camera_quality_audit/fixes/backups/annotate.py.before_fix4
"""

from __future__ import annotations

import cv2
import numpy as np

from src.compliance.compliance_analyzer import (
    COMPLIANT_EVIDENCE,
    POTENTIAL_VIOLATION,
    UNCERTAIN,
    ComplianceResult,
)
from src.compliance.worker_association import CLASS_TO_ITEM, PERSON_CLASS
from src.detection.detector import Detection

# BGR colours
POSITIVE_COLOR = (80, 160, 40)     # PPE present: green
NEGATIVE_COLOR = (40, 40, 210)     # missing-PPE class: red
PERSON_COLOR = (170, 120, 60)      # worker box: steel blue
OTHER_COLOR = (0, 190, 230)        # forklift etc.: amber
STATUS_COLORS = {
    POTENTIAL_VIOLATION: (30, 30, 200),
    COMPLIANT_EVIDENCE: (70, 150, 40),
    UNCERTAIN: (0, 150, 240),
}
STATUS_SHORT = {POTENTIAL_VIOLATION: "Potential", COMPLIANT_EVIDENCE: "Compliant", UNCERTAIN: "Uncertain"}

OUTLINE_COLOR = (20, 20, 20)       # dark edge under every coloured line
TEXT_COLOR = (255, 255, 255)
LABEL_ALPHA = 0.82                 # label background opacity
FONT = cv2.FONT_HERSHEY_SIMPLEX


def class_color(name: str) -> tuple[int, int, int]:
    if name == PERSON_CLASS:
        return PERSON_COLOR
    if name in CLASS_TO_ITEM:
        return NEGATIVE_COLOR if CLASS_TO_ITEM[name][1] else POSITIVE_COLOR
    return OTHER_COLOR


def overlay_style(shape: tuple[int, ...]) -> dict:
    """Line and text sizes for an image of this shape (based on the short side, so portrait and landscape match)."""
    short = min(shape[0], shape[1])
    worker_font = float(np.clip(short / 720 * 0.6, 0.42, 0.95))
    item_font = max(0.38, worker_font * 0.85)
    return {
        "worker_thick": max(2, int(round(short / 220))),
        "item_thick": max(2, int(round(short / 300))),
        "worker_font": worker_font,
        "item_font": item_font,
        "text_thick": 1 if worker_font < 0.7 else 2,
        "pad": max(2, int(round(short / 240))),
    }


def _box(img: np.ndarray, p1: tuple[int, int], p2: tuple[int, int], color, thick: int) -> None:
    """Coloured rectangle with a dark outline; the coloured line keeps exactly the box coordinates."""
    cv2.rectangle(img, p1, p2, OUTLINE_COLOR, thick + 2)
    cv2.rectangle(img, p1, p2, color, thick)


def _label(img: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int], scale: float,
           box_bottom: int | None = None, text_thick: int = 1, pad: int = 3) -> None:
    """Label whose bottom edge sits at y (above the box). It is kept inside the image: shifted left at the right edge,
    moved below the box (box_bottom) or inside it when there is no room above."""
    h, w = img.shape[:2]
    (tw, th), base = cv2.getTextSize(text, FONT, scale, text_thick)
    lw, lh = tw + 2 * pad, th + base + 2 * pad
    x0 = int(min(max(0, x), max(0, w - lw)))
    if y - lh >= 0:
        y0 = y - lh                                   # above the box
    elif box_bottom is not None and box_bottom + lh <= h:
        y0 = box_bottom                               # below the box
    else:
        y0 = max(0, min(y, h - lh))                   # inside the top of the box
    x1, y1 = min(w, x0 + lw), min(h, y0 + lh)
    roi = img[y0:y1, x0:x1]
    if roi.size:
        bg = np.empty_like(roi)
        bg[:] = color
        cv2.addWeighted(bg, LABEL_ALPHA, roi, 1 - LABEL_ALPHA, 0, dst=roi)
    cv2.putText(img, text, (x0 + pad, y0 + pad + th), FONT, scale, TEXT_COLOR, text_thick, cv2.LINE_AA)


def draw_detections(image: np.ndarray, detections: list[Detection], include_person: bool = True) -> np.ndarray:
    out = image.copy()
    st = overlay_style(out.shape)
    drawn = []
    for d in detections:
        if d.class_name == PERSON_CLASS and not include_person:
            continue
        color = class_color(d.class_name)
        p1, p2 = (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2))
        _box(out, p1, p2, color, st["item_thick"])
        drawn.append((d, p1, p2, color))
    for d, p1, p2, color in drawn:  # labels after all boxes, so a label is never hidden under another box
        _label(out, f"{d.class_name} {d.confidence:.2f}", p1[0], p1[1], color, st["item_font"],
               box_bottom=p2[1], text_thick=1, pad=max(2, st["pad"] - 1))
    return out


def draw_compliance(image: np.ndarray, result: ComplianceResult, show_items: bool = True) -> np.ndarray:
    """Worker boxes coloured by status, plus the PPE/no-PPE boxes."""
    item_dets = [d for d in result.all_detections if d.class_name != PERSON_CLASS] if show_items else []
    out = draw_detections(image, item_dets, include_person=False)
    st = overlay_style(out.shape)
    for w in result.workers:
        p = w.person
        _box(out, (int(p.x1), int(p.y1)), (int(p.x2), int(p.y2)), STATUS_COLORS[w.status], st["worker_thick"])
    for w in result.workers:
        p = w.person
        text = f"{w.worker_ref} {STATUS_SHORT[w.status]}"
        if w.violations:
            text += ": " + ", ".join(f"no {v.item}" for v in w.violations)
        _label(out, text, int(p.x1), int(p.y1), STATUS_COLORS[w.status], st["worker_font"],
               box_bottom=int(p.y2), text_thick=st["text_thick"], pad=st["pad"])
    return out
