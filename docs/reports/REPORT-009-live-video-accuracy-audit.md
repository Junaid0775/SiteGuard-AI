# REPORT-009 — Live / Video Detection Accuracy Audit

**Date:** 2026-11-19 **Status:** Audit complete. **No fix has been applied yet.** As requested, this report stops before any implementation change.

**Labels used in this report:**
- **[MEASURED]** = a number produced by code in this audit against real ground truth (or a direct measurement such as timing).
- **[DERIVED]** = follows directly from measured numbers plus code reading, but was not itself measured end-to-end.
- **[HYPOTHESIS]** = plausible but not tested.

---

## A. Task summary

- **Requested:** find out why live webcam and video detection perform worse than still-image detection, and why live detects objects incorrectly. Compare both pipelines on the same frames, separate model errors from compliance-analysis errors, measure everything, and test configuration options. Do not retrain, do not change the model or dataset, and do not make speculative fixes.
- **Done:**
  - a code-level comparison of the three pipelines;
  - a reproducible measurement harness (`src/evaluation/live_audit.py`) checked against the app's own detector;
  - 29 controlled conditions on the 200 labelled val images (2,961 boxes);
  - a frame-skipping simulation on 600 labelled frames;
  - latency and device tests;
  - a WebRTC colour-conversion check;
  - a detection-to-compliance error analysis;
  - 149 real webcam frames run through both pipelines, 10 of them manually labelled.
- **Completion:** the audit is complete. The recommended fixes are listed in §8 and are **not implemented**.

## B. Summary of root causes (ranked by measured impact on what the user sees)

| # | Cause | Kind | Evidence |
|---|---|---|---|
| 1 | **Stale boxes on skipped frames.** Live analyses every 3rd frame, video every 5th, and the frames in between redraw the *previous* result on the *new* frame. On anything that moves, the boxes are drawn where the object used to be. | Pipeline (display) | [MEASURED] At 10 px/frame motion, displayed precision drops from 0.790 to **0.508** (every 3rd) and **0.351** (every 5th). At 20 px/frame it drops from 0.804 to 0.375 / 0.242. |
| 2 | **Live runs at imgsz 480, image upload at 640.** | Pipeline (config) | [MEASURED] On the val images, mAP50-95 falls from 0.514 to **0.454** and recall from 0.745 to **0.676**. Most of the loss is in the missing-PPE classes (no_helmet recall 0.615 → 0.497). The compliance layer finds **10 % fewer potential violations** (violation recall 0.542 → 0.489). The speed gain is under 1 ms per frame. |
| 3 | **Webcam scenes are outside the training data** (indoor, close range, reclining, camera looking up). The person's head and torso are larger, and the torso is wider, than anything in the training set. | Model / data | [MEASURED] On real webcam frames, every error is a missing-PPE box with low confidence (0.25–0.42) and a wrong extent. At imgsz 640 the head is 178 px tall, larger than **every** no_helmet box in training (maximum 172 px). The torso aspect is 4.2, against ≤ 1.56 for 99 % of training no_vest boxes. Image upload at 640 scores P 0.40 / R 0.33 on these frames; imgsz 320 scores P 0.97 / R 1.00. *Single scene, single person.* |
| 4 | **Motion blur and low light** (typical of indoor webcams and moving subjects). | Environment | [MEASURED] 17 px blur: mAP50-95 −0.143, recall −16.8 points. Dark scene: −0.095, with contradictory box pairs rising from 38 to 57. |
| 5 | **Contradictory and duplicate boxes on one object** (e.g. helmet *and* no_helmet; two nested no_helmet boxes). NMS is per class at IoU 0.5. | Post-processing | [MEASURED] 12–57 contradicting pairs per 200 images across conditions (33 for still images), 0 with class-agnostic NMS. Wrong-class false positives are mostly complement pairs (boots↔no_boots, helmet vs no_helmet …). On webcam frames, the live path showed two nested no_helmet boxes (IoU ≈ 0.37) in 17 of 50 analysed frames. |
| 6 | **WebRTC compression at low bitrate** (the first seconds of a stream). | Transport | [MEASURED] Against the same uncompressed 720p frames: VP8 at 300 kbps −0.049 mAP50-95, at 1 Mbps −0.006, at 2.5 Mbps −0.003; H.264 at 1 Mbps −0.041. On the real webcam frames, VP8 at 1 Mbps reduced recall from 0.633 to 0.533 (10 frames). |

**Ruled out as causes (all [MEASURED]):**
- BGR/RGB channel order and colour conversion: channel order preserved, error ≤ 4/255.
- Capture resolution: 720p-class +0.003 and VGA-class +0.004 mAP50-95 against still_640.
- YUV 4:2:0 chroma subsampling: 0.000 against the same 720p frames.
- Device: MPS and CPU give identical TP/FP/FN.
- Bounding-box scaling: the harness matches the app 60/60, and webcam boxes align with the labels.
- Inference latency: about 8 ms per frame, far below the 33 ms frame interval. [DERIVED] So streamlit-webrtc's async mode should not be dropping frames.
- The compliance rules themselves: on the same detections the rules behave as specified, and false violations stay at 5–6 per 481 workers in every configuration.

**Answer to the primary question ("live detects objects incorrectly"):** two different things happen.
1. On moving scenes, boxes look wrong because they are **stale** (cause 1). This is a SiteGuard pipeline issue and can be fixed without touching the model.
2. On a desk or bedroom webcam, the **model itself** mislocalises missing-PPE boxes, because such close-range scenes are outside its training data (cause 3). This happens in *both* the image-upload and live pipelines. Live's smaller imgsz changes *which* errors appear, not whether they appear.

---

## C. Pipeline comparison (code inspection)

| Setting | Image upload | Video upload | Live webcam |
|---|---|---|---|
| Source and decode | `cv2.imdecode` → BGR at full resolution (e.g. 2048×1360) — `image_processor.py:decode_image_bytes` | `cv2.VideoCapture` → BGR, codec-compressed file — `video_processor.py` | Browser camera → WebRTC VP8/H.264 → aiortc decode (yuv420p) → `frame.to_ndarray("bgr24")` — `app.py:290` |
| Requested capture size | n/a | file resolution | ideal 1280×720 — `app.py:301` |
| **Inference size (imgsz)** | **640** (`cfg["image_size"]`, `app.py:385`) | **640** (`app.py:435`) | **480** (`cfg["live_image_size"]`, `app.py:283`; `settings.yaml:42` "smaller resolution for live speed") |
| Confidence | 0.25 | 0.25 | 0.25 |
| NMS | Ultralytics default `nms=None`: **one-to-many head + NMS, IoU 0.5, per class**. `detector.py:139` passes `iou=0.5`, and `agnostic_nms` is not set. | same | same |
| Device | MPS (shared `PPEDetector`, lock) | MPS | MPS |
| Frames analysed | 1 | every **5th** frame (`video_processor.py:102`) | every **3rd** delivered frame (`camera_processor.py:74`). streamlit-webrtc async mode also processes only the newest queued frame (`streamlit_webrtc/process.py:126`). |
| **Skipped frames show** | n/a | **the last result drawn on the new frame** (`video_processor.py:116`) | **the last result drawn on the new frame** (`camera_processor.py:96`) |
| Compliance rules | same `ComplianceAnalyzer` | same | same |
| Events | 1 hit | 3 hits, cooldown 30 s (video time) | 3 hits, cooldown 30 s (wall clock) |

Code-inspection findings:
- `configs/settings.yaml:13` says the NMS IoU is "ignored by NMS-free YOLO26 heads". **This is wrong.** [MEASURED] Probing the predictor shows `nms=None` → AutoBackend `end2end=False`, so the one-to-many head with NMS is used and the IoU threshold is active (IoU 0.7 changes the box count: 41 → 47 on one image). `nms=False` would select the NMS-free head.
- The Ultralytics `val` mAP in docs/EVALUATION.md (0.523) used NMS IoU 0.7. The app predicts with IoU 0.5. The audit's still-image baseline uses the app's settings (0.514), which is why it differs slightly.
- The live callback converts frames with `to_ndarray(format="bgr24")` / `from_ndarray(..., "bgr24")`, which is the correct BGR order for Ultralytics numpy input (also verified by measurement in §5.5).

---

## D. Method — how everything was measured

1. **Ground truth.** The official val split (200 images, 2,961 labelled boxes), plus 10 manually labelled webcam frames (§5.6). No unlabelled image was scored.
2. **Harness = the app's detector.** `Predictor` calls `YOLO.predict` with the same arguments as `PPEDetector.detect`. [MEASURED] 60/60 identical outputs against the real `PPEDetector.detect` (30 images × {640 original, 480 on 720p}) — `experiments/live_audit/harness_equivalence.json`. Also, filtering conf-0.001 predictions at 0.25 gives exactly the same boxes as running at 0.25 (60/60).
3. **Metrics.**
   - mAP50 and mAP50-95 use Ultralytics' own `ap_per_class`, with matching identical to Ultralytics' `match_predictions`. Note that `ap_per_class` reports 0.995 for a perfect detector.
   - At the app's threshold (conf 0.25, IoU 0.5) the harness counts TP / FP / FN, precision, recall and F1.
   - Every FP is typed as **duplicate** (same-class GT already matched), **wrong_class** (IoU ≥ 0.5 with a GT of another class), **localization** (0.1 ≤ IoU < 0.5) or **background** (IoU < 0.1).
   - **Contradiction pairs** = boxes of complementary classes (helmet/no_helmet …) with IoU ≥ 0.5.
4. **Conditions.** Each transform reproduces one property of the live or video path (resize, YUV round trip, VP8/H.264 encode-decode of a 15-frame static stream with sensor noise σ = 3, blur, lighting, webcam-style crop, imgsz, NMS mode). Ground truth is transformed with the image. Partly visible objects after cropping become ignore regions.
5. **Unit tests for the evaluator.** 13 tests in `tests/test_live_audit.py` cover perfect, duplicate, wrong-class, background and localization cases, ignore regions, threshold independence, crop re-mapping, channel order, codec frame counts and the compliance-effect logic.

---

## E. Measured results

### 5.1 Configuration and environment conditions (val, 200 images, 2,961 GT, conf 0.25)

`experiments/live_audit/conditions.json`.

| Condition | imgsz | mAP50 | mAP50-95 | P | R | TP | FP | FN | FP/img | Contra |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **still_640 (image upload, reference)** | 640 | 0.730 | **0.514** | 0.884 | **0.745** | 2206 | 289 | 755 | 1.45 | 33 |
| still_320 | 320 | 0.554 | 0.340 | 0.848 | 0.557 | 1649 | 295 | 1312 | 1.48 | 29 |
| still_480 | 480 | 0.675 | 0.457 | 0.880 | 0.683 | 2023 | 277 | 938 | 1.39 | 33 |
| still_800 | 800 | 0.759 | 0.539 | 0.879 | 0.773 | 2289 | 315 | 672 | 1.57 | 37 |
| still_960 | 960 | 0.771 | 0.540 | 0.873 | 0.792 | 2346 | 341 | 615 | 1.71 | 36 |
| cam720 (1280-px frame) | 640 | 0.735 | 0.517 | 0.888 | 0.746 | 2208 | 279 | 753 | 1.40 | 38 |
| cam720 | 480 | 0.675 | 0.458 | 0.882 | 0.678 | 2009 | 268 | 952 | 1.34 | 31 |
| cam480 (640-px frame) | 640 | 0.730 | 0.518 | 0.886 | 0.743 | 2200 | 282 | 761 | 1.41 | 40 |
| cam480 | 480 | 0.674 | 0.459 | 0.883 | 0.680 | 2013 | 267 | 948 | 1.33 | 39 |
| cam720 + YUV 4:2:0 | 640 | 0.732 | 0.517 | 0.889 | 0.743 | 2200 | 275 | 761 | 1.38 | 36 |
| cam720 + noise σ3 (codec control) | 640 | 0.732 | 0.516 | 0.891 | 0.746 | 2209 | 270 | 752 | 1.35 | 36 |
| cam720 + VP8 300 kbps | 640 | 0.689 | 0.468 | 0.864 | 0.700 | 2073 | 326 | 888 | 1.63 | 43 |
| cam720 + VP8 1 Mbps | 640 | 0.723 | 0.511 | 0.882 | 0.734 | 2173 | 292 | 788 | 1.46 | 36 |
| cam720 + VP8 2.5 Mbps | 640 | 0.731 | 0.514 | 0.890 | 0.746 | 2208 | 272 | 753 | 1.36 | 39 |
| cam720 + H.264 1 Mbps | 640 | 0.696 | 0.476 | 0.866 | 0.706 | 2091 | 324 | 870 | 1.62 | 33 |
| **live_now (720p + VP8 1 Mbps + imgsz 480)** | 480 | 0.670 | **0.454** | 0.877 | **0.676** | 2002 | 280 | 959 | 1.40 | 28 |
| cam720 + blur 9 px | 640 | 0.696 | 0.475 | 0.886 | 0.696 | 2061 | 264 | 900 | 1.32 | 51 |
| cam720 + blur 17 px | 640 | 0.614 | 0.374 | 0.887 | 0.578 | 1710 | 217 | 1251 | 1.08 | 34 |
| cam720 + blur 31 px | 640 | 0.432 | 0.225 | 0.909 | 0.360 | 1066 | 107 | 1895 | 0.54 | 12 |
| cam720 dim (×0.5, noise 4) | 640 | 0.721 | 0.505 | 0.896 | 0.728 | 2155 | 251 | 806 | 1.25 | 25 |
| cam720 dark (×0.25, noise 8) | 640 | 0.651 | 0.422 | 0.875 | 0.632 | 1870 | 266 | 1091 | 1.33 | 57 |
| still_640, NMS IoU 0.3 | 640 | 0.725 | 0.510 | 0.892 | 0.742 | 2197 | 267 | 764 | 1.33 | 33 |
| still_640, NMS IoU 0.7 | 640 | 0.726 | 0.520 | 0.834 | 0.747 | 2211 | 439 | 750 | 2.19 | 33 |
| still_640, class-agnostic NMS | 640 | 0.716 | 0.508 | 0.891 | 0.737 | 2182 | 266 | 779 | 1.33 | **0** |
| still_640, NMS-free head | 640 | 0.714 | 0.502 | 0.814 | 0.708 | 2096 | 478 | 865 | 2.39 | 30 |
| live stream 640, class-agnostic NMS | 640 | 0.710 | 0.504 | 0.889 | 0.726 | 2149 | 267 | 812 | 1.33 | **0** |
| framing reference (164 images, uncropped) | 640 | 0.849 | 0.633 | 0.910 | 0.860 | 1795 | 177 | 292 | 1.08 | 33 |
| webcam-style head+torso crop (164) | 640 | 0.830 | 0.613 | 0.910 | 0.870 | 1016 | 101 | 152 | 0.62 | 11 |
| webcam-style head+torso crop (164) | 480 | 0.837 | 0.628 | 0.906 | 0.875 | 1022 | 106 | 146 | 0.65 | 14 |

**False-positive types at conf 0.25 [MEASURED]:**

| Condition | Total FP | Localization | Wrong class | Background | Duplicate |
|---|---:|---:|---:|---:|---:|
| still_640 | 289 | 137 | 93 | 53 | 6 |
| live_now | 280 | 136 | 85 | 49 | 10 |

The most common wrong-class confusions at still_640 are boots on true no_boots (26), helmet on true no_helmet (16), gloves on true no_gloves (10) and vest on true no_vest (9). In other words, the model mostly confuses an item with its own "missing" class.

Background FPs in live_now are mostly Person (15), gloves (12), forklift (7) and helmet (6). Example (`examples/live_now_2_…`): "forklift" boxes on wire-mesh cages of metal parts, and "Person" on a seated forklift driver who is not in the dataset labels. That second one is a *label omission*, which this evaluator counts as an FP.

**Per-class recall, still_640 → live_now [MEASURED]:**
- helmet 0.789 → 0.701
- vest 0.838 → 0.774
- gloves 0.740 → 0.693
- boots 0.715 → 0.603
- Person 0.902 → 0.863
- **no_helmet 0.615 → 0.497**
- no_vest 0.623 → 0.546
- no_gloves 0.567 → 0.498

Precision changes little for most classes (within ±0.05). The exceptions are no_boots (0.889 → 0.784) and the weak class no_goggle (0.467 → 0.346). Live mainly **misses more**; it does not invent many more boxes on this data.

**Confidence-threshold sweep [MEASURED]** (`threshold_sweep` in conditions.json):

| Condition | conf | P | R | F1 | FP/img | Contra |
|---|---:|---:|---:|---:|---:|---:|
| still_640 | 0.15 | 0.815 | 0.770 | 0.792 | 2.58 | 55 |
| still_640 | **0.25** | 0.884 | 0.745 | **0.809** | 1.45 | 33 |
| still_640 | 0.35 | 0.922 | 0.720 | 0.808 | 0.91 | 19 |
| still_640 | 0.45 | 0.948 | 0.698 | 0.804 | 0.56 | 11 |
| live_now | 0.25 | 0.877 | 0.676 | 0.764 | 1.40 | 28 |
| live_now | 0.35 | 0.913 | 0.656 | 0.763 | 0.92 | 19 |
| webcam-style crop 640 | 0.25 | 0.910 | 0.870 | 0.889 | 0.62 | 11 |
| webcam-style crop 640 | 0.35 | 0.933 | 0.854 | 0.892 | 0.44 | 4 |

F1 is flat between 0.25 and 0.35. Lowering the threshold below 0.25 adds about 1.1 FP per image for +2.5 points of recall, so it is **not** recommended.

### 5.2 Frame skipping and stale boxes (600 labelled frames)

40 val images, each turned into a 15-frame horizontal pan at 720p. Inference at imgsz 480 (current live), conf 0.25. The boxes *displayed* on every frame are scored against that frame's moved ground truth. `overlay_staleness.json`.

| Motion (px/frame at 720p) | Every frame (P / R / F1) | Every 3rd — current live | Every 5th — current video |
|---:|---|---|---|
| 0 | 0.800 / 0.433 / 0.562 | 0.800 / 0.433 / 0.562 | 0.800 / 0.433 / 0.562 |
| 4 | 0.801 / 0.461 / 0.585 | 0.729 / 0.418 / 0.531 | 0.580 / 0.334 / 0.424 |
| 10 | 0.790 / 0.474 / 0.593 | **0.508** / 0.305 / 0.381 | **0.351** / 0.212 / 0.264 |
| 20 | 0.804 / 0.516 / 0.629 | **0.375** / 0.241 / 0.293 | **0.242** / 0.158 / 0.191 |

Compare rows only within the same speed: faster pans use a narrower crop window, which changes the image set. The absolute level is low because the first 40 val images are the harder wide-scene images. At realistic walking speed, **more than half of the displayed boxes are wrong purely because they are stale.**

### 5.3 Latency (720p frame, after warm-up, 40 runs)

`latency.json`.

| Device | imgsz | detect ms (mean / p95) | full callback ms (detect + rules + draw) | max analysed fps |
|---|---:|---:|---:|---:|
| MPS | 320 | 6.7 / 8.0 | 6.9 | 144 |
| MPS | **480** | 6.9 / 7.0 | 7.0 | 142 |
| MPS | **640** | 7.7 / 7.9 | 7.9 | 127 |
| MPS | 800 | 9.1 / 10.1 | 9.2 | 108 |
| MPS | 960 | 10.0 / 10.3 | 10.2 | 99 |
| CPU | 480 | 11.2 / 12.6 | 11.4 | 88 |
| CPU | 640 | 15.8 / 18.5 | 16.0 | 62 |
| CPU | 960 | 28.1 / 28.8 | 28.3 | 35 |

[DERIVED] Analysing **every** 30 fps frame at 640 on MPS uses about 24 % of the frame budget. Neither imgsz 480 nor frame skipping is needed for speed on this machine. Frame conversion and the aiortc output encode are not included; those were not measured.

### 5.4 Device parity (val, imgsz 640)

`device_parity.json`. [MEASURED]

| | mAP50 | mAP50-95 | P | R | TP / FP / FN |
|---|---:|---:|---:|---:|---|
| MPS | 0.72964 | 0.51423 | 0.884 | 0.745 | 2206 / 289 / 755 |
| CPU | 0.72964 | 0.51423 | 0.884 | 0.745 | 2206 / 289 / 755 |

All 200 images have identical class sets on both devices. The maximum box or confidence difference is 0.0018.

### 5.5 WebRTC colour conversion

`colour_check.json`. [MEASURED] BGR → yuv420p → BGR through PyAV/libswscale, the same calls as the live callback:
- Channel order preserved: red stays red, blue stays blue.
- Largest patch error: 4/255.
- Hi-vis yellow (0,230,230) → (0,230,229); hi-vis orange (0,120,255) → (0,120,252).
- Mean absolute error on a site photo: 1.26/255.

**Colour handling is not a cause.**

### 5.6 Real webcam frames — same frames through both pipelines

- **Capture** (`scripts/capture_webcam_frames.py`): 149 frames, 1280×720, 29.8 fps, MacBook Air camera.
- **Scene:** one person reclining indoors, no PPE, camera looking up. Near-static: the measured head shift is ≤ 11 px between labelled frames.
- **Ground truth:** 10 frames (every 15th), labelled manually with an 80-px coordinate grid using the dataset's own box conventions, checked against val examples: no_helmet = whole head from hair to chin; no_vest = torso; Person = whole visible person. Labels were propagated by measured template-matching shift (match score ≥ 0.98) and every frame was checked visually. That gives 30 GT objects (10 Person, 10 no_helmet, 10 no_vest). The eye band is an *ignore* region for no_goggle, because the dataset is inconsistent about bare eyes. No hands are visible. Method recorded in `webcam/labels/LABELLING.json`.
- **Pipelines:**
  - image upload = `inspect_image(…, imgsz 640)` on the raw frames;
  - live = `LiveFrameProcessor` (every 3rd frame, imgsz 480) on the same frames after a real VP8 1 Mbps encode/decode of the whole sequence.

**Unlabelled comparison, all frames** (`webcam_summary.json`) [MEASURED]:
- Image upload over 149 frames: Person 149, no_helmet 97, no_vest 105.
- Live over 50 analysed frames: Person 50, no_helmet 59, no_gloves 1, **no_vest 0**.
- **No PPE-present class (helmet, vest, gloves, boots, goggles) was predicted on any frame by either pipeline.** So there were no "background object classified as PPE" errors in this scene.
- All no_helmet and almost all no_vest boxes have confidence **0.25–0.42**. They sit just above the 0.25 threshold, so they flicker.
- Live had two nested no_helmet boxes (whole head plus upper head, IoU ≈ 0.37, so NMS at 0.5 keeps both) in **17 of 50** analysed frames. Image upload had this in 1 of 149.
- Live raised 1 no_gloves box (0.31) on the forearm at the frame edge. It's a false positive, because no hand is visible.
- Image upload vs live on the analysed frames: 70 boxes matched, 45 only in image upload, 40 only in live.
- VP8 transport alone (live code, raw vs transported): 107 matched, 20 lost, 3 added.

**Accuracy against the manual labels (10 frames, 30 GT, conf 0.25)** (`webcam_summary.json`, `webcam_sweep.json`) [MEASURED]:

| Pipeline / setting | TP | FP | FN | P | R | FP type |
|---|---:|---:|---:|---:|---:|---|
| Image upload, imgsz 640 | 10 | 15 | 20 | 0.400 | 0.333 | all localization |
| Live code, raw frames, 480 | 19 | 6 | 11 | 0.760 | 0.633 | localization |
| Live, VP8 1 Mbps, 480 (current live) | 16 | 5 | 14 | 0.762 | 0.533 | localization |
| Live, VP8, 640 | 11 | 15 | 19 | 0.423 | 0.367 | localization |
| Live, VP8, 800 | 10 | 13 | 20 | 0.435 | 0.333 | localization |
| Raw, **320** | **30** | 1 | **0** | **0.968** | **1.000** | — |
| Raw, 416 | 20 | 9 | 10 | 0.690 | 0.667 | localization (no_vest missed) |
| VP8, **320** | 26 | 5 | 4 | 0.839 | 0.867 | — |
| Raw 480, NMS IoU 0.3 | 17 | 2 | 13 | 0.895 | 0.567 | — |

What the errors look like (`webcam/examples/compare_*.jpg`):
- at **640**, the no_helmet box covers only the top half of the head, and the no_vest box lands on the bed and blanket beside the person;
- at **480**, the head gets two nested boxes, and no_vest disappears.

Person is found in every frame at every size.

**Why** (`object_scale.json`) [MEASURED]:

| Object | Webcam size at imgsz 640 | Training range at 640 | Notes |
|---|---|---|---|
| Head (no_helmet) | 178 px tall | median 12.9 px, 99th 124.5 px, max 171.6 px | Taller than **every** training no_helmet box. At 480: 133 px (99.5th percentile). At 320: 89 px (91.5th percentile). |
| Torso (no_vest) | aspect w/h 4.23 | 99 % ≤ 1.56 | Out of distribution at every size |
| Person | aspect 2.23 | 99 % ≤ 1.01 | Still detected well |

[DERIVED] Shrinking the inference size brings an extreme close-up back into the size range the model learned, which is why 320 works on this scene while it is the *worst* size on construction-site images (§5.1).

**Limits of this webcam evidence:** one person, one room, near-static frames. The 10 labelled frames are strongly correlated and behave like about one independent scene. The numbers show the failure *mechanism*; they do **not** estimate webcam accuracy in general.

### 5.7 Detection errors vs compliance-analysis errors

`compliance_effect.json`. The same `ComplianceAnalyzer` is run once on the ground-truth boxes (what the rules conclude with perfect detection) and once on the model's boxes. Workers are matched by Person IoU ≥ 0.5. Every difference is therefore caused by detection, because the rules are identical in both runs. [MEASURED]

| Data / config | Reference workers | Workers missed | Reference violation items | Violation recall | False violations | Violation shown as *compliant* |
|---|---:|---:|---:|---:|---:|---:|
| val, still_640 | 481 | 58 | 419 | **0.542** | 6 | 19 |
| val, still_480 | 481 | 77 | 419 | 0.487 | 6 | — |
| val, live_now | 481 | 81 | 419 | **0.489** | 5 | 12 |
| val, live stream at 640 | 481 | 63 | 419 | 0.535 | 6 | 18 |
| webcam, image upload 640 | 10 | 0 | 20 | 0.000 | 0 | 0 |
| webcam, live 480 | 10 | 0 | 20 | 0.000 | 0 | 0 |
| webcam, VP8 at 320 | 10 | 0 | 20 | 0.150 | 0 | 0 |

What this shows:
- **The rules do not create the errors.** False violations stay at 5–6 per 481 workers in every configuration.
- Live loses violations because detection loses no_helmet / no_vest boxes and whole workers.
- On the webcam, every missing-PPE box is below the 0.5 violation threshold, so the rules correctly say *uncertain*. The 12–19 "violation shown as compliant" cases on val come from detection confusing an item with its missing class (e.g. helmet predicted on a bare head).

---

## F. Bottlenecks identified

1. **Display staleness** (pipeline): frame skipping plus redrawing old boxes. This is the largest effect on what the user sees, and is fixable without the model.
2. **Resolution mismatch between paths** (pipeline config): live runs at imgsz 480 against 640 for image upload, with no speed benefit (0.9 ms).
3. **Domain and scale shift** (model/data): close-range indoor webcam content lies outside the training distribution. Inference configuration cannot fix it in general.
4. **Weak missing-PPE classes** (model): low recall (0.50–0.67) and complement-class confusion. These are the classes the compliance layer depends on.
5. **Motion blur and low light** (environment).
6. **Low-bitrate WebRTC start-up** (transport, minor).

---

## G. Recommended configuration (based on the measurements; **not applied**)

| # | Change | Expected effect (from the measurements above) | Confidence |
|---|---|---|---|
| R1 | Live: analyse **every** frame (`process_every_n_frames: 1`), or never redraw stale boxes on skipped frames. Video: the same (`frame_stride: 1`, or draw only on analysed frames). | Displayed precision under motion back to the "every frame" level (0.79–0.80 instead of 0.24–0.51) for about 8 ms per frame on MPS. Video processing time grows about 5× [DERIVED, not measured]. | High (§5.2, §5.3) |
| R2 | Live imgsz **640**, the same as image upload, for site-camera use. | +0.057 mAP50-95, +6 points recall, +4.6 points violation recall on site imagery, for +0.9 ms. | High for construction imagery (§5.1, §5.7) |
| R3 | Do **not** treat a close desk webcam as a valid test of the model. For close-range demos, offer a "close-range camera" preset (imgsz 320) only after testing it on more webcam scenes. Alternatively, test a scale-adaptive two-pass scheme (re-run at a smaller imgsz when the Person box fills the frame). | 320 fixed the single measured webcam scene but is the worst size for site images. | Low: one scene [HYPOTHESIS beyond that scene] |
| R4 | Keep conf **0.25** for analysis. Optionally use a separate *display* threshold of about 0.35. | At 0.35: FP/img 1.45 → 0.91, contradictions 33 → 19, recall −2.5 points, F1 unchanged. | Medium |
| R5 | Resolve contradicting boxes. Option (a): class-agnostic NMS (contradictions 33 → 0, FP/img −0.12, recall −0.8 points, mAP50-95 −0.006). Option (b): keep NMS and suppress only complement-class pairs in post-processing. For nested same-class duplicates, NMS IoU 0.3 helps precision but cost recall on the webcam scene (0.633 → 0.567). Measure (a) and (b) on webcam framing before choosing. | Fewer helmet-*and*-no_helmet boxes on one head | Medium |
| R6 | Keep MPS; keep the colour conversion as is. | No change needed (identical accuracy, correct colours) | High |
| R7 | Correct the `settings.yaml:13` comment: the NMS IoU **is** used. | Documentation accuracy | High |
| R8 | **Data:** collect and label real webcam/CCTV footage: different distances, standing and seated, with and without PPE (hard hat, hi-vis vest, gloves), indoor and outdoor. Use it as a real benchmark, and later for fine-tuning. Retraining was **out of scope** for this audit. | Addresses the root cause of §5.6 | — |

---

## H. Errors and issues during the audit

| Issue | Resolution |
|---|---|
| `ap_per_class` returns 0.995 for a perfect detector, which failed the first unit test | This is an Ultralytics convention; the test now expects 0.995 |
| macOS has no `timeout` command for the webcam capture | Used `perl -e 'alarm 90; exec …'` instead |
| Partial condition re-runs would overwrite `conditions.json` | `--only` now merges into the existing results |

## I. Files

**Inspected:**
- `app.py` (lines 80–91, 280–310, 385, 435, 701–714)
- `src/detection/camera_processor.py`, `video_processor.py`, `image_processor.py`, `detector.py`, `annotate.py`
- `src/compliance/compliance_analyzer.py`, `worker_association.py`
- `src/events/event_manager.py`
- `configs/settings.yaml`
- `.venv/…/streamlit_webrtc/process.py`
- `.venv/…/ultralytics/utils/nms.py`, `engine/predictor.py`, `nn/autobackend.py`, `nn/modules/head.py`, `cfg/default.yaml`, `utils/metrics.py`, `engine/validator.py`

**Created:**

| File | Purpose |
|---|---|
| `src/evaluation/live_audit.py` | Audit harness. Subcommands: `conditions`, `overlay`, `latency`, `colour`, `webcam`, `webcam-sweep`, `compliance`, `scale`, `device`, `equivalence` |
| `scripts/capture_webcam_frames.py` | Webcam frame capture (OpenCV / AVFoundation) |
| `tests/test_live_audit.py` | 13 evaluator tests |
| `experiments/live_audit/*.json`, `suspicious_detections.jsonl` (776 FP records with class, confidence, box, frame size, imgsz, timestamp, FP type), `examples/*.jpg` | Results and evidence |
| `experiments/live_audit/webcam/` (frames, labels, summaries, `webcam_detections.jsonl`, `examples/`) | **Contains images of a person. Git-ignored. Delete when no longer needed.** |
| `docs/reports/REPORT-009-live-video-accuracy-audit.md` | This report |

**Modified:**
- `.gitignore` (added `experiments/live_audit/webcam/`)
- `docs/IMPLEMENTATION_LOG.md`

**Not modified:** `app.py`, everything under `src/detection`, `src/compliance` and `src/events`, `configs/*`, `models/trained/best.pt` (sha256 still `890dc61f…`), and the original dataset (2,004 checksums OK, no new files).

## J. Commands and tests executed

```bash
# inspection
grep/sed on the files listed above; Python probes of predictor.model.end2end and the nms/iou/agnostic options
system_profiler SPCameraDataType; python -c "import av; ... codecs_available"
# measurements (all from the SiteGuard-AI folder)
.venv/bin/python -m src.evaluation.live_audit colour
.venv/bin/python -m src.evaluation.live_audit conditions --limit 10        # smoke run
.venv/bin/python -m src.evaluation.live_audit conditions                   # 28 conditions
.venv/bin/python -m src.evaluation.live_audit conditions --only still_640_iou03
.venv/bin/python -m src.evaluation.live_audit overlay
.venv/bin/python -m src.evaluation.live_audit latency
perl -e 'alarm 90; exec @ARGV' .venv/bin/python scripts/capture_webcam_frames.py --seconds 5
.venv/bin/python -m src.evaluation.live_audit webcam
.venv/bin/python -m src.evaluation.live_audit webcam-sweep
.venv/bin/python -m src.evaluation.live_audit compliance
.venv/bin/python -m src.evaluation.live_audit scale
.venv/bin/python -m src.evaluation.live_audit device
.venv/bin/python -m src.evaluation.live_audit equivalence
.venv/bin/python -m pytest -q
```

| Test or check | Result |
|---|---|
| `tests/test_live_audit.py` (13 tests) | PASS |
| Full suite `pytest -q` | **77 passed** |
| Harness = app detector (60 checks) | PASS 60/60 |
| Model checkpoint unchanged | PASS (`890dc61f…`) |
| Dataset unchanged | PASS (0 checksum mismatches, 0 new files) |
| App, pipeline and config files unchanged | PASS (no files newer than REPORT-008 under `app.py`, `src/detection`, `src/compliance`, `src/events`, `configs`) |

## K. Acceptance criteria (audit prompt)

| Criterion | Status |
|---|---|
| Pipeline inspected; every image-vs-live difference identified | PASS (§C) |
| Possible causes investigated; model errors separated from compliance errors | PASS (§5.1–5.7) |
| Reproducible evaluation on manually annotated webcam frames; same frames through both pipelines | PASS (10 labelled frames, 149 compared). Small sample, see limits. |
| TP / FP / FN / P / R / mAP / latency / effective FPS | PASS |
| Configuration options tested under controlled comparison | PASS (imgsz, conf, NMS IoU, agnostic, NMS-free, frame sampling, device) |
| Suspicious detections logged with class, confidence, box, frame size, imgsz, timestamp; frames saved | PASS (`suspicious_detections.jsonl`, `webcam_detections.jsonl`, `examples/`) |
| No retraining, no model, dataset or app changes, no claimed improvement | PASS |

## L. Unresolved limitations

- The webcam evidence is a single near-static scene with one person and 30 objects. A proper webcam benchmark needs more scenes, distances and PPE items.
- The VP8/H.264 simulation uses fixed bitrates. Real browsers adapt bitrate and resolution, and the actual browser-side encoder was not captured.
- The frame-skipping test uses synthetic horizontal pans of still images, not real motion of people.
- Some val "false positives" are label omissions (e.g. an unlabelled forklift driver).
- [HYPOTHESIS] The user's own "incorrect detections" may include label flicker near the 0.25 threshold. That fits the webcam data (all missing-PPE boxes at 0.25–0.42), but the user's exact scenes were not observed.

## M. Next recommended task

After your approval, implement **R1 + R2** (fix stale overlays; live imgsz 640) behind settings. Then re-run this harness unchanged (`conditions`, `overlay`, `webcam`, `compliance`) as a before/after A/B, and report the measured difference. In parallel, collect a larger labelled webcam/CCTV sample (R8) before deciding on R3 and R5.
