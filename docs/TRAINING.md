# SiteGuard AI — Training

## 1. Approach: transfer learning

SiteGuard does **not** train a network from scratch. It starts from **YOLO26n** (Ultralytics YOLO26, nano size, 2.57 M parameters), pretrained on the 80-class COCO dataset. Ultralytics then:

1. loads the pretrained backbone and neck weights;
2. replaces the 80-class detection head with a 12-class head that matches `configs/dataset.yaml`. The log shows `Overriding model.yaml nc=80 with nc=12` and `Transferred …/… items from pretrained weights`;
3. fine-tunes all layers on the 800 training images, validating on the 200 val images after every epoch;
4. keeps `best.pt` (highest validation fitness = 0.1·mAP50 + 0.9·mAP50-95) and `last.pt`.

**Why YOLO26n?** It is the smallest current Ultralytics detector. It is a supported asset of the installed Ultralytics 8.4.215 (`yolo26n` is in `GITHUB_ASSETS_STEMS`), and it runs in real time on an M5 MacBook Air. Its end-to-end, NMS-free head simplifies post-processing.

## 2. Configuration

All parameters live in `configs/settings.yaml` (`training:` section). They can be overridden on the command line.

| Parameter | Value | Reason |
|---|---|---|
| epochs | 30 | Spec asks for a conservative 20–30. See results for whether more would help. |
| imgsz | 640 | Standard YOLO resolution. Images are 1024–2048 px and are letterboxed down. |
| batch | 8 | Uses about 3.3 GB of unified memory on MPS, which is safe on a 16 GB machine. |
| workers | 4 (Ultralytics forces 0 on MPS) | Ultralytics loads data in the main process on MPS. |
| patience | 15 | Early stopping if validation fitness stops improving. |
| optimizer | auto (AdamW, lr 0.000625, momentum 0.9) | Chosen automatically by Ultralytics for short schedules. |
| seed / deterministic | 42 / True | Reproducibility. Some MPS ops have no deterministic kernel, which Ultralytics warns about. |
| cache | false | Keeps memory low. |
| device | `mps` (auto-detected) | Apple-silicon GPU. |

Data: `data/generated/dataset_resolved.yaml`, which points to the symlink mirror of the original dataset.

## 3. How to run

```bash
cd "~/Desktop/471 Project/SiteGuard-AI"
.venv/bin/python -m src.training.train                      # full run (settings.yaml)
.venv/bin/python -m src.training.train --epochs 1 --fraction 0.1 --no-promote --name smoke_test   # 1-minute smoke test
```

What the script does:

1. Validates the dataset and builds the mirror.
2. Trains into `experiments/<run_name>/`. Ultralytics adds a numeric suffix when the folder exists, so old runs are never overwritten.
3. Writes `experiments/<run>/training_metadata.json`, with all parameters, library versions, duration and final metrics.
4. Copies `best.pt` and `last.pt` to `models/trained/`. An existing file there is first renamed to `best.<timestamp>.bak.pt`, so it is never lost. `models/trained/MODEL_SOURCE.json` records which run the checkpoint came from.

**Interrupted training:** `last.pt` is saved at the end of every epoch. To continue an interrupted run, whether it was stopped with Ctrl-C, by a crash, or because the laptop was closed:

```bash
.venv/bin/python -m src.training.train --resume experiments/siteguard_yolo26n/weights/last.pt
```

The run continues from the first unfinished epoch with its original settings, and writes `training_metadata_resumed.json`.

*Tested 2026-11-19:* a 4-epoch run (`experiments/resume_test`) was killed with SIGTERM during epoch 2. Resume continued from epoch 2 to 4 and exited 0.

**Google Colab fallback** (not needed here, because MPS training took 21.2 minutes): upload the `SiteGuard-AI` folder *without* `.venv` and with the dataset at `../construction-ppe`. Then run:

```bash
pip install -r requirements.txt
python -m src.training.train --device 0
```

The dataset is never uploaded anywhere by the code itself.

## 4. Outputs

| Path | Content |
|---|---|
| `experiments/siteguard_yolo26n/weights/best.pt`, `last.pt` | Checkpoints |
| `experiments/siteguard_yolo26n/results.csv`, `results.png` | Per-epoch losses and validation metrics |
| `experiments/siteguard_yolo26n/confusion_matrix*.png`, `Box*_curve.png` | Validation plots |
| `experiments/siteguard_yolo26n/args.yaml` | Exact Ultralytics arguments |
| `experiments/siteguard_yolo26n/training_metadata.json` | SiteGuard summary (versions, duration, metrics) |
| `experiments/train_main_stdout.log`, `experiments/training.log` | Console and script logs |
| `models/trained/best.pt` | Checkpoint used by the app |

## 5. Results (main model, run `experiments/siteguard_yolo26n`)

| Item | Value |
|---|---|
| Date | 2026-11-19 |
| Hardware | MacBook Air, Apple M5, 16 GB; device `mps` |
| Software | Python 3.12.16, torch 2.15.0, Ultralytics 8.4.215, macOS 27.0.1 |
| Pretrained weights | `models/pretrained/yolo26n.pt` (sha256 `9b09cc8b…`) |
| Log lines | `Overriding model.yaml nc=80 with nc=12`, `Transferred 708/708 items from pretrained weights` |
| Epochs completed | 30 of 30 (early stopping not triggered) |
| Duration | 1,273 s (21.2 min), about 42 s per epoch |
| GPU memory | about 3.3 GB at batch 8 |
| Best epoch (fitness) | 25 |
| Checkpoint | `models/trained/best.pt`, 5.44 MB, sha256 `890dc61f…`, 2,392,408 parameters (fused) |

Validation (official val split, 200 images, 2,961 boxes):

| Precision | Recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|
| 0.832 | 0.681 | 0.734 | 0.523 |

Learning curve (from `results.csv`):

| Epoch | train box loss | train cls loss | val box loss | val cls loss | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.537 | 6.991 | 1.351 | 5.035 | 0.300 | 0.200 |
| 5 | 1.401 | 1.442 | 1.206 | 1.285 | 0.677 | 0.457 |
| 10 | 1.325 | 1.065 | 1.164 | 0.948 | 0.705 | 0.488 |
| 15 | 1.267 | 0.926 | 1.133 | 0.862 | 0.716 | 0.504 |
| 20 | 1.263 | 0.871 | 1.123 | 0.801 | 0.732 | 0.517 |
| 25 | 1.180 | 0.762 | 1.102 | 0.751 | 0.734 | 0.524 |
| 30 | 1.141 | 0.736 | 1.084 | 0.747 | 0.735 | 0.523 |

**Interpretation.** Most of the gain comes in the first 10 epochs. From epoch 20 to 30, mAP50-95 rose only by +0.006, while validation loss was still falling slowly. There is no sign of overfitting: validation loss decreased throughout. A longer schedule *might* add a little accuracy, but this was not tested, so no claim is made. Per-class results are in docs/EVALUATION.md.
