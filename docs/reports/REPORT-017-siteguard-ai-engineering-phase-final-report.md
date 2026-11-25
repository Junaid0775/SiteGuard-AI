# REPORT-017 — SiteGuard AI Engineering Phase: Final Report and Decision

**Date:** 2026-11-19 (engineering phase 20:48–23:17 IST) **Spec:** `SiteGuard_AI_Master_Engineering_Specification.md` §14 (Phase 12), §18, §19
**Phase reports:** REPORT-010 (discovery, baseline) · 011 (dataset) · 012 (R1/R2) · 013 (YOLO26m readiness) · 014 (YOLO26m training) · 015 (comparison) · 016 (real-time)
**Execution log:** `experiments/engineering_phase/EXECUTION_LOG.md`

---

## 1. Executive summary

- **Pipeline:**
  - **R1 eliminated stale bounding boxes.** On 600 moving frames, 400 had stale boxes before and 0 after. On the 270-frame video, 216 frames reused boxes before and 0 after. A mutation check shows the new tests fail on the old code.
  - Every frame now has a source identity. Drops are counted, the session lifecycle is safe, and latency is measured.
  - **R2 put live inference at 640**, the same as images and video, for +0.76 ms per frame. Recall rose by +0.08 to +0.09 on moving frames and +0.10 on static frames.
- **Model:**
  - **YOLO26m beats YOLO26n on every class.** Val mAP50-95 rose from 0.523 to **0.620** (+0.097, Ultralytics val). A paired bootstrap over images (audit evaluator, NMS IoU 0.5) gives +0.093, 95 % CI [0.081, 0.103], with YOLO26m better in all 1,000 resamples.
  - Recall at the app threshold rose from 0.745 to 0.828. The largest gains are on small objects, wide scenes (recall 0.547 → 0.694) and overhead views (0.540 → 0.687), and on no_goggle, no_gloves and no_helmet.
  - The cost: about 3× the latency (8 → 25 ms per 720p frame), an 8.6× parameter count, and about 1.2 GB of GPU memory.
  - On this M5, **both models keep up with a 30 fps camera** (physical-camera test). YOLO26m does so with a thin margin on battery: about 27 ms of a 33 ms budget.
- **Data:** structurally clean, with no material train/val leakage. Two problems remain:
  1. the missing-PPE classes are mostly *tiny* boxes;
  2. labelling-policy inconsistencies: vehicle operators, eyeglasses vs goggles, no_goggle where eyes are unresolvable, missing Person boxes on partly visible people.
- **Not solved by either model:** close-range indoor webcam scenes (scale outside the training range), and weak no_goggle and small no_vest.
- **Decision:** YOLO26m is the **recommended production candidate** for image and video inspection, and for live use once the browser test is confirmed on mains power. **The production checkpoint was not switched.** That requires your approval (spec rule 18).

## 2. Objective

Execute the spec's sequence (Discover → … → Report), separate pipeline effects from model effects, and give an evidence-based recommendation.

## 3. Initial project state

YOLO26n in production. R1/R2 defects identified in REPORT-009. 77 tests. Not a Git repository.

## 4. Technical investigation — what was done

| Phase | Outcome | Report |
|---|---|---|
| 0 Discovery and preservation | Code map; environment; 604 + 2,004 + 30 files hashed; source snapshot; MPS verified | 010 |
| 1 YOLO26n baseline | Reproduced exactly (P 0.832, R 0.681, mAP50 0.734, mAP50-95 0.523) | 010 |
| 2 R1 synchronisation | Implemented and tested; stale boxes eliminated | 012 |
| 3 R2 inference at 640 | Implemented and tested; coordinates verified | 012 |
| 4 Dataset audit | Clean structure; scale imbalance; 1 background-level overlap; 162 suspects | 011 |
| 5 YOLO26m readiness | Supported; smoke tests; batch 4 chosen on memory | 013 |
| 6 YOLO26m training | 30 epochs, 94.6 min, stable; checkpoint verified, not promoted | 014 |
| 7 Comparison | +0.097 mAP50-95; all classes improved; 3× latency | 015 |
| 8 Real-time | 30 fps for both models on a physical camera; integrity checks pass | 016 |
| 9 Compliance regression | Rules and thresholds unchanged; 15 regression tests | this report §10.2 |
| 10 Tests | **124 passed**, 0 failed, 0 skipped (11.6 s) | this report §10.2 |
| 11 Evidence | All under `experiments/{engineering_phase,dataset_audit,yolo26m}/` | §6 |

## 5. Files inspected

The whole application and test code, configurations, the streamlit-webrtc and Ultralytics internals, the dataset (read-only) and the user's events DB (SELECT only). See the phase reports.

## 6. Files modified (whole engineering phase)

Pre-change copies are in `experiments/engineering_phase/baseline/source_snapshot_20261119-204914.tar.gz`.

| File | Change | Report |
|---|---|---|
| `src/detection/camera_processor.py` | Rewritten for R1 (frame/result identity, latest-frame policy, lifecycle, timing); public API kept | 012 |
| `src/detection/video_processor.py` | R1: every frame by default; explicit sampling with untagged-box policy; per-frame integrity log | 012 |
| `app.py` | Minimal: queued-frames callback, live imgsz = image size, measured status caption, `close()` on stop, sampling-policy captions | 012 |
| `configs/settings.yaml` | `live.image_size: null` (use 640), `process_every_n_frames: 1`, `frame_stride: 1`, NMS comment corrected | 012 |
| `src/training/train.py` | Added `--project` (default unchanged) | 013 |
| `tests/test_app.py` | One expectation updated (video analyses every frame); one new error-state test | 012 / this report |
| `pytest.ini` (new) | `testpaths = tests` | this report |

New files:
- tests: `test_frame_sync.py`, `test_resolution_coordinates.py`, `test_compliance_regression.py`, `test_model_loading.py`;
- `scripts/engineering/*.py` (hash_manifest, code_map, evaluate_model, measure_r1_r2, dataset_audit, yolo26m_smoke, compare_models, realtime_eval);
- `models/pretrained/yolo26m.pt`;
- all evidence folders.

**Side effects, stated honestly:**
- `experiments/training.log` gained appended lines (the training logger appends; nothing was overwritten).
- `outputs/streamlit_server.log`, the log of *my own* dashboard process, was overwritten when the dashboard restarted.
- The user's events DB and evidence images are **unchanged** (hash-verified).

## 7. Engineering decisions and alternatives

| Decision | Main alternative | Why |
|---|---|---|
| R1 in the library worker thread with a latest-frame policy | A separate inference thread and queues | The existing architecture already provides one; ~8 ms inference needs nothing more |
| Analyse every frame by default | Skip frames | The measured cost fits the frame budget; skipping caused the stale boxes |
| YOLO26m batch 4 | Batch 8 | Batch 8 gave 10 % free memory and +3.7 GB swap |
| No threshold, rule or class change | Tune to "look better" | Spec rules 5 and 9 |
| No automatic promotion | Switch to YOLO26m | Spec rule 18 |

## 8. Implementation details

See REPORT-012 (pipeline) and REPORT-013/014 (training). Every number in this report traces to a JSON or CSV file under `experiments/`.

During the final check (spec §20, step 8), this report's statements were verified against the evidence files. One error was found in REPORT-015 §1 and corrected there: the YOLO26m missing-PPE recall values had been taken from the Ultralytics-val column instead of the app threshold.

## 9. Testing methodology

- Unit tests with deterministic frames and mocked inference.
- Model integration tests.
- AppTest dashboard flows.
- A mutation check against the pre-change code.
- Real-model evaluations against ground truth.
- A physical-camera hardware test, with no frames saved.

Hardware-dependent tests are labelled as such.

## 10. Actual measured results — answers to the final engineering questions (spec §19)

### 10.1 Answers

1. **Did R1 eliminate stale bounding-box rendering?** **Yes.**
   - Stale-box frames: 400/600 → 0/600 (simulated motion); 216/270 → 0/270 (video); 0/149 in the webcam replay and 0 on the physical camera.
   - `render()` refuses foreign results, and 13 tests cover this. The mutation check fails on the old code (REPORT-012).
2. **Did R2 standardise live inference to 640, and what was the impact?** **Yes,** via one setting (`inference.image_size`), with the live override null.
   - Cost: +0.76 ms median per frame (7.03 → 7.79 ms, MPS).
   - Benefit: recall +0.099 on static frames and +0.081 to +0.090 on moving frames (480 vs 640, R1 policy, 600 displayed frames per cell). Earlier, on val images passed through a simulated 720p, VP8 1 Mbps stream: mAP50-95 0.454 at 480 vs 0.511 at 640 (REPORT-009).
3. **Reproduced YOLO26n metrics:** P 0.8322, R 0.6809, mAP50 0.7339, mAP50-95 0.5227 (200 val images, Ultralytics defaults). Identical to the historical values.
4. **Actual YOLO26m metrics:** P 0.8909, R 0.7773, mAP50 0.8311, mAP50-95 0.6195. Same procedure.
5. **Which classes improved or regressed?** All 12 improved in AP50-95, by +0.044 (no_vest) to +0.157 (goggles). None regressed in AP.
   - Ultralytics val precision fell slightly for no_helmet (−0.036), no_gloves (−0.018) and no_vest (−0.021). At the app threshold, precision fell for no_boots (−0.029), no_helmet (−0.024), boots (−0.019), no_vest (−0.013) and forklift (−0.010).
   - FP counts at the app threshold rose for boots (+23), no_helmet (+7) and no_boots (+5). Background false positives rose overall (53 → 89).
   - no_goggle (82 instances) and forklift (73) are too small for confident conclusions.
6. **What annotation or split-quality issues were found?**
   - No exact duplicates. One val image shares a near-identical background with train (r = 0.991, different worker), so no material leakage.
   - The missing-PPE classes are mostly tiny: no_helmet is 53 % under 0.1 % of the image area; no_goggle is 99.7 % small.
   - 51 missing-PPE boxes have less than 60 % of their area inside any Person box (Person label missing, or association impossible).
   - Policy inconsistencies (vehicle operators, eyeglasses vs goggles, unresolvable eyes).
   - 53.6 % of persons have no eye-region label.
   - 162 suspect rows to review (REPORT-011).
7. **Small PPE objects?** For small boxes (< 1 % of the image area), YOLO26m raises recall at the app threshold for every class that has them:
   - helmet 0.69 → 0.85; gloves 0.71 → 0.82; no_helmet 0.47 → 0.63; no_gloves 0.57 → 0.70; no_goggle 0.17 → 0.48;
   - no_vest 0.20 → 0.36 (still poor).
8. **Webcam-style scenes?**
   - Head-and-torso crops of val images: recall 0.870 → 0.920.
   - The real indoor webcam scene at 640 (one scene, 10 labelled frames): both poor (P 0.40 / 0.38, R 0.33 / 0.33). YOLO26m is less stable (0.18 vs 0.11 boxes appearing per frame) and adds background false positives.
   - At imgsz 320, both do much better on that scene (n P 0.97 / R 1.00), but 320 is the worst size for site imagery. This is an unsolved scale and domain issue.
9. **Measured capture, inference and display FPS on the M5** (physical camera, battery):
   - Camera capture 29.93 / 30.07 fps.
   - Analysed 29.94 / 30.05 fps (n / m).
   - Rendered (server-side display) 29.94 / 30.05 fps.
   - Browser display FPS was **not measured** (manual test pending).
10. **Measured inference and frame-to-display latency** (physical camera, battery):
    - Inference: n 18.7 ms mean / 24.2 ms p95; m 26.9 ms mean / 28.4 ms p95.
    - Received → rendered p95: n 24.7 ms; m 28.7 ms.
    - In a tight loop (saturated GPU): n 8.0 ms, m 25.0 ms per 720p frame.
    - On battery, pacing at 30 fps raises n to about 25 ms because of power management (REPORT-016 §10.7).
11. **Memory pressure:**
    - YOLO26m training at batch 4: minimum free 18 %, swap did not grow; batch 8 was rejected (10 % free, +3.7 GB swap).
    - Inference: MPS driver memory about 0.1 GB (n) vs about 1.2 GB (m).
    - Live YOLO26m: system free memory 68 → 62 %.
12. **Is the application stable?**
    - In all tested runs: 0 processing errors, 0 stale frames, at most 1 dropped frame per 12 s at 30 fps, and every video integrity check passing.
    - Inference exceptions don't block the pipeline (tested), and restart and stop are safe (tested).
    - The browser path still needs your manual check.
13. **Did regression tests pass?** **Yes: 124 passed, 0 failed, 0 skipped** (11.6 s; `final_validation/pytest_final.xml`).
14. **Which model is recommended, and why?** **YOLO26m as the production candidate.**
    - It has consistently better detection on every class and on small and missing-PPE objects, with statistically clear gains on this val set. It is better on overhead views and wide scenes, and under motion, dimming and blur.
    - It still meets 30 fps on the M5.
    - **Conditions before switching** (needs your approval):
      1. the browser live test on mains power shows analysed FPS ≈ camera FPS with low drops;
      2. accept about 1.2 GB GPU memory and higher energy use.
    - YOLO26n stays a valid fallback for battery operation or slower Macs.
15. **What limitations remain?**
    - In-distribution validation only (no real site footage).
    - One training run per model.
    - The webcam evidence is one indoor scene.
    - Low light is synthetic; the video clip is a slideshow.
    - Viewpoint labels are AI-assisted.
    - No identity tracking (W labels are per frame).
    - YOLO26m missing-PPE recall at the app threshold is 0.69–0.72 (no_boots 0.691, no_vest 0.692, no_gloves 0.700, no_helmet 0.715) and 0.48 for no_goggle. About 3 in 10 missing-PPE boxes are still missed.
    - The no_goggle policy is unclear.
    - Event persistence now spans less time (§10.3).
16. **What is the next engineering phase?** See §16.

### 10.2 Software quality (Phase 10)

| Item | Result |
|---|---|
| Suite at the start of the phase | 77 passed |
| Suite at the end | **124 passed**, 0 failed, 0 skipped, 11.63 s |
| New tests (47) | frame sync 13, resolution/coordinates 13, compliance regression 15, model loading 5, dashboard invalid-video error state 1 |
| Intentional expectation change | Video flow analyses 60/60 frames (was 12/60) because of R1 |
| Hardware tests | Physical camera (`realtime_eval.py camera`), run manually and reported in REPORT-016; not part of pytest. A mocked camera release is in pytest. |
| Model quality | **Not** established by software tests; see REPORT-010/015/016 |

### 10.3 Pipeline before/after (R1/R2), separated from model effects

| Aspect | Before | After | Evidence |
|---|---|---|---|
| Stale-box occurrence | 66.7 % of live frames; 80 % of video frames | 0 % | 012 §10.2/10.5; 016 |
| Incorrect frame association | Every skipped frame | 0 | 012 tests and mutation check |
| Displayed detection quality (20 px/frame motion, imgsz 640) | P 0.362, R 0.271 | P 0.804, R 0.597 | 012; `pipeline_r1/displayed_accuracy.json` |
| Live inference size | 480 | 640 | 012 §10.4 |
| Live analysed rate (30 fps camera) | ~10 fps | ~30 fps | 012 §10.3; 016 §10.1 |
| Dropped frames | Not counted | Counted (0–1 per 360) | 016 |
| Latency visibility | None | Mean/median/p95/max in the UI | 012 |
| Event timing | 3 analysed frames ≈ 0.3–1 s | 3 frames ≈ 0.1 s (30 fps live) / 0.2 s (15 fps video); 15/16 events match | 012 §11 |

These improvements are **pipeline** effects and are independent of the model. The model gains in §10.1 were measured on identical inputs with the R1/R2 pipeline in place for both models.

### 10.4 Readiness levels (spec §19)

| Level | Status |
|---|---|
| Academic prototype readiness | **Yes.** Working end-to-end system, reproducible evaluation, documented limitations |
| Controlled laboratory testing | **Partly.** Val-set and simulated tests are complete; the laptop physical-camera test is done; the browser end-to-end test is pending |
| Real construction-site validation | **Not done.** No real site footage, cameras or ground truth from a site |
| Production deployment readiness | **No.** Needs site validation, identity tracking for unique-worker counts, a security/privacy review and operational monitoring. A laptop demonstration does not establish production readiness. |

## 11. Before/after comparison

The pipeline before/after is in §10.3. The model comparison across the spec §14 dimensions is below. Both models ran on identical inputs with the R1/R2 pipeline in place.

| Dimension | YOLO26n | YOLO26m | Evidence |
|---|---|---|---|
| Val P / R / mAP50 / mAP50-95 (Ultralytics val) | 0.832 / 0.681 / 0.734 / 0.523 | 0.891 / 0.777 / 0.831 / 0.620 | 015 §1 |
| App threshold P / R / F1 (conf 0.25, NMS IoU 0.5) | 0.884 / 0.745 / 0.809 | 0.885 / 0.828 / 0.856 | 015 §10.1 |
| Per-class AP50-95 | baseline | All 12 classes higher (+0.044 to +0.157) | 015 §10.3 |
| Missing-PPE recall at app threshold: no_helmet / no_gloves / no_boots / no_vest / no_goggle | 0.615 / 0.567 / 0.674 / 0.623 / 0.171 | 0.715 / 0.700 / 0.691 / 0.692 / 0.476 | `operating_point.json` (both models) |
| Small-box recall (< 1 % of area): helmet / no_helmet / no_vest | 0.693 / 0.469 / 0.203 | 0.852 / 0.631 / 0.356 | 015 §10.4 |
| Viewpoint recall: frontal (1,554 GT) / overhead (1,083) / side (270) / low angle (54) | 0.871 / 0.540 / 0.922 / 0.352 | 0.920 / 0.687 / 0.926 / 0.537 | `stratified_recall.csv` (AI-assisted viewpoint labels; low angle too small to conclude) |
| Recall on close-up images / wide scenes | 0.897 / 0.547 | 0.931 / 0.694 | `stratified_recall.csv` |
| Webcam-style crops of val images, P / R | 0.910 / 0.870 | 0.913 / 0.920 | 015 §10.5 |
| Real webcam scene at 640 (10 frames, one scene), P / R | 0.400 / 0.333 | 0.385 / 0.333 | 015 §10.5 |
| Inference per 720p frame, tight loop (mean) | 8.0 ms (125 fps) | 25.0 ms (39.9 fps) | 015 §10.6 |
| Physical camera (battery): analysed fps / inference mean / received to rendered p95 | 29.94 fps / 18.7 ms / 24.7 ms | 30.05 fps / 26.9 ms / 28.7 ms | 016 |
| Parameters / file size | 2.54 M / 5.4 MB | 21.79 M / 44.0 MB | 015 §10.6 |
| MPS memory after inference | 100.5 MB | 1,213.5 MB | 015 §10.6 |
| Training duration (30 epochs, MPS) | 21.2 min (batch 8) | 94.6 min (batch 4) | `training_metadata.json` of each run |
| Operational stability (physical camera, replay, video) | 0 errors, 0 stale frames, 0/359 dropped; replay flicker 0.11 box appearances per frame | 0 errors, 0 stale frames, 1/361 dropped; replay flicker 0.18 box appearances per frame | 016 |

YOLO26m is better on every detection dimension except the single real webcam scene, where neither model is adequate. It costs about 3× the inference time, about 12× the GPU memory and 4.5× the training time.

## 12. Limitations and uncertainty

See §10.1 answer 15. All metrics come from 200 in-distribution val images. The bootstrap covers image sampling only.

## 13. Known unresolved issues

1. **Manual browser live test on mains power** (REPORT-016 §13).
2. **Production switch to YOLO26m:** your decision.
3. **Event persistence window:** keep the 3 frames, or move to a time-based window? That is a rule change and needs your approval.
4. **Dataset policy questions** and 51 high-priority suspect labels: needs a human.
5. The close-range webcam scale problem; no_goggle; small no_vest.

## 14. Exact reproduction

```bash
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI"
.venv/bin/python -m pytest -q                                                   # 124 tests
.venv/bin/python scripts/engineering/evaluate_model.py --weights models/trained/best.pt --name yolo26n --out experiments/engineering_phase/baseline/yolo26n
.venv/bin/python scripts/engineering/measure_r1_r2.py
.venv/bin/python scripts/engineering/dataset_audit.py
.venv/bin/python scripts/engineering/yolo26m_smoke.py inference
.venv/bin/python -m src.training.train --weights models/pretrained/yolo26m.pt --epochs 30 --batch 4 --no-promote --project experiments/yolo26m/training --name yolo26m_e30_b4
.venv/bin/python scripts/engineering/evaluate_model.py --weights experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt --name yolo26m --out experiments/yolo26m/validation
.venv/bin/python scripts/engineering/compare_models.py
.venv/bin/python scripts/engineering/realtime_eval.py offline
.venv/bin/python scripts/engineering/realtime_eval.py camera --seconds 12        # turns the camera on; no frames saved
.venv/bin/python scripts/engineering/hash_manifest.py verify experiments/engineering_phase/baseline/dataset_manifest.csv
```

## 15. Conclusion

- The live-pipeline defects are fixed and verified.
- YOLO26m is a substantially better detector on this dataset and is real-time capable on the M5 with a thin margin.
- The remaining quality limits come from **data** (scale, labelling policy, domain coverage), not from the pipeline.

**Final acceptance checklist (spec §18):**

| Area | Item | Status |
|---|---|---|
| Integrity | Original dataset preserved | ✅ 2,004/2,004 hashes unchanged, no new files |
| | YOLO26n checkpoint preserved | ✅ `890dc61f…` |
| | User changes preserved | ✅ No Git; snapshot plus hashes; events DB and evidence unchanged |
| | Git state and hashes recorded | ✅ Not a repository (recorded); manifests stored |
| | No public push or deployment | ✅ |
| Baseline | Reproduced; per-class; configuration and evidence | ✅ ✅ ✅ |
| Pipeline | R1; stale boxes eliminated; bounded queue and drops; IDs and lifecycle | ✅ ✅ ✅ ✅ |
| | R2 at 640; coordinate transforms tested; latency measured | ✅ ✅ ✅ |
| Dataset | Inventory and distribution; box scale; duplicates and leakage | ✅ ✅ ✅ |
| | Visual review (29 images, scope stated); suspects reported; dataset unchanged | ✅ ✅ ✅ |
| YOLO26m | Architecture verified; MPS readiness; smoke test; full training | ✅ ✅ ✅ ✅ |
| | Separate checkpoint and config; validation | ✅ ✅ |
| Comparison | Controlled; overall and per-class; visual; latency and memory; limitations and recommendation | ✅ ✅ ✅ ✅ ✅ |
| Real-time | Webcam and video tested | ✅ Physical camera, replay and video. ⚠️ Browser/WebRTC path pending (manual) |
| | Synchronisation verified; capture, inference and display FPS separated | ✅ ⚠️ Server-side render FPS only (browser display not observable) |
| | Latency and drops recorded; privacy preserved | ✅ ✅ No frames saved or uploaded; webcam folder git-ignored; no identifiable images in reports |
| Software | Suite rerun; regression tests added; integration tests executed; failures documented | ✅ ✅ ✅ ✅ |
| Documentation | Reports 010–017; configs and logs; metrics traceable; final report | ✅ ✅ ✅ ✅ |

## 16. Recommended next step (next engineering phase)

1. **You:** run the browser live test on mains power (REPORT-016 §13). If it is satisfactory, approve the production switch to YOLO26m. The switch would be done by adding a configurable checkpoint path, with no overwrite of `models/trained/best.pt`.
2. **You:** decide whether event persistence should be time-based (e.g. ≥ 0.3 s); it would be measured before and after.
3. **Data:**
   - a human review of the 51 high-priority suspects and the three policy questions;
   - collect and label real site CCTV and close-range webcam footage as an independent test set;
   - then consider a corrected dataset version (separate and traceable).
4. **Model:**
   - multiple seeds;
   - a longer schedule (the curve had not plateaued);
   - tiling or higher imgsz for tiny missing-PPE boxes, evaluated on the independent test set.
5. **Product:** multi-object tracking for persistent worker IDs, before any unique-worker or compliance-rate metric.
