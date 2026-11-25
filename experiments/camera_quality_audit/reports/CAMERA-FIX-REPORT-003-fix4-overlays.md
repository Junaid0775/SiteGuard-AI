# CAMERA-FIX-REPORT-003 — Phase 3: Fix 4, detection-overlay legibility

**Date:** 2026-11-23, 12:47–12:58 IST. **Status:** **implemented and verified.**

## 1. Change

**File:** `src/detection/annotate.py` (pre-change copy: `fixes/backups/annotate.py.before_fix4`).

| Function or value | Before | After |
|---|---|---|
| Size basis | image **width** | image **short side**, so portrait and landscape behave alike |
| Item box line | `max(1, round(width/600))`, **1 px** below 900 px width | `max(2, round(short/300))`, **≥ 2 px** |
| Worker box line | `max(2, round(width/450))` | `max(2, round(short/220))` (2 px at 270–360 p, 3 px at 720 p, 5 px at 1080 p) |
| Item label font | `max(0.4, width/1600) × 0.8`, **0.32** at 480–640 px | `max(0.38, 0.85 × worker font)` |
| Worker label font | `max(0.4, min(1.0, width/1800))` | `clip(short/720 × 0.6, 0.42, 0.95)` |
| Box contrast | coloured line only | **dark outline** (`OUTLINE_COLOR`, +2 px) under the coloured line; the coloured line keeps the exact coordinates |
| Label placement | above the box (could be clipped at the right edge); below the box if `y1 < 40` | above the box if there is room, else below the box, else inside its top. **Shifted left to stay inside the image** |
| Label background | opaque | 82 % opaque, so workers and PPE underneath stay partly visible |
| Drawing order | label right after each box | all boxes first, then all labels, so labels are not crossed by later item boxes |

**New helper:** `overlay_style(shape)` returns the sizes and is tested.

**Unchanged:**
- box coordinates;
- colours (`STATUS_COLORS`, class colours);
- label texts;
- which detections are drawn;
- drawing on a copy;
- output shape.

## 2. Measurements (`evidence/fix4_overlay_timing.json`)

Inputs: a dataset validation image (no camera content), the real YOLO26n detections and the real compliance analysis.

| Frame | Detections / workers | Draw time before | Draw time after |
|---|---|---|---|
| 480 × 270 | 44 / 8 | 0.29 ms | 0.56 ms |
| 640 × 360 | 43 / 7 | 0.28 ms | 0.57 ms |
| 1280 × 720 | 42 / 7 | 0.44 ms | 0.81 ms |

- **Speed:** the added 0.3–0.4 ms per frame is negligible against the 33 ms frame budget.
- **Visual comparison:** `evidence/fix4_overlay_{480x270,640x360,1280x720}_old_vs_new.png` (left old, right new). Thicker outlined boxes, readable labels, and no labels cut at the frame edge.
- **Not affected:** frame rate, dropped frames, CPU and memory.

## 3. Tests

**New: `tests/test_annotation_overlay.py`, 5 tests:**
- shape, dtype and input preserved;
- **the coloured line pixels lie exactly on the detection coordinates** (worker left, right and bottom edges, and the item edge);
- readable minimum sizes at 480 × 270, with upper bounds;
- labels stay inside the image at the edges;
- drawing is deterministic and fast (20 boxes on 720 p in under 25 ms).

**Existing:**
- `test_frame_sync.py` (13), which checks box colour at exact coordinates;
- `test_resolution_coordinates.py` (13).

All pass.

**Full suite: 175 passed** (170 + 5).

## 4. Rollback

Copy `fixes/backups/annotate.py.before_fix4` back to `src/detection/annotate.py` and delete `tests/test_annotation_overlay.py`.

## 5. Remaining issue

Crowded scenes (more than 40 detections) still have overlapping labels. That is inherent to labelling every detection, and would need a label-declutter policy, which is out of scope.
