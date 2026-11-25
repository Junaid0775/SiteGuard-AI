# REPORT-018 — Phase 0: Discovery, Environment and Integrity

**Programme:** YOLO26m accuracy improvement (`SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md`, §2)
**Date:** 2026-11-20, 00:51–01:00 IST
**Evidence folder:** `experiments/accuracy_improvement/manifests/20261120-005540_phase0/`
**Status:** **Complete.** All Phase 0 acceptance criteria pass (§17). No application code, configuration, checkpoint or dataset file was modified.

---

## 1. Objective

Spec §2:
- verify the actual workspace, environment and model identities before any change;
- inventory and hash every protected file;
- confirm the original dataset is untouched;
- measure MPS and memory;
- record the baseline test suite.

## 2. Scope

Discovery and preservation only:
- no training, tuning, label edits or dependency changes;
- no application changes.

The only writes are this report, three new read-only tools under `scripts/accuracy/`, the evidence folder, a verbatim copy of the specification, and a log row.

## 3. Summary of findings

| Item | Result |
|---|---|
| Specification | Not on disk at the start; it arrived as a message attachment. Saved verbatim as `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md` (project root) so it can be reread on continuation |
| Active application checkpoint | `models/trained/best.pt`: **YOLO26n**, sha256 `890dc61f…995b9b`; set by `configs/settings.yaml → model.trained_weights` |
| Previously evaluated YOLO26m | `experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt`, sha256 `399c4e5b…1773f`. Both hashes equal the values recorded in REPORT-014/015 |
| Model identity re-check | Both checkpoints re-validated with the historical procedure. **All four headline metrics and all 48 per-class values reproduce exactly** (largest difference 0.0000) |
| Original dataset | 2,004 files; **2,004/2,004 match the pre-project baseline** `data/dataset_baseline.sha256`; 1,000/1,000 image hashes match the dataset's own `manifest.jsonl`; 0 new, 0 missing |
| Class mapping | `configs/dataset.yaml` = original `data.yaml` = the spec's table = names stored in both checkpoints (12 classes, IDs 0–11) |
| Environment | Python 3.12.16 (uv venv), Ultralytics 8.4.215, torch 2.15.0, OpenCV 5.1.0, NumPy 2.5.5, Pillow 13.0.0. **Albumentations not installed.** MPS available and selected by both the inference and training code |
| Hardware state | Apple M5 (4P + 6E cores), 16 GB. 70–73 % memory free, swap 3.68 of 5.12 GB used. **On battery: 27 % → 26 %, discharging** |
| Tests | **124 passed, 0 failed, 0 skipped** (12.70 s) |
| Integrity after Phase 0 | Re-verified: dataset 0 changed / 0 missing / 0 new; protected files 0 changed; user data 0 changed |

## 4. Environment and hardware state (`environment.json`, `packages.txt`)

| Item | Value |
|---|---|
| Machine | Mac17,3, Apple M5, 10 CPU cores (4 performance, 6 efficiency), 16.0 GB unified memory |
| OS | macOS (Darwin 27.0.0); details in `environment.json → os` |
| Python | 3.12.16, CPython, virtual environment `.venv` (base: uv-managed CPython) |
| Key libraries (imported versions) | ultralytics 8.4.215; torch 2.15.0; OpenCV 5.1.0; NumPy 2.5.5; Pillow 13.0.0; albumentations **absent** |
| All distributions | 76, listed with versions in `packages.txt` |
| MPS | Built and available. A 2048×2048 matmul ×10 ran on `mps:0` in 70.3 ms, including the first-call warm-up. Recommended maximum working set 12.71 GB |
| Device selection actually used | `src/detection/detector.py: resolve_device('auto')` returns `mps`; `src/training/train.py: pick_device('auto')` returns `mps` |
| Ultralytics config | Project-local (`.ultralytics/`); `runs_dir` = `experiments/`, `weights_dir` = `models/pretrained/` |
| Memory | 70 % free at 00:56, 73 % at 00:57 (`memory_pressure`); swap used 3,683 MB of 5,120 MB |
| Power / thermal | Battery 27 % → 26 %, discharging. No thermal or performance warning recorded (`pmset -g therm`) |
| Disk | 737 GB free of 995 GB |

**Albumentations:**
- Ultralytics applies its built-in light Albumentations transforms (Blur, MedianBlur, ToGray, CLAHE, each p = 0.01) only when the package is installed.
- So **no previous run used them**.
- This matters for the blur and noise policies in Phase 3. Installing it would be a dependency change, made only for a verified need and isolated (spec §2).

**Power:** long MPS training on battery is not viable. Phases 3–4 need mains power.

## 5. Files inspected

| Area | Files |
|---|---|
| Workspace | Project tree (2 levels); `README.md`; both specifications |
| Training | `src/training/train.py` (arguments, defaults, promotion logic); `configs/settings.yaml → training` |
| Inference / loading | `src/detection/detector.py` (`PPEDetector`, `resolve_device`, `info`); `configs/settings.yaml → model, inference` |
| Dashboard | `app.py` (model loading via `st.cache_resource`, model status, settings page) |
| Dataset configuration | `configs/dataset.yaml`; `data/generated/dataset_resolved.yaml`; `data/dataset_mirror/` (2,000 symlinks + 2 label caches); `src/utils/paths.py`; `src/utils/dataset_tools.py` |
| Original dataset (read only) | `../construction-ppe/data.yaml`, `README.md`, `LICENSE.txt` (first lines), `manifest.jsonl`, file listing, label line count |
| Models | `models/trained/{best.pt,last.pt,MODEL_SOURCE.json}`; `models/pretrained/{yolo26n.pt,yolo26m.pt}`; all 18 `.pt` files under `experiments/` (listed in `protected.csv`) |
| Reports | REPORT-010 to REPORT-017. The context in spec §1 was checked against them: all quoted values match, including the corrected missing-PPE recall values from the REPORT-015 correction |
| Tests | `tests/` (11 files), `pytest.ini` |
| Existing tooling | `scripts/engineering/hash_manifest.py` (its create/verify logic was reused in a new script) |

## 6. Files created or modified

| Path | Action | Purpose |
|---|---|---|
| `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md` | **created** | Verbatim copy of the specification (protocol rule 11: reread on continuation) |
| `scripts/accuracy/integrity_manifest.py` | created | Timestamped SHA-256 manifests (dataset / protected / user data), provenance checks, verify with new-file detection |
| `scripts/accuracy/phase0_environment.py` | created | Environment, device, memory, power and disk record |
| `scripts/accuracy/model_identity.py` | created | Checkpoint identity (hash, architecture, classes, parameters, stored training arguments) and optional re-validation |
| `experiments/accuracy_improvement/{manifests,splits,data_audit,annotation_review,augmented_samples,training,evaluation,error_analysis,qualification,reports}/` | created | Spec §11 layout |
| `experiments/accuracy_improvement/manifests/20261120-005540_phase0/*` | created | Evidence (§7) |
| `experiments/accuracy_improvement/reports/REPORT-018-discovery-and-integrity.md` | created | This report |
| `docs/IMPLEMENTATION_LOG.md` | one row appended | Project log convention |

**No existing file was modified** apart from the log row.

**Side effects observed:**
- The test suite rewrote `data/generated/dataset_resolved.yaml` with **identical content**: its mtime changed, its hash did not. `tests/test_dataset.py` regenerates it.
- Ultralytics refreshed its project-local settings file `.ultralytics/Ultralytics/settings.json`.

Neither is user data.

## 7. Commands (run from `SiteGuard-AI/`)

```bash
pmset -g batt; pmset -g therm                      # power and thermal state
.venv/bin/python scripts/accuracy/integrity_manifest.py create phase0
.venv/bin/python scripts/accuracy/phase0_environment.py experiments/accuracy_improvement/manifests/20261120-005540_phase0
.venv/bin/python scripts/accuracy/model_identity.py   experiments/accuracy_improvement/manifests/20261120-005540_phase0 --val
.venv/bin/python -m pytest -q --junitxml=experiments/accuracy_improvement/manifests/20261120-005540_phase0/pytest_baseline.xml
.venv/bin/python scripts/accuracy/integrity_manifest.py verify experiments/accuracy_improvement/manifests/20261120-005540_phase0 \
    --json experiments/accuracy_improvement/manifests/20261120-005540_phase0/verify_end_of_phase0.json
```

Evidence files:
- `dataset.csv` (2,004 rows), `protected.csv` (824), `user_data.csv` (313), `summary.json`;
- `environment.json`, `packages.txt`, `model_identity.json`;
- `pytest_baseline.{txt,xml}`, `verify_end_of_phase0.json`.

## 8. Configurations as found

**Inference** (`configs/settings.yaml`): weights `models/trained/best.pt`; confidence 0.25; NMS IoU 0.5; image size 640; device auto (= mps). Live and video analyse every frame (R1/R2 from REPORT-012).

**Compliance and events** — recorded as the baseline; must not change during model experiments (spec §0.1 rule 10):
- Compliance: required PPE helmet, vest and gloves; person confidence 0.40; violation confidence 0.50; evidence confidence 0.40; containment 0.60; ambiguity margin 0.15; person box margin 0.10; conflict IoU 0.50.
- Events: cooldown 30 s; match IoU 0.30; 3 consecutive hits; candidate timeout 3 s.

**Training entry point** (`src/training/train.py`, defaults from `settings.yaml → training`):
- epochs 30, imgsz 640, batch 8, workers 4, patience 15, seed 42;
- `deterministic=True`, cache off, optimizer `auto` (resolves to AdamW, lr0 0.000625), AMP on;
- `exist_ok=False`, so a new run never reuses a folder.
- Dataset: default YAML generated from the symlink mirror, or `--data`.

**Dataset YAML:**
- `configs/dataset.yaml` points to `../construction-ppe` through the symlink mirror `data/dataset_mirror/`.
- The mirror has 2,000 symlinks, all resolving into the original dataset, 0 broken.
- Ultralytics writes its label caches into the mirror, never into the original folder.

## 9. Seeds

- Both existing checkpoints: seed 42, `deterministic=True` (stored `train_args`).
- No new training was run in this phase.
- The re-validation is deterministic: no sampling, identical results.

## 10. Data provenance and hashes

| Item | Value |
|---|---|
| Source | Ultralytics Construction-PPE (`../construction-ppe/README.md`): "created and open-sourced in November 2026 by the Ultralytics team"; "human-collected and generated images"; "expert human annotation and AI auto-annotation"; "All images and annotations were reviewed and corrected" |
| Licence | CC BY 4.0 (`LICENSE.txt`). Attribution and indication of changes are required when redistributing or adapting |
| Split | 800 train / 200 val; **no separate test split** (README). The README advises: "Use independent deployment imagery for final evaluation" |
| Stated label policy | One rule is given by the source: "Missing-PPE labels refer to visible body regions; occlusion alone is not evidence of missing equipment." No fuller policy is published in the dataset folder (input to Phase 1) |
| Counts verified | 1,000 images and 1,000 label files; **14,863 label rows**; 4 metadata files |
| Filename families | `ultralytics-ppe-nov2026-NNN.jpg`: 566 train / 141 val. `source-<32 hex>.jpg`: 234 train / 59 val. What each family means (collected or generated) is **not documented**; to be investigated in Phases 1–2 |
| Hashes | `dataset.csv`: per-file SHA-256 of all 2,004 files (647.8 MB). Equal to the pre-project baseline (2,004/2,004) and to the dataset's own `manifest.jsonl` (1,000/1,000 images) |

**Protected checkpoints** (`summary.json → key_checkpoints`):

| Path | Role | SHA-256 | Bytes |
|---|---|---|---:|
| `models/trained/best.pt` | **Active** application checkpoint (YOLO26n) | `890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b` | 5,443,013 |
| `models/trained/last.pt` | YOLO26n last epoch | `c32a10ec685b9e71f0621189af9ca96b899c52db823cf859aadddbf5a24d750d` | 5,443,013 |
| `experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt` | **Previously evaluated YOLO26m** | `399c4e5be335e3544afe185c7abb08d5fc894a382b891d970f71b94df3f1773f` | 44,029,401 |
| `experiments/yolo26m/training/yolo26m_e30_b4/weights/last.pt` | YOLO26m last epoch | `5412989709673b497de966a3958fbbd40abd7921470ccddc1c2f18b76f05596f` | 44,029,401 |
| `models/pretrained/yolo26n.pt` | Pretrained YOLO26n | `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef` | 5,544,453 |
| `models/pretrained/yolo26m.pt` | Pretrained YOLO26m (prefix matches REPORT-013) | `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7` | 44,255,705 |

**User data** (`user_data.csv`):
- events DB `outputs/siteguard_events.db`, sha256 `86ba4321…8575`, 32,768 B;
- 122 evidence images and 5 other outputs;
- 184 private webcam audit files under `experiments/live_audit/webcam/`. These are hashed locally only, never copied or opened.

The dashboard server log is flagged as volatile.

## 11. Model identities (`model_identity.json`)

| | YOLO26n (active) | YOLO26m (previous) |
|---|---|---|
| Architecture YAML / classes | `yolo26n.yaml`, nc 12 | `yolo26m.yaml`, nc 12 |
| Parameters (unfused) | 2,539,232 | 21,791,392 |
| Class names in checkpoint = dataset | yes | yes |
| Stored training arguments | 30 epochs, batch 8, imgsz 640, seed 42, AdamW lr0 0.000625, close_mosaic 10, patience 15 | 30 epochs, batch 4, imgsz 640, seed 42, AdamW lr0 0.000625, close_mosaic 10, patience 15 |
| Created / Ultralytics version | 2026-11-19 18:56 / 8.4.215 | 2026-11-19 22:57 / 8.4.215 |
| Source run | `experiments/siteguard_yolo26n/` (promoted 18:59, `MODEL_SOURCE.json`) | `experiments/yolo26m/training/yolo26m_e30_b4/` (not promoted) |

## 12. Metrics: definitions, denominators and identity re-validation

**Definitions** (Ultralytics 8.4.215 `val`, used unchanged):
- **Precision / recall:** mean over the 12 classes, at the confidence that maximises each class's F1. They are not values at the app threshold.
- **mAP50:** mean over classes of the area under the interpolated precision–recall curve (101-point), with a prediction counted as correct at IoU ≥ 0.50.
- **mAP50-95:** the same, averaged over IoU 0.50:0.05:0.95.
- **Matching:** greedy by IoU per class.

**Settings:** conf 0.001, NMS IoU 0.7, max 300 detections, imgsz 640, batch 8, MPS.

**Denominators:** 200 val images, 2,961 ground-truth boxes. Per class:
- helmet 294, gloves 381, vest 340, boots 481, goggles 139, Person 481;
- no_helmet 179, no_goggle 82, no_gloves 203, no_boots 178, forklift 73, no_vest 130.

**Status of this split:** the 200-image val set has been used repeatedly. It selected both models' best epochs and served every earlier comparison. From now on it is **development data**, not a pristine test (spec §4).

| Metric | YOLO26n historical / re-run | YOLO26m historical / re-run |
|---|---|---|
| Precision | 0.8322 / 0.8322 | 0.8909 / 0.8909 |
| Recall | 0.6809 / 0.6809 | 0.7773 / 0.7773 |
| mAP50 | 0.7339 / 0.7339 | 0.8311 / 0.8311 |
| mAP50-95 | 0.5227 / 0.5227 | 0.6195 / 0.6195 |

**Per class (re-run).** P and R here are Ultralytics val values. App-threshold values (conf 0.25) are in REPORT-015 §10.1 and `operating_point.json`.

| Class | n P | n R | n AP50 | n AP50-95 | m P | m R | m AP50 | m AP50-95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| helmet | 0.901 | 0.776 | 0.825 | 0.627 | 0.938 | 0.881 | 0.916 | 0.743 |
| gloves | 0.842 | 0.735 | 0.793 | 0.601 | 0.906 | 0.835 | 0.889 | 0.737 |
| vest | 0.936 | 0.829 | 0.887 | 0.685 | 0.952 | 0.875 | 0.920 | 0.753 |
| boots | 0.812 | 0.682 | 0.771 | 0.572 | 0.828 | 0.790 | 0.849 | 0.659 |
| goggles | 0.829 | 0.921 | 0.924 | 0.561 | 0.940 | 0.957 | 0.967 | 0.718 |
| Person | 0.933 | 0.897 | 0.940 | 0.781 | 0.954 | 0.948 | 0.975 | 0.863 |
| no_helmet | 0.894 | 0.553 | 0.652 | 0.383 | 0.858 | 0.687 | 0.756 | 0.477 |
| no_goggle | 0.382 | 0.128 | 0.148 | 0.045 | 0.789 | 0.427 | 0.531 | 0.182 |
| no_gloves | 0.898 | 0.564 | 0.620 | 0.384 | 0.880 | 0.687 | 0.765 | 0.484 |
| no_boots | 0.839 | 0.673 | 0.748 | 0.574 | 0.868 | 0.714 | 0.805 | 0.659 |
| forklift | 0.801 | 0.795 | 0.807 | 0.585 | 0.879 | 0.836 | 0.848 | 0.639 |
| no_vest | 0.920 | 0.619 | 0.692 | 0.475 | 0.899 | 0.692 | 0.753 | 0.519 |

**Gap to the programme targets (facts only):**
- Best existing mAP50 on development data is 0.831 against a target of ≥ 0.93.
- Missing-PPE recall at the app threshold (YOLO26m, REPORT-015): 0.476 (no_goggle) to 0.715 (no_helmet), against a target of ≥ 0.90 per class.
- no_goggle AP50 is 0.531.

These are development-set values. Whether the targets are reachable is a question for Phases 1–6.

## 13. Tests and exact counts

| Item | Value |
|---|---|
| Command | `.venv/bin/python -m pytest -q` (`pytest.ini`: `testpaths = tests`) |
| Result | **124 passed, 0 failed, 0 skipped, 0 errors**, 12.70 s |
| Per file | test_app 15, test_compliance 15, test_compliance_regression 15, test_dataset 13, test_events_and_reports 10, test_frame_sync 13, test_image_and_model 8, test_live_audit 13, test_model_loading 5, test_pipeline_integration 4, test_resolution_coordinates 13 |
| Evidence | `pytest_baseline.txt`, `pytest_baseline.xml` |

## 14. Findings that constrain later phases

1. **Promotion risk in the training entry point.**
   - Without `--no-promote`, `src/training/train.py` copies the new `best.pt` and `last.pt` into `models/trained/`, after a backup.
   - That would replace the active checkpoint, which this programme forbids (rule 4).
   - **Decision:** every run in this programme passes `--no-promote` and a versioned `--project` under `experiments/accuracy_improvement/training/`. The Phase 4 runner will enforce this.
2. **The training entry point cannot pass experiment parameters.**
   - `train.py` exposes only epochs, imgsz, batch, workers, patience, device, name, project, resume and fraction.
   - Augmentation, schedule, multi-scale and sampling parameters are fixed at Ultralytics defaults.
   - Phase 3/4 will add a minimal, backward-compatible override mechanism with a test, or a separate runner that uses the same code path. The decision will be documented when made.
3. **The model loader validates little.**
   - `PPEDetector.load()` checks only that the file exists and that the task is `detect`.
   - It does not check the class count or order, and it has no metadata or fallback.
   - The dashboard has **no model selector**: the model is fixed by `settings.yaml → model.trained_weights` and cached per server process (`st.cache_resource`), so a change needs a restart.
   - These are Phase 7 requirements.
4. **Albumentations is absent** (§4). Blur and noise augmentation will need either an isolated dependency addition or a custom transform.
5. **Power:** on battery at 26 %. Long training must wait for mains power.
6. **Dataset README:** it gives one labelling rule (missing-PPE refers to visible body regions) and recommends independent deployment imagery for final evaluation. Both feed Phases 1–2.
7. **Two filename families** with undocumented meaning. Possible source or generation grouping, relevant to leakage-resistant splitting (Phase 2).

## 15. Limitations

- Device and memory figures are a snapshot taken on battery power. Training-time memory is measured in Phase 4.
- The meaning of the `source-*` and `ultralytics-ppe-*` families is not established.
- The re-validation confirms identity and reproducibility on the development set only. It says nothing about generalisation.

## 16. Decisions

- Keep the existing project layout. New work lives under `experiments/accuracy_improvement/`, plus `scripts/accuracy/` for tools.
- Treat the original 200-image val split as development data from now on.
- All new training: `--no-promote`, versioned run names, never `exist_ok=True`, never write into `models/trained/` until Phase 7 gates pass. Phase 7 uses a new versioned folder (`models/trained/yolo26m_accuracy_candidate/`).
- No dependency changes in Phase 0.

## 17. Acceptance criteria (spec §2)

| Criterion | Status | Evidence |
|---|---|---|
| Exact paths and model identities verified | **PASS** | `model_identity.json`: hashes equal recorded values; architecture, classes and stored arguments read; metrics reproduced exactly |
| Protected files inventoried and hashed | **PASS** | `dataset.csv`, `protected.csv`, `user_data.csv`, `summary.json` |
| Original data confirmed read-only | **PASS** | Unchanged against the pre-project baseline and the dataset's own manifest. Verified again at the end of the phase: 0 changed, 0 missing, 0 new. Training and validation read through the mirror, so no cache is written into the original folder |
| MPS and available memory measured | **PASS** | `environment.json → mps, memory` |
| Baseline tests recorded | **PASS** | 124 passed (`pytest_baseline.*`) |
| REPORT-018 written | **PASS** | This file |

## 18. Next-phase readiness

**Ready for Phase 1** (dataset quality and annotation policy). It needs no training and runs safely on battery.

**Outstanding:**
- Mains power before Phases 3–4.
- Human review of suspect labels (Phase 1). A review artefact will be prepared. Cases stay `unreviewed` or `uncertain` until you review them; no human review will be claimed.
