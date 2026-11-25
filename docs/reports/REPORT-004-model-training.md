# REPORT-004 — Model Training

**Date:** 2026-11-19 **Status:** Complete

## A. Task summary

- **Requested:** fine-tune a small pretrained Ultralytics model (YOLO26n if available) on the 12-class dataset. Save best.pt and last.pt plus logs, plots and the parameters used, and handle interruptions.
- **Done:** a 30-epoch transfer-learning run on MPS. `models/trained/best.pt` was produced and verified.
- **Completion:** full.

## B. Technical implementation

- `src/training/train.py`:
  - validates the dataset, builds the mirror and loads `models/pretrained/yolo26n.pt`;
  - calls `YOLO.train()` with parameters from `configs/settings.yaml`;
  - writes `training_metadata.json`;
  - copies best/last into `models/trained/`, backing up any existing file first (`best.<timestamp>.bak.pt`);
  - writes `MODEL_SOURCE.json`;
  - supports `--resume <last.pt>`.
- Run folders use `exist_ok=False`, so a new run never overwrites an old one.
- **Transfer learning:** COCO-pretrained weights were loaded and the head re-sized to 12 classes. The log shows `Overriding model.yaml nc=80 with nc=12` and `Transferred 708/708 items from pretrained weights`.
- **Parameters:** epochs 30, imgsz 640, batch 8, patience 15, AdamW (auto) lr 0.000625, seed 42, deterministic, cache off, device mps.

## C. Files created

| File | Purpose |
|---|---|
| `src/training/train.py` | Training script |
| `configs/settings.yaml` (`training:` section) | Central parameters |
| `experiments/smoke_test/` | 1-epoch, 10 % smoke run (pipeline check only, not used by the app) |
| `experiments/siteguard_yolo26n/` | Main run: weights, `results.csv`, plots, `args.yaml`, `training_metadata.json` |
| `experiments/train_main_stdout.log`, `experiments/training.log` | Logs |
| `models/trained/best.pt`, `last.pt`, `MODEL_SOURCE.json` | Application checkpoint and its origin |
| `docs/TRAINING.md` | Training documentation |

## D. Files modified

| File | Change |
|---|---|
| `src/training/train.py` | Metadata writing moved into `write_metadata()`, and now also used after `--resume`. The resume path is checked to exist. No change to normal training behaviour. |

## E. Commands executed

```bash
.venv/bin/python -m src.training.train --epochs 1 --fraction 0.1 --no-promote --name smoke_test
.venv/bin/python -m src.training.train > experiments/train_main_stdout.log 2>&1
```

## F. Testing and verification

| Test | What | Command | Result |
|---|---|---|---|
| Smoke training | End-to-end train and val on 80 images | as above | PASS (0.7 min) |
| Original dataset untouched by caches | `find construction-ppe -newer …` | — | PASS (no new files) |
| Full training | 30 epochs | as above | PASS (exit 0, 21.2 min) |
| Interrupt and resume | Kill with SIGTERM after epoch 1, then `--resume …/last.pt` | see acceptance table | PASS |
| best.pt loads, 12 classes, task detect | `pytest tests/test_image_and_model.py::test_model_loads_with_dataset_class_names` | pytest | PASS |
| Real inference format | `…::test_detection_output_format` | pytest | PASS |

## G. Model and dataset status

- **Dataset:** construction-ppe, 800 train / 200 val, 12 classes (mapping unchanged).
- **Checkpoint:** `models/trained/best.pt` from epoch 25 (best fitness), sha256 `890dc61fd024b247…`, 5.44 MB.
- **Validation (real, 200 images):** precision 0.832, recall 0.681, mAP50 0.734, mAP50-95 0.523.
- **Hardware:** Apple M5 via MPS, about 3.3 GB GPU memory, about 42 s per epoch.

## H. Errors and resolutions

| Issue | Resolution |
|---|---|
| `UserWarning: index_put_with_accumulate_mps does not have a deterministic implementation` | Expected with `deterministic=True` on MPS. Results may vary very slightly between runs. |
| Ultralytics forces `workers=0` on MPS | Expected behaviour. Training was still fast enough. |
| First interrupt test did not interrupt (SIGINT ignored by a background job) | Re-tested with SIGTERM, which is a harder, crash-like stop. Resume verified. |
| Resume path wrote no metadata | Added `write_metadata()`, so resumed runs write `training_metadata_resumed.json` |

## I. Acceptance criteria

| Criterion | Status |
|---|---|
| Pretrained weights used (no training from scratch) | PASS |
| All 12 class IDs, meaning unchanged | PASS |
| Central configuration | PASS |
| Logs, validation results and plots saved | PASS |
| best.pt and last.pt saved | PASS |
| Exact versions and parameters recorded | PASS (`training_metadata.json`, `args.yaml`) |
| Interruption handling | PASS. A 4-epoch run (`--name resume_test`, 10 % data) was hard-killed with SIGTERM during epoch 2, then `--resume experiments/resume_test/weights/last.pt` continued it: Ultralytics logged "Resuming training … from epoch 2 to 4 total epochs", `results.csv` shows epochs 1–4, exit code 0, and `training_metadata_resumed.json` was written. The Ctrl-C (KeyboardInterrupt) message path was **not** exercised, because SIGINT is ignored by background jobs in a non-interactive shell. |
| No checkpoint overwrite without backup | PASS (backup logic in place; there was no previous best.pt) |
| Valid best.pt before claiming the model is ready | PASS |

## J. Remaining work

- Optional longer schedule (more epochs). Not tested.
- The `no_goggle` class is weak (mAP50 0.148, 82 val boxes). It would need more data.

## K. Next task

Detection, compliance and event pipeline (REPORT-005).
