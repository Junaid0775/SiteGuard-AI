# REPORT-025 — Phase 8: final research decision

**Written:** 2026-11-23, about 03:45–04:01 IST. **Specification:** §10. **Programme dates:** 2026-11-20 to 2026-11-23.

## Decision

1. **Production model: unchanged.** YOLO26n (`models/trained/best.pt`, sha256 `890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b`, 640 px) stays the application's active model and its automatic fallback.
2. **Research candidate: YOLO26m `E3_m896`.**
   - Stored at `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt` (sha256 `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6`) with a model card.
   - It is the best model produced, and its gains over the controlled reference hold on held-out data.
   - It **failed the pre-registered promotion gates** (accuracy targets G1–G3 and the 30 fps latency budget G6). It is therefore **not promoted and not registered** in the application.
3. **The 93–95 % ambition was not achieved** on any qualifying metric (§1).
4. **Recommendation:**
   - Keep YOLO26n for the application.
   - Treat E3 as the starting point for the next iteration (§11).
   - If a demonstration of YOLO26m is wanted, enable it only as a clearly labelled, non-default provisional option, with the user's approval (REPORT-024 §B3).

## 1. Was 93–95 % achieved, and on which metric?

**No.** The primary target is **mAP50 ≥ 0.93** on a leakage-resistant held-out test. The candidate reached **mAP50 = 0.847** on the locked test. None of the qualifying targets was met:

| Target (spec §0) | Required | Candidate (locked test) |
|---|---|---|
| mAP50 | ≥ 0.93 | **0.847** |
| Precision at the application operating point | ≥ 0.90 | **0.885** |
| Recall at the application operating point | ≥ 0.90 | **0.862** |
| Recall, each missing-PPE class | ≥ 0.90 | **0.522–0.796** |
| mAP50-95 (stretch) | ≥ 0.80 | **0.644** |

**Per-class AP50 above 0.93:** a few present-PPE classes exceed it on the locked test (Person 0.987, goggles 0.972, vest 0.962, helmet 0.949). Under spec §8, one metric reaching 93 % does not meet the ambition, and these classes are not the safety-critical ones.

## 2. Development validation or locked test?

**Both are reported, and the decision rests on the locked test.**

**Development set:**
- `splits/dev.txt`: 200 images, 2,961 objects. It is the original val set.
- It selected best epochs and the candidate, so it is optimistic. Candidate mAP50 on dev: 0.854.

**Locked test:**
- `splits/test.txt`: 160 images, 2,480 objects, held out as whole groups.
- Accessed in one pre-registered qualification session: the candidate plus one controlled reference. Two earlier attempts failed before reading any data and are documented.
- Nothing was tuned on it. Every access is recorded in `qualification/locked_test_access_log.csv` and explained in `qualification/locked_test_access_notes.md`.

## 3. Is the data representative and leakage-resistant?

**Leakage-resistant: yes**, within this dataset (REPORT-020):
- The test consists of whole groups (pixel near-duplicates, embedding cosine ≥ 0.95, generated prompt families).
- Train and test share 0 groups and 0 near-duplicates. The maximum train-to-test embedding cosine is 0.945.
- The training YAMLs never reference the test images, and the runner checked every run for that.

**Representative of real sites: no.**
- The locked test is **in-distribution**: the same public dataset, photographers and generator.
- 113 of its 160 images are generated close-ups, on which the candidate scores mAP50 0.951. The 47 real-scene images score only **0.592**.
- On 10 labelled frames from a real webcam (earlier live audit), all models found about a third of the objects.
- Results must be quoted as **"on this limited, held-out, in-distribution test set (160 images)"**, never as real-world or deployment accuracy.

## 4. Selected checkpoint

| Item | Value |
|---|---|
| Candidate | `E3_m896`: YOLO26m from `models/pretrained/yolo26m.pt` (sha256 `401cea9a…0b7`), 30 epochs, batch 4, **imgsz 896**, seed 42, Ultralytics 8.4.215 defaults otherwise, MPS (FP32) |
| Checkpoint | `experiments/accuracy_improvement/training/E3_m896/weights/best.pt` = `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt` |
| SHA-256 | `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6` (44,059,865 bytes) |
| Frozen | 2026-11-23 02:47:31 (`qualification/frozen_candidate.json`) |
| Inference configuration | 896 px, conf 0.25, NMS IoU 0.5; compliance thresholds unchanged |
| Status | Not promoted (`model_card.json`) |

## 5. Missing-PPE recall (locked test, conf 0.25; 95 % bootstrap interval)

| Class | Ground-truth boxes | Candidate E3 | Reference E1 (640) | At the alert threshold 0.50 (E3) |
|---|---|---|---|---|
| no_helmet | 142 | 0.739 [0.639, 0.835] | 0.676 | 0.648 |
| no_gloves | 183 | 0.650 [0.551, 0.752] | 0.650 | 0.585 |
| no_goggle | 46 | 0.522 [0.375, 0.691] | 0.413 | 0.348 |
| no_boots | 108 | 0.796 [0.680, 0.918] | 0.815 | 0.741 |
| no_vest | 93 | 0.688 [0.554, 0.818] | 0.591 | 0.645 |

**Missed violations:** the application raises a potential violation only at confidence ≥ 0.50, after the compliance checks. Even with the candidate, about 26–65 % of missing-PPE boxes would not raise an alert on this test set.

## 6. Precision–recall trade-off

**At the operating point (conf 0.25), locked test:**
- The candidate has precision 0.885 and recall 0.862. The 640-px reference E1 has 0.898 and 0.835.
- **Gain:** the candidate's higher resolution buys recall: +0.026 overall (95 % CI [+0.016, +0.038]) and +0.051 mean missing-PPE recall ([+0.022, +0.084]).
- **Cost:** more false positives (278 against 235) and more contradiction pairs (20 against 8).

**On dev (threshold sweep, REPORT-023 §7):**
- Raising the detection threshold to 0.40 would maximise overall F1, but it costs 2–5 recall points on every missing-PPE class.
- The alert threshold 0.50 gives 0.89–0.98 alert precision, at the cost of 5–18 recall points per class against 0.25.

**Thresholds were left unchanged on the user's instruction.** Per-class alert thresholds are a possible future policy decision; they need approval and re-qualification.

**Detector confidence** is under-confident between 0.45 and 0.75 (calibration error 0.107 for missing-PPE predictions). It must not be presented as a probability.

## 7. mAP50 and mAP50-95

| Model | Split | mAP50 | mAP50-95 |
|---|---|---|---|
| **E3 candidate (896)** | **locked test** | **0.847** | **0.644** |
| E1 reference (640) | locked test | 0.828 | 0.621 |
| E3 candidate | dev | 0.854 | 0.628 |
| YOLO26n production | dev | 0.734 | 0.523 |
| YOLO26m e30_b4 (earlier) | dev | 0.831 | 0.620 |

- Metrics are Ultralytics val at conf 0.001 and NMS 0.7.
- YOLO26n and e30_b4 cannot be evaluated on the locked test, because they were trained on it. Dev is the only shared basis.
- **On dev, the candidate beats YOLO26n:** mAP50 +0.111 [+0.090, +0.131] and mean missing-PPE recall +0.191 [+0.156, +0.227].

## 8. Runtime on the M5 (MacBook Air, 16 GB, MPS; measured 2026-11-23, on battery)

| Model | Video pipeline inference mean / p95 | Live replay at 29.8 fps: analysed fps, dropped, inference p95 | GPU memory (evaluator) |
|---|---|---|---|
| YOLO26n (640) | 9.3 / 14.1 ms | 29.8 fps, 0 of 149 dropped, 24.8 ms | — |
| YOLO26m e30 (640) | 25.7 / 27.1 ms | 29.8 fps, 0 dropped, 35.7 ms | — |
| **E3 candidate (896)** | **42.7 / 45.1 ms** | **23.7 fps, 31 of 149 dropped, 43.1 ms** | 4.5 GB (E1 at 640: 2.3 GB) |

- **No 30 fps camera at 896 px:** the candidate cannot analyse every frame of a 30 fps camera. The latest-frame policy keeps the display correct (no stale boxes), but about 1 frame in 5 is skipped.
- **Physical camera:** the test is pending the user's go-ahead.
- **Browser frame rate:** not measured, so not claimed.

## 9. Remaining weaknesses and risks

1. **Tiny objects.**
   - About half of the missed missing-PPE boxes are under 8 px at 640.
   - Recall on objects below 0.1 % of the image area is 0.57 overall, and 0.31–0.56 for missing-PPE classes.
2. **Present-versus-missing confusion:**
   - boots and no_boots (the largest confusion pair);
   - no_vest labelled where a Person or vest is predicted;
   - helmet predicted where no_helmet is labelled.
3. **Real-scene domain.**
   - Real-scene images score about 0.59 mAP50, against 0.95 on generated close-ups.
   - The real-webcam replay shows the same gap.
4. **Label quality unknown.**
   - 178 suspect annotations, 37 of them in dev, remain **unreviewed**.
   - 12 of the candidate's missed boxes on dev are flagged cases.
5. **Robustness.** In synthetic darkness the candidate is worse than YOLO26n (mAP50 0.626 against 0.651), and under blur it is worse than the earlier YOLO26m.
6. **Single seed.** Seed-to-seed variance is unknown. The planned 3-seed run was cancelled for the deadline.
7. **Runtime.** 896 px does not fit the 30 fps frame budget on the M5.
8. **Small test set.** Per-class intervals are wide (no_goggle: 46 instances, interval [0.375, 0.691]).
9. **Not run:** longer training (E2), tiling (E6), the combined configuration (E7) and extra seeds. See REPORT-022 §7.

## 10. Reproduction

All commands run from the project root with `.venv` (Python 3.12.16, torch 2.15.0, Ultralytics 8.4.215).

```bash
# integrity baseline and verification
.venv/bin/python scripts/accuracy/integrity_manifest.py verify experiments/accuracy_improvement/manifests/20261120-005540_phase0 --json /tmp/verify.json
# splits (deterministic; REPORT-020)
.venv/bin/python scripts/accuracy/phase2_splits.py build --emb-threshold 0.95 --test-images 160 --seed 0
# candidate training (REPORT-022)
.venv/bin/python -m src.training.train --weights models/pretrained/yolo26m.pt \
  --data experiments/accuracy_improvement/datasets/v1_original_labels/dev.yaml --epochs 30 --batch 4 --imgsz 896 --seed 42 \
  --no-promote --project experiments/accuracy_improvement/training --name <new_run_name>
# dev evaluation and comparison (REPORT-023)
.venv/bin/python scripts/accuracy/evaluate.py --weights <best.pt> --split dev --imgsz 896 --out experiments/accuracy_improvement/evaluation/dev_<run>
.venv/bin/python scripts/accuracy/compare_candidates.py --split dev --reference dev_E1_m640_base --runs dev_<run> --out <dir> --sweep dev_<run>
# locked test: qualification only, logged (REPORT-024); never for tuning
.venv/bin/python scripts/accuracy/evaluate.py --weights <frozen best.pt> --split test --imgsz 896 --out <dir> \
  --locked-test-purpose "<purpose>" --frozen-sha256 <sha256>
# runtime and tests
.venv/bin/python scripts/engineering/realtime_eval.py offline --model <name>=<path>@<imgsz> ... --out <dir>
.venv/bin/python -m pytest -q
```

**Exact reproduction is not guaranteed.** MPS training with `deterministic=True` and a fixed seed reproduces the configuration. Bit-identical weights are not guaranteed, and E1 was resumed twice.

## 11. Work remaining before real-site validation

1. **Human label review** of the 178 flagged annotations (`annotation_review/review.html`), then re-evaluate. Some measured error may be label noise.
2. **Independent site data.** Collect and label (with consent, and licensed) footage from real construction sites, cameras and lighting, including night. Use it as a **new** test set, because the current locked test has now been used.
3. **Small-object strategy.** Tiled training (E6), higher-resolution training with longer schedules (E2-style), and the combined configuration E7. Run each with ≥ 3 seeds.
4. **Runtime for 896 px:** export to Core ML or half precision, or analyse every second frame with honest frame-rate display. Measure, do not assume.
5. **Boots and vest confusions.** Targeted data, or annotation-policy clarification for feet and torso visibility.
6. **Robustness.** Low-light and blur augmentation, validated on real night footage rather than synthetic transforms.
7. **Alert policy.** If fewer missed violations are wanted, a separately approved review of per-class alert thresholds on dev, followed by re-qualification on new data.
8. **Physical-camera test** of the candidate and YOLO26n, with the user present.

## 12. Tests and integrity at the end of the programme

- **Tests:** 156 passed, 0 failed, 0 skipped (2026-11-23 03:56).
- **Dataset:** 2,004 files, 0 changed.
- **Key checkpoints:** unchanged.
- **Events database and evidence:** not modified by the programme. The last change was the user's own inspection on 2026-11-20 at 21:19.
- **Seven protected files:** changed as intended, with pre-change copies in `manifests/`.
- Details: REPORT-024 §B5 and §B8.

## 13. Programme acceptance summary

| Phase | Report | Status |
|---|---|---|
| 0 Discovery and integrity | REPORT-018 | Complete |
| 1 Dataset quality and label policy | REPORT-019 | Complete; human review pending |
| 2 Evaluation protocol and splits | REPORT-020 | Complete |
| 3 Data expansion and augmentation | REPORT-021 | Complete |
| 4 Training matrix | REPORT-022 | Complete, with documented reductions (E2, E6, E7 and seeds not run) |
| 5 Comparison and error analysis | REPORT-023 | Complete |
| 6 Locked-test qualification | REPORT-024 Part A | Complete: gates failed |
| 7 Controlled integration | REPORT-024 Part B | Complete: not promoted; YOLO26n kept; camera test pending the user |
| 8 Final decision and handoff | this report, `README.md`, `HANDOFF-ML-to-frontend.md` | Complete |


---

## Correction note — 2026-11-23 12:36 IST (appended; the original text above is unchanged)

**What was wrong:** this document says that the evidence images were not modified by the accuracy programme. **That statement was inaccurate.**

**What happened:**
- The Phase 7 offline real-time test (`scripts/engineering/realtime_eval.py offline`, 2026-11-23 03:17–03:38) replayed the private webcam frames from `experiments/live_audit/webcam/`.
- It processed them through `LiveFrameProcessor(..., store=None)`. `EventManager` still saves evidence when `store` is `None`.
- As a result, the test wrote **one** webcam-derived image into production evidence storage: `outputs/evidence/EVT-20261123-031826-215199.jpg` (78,413 bytes, sha256 `f9d2380ca37b803c3c3ff8ba0612c876ac2065eb666eab1dd35b9425c34bc3eb`, created 03:18:26).
- It was **not** linked to any event (0 database rows reference it).

**Why the integrity check missed it:** `integrity_manifest.py verify` reports changed or missing *listed* files. It does not report *new* evidence files.

**How it was found and resolved:**
- Found during the camera quality audit: `experiments/camera_quality_audit/reports/CAMERA-QUALITY-REPORT-001.md` §8.
- With the project owner's authorisation, that single file was deleted on 2026-11-23 at 12:35:48, after its name, size and hash were recorded. The other 131 evidence files were verified byte-identical before and after.
- Record: `experiments/camera_quality_audit/fixes/phase1/target_file_record.txt`.
- The cause in the test script is fixed in the camera-quality fix programme (Fix 6).

**Unaffected:** all experiment results, metrics and decisions in this document. The events database, which was opened read-only, was never modified by the programme.

