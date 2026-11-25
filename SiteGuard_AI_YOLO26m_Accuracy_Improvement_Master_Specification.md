# SiteGuard AI — YOLO26m Accuracy Improvement Master Specification

**Document:** Single execution-ready Master Specification for Claude Code  
**Workspace:** `~/Desktop/471 Project/SiteGuard-AI/`  
**Selected research model:** YOLO26m  
**Baseline/rollback:** YOLO26n (preserve; never overwrite)  
**Hardware:** MacBook Air M5, 16 GB unified memory  
**Scope:** Model/data research, evaluation, qualification, and minimum safe model integration. No frontend redesign or unrelated feature development.

## 0. Mandatory instructions

Read this entire document before changing anything. Inspect the actual workspace, code, configurations, and reports 010–017. Treat all details below as context to verify, not as permission to assume files or behaviour still match.

The user has approved proceeding with YOLO26m as the intended model. Promote it to the application's default only after the qualification gates below pass. Preserve YOLO26n as a rollback option and preserve the existing YOLO26m checkpoint.

The user's requested 93–95% performance is an **ambition, not a guaranteed outcome**. Define and report metrics precisely:
- Primary target: **mAP50 >= 0.93** on a representative, leakage-resistant held-out test set.
- Supporting target: precision >= 0.90 and recall >= 0.90 at the documented application operating point.
- Safety-critical target: recall >= 0.90 for each missing-PPE class (`no_helmet`, `no_gloves`, `no_goggle`, `no_boots`, `no_vest`).
- Stretch target: mAP50-95 >= 0.80. An mAP50-95 of 0.90 is aspirational only; never promise it.
- Never report a single unqualified “accuracy” percentage. mAP50, mAP50-95, precision, recall, and classification accuracy are different measures.

Do not manipulate labels, validation data, thresholds, or metric definitions to manufacture a 90–95% result. If the target is not achieved, report the actual result and the limiting evidence.

### 0.1 Preservation rules

1. Original dataset at `../construction-ppe/` is read-only. Never edit, rename, move, delete, recompress, or overwrite original images, labels, YAML, manifest, README, or licence.
2. Preserve the active YOLO26n checkpoint and record SHA-256.
3. Preserve the previously trained YOLO26m checkpoint and record SHA-256.
4. Never overwrite an existing checkpoint. Use versioned paths for new runs.
5. Preserve the SQLite events database, evidence, user configuration, and existing reports.
6. Do not delete experiment folders or evidence to make results appear cleaner.
7. Hash protected files before and after work.
8. Keep images, videos, camera frames, and dataset processing local. Do not upload them to external services.
9. No public GitHub push, public deployment, or external publication.
10. Do not silently alter compliance rules, event persistence, thresholds, or alert behaviour during model experiments.

### 0.2 Reports required after every phase

Create `experiments/accuracy_improvement/reports/` and write a detailed Markdown report after each phase:

- `REPORT-018-discovery-and-integrity.md`
- `REPORT-019-dataset-quality-and-label-policy.md`
- `REPORT-020-evaluation-protocol-and-splits.md`
- `REPORT-021-data-expansion-and-augmentation.md`
- `REPORT-022-training-experiment-matrix.md`
- `REPORT-023-model-comparison-and-error-analysis.md`
- `REPORT-024-qualification-and-integration.md`
- `REPORT-025-final-research-decision.md`

Every report must include objective, scope, files inspected/modified, commands, environment/hardware state, configurations, seeds, data provenance and hashes, metrics with definitions and denominators, per-class results, tests and exact counts, limitations, decisions, and next-phase readiness. Include relative paths and annotation IDs for error examples. Do not include private camera imagery in public-facing documentation.

A blocked phase still requires a report explaining the blocker, evidence, and safe next action. Do not claim completion until acceptance criteria pass.

---

## 1. Verified context to confirm

Workspace:
`/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI/`

Original dataset:
`/Users/junaidahmad/Desktop/471 Project/construction-ppe/`

Known structure:
```text
construction-ppe/
  images/train/
  images/val/
  labels/train/
  labels/val/
  data.yaml
  LICENSE.txt
  manifest.jsonl
  README.md
```

Previously audited inventory:
- 800 training images and 200 validation images;
- 800 training labels and 200 validation labels;
- 14,863 annotations;
- 0 missing image-label pairs;
- 0 labels without images;
- 0 structurally invalid annotation rows;
- all 12 class IDs present.

Verify class mapping from `data.yaml` before use:

| ID | Class |
|---:|---|
| 0 | helmet |
| 1 | gloves |
| 2 | vest |
| 3 | boots |
| 4 | goggles |
| 5 | Person |
| 6 | no_helmet |
| 7 | no_goggle |
| 8 | no_gloves |
| 9 | no_boots |
| 10 | forklift |
| 11 | no_vest |

Historical YOLO26n results on the 200-image validation set:
- Precision 0.8322
- Recall 0.6809
- mAP50 0.7339
- mAP50-95 0.5227

Previously trained YOLO26m, same reported evaluation procedure:
- Precision 0.8909
- Recall 0.7773
- mAP50 0.8311
- mAP50-95 0.6195

Previously reported YOLO26m missing-PPE recall at the app operating point:
- `no_helmet`: 0.715
- `no_gloves`: 0.700
- `no_goggle`: 0.476
- `no_boots`: 0.691
- `no_vest`: 0.692

Known data issues from earlier audits:
- 162 suspect label rows; 51 high-priority missing-PPE-related suspects.
- Missing-PPE boxes are often extremely small.
- 99.7% of `no_goggle` boxes were reported as small under the previous audit's area definition.
- Some people have no eye-region label.
- Policy ambiguities: vehicle operators, ordinary eyeglasses versus protective goggles, unresolvable eyes, and partially visible people with missing `Person` boxes.
- Viewpoint metadata was AI-assisted and not independently human-verified.

Inspect previous reports 010–017, especially:
- REPORT-011 dataset audit;
- REPORT-013 YOLO26m readiness;
- REPORT-014 YOLO26m training;
- REPORT-015 controlled comparison;
- REPORT-016 real-time evaluation;
- REPORT-017 final engineering decision.

Prior comparison found YOLO26m improved AP50-95 on all 12 classes, but some app-threshold false positives increased. Background false positives reportedly rose from 53 to 89. Keep this trade-off visible.

---

## 2. Phase 0 — Discovery, environment, preservation

Inspect:
- workspace tree and current code;
- Python and virtual environment versions;
- Ultralytics, PyTorch, torchvision, OpenCV, NumPy, Pillow, Albumentations (if present);
- MPS availability and actual device selection;
- training entry point and defaults;
- inference/model loader and settings;
- dataset YAML and class names;
- model paths, hashes, and training arguments;
- reports 010–017;
- tests and current test count;
- dashboard model-selection behaviour.

Do not upgrade dependencies as the first action. Record versions. Change dependencies only for a verified need, and isolate that change.

Create a timestamped SHA-256 manifest for original dataset files, both existing checkpoints, configs, SQLite database, reports, and key evidence. Record which checkpoint is currently active and which YOLO26m checkpoint was previously evaluated.

Run the existing test suite before modifications.

**Acceptance:** exact paths and model identities verified; protected files inventoried and hashed; original data confirmed read-only; MPS and available memory measured; baseline tests recorded; REPORT-018 written.

Stop if model identity or environment is ambiguous. Diagnose without destructive changes.

---

## 3. Phase 1 — Dataset quality and annotation policy

### 3.1 Full audit

Audit:
- image dimensions and aspect ratios;
- per-class object and image counts;
- bounding-box width, height, area, and relative image area;
- object-size bands;
- boxes at image boundaries;
- tiny boxes and likely unresolvable objects;
- overlapping boxes;
- duplicate and near-duplicate images;
- train/validation scene similarity;
- invalid normalized YOLO coordinates;
- empty/background-only labels;
- missing image-label pairs;
- people potentially missing `Person` annotations;
- missing-PPE boxes without plausible person association;
- class co-occurrence;
- viewpoint/scene distribution, clearly marking uncertain metadata.

Do not auto-correct labels based only on heuristics.

### 3.2 Review suspect annotations

Locate all 162 suspect rows and prioritise the 51 high-priority cases. Build a review manifest with image path, label file, row/annotation ID, class, reason, coordinates, local thumbnail reference, review status, reviewer, and timestamp.

Statuses:
`unreviewed`, `confirmed`, `corrected-in-derived-copy`, `exclude-with-reason`, `uncertain`.

Do not invent human review. If the user is not available to review a case, leave it unreviewed or uncertain. Make only defensible corrections, and only in a derived dataset copy. Keep a change log with old/new labels, reason, reviewer, and source annotation ID.

### 3.3 Annotation policy

Create `docs/ANNOTATION_POLICY.md` defining all 12 classes and rules for:
- helmet, gloves, vest, boots, goggles;
- missing-PPE labels;
- partially visible people;
- forklift/vehicle operators;
- unresolvable eye regions;
- ordinary eyeglasses versus protective goggles;
- tiny, occluded, or unjudgeable PPE;
- overlapping workers and boxes;
- when a missing-PPE label is justified;
- uncertain/excluded examples.

Critical: absence of a PPE detection is not proof of a violation. A missing-PPE class must be supported by a valid annotation and policy. Preserve conservative compliance logic.

If the source dataset's original policy is unknown, say so. Do not claim the new policy reproduces the original creator's intent.

**Acceptance:** all 162 suspects accounted for; 51 high-priority cases individually listed; ambiguities documented; original files unchanged; REPORT-019 written.

---

## 4. Phase 2 — Evaluation design and leakage-resistant splits

The existing 200-image validation set has already been used repeatedly. Preserve its historical results, but do not treat it as a pristine final test set.

Inspect whether the 800 training images can support a defensible train/development-validation/locked-test split. Group by scene/source and near-duplicate similarity so related frames or images cannot cross splits. Use image similarity and manual checks where practical. Stratify rare missing-PPE classes where possible, but prioritise preventing scene leakage.

Never split crops or annotations from one original image across train and test.

If the dataset is too small for a reliable locked test, state that limitation. Grouped cross-validation may support research, but retain an untouched final test set if feasible. If not feasible, do not claim that the 93–95% goal has been independently certified.

For each evaluation, report:
- precision and recall;
- mAP50 and mAP50-95;
- per-class AP50 and AP50-95;
- per-class precision/recall at the application operating point;
- confusion matrix;
- false positives and false negatives by class;
- background false positives;
- object-size-stratified results;
- scene/viewpoint breakdown only when metadata is reliable;
- latency, memory, and analysed FPS.

Record IoU thresholds, confidence thresholds, NMS settings, image size, evaluator version, matching rules, and dataset manifest.

Do not tune confidence thresholds on the locked test set. For comparisons, use paired image-level bootstrap confidence intervals where appropriate. Do not treat boxes from one image as independent samples.

**Acceptance:** split manifests and hashes saved; leakage checks documented; locked test excluded from training and threshold tuning; metric definitions explicit; REPORT-020 written.

---

## 5. Phase 3 — Data expansion, augmentation, small-object strategy

### 5.1 Additional datasets

Investigate additional PPE/construction datasets only when licence, provenance, class semantics, and label quality are clear. Do not scrape images of unclear rights. Do not import until a data-source register records dataset, source, licence, download date, version, hashes, mapping, and limitations.

If no suitable dataset is available, proceed with existing verified data and document the limitation. Never block all progress waiting for an external dataset.

### 5.2 Controlled augmentation

Experiment with conservative, physically plausible:
- scale/translation;
- horizontal flips only when semantically valid;
- moderate brightness/contrast and colour changes;
- mild blur/noise;
- moderate exposure variation;
- mosaic/mixup only if supported and beneficial;
- copy-paste only if labels and object boundaries remain valid.

Avoid transformations that erase tiny objects, distort PPE, or create impossible safety scenarios.

For every policy, save configuration, visualise samples and labels, verify boxes, compare class/size distributions, and run ablations. Synthetic robustness tests must be labelled separately and must not replace real-world test data.

### 5.3 Small-object investigation

Investigate:
- image sizes 768, 896, and 1024 within memory limits;
- multi-scale training if supported;
- tiled/sliced high-resolution inference with overlap and duplicate-box merging;
- resolution versus latency;
- class-aware sampling or loss weighting if supported and justified;
- training crops derived only from training images;
- whether tiny annotations are visually resolvable.

Do not blindly increase resolution. Measure gains, memory, and latency. Tiling must not generate duplicate safety events for one worker; test merging at image and frame level.

**Acceptance:** source licences documented; original data unchanged; augmented samples visually audited; small-object strategies compared; REPORT-021 written.

---

## 6. Phase 4 — YOLO26m training programme

Use the verified YOLO26m architecture and current training pipeline. Do not change architecture or dependencies without a controlled experiment.

### 6.1 Reproduce baseline

Re-run the existing YOLO26m configuration from verified pretrained weights. Confirm approximate reproducibility. Record:
- pretrained/checkpoint hashes;
- epochs, batch, image size;
- optimiser, learning rate/schedule, warm-up, weight decay;
- augmentation, patience, seed;
- device and actual acceleration;
- training duration and peak memory;
- loss/validation curves.

Previous run used 30 epochs and batch 4 on MPS. More epochs do not automatically improve generalisation.

### 6.2 Controlled experiment matrix

Plan and run a hardware-feasible matrix:
1. Reproduced YOLO26m baseline.
2. Longer training with early stopping and best-checkpoint retention.
3. Higher image size at safe batch size.
4. Improved conservative augmentation.
5. Class-imbalance strategy.
6. Small-object crop/tiling strategy.
7. Best combined configuration only after useful individual ablations are identified.

Before each experiment, write hypothesis, changed variable(s), fixed variables, expected trade-offs, and success criteria. Use unique run names and separate directories. Never overwrite checkpoints.

### 6.3 Hardware safeguards

Monitor memory pressure, swap, thermal state if available, and system responsiveness. Do not run multiple large training jobs concurrently. Stop safely if memory pressure becomes severe. Use resumable checkpoints if supported. Do not claim MPS/GPU acceleration unless logs confirm it.

Use at least three seeds for the leading candidate if practical. If compute prevents that, run the best feasible number and clearly state uncertainty. Report all seeds, not only the best result.

**Acceptance:** every run reproducible; configs and hashes saved; no overwrite; curves retained; REPORT-022 written.

---

## 7. Phase 5 — Model comparison and error analysis

Compare YOLO26n historical baseline, existing YOLO26m, and all new candidates under identical data, evaluator, class mapping, image size, and thresholds. Mark any non-controlled comparison clearly.

Review per-class:
- false positives/negatives;
- duplicate detections;
- localisation errors;
- PPE class confusions;
- tiny/occluded objects;
- background detections;
- ambiguous ground truth.

Prioritise `no_helmet`, `no_gloves`, `no_goggle`, `no_boots`, `no_vest`, and `Person`.

Generate contact sheets and error manifests from development data only. Do not use locked-test examples to tune.

Choose application thresholds on development data with a documented balance between missed violations and false alarms. Do not improve headline precision by sacrificing safety-critical recall. Report the trade-off. Per-class thresholds may be considered only if transparently supported by application logic and defensible policy.

Investigate confidence calibration if feasible. A detector confidence score is not automatically a probability of correctness; do not label it a calibrated safety probability.

**Acceptance:** overall and per-class comparison; traceable errors; false positives/negatives discussed; threshold choice documented; REPORT-023 written.

---

## 8. Phase 6 — Locked-test qualification

After selecting the best candidate using development data, evaluate it on the locked test using a frozen checkpoint and configuration.

Report precision, recall, mAP50, mAP50-95, per-class AP, per-class precision/recall, confusion matrix, FP/FN counts, confidence intervals where feasible, size-stratified results, reliable scene breakdowns, latency, memory, and failure cases.

Do not revise the model after viewing locked-test results and continue calling that same set untouched. If you change the model after inspecting test results, the set becomes development data; a new independent test is required for final certification.

A model does not meet the user's ambition merely because one metric reaches 93%. Disclose the exact metric, test-set size and representativeness, per-class performance, missing-PPE recall, uncertainty, and runtime. If the locked test is small, use wording such as “93% mAP50 on this limited test set,” not “93% real-world accuracy.”

**Acceptance:** frozen candidate/config hashed; locked-test protocol followed; all metrics disclosed; no test tuning; REPORT-024 qualification section complete.

---

## 9. Phase 7 — Controlled application integration

The user has approved YOLO26m as the direction. Integrate the qualified candidate only after it passes the gates, or clearly document a provisional integration if a gate cannot yet be passed.

Requirements:
- preserve YOLO26n as selectable rollback;
- store YOLO26m as a separate versioned checkpoint;
- record model name, architecture, training run, checkpoint hash, dataset version, class mapping, image size, thresholds, and evaluation report;
- validate checkpoint existence, class count/order, and metadata;
- never silently load an incompatible checkpoint;
- log active model identity in dashboard and application logs;
- provide safe fallback if model loading fails;
- preserve database and evidence;
- do not alter compliance association, event persistence, or alert rules without separate approval.

Run all existing tests (previously reported 124) and add tests for:
- YOLO26m loading and YOLO26n rollback;
- missing/corrupt checkpoint;
- incorrect class mapping;
- model switching and session restart;
- image/video/live processing;
- stale-box prevention;
- event generation and duplicate suppression;
- evidence persistence;
- no database reset.

Do not remove or weaken tests to get a green suite.

Re-run physical camera, replay, and video tests. Measure capture, analysed and rendered FPS (where actually measurable), dropped frames, inference mean/p50/p95/max, received-to-rendered latency, memory pressure, stale boxes, and event integrity. Previous YOLO26m physical-camera results were approximately 30.05 analysed FPS, 26.9 ms mean inference, and 28.4 ms p95 on the tested M5 setup; these are historical reference values, not guarantees.

Do not claim browser FPS unless measured.

**Acceptance:** YOLO26m selection works; YOLO26n rollback works; tests pass or failures are documented; user data intact; runtime measured; REPORT-024 integration section complete.

---

## 10. Phase 8 — Final decision and handoff

Create `REPORT-025-final-research-decision.md` and `experiments/accuracy_improvement/README.md`.

The final report must state:
1. Whether 93–95% was achieved and which exact metric.
2. Whether result is development validation or locked test.
3. Whether data is representative and leakage-resistant.
4. Selected checkpoint and SHA-256.
5. Per-class missing-PPE recall.
6. Precision/recall trade-off.
7. mAP50 and mAP50-95.
8. Runtime on the M5.
9. Remaining weaknesses and risks.
10. Reproduction commands.
11. Work remaining before real-site validation.

Do not start frontend redesign, unrelated dashboard features, deployment, or public release in this assignment. The user wants the main model work completed first.

---

## 11. Directory layout

Adapt after inspection; do not unnecessarily reorganise existing files:

```text
experiments/
  accuracy_improvement/
    manifests/
    splits/
    data_audit/
    annotation_review/
    augmented_samples/
    training/
    evaluation/
    error_analysis/
    qualification/
    reports/
    README.md

models/
  trained/
    # Preserve existing checkpoints.
    yolo26m_accuracy_candidate/
```

If current paths differ, retain them and document the mapping.

---

## 12. Claude Code execution protocol

1. Read this complete file before work.
2. Inspect actual project and previous reports.
3. Begin with Phase 0 only.
4. Produce REPORT-018 before proceeding.
5. Execute phases in order, with a report after every phase.
6. At each phase boundary, state completion, outstanding work, and readiness for the next phase.
7. If human review is required, prepare a review artifact and pause only that decision; continue independent safe work.
8. Do not ask the user to manually edit source code. If input is needed, request a precise, minimal review or decision.
9. Keep work within this specification.
10. If actual code conflicts with this specification, document the conflict and choose the least destructive solution.
11. If context limits are reached, write a continuation report with current phase, completed work, modified files, commands, results, next task, and safety constraints. On continuation, reread this specification and the continuation report.
12. Never claim 93–95% performance without the locked-test evidence described above.

**Final objective:** genuinely improve construction PPE and missing-PPE detection while preserving honest evaluation, real-time performance, dataset integrity, and the existing working application. Start with Phase 0. Do not begin frontend redesign or unrelated product development.
