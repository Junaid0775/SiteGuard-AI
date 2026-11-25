"""Associate PPE / missing-PPE detections with worker (Person) boxes.

The model detects objects independently: a `helmet` box is not linked to any
person. This module links each item box to at most ONE worker using simple
bounding-box geometry, so one detection can never create alerts for several
workers.

Rules for one item box `d` and one worker box `p`:
1. Expand `p` by `person_box_margin` (helmets and boots often stick out).
2. containment = area(d ∩ expanded p) / area(d). Must be >= `min_containment`.
3. region factor = 1.0 if the centre of `d` lies in the expected vertical band
   of the body for that item (helmet near the top, boots near the bottom...),
   otherwise 0.5.
4. centring factor = 0.8 + 0.2 * (1 - horizontal offset / half width), in [0.8, 1].
5. score = containment * region factor * centring factor.

The item goes to the worker with the highest score. If the second-best worker
scores within `ambiguity_margin` of the best, the item is marked AMBIGUOUS and
given to nobody (overlapping workers are handled cautiously).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.detection.detector import Detection

# Expected vertical position of each item's centre, as a fraction of person height
# (0 = top of the person box, 1 = bottom).
ITEM_REGIONS: dict[str, tuple[float, float]] = {
    "helmet": (-0.10, 0.40),
    "goggles": (-0.05, 0.35),
    "vest": (0.10, 0.80),
    "gloves": (0.10, 0.95),
    "boots": (0.65, 1.10),
}

# Which detector class belongs to which PPE item, and whether it is negative evidence.
CLASS_TO_ITEM: dict[str, tuple[str, bool]] = {
    "helmet": ("helmet", False),
    "no_helmet": ("helmet", True),
    "vest": ("vest", False),
    "no_vest": ("vest", True),
    "gloves": ("gloves", False),
    "no_gloves": ("gloves", True),
    "boots": ("boots", False),
    "no_boots": ("boots", True),
    "goggles": ("goggles", False),
    "no_goggle": ("goggles", True),
}

PERSON_CLASS = "Person"


def box_area(b: tuple[float, float, float, float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    inter = intersection(a, b)
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def containment(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> float:
    """Share of `inner`'s area that lies inside `outer` (0..1)."""
    a = box_area(inner)
    return intersection(inner, outer) / a if a > 0 else 0.0


def expand_box(b: tuple[float, float, float, float], margin: float) -> tuple[float, float, float, float]:
    w, h = b[2] - b[0], b[3] - b[1]
    return (b[0] - margin * w, b[1] - margin * h, b[2] + margin * w, b[3] + margin * h)


@dataclass
class AssociationParams:
    min_containment: float = 0.60
    ambiguity_margin: float = 0.15
    person_box_margin: float = 0.10


def association_score(item: Detection, item_name: str, person: Detection, params: AssociationParams) -> float:
    """Score in [0, 1] for linking `item` to `person`; 0 means 'not possible'."""
    c = containment(item.box, expand_box(person.box, params.person_box_margin))
    if c < params.min_containment:
        return 0.0
    cx, cy = item.center
    rel_y = (cy - person.y1) / person.height if person.height > 0 else 0.5
    lo, hi = ITEM_REGIONS.get(item_name, (0.0, 1.0))
    region_factor = 1.0 if lo <= rel_y <= hi else 0.5
    half_w = person.width / 2 if person.width > 0 else 1.0
    offset = min(1.0, abs(cx - person.center[0]) / half_w)
    centring = 0.8 + 0.2 * (1.0 - offset)
    return c * region_factor * centring


@dataclass
class AssociationResult:
    # worker index -> list of item detections assigned to that worker
    assigned: dict[int, list[Detection]] = field(default_factory=dict)
    ambiguous: list[Detection] = field(default_factory=list)
    unassigned: list[Detection] = field(default_factory=list)
    scores: dict[int, float] = field(default_factory=dict)  # id(detection) -> winning score


def associate_items(workers: list[Detection], items: list[Detection], params: AssociationParams) -> AssociationResult:
    """Give every PPE/no-PPE detection to at most one worker."""
    result = AssociationResult(assigned={i: [] for i in range(len(workers))})
    for item in items:
        mapping = CLASS_TO_ITEM.get(item.class_name)
        if mapping is None:
            continue  # e.g. forklift: not personal equipment
        item_name = mapping[0]
        scores = sorted(
            ((association_score(item, item_name, w, params), i) for i, w in enumerate(workers)),
            reverse=True,
        )
        if not scores or scores[0][0] <= 0:
            result.unassigned.append(item)
            continue
        best_score, best_idx = scores[0]
        if len(scores) > 1 and scores[1][0] > 0 and best_score - scores[1][0] < params.ambiguity_margin:
            result.ambiguous.append(item)
            continue
        result.assigned[best_idx].append(item)
        result.scores[id(item)] = best_score
    return result
