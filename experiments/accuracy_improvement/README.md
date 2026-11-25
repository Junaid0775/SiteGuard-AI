# SiteGuard AI — YOLO26m accuracy-improvement programme

This folder holds the evidence for the programme defined in `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md` (project root). The programme ran Phases 0–8 between 2026-11-20 and 2026-11-23.

## Outcome in brief

- **Candidate:** `E3_m896`, a YOLO26m fine-tuned at 896 px (seed 42). Checkpoint sha256 `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6`, stored at `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/` with `model_card.json`.
- **Locked test** (160 held-out, in-distribution images, 2,480 objects):

| Metric | Value |
|---|---|
| mAP50 | 0.847 |
| mAP50-95 | 0.644 |
| Precision at the application operating point (conf 0.25) | 0.885 |
| Recall at the operating point | 0.862 |

- **Missing-PPE recall at 0.25:**

| no_helmet | no_gloves | no_goggle | no_boots | no_vest |
|---|---|---|---|---|
| 0.739 | 0.650 | 0.522 | 0.796 | 0.688 |

- **Targets not met:**
  - mAP50 target: 0.93;
  - precision and recall target: 0.90 each;
  - recall target for each missing-PPE class: 0.90.
- **Decision:** the candidate was **not promoted**. YOLO26n (`models/trained/best.pt`, sha256 `890dc61f…`) remains the application's active model and its automatic fallback.
- **Gain over the earlier models:**
  - on the locked test, the candidate beats the controlled 640-px reference E1 (mAP50 +0.021, 95 % CI [+0.003, +0.040]);
  - on development data, it beats the production YOLO26n (mAP50 +0.111 [+0.090, +0.131]; mean missing-PPE recall +0.191).
- **Reports:**
  - **REPORT-025** has the full decision;
  - **REPORT-024** has the qualification and integration evidence;
  - **`reports/HANDOFF-ML-to-frontend.md`** has the frontend integration requirements.

## Reports

| Report | Phase |
|---|---|
| `reports/REPORT-018-discovery-and-integrity.md` | 0: environment, protected-file hashes, model identities |
| `reports/REPORT-019-dataset-quality-and-label-policy.md` | 1: dataset audit, 178 suspect annotations (human review still pending), annotation policy |
| `reports/REPORT-020-evaluation-protocol-and-splits.md` | 2: grouped train 640 / dev 200 / locked test 160 split, evaluation protocol v1, locked-test guard |
| `reports/REPORT-021-data-expansion-and-augmentation.md` | 3: data sources (none imported), augmentation audit, small-object options, memory limits |
| `reports/REPORT-022-training-experiment-matrix.md` | 4: training runs E1, E3, E4, E5; skipped E2, E6, E7 and extra seeds |
| `reports/REPORT-023-model-comparison-and-error-analysis.md` | 5: dev comparison, bootstrap, strata, errors, thresholds, calibration |
| `reports/REPORT-024-qualification-and-integration.md` | 6–7: locked test, gates, integration, runtime, tests |
| `reports/REPORT-025-final-research-decision.md` | 8: final decision and remaining work |
| `reports/HANDOFF-ML-to-frontend.md` | Handoff: metrics, checkpoint identity, promotion decision, frontend integration requirements |
| `reports/CONTINUATION-001.md` | Continuation notes, the overheating incident of 2026-11-20 and the deadline re-plan |

## Folders

| Folder | Contents |
|---|---|
| `manifests/` | Integrity manifests (`20261120-005540_phase0/`) and pre-change copies of every modified source file (`*.before_phase*`) |
| `data_audit/`, `annotation_review/` | Phase 1 audit outputs and the label-review page (`review.html`, `review_manifest.csv`) |
| `splits/` | `train.txt`, `dev.txt` and `test.txt` (locked) with their analysis |
| `datasets/v1_original_labels/` | Derived dataset of symlinks to `../construction-ppe` (labels unchanged); `dev.yaml` trains on train and validates on dev; `locked_test.yaml` is the locked test |
| `datasets/v2_train_tiles/` | Training-only tiles (Phase 3; not used for training because E6 was skipped) |
| `augmented_samples/` | Phase 3 augmentation previews |
| `training/` | One folder per run (weights, `args.yaml`, `results.csv`, plots), `configs/` (plans, hyperparameter files), `logs/` (training logs, monitor CSVs, runner log), matrix YAMLs, `matrix_status.json` |
| `evaluation/` | `dev_<run>/` and `test_<run>/` outputs of `scripts/accuracy/evaluate.py` |
| `error_analysis/` | Dev comparisons (`comparison_dev_vs_E1/`, `comparison_dev_vs_yolo26n/`), error manifests and contact sheets (`E3_m896_dev/`, `E1_m640_base_dev/`), `calibration/` |
| `qualification/` | Pre-registration, frozen-candidate record, locked-test ledger and notes, locked-test analysis, real-time results (`realtime/`), test logs (`tests/`), logs |

## Rules that apply to anyone continuing this work

- **Original dataset:** `../construction-ppe/` is read-only.
- **Locked test:**
  - only `scripts/accuracy/evaluate.py --split test` and `scripts/accuracy/compare_candidates.py --split test` may read it;
  - both require a purpose and append a row to `qualification/locked_test_access_log.csv`;
  - it has now been used once for qualification. Using it to tune anything turns it into development data, and a new independent test set is then needed for any certification claim.
- **Checkpoints:** never overwrite one; use new versioned paths. `models/trained/best.pt` is the production rollback model.
- **Thresholds and compliance rules:** change these only with explicit approval, and re-qualify afterwards.
- **Accuracy wording:** never quote a single "accuracy". Quote the exact metric, the split and its size, for example "mAP50 0.847 on the 160-image in-distribution locked test".
- **Private data:** `experiments/live_audit/webcam/` contains private camera frames. Keep them local; do not open, upload or commit them.

## Reproduction (from the project root)

```bash
# Phase 2 splits (deterministic)
.venv/bin/python scripts/accuracy/phase2_splits.py build --emb-threshold 0.95 --test-images 160 --seed 0
# Phase 4 training (guarded queue; equivalent single command in REPORT-022 §10)
.venv/bin/python scripts/accuracy/run_matrix.py experiments/accuracy_improvement/training/matrix_phase4.yaml
# Dev evaluation of the candidate
.venv/bin/python scripts/accuracy/evaluate.py --weights experiments/accuracy_improvement/training/E3_m896/weights/best.pt \
  --split dev --imgsz 896 --out experiments/accuracy_improvement/evaluation/dev_E3_m896
# Dev comparison and error analysis (REPORT-023 §11 has all four commands)
.venv/bin/python scripts/accuracy/compare_candidates.py --split dev --reference dev_E1_m640_base --runs dev_E3_m896 ... --out ...
.venv/bin/python scripts/accuracy/error_sheets.py --run dev_E3_m896 --out experiments/accuracy_improvement/error_analysis/E3_m896_dev
# Real-time tests (offline; the camera mode needs the user's go-ahead)
.venv/bin/python scripts/engineering/realtime_eval.py offline --model yolo26n=models/trained/best.pt@640 \
  --model e3_candidate=models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt@896 \
  --out experiments/accuracy_improvement/qualification/realtime
# Tests and integrity
.venv/bin/python -m pytest -q
.venv/bin/python scripts/accuracy/integrity_manifest.py verify experiments/accuracy_improvement/manifests/20261120-005540_phase0 --json
```

The locked-test command is in REPORT-024. It must not be re-run to tune anything.
