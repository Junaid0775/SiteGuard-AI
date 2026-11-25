# REPORT-013 — YOLO26m Readiness and Training Configuration

**Date:** 2026-11-19 (21:16–21:22 IST, from file timestamps) **Spec:** §7 (Phase 5) **Experiment folder:** `experiments/yolo26m/`
**Status:** All readiness prerequisites pass. Full training is cleared to start with **batch 4**, chosen from measured memory pressure. `models/trained/best.pt` is untouched (sha256 `890dc61f…`).

---

## 1. Executive summary

- **YOLO26m is supported** by the installed Ultralytics 8.4.215 (`yolo26m` is in `GITHUB_ASSETS_STEMS`).
- **Checkpoint:** the official weights were downloaded to `models/pretrained/yolo26m.pt` (44,255,705 bytes, sha256 `401cea9ab23ad192…0b7`). It loads as `yolo26m.yaml` (scale m), task detect, 80 COCO classes, **21,896,248 parameters**, on `mps:0` in fp32.
- **Smoke tests:** all pass on MPS:
  - single-image inference: wall time 36.1 ms mean, 38.8 ms p95;
  - 8-image batch inference;
  - three 1-epoch training runs on 10 % of train, at batch 4, 6 and 8.
- **Memory decided the batch size:**
  - **batch 8** peaked at 9.7 GB MPS memory, system free memory fell to **10 %**, and **swap grew by 3.7 GB**. Rejected as unacceptable.
  - **batch 6:** 7.66 GB, minimum free 26 %.
  - **batch 4:** 5.5 GB, minimum free **41 %**, swap stable.
  - Throughput was the same at every batch size (about 12.7 images/s).
- **Optimiser parity with YOLO26n:** AdamW lr 0.000625 and nominal batch 64 via gradient accumulation (16 × 4 here, 8 × 8 for YOLO26n).

## 2. Objective

Spec §7: verify that YOLO26m is supported and stable on the M5/MPS, select a safe configuration through smoke tests, and record a fully reproducible training configuration before any full training run.

## 3. Initial state

- YOLO26n baseline reproduced (REPORT-010).
- Dataset audited, with no blocking leakage (REPORT-011).
- No YOLO26m files existed.
- Memory before testing: about 63–66 % free; swap in use was 2.44 GB, pre-existing.

## 4. Technical investigation

| Check | Command / evidence | Result |
|---|---|---|
| Ultralytics support | `"yolo26m" in GITHUB_ASSETS_STEMS` | True. Model YAML family `cfg/models/26/yolo26.yaml` (scale m) |
| Checkpoint source | `curl https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m.pt` (same release as yolo26n) | 44,255,705 bytes, zip/torch archive, sha256 `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7` |
| Load | `YOLO("models/pretrained/yolo26m.pt")` | 0.038 s; detect; `yolo26m.yaml`; scale m; nc 80; 21,896,248 params |
| MPS | `torch.backends.mps.is_available()` / `is_built()` | True / True. Predict backend `mps`, parameters on `mps:0`, fp16 False |
| Single-image inference (20 val images, 640) | `benchmarks/smoke_inference.json` | Wall time 36.13 ms mean / 38.81 ms p95. First predict (setup and warm-up) 0.943 s |
| Batch inference (8 images) | same | 0.461 s total |
| MPS memory after inference | `torch.mps.driver_allocated_memory()` | 2,277.9 MB driver, 81.8 MB current |
| Warnings, CPU fallbacks, unsupported ops | grep of the smoke logs for `WARNING`, `fallback`, `not supported` | **none** |

**Measurement note:** Ultralytics' `speed["inference"]` on MPS does not synchronise the device. It read 3.17 ms median while the wall time was 36 ms, because the asynchronous MPS work is absorbed into "postprocess". Model latency comparisons therefore use **synchronised wall-clock** time per `predict` call.

### 4.1 Training smoke tests (1 epoch, 10 % of train = 80 images, then full val of 200 images; memory sampled every 5 s)

| Batch | Exit | Wall time | Peak MPS mem (Ultralytics) | Min system free mem | Swap before → after | it/s | images/s | Verdict |
|---:|---:|---:|---:|---:|---|---:|---:|---|
| 8 | 0 | 47.0 s | **9.7 GB** | **10 %** | 2,443 → **6,151 MB** | 1.6 | 12.8 | **Rejected:** unacceptable memory pressure |
| 6 | 0 | 41.1 s | 7.66 GB | 26 % | 5,991 → 5,959 MB | 2.1 | 12.6 | Acceptable, small margin |
| **4** | 0 | 40.4 s | **5.5 GB** | **41 %** | 6,079 → 5,991 MB | 3.2–3.5 | 12.8–14.0 | **Selected** |

Evidence: `benchmarks/smoke_b{4,6,8}_f10_e1.json`, `logs/smoke_b*.log`, `training/smoke_b*_f10_e1/`. The 1-epoch smoke checkpoints are not models; their mAP (~0.05) is meaningless after 10 iterations.

All three smoke checkpoints load as `yolo26m.yaml` with **12 classes equal to `configs/dataset.yaml`**. `optimizer=auto` gives AdamW lr 0.000625, momentum 0.9, nbs 64; accumulation is 16 / 11 / 8 for batch 4 / 6 / 8.

## 5. Files inspected

`src/training/train.py`; `.venv/…/ultralytics/engine/trainer.py` (accumulation `max(round(nbs / batch), 1)`; validation batch = 2 × train batch, line 321); `ultralytics/utils/downloads.py`; `ultralytics/cfg/models/26/`.

## 6. Files modified / created

| File | Change | Previous → new behaviour | Reason |
|---|---|---|---|
| `src/training/train.py` | Added a `--project` option | Runs always went to `experiments/<name>` → runs can go to any parent folder; **the default is unchanged** | Spec §7.1: keep YOLO26m in an isolated folder |
| `models/pretrained/yolo26m.pt` | new | — | Official pretrained checkpoint |
| `scripts/engineering/yolo26m_smoke.py` | new | — | Readiness and smoke tests with memory sampling |
| `experiments/yolo26m/{configs,training,validation,predictions,benchmarks,logs}/` | new | — | Isolated experiment tree |

## 7. Engineering decisions and alternatives

| Decision | Alternatives | Reason |
|---|---|---|
| **batch 4** | 6 (closer to YOLO26n's 8); 8 | Same throughput as 6 and 8, with the most headroom (41 % free) for a 30-epoch run on a 16 GB machine the user may also be using. Batch 8 failed the memory criterion. |
| Keep imgsz 640, 30 epochs, seed 42, `optimizer=auto` | Tune hyperparameters for YOLO26m | Controlled comparison with YOLO26n (spec §7.4: initial experiment). Tuning on val would bias the comparison (spec rule 9). |
| `--no-promote` | Promote best.pt | Spec rules 3 and 18: never overwrite production; switching needs approval |

## 8. Full training configuration (frozen before the run; `configs/train_config.json`)

```text
.venv/bin/python -m src.training.train --weights models/pretrained/yolo26m.pt --epochs 30 --batch 4 \
    --no-promote --project experiments/yolo26m/training --name yolo26m_e30_b4
```

| Parameter | Value |
|---|---|
| Model / weights | YOLO26m, `models/pretrained/yolo26m.pt` (sha256 `401cea9a…`) |
| Data | `data/generated/dataset_resolved.yaml`: the original dataset via the symlink mirror, 800 train / 200 val, 12 classes, mapping preserved |
| Epochs / imgsz / batch | 30 / 640 / **4** (validation batch 8) |
| Effective optimiser batch | nominal 64 (accumulation 16) — same as YOLO26n (8 × 8) |
| Optimiser | auto → AdamW lr0 0.000625, momentum 0.9 (0.937 configured, auto overrides), weight decay 0.0005 (scaled), lrf 0.01, linear schedule (`cos_lr` false), warm-up 3 epochs (momentum 0.8, bias lr 0.1) |
| Augmentation | Ultralytics defaults: mosaic 1.0 (closed for the last 10 epochs), fliplr 0.5, flipud 0, HSV (0.015, 0.7, 0.4), translate 0.1, scale 0.5, degrees/shear/perspective 0, mixup/cutmix/copy-paste 0, erasing 0.4 |
| Loss gains | box 7.5, cls 0.5, dfl 1.5 |
| Validation | Every epoch; best = max fitness; plots on |
| Early stopping | patience 15 |
| Seed / determinism | 42 / True (some MPS ops have no deterministic kernel; Ultralytics warns) |
| Device / workers / cache | mps / 4 requested (Ultralytics uses 0 on MPS) / off |

**Expected duration** (from the smoke throughput of about 12.8 img/s; not a measured result): about 62 s of training plus validation per epoch, so roughly 35–50 minutes for 30 epochs.

**Differences from the YOLO26n run:** architecture (the variable under test) and batch 4 vs 8 (same nominal batch; BatchNorm batch statistics differ). These go into REPORT-015 as a limitation.

## 9. Testing methodology

Smoke inference and training through the same `src.training.train` entry point as the full run. Memory was sampled with `memory_pressure` and `sysctl vm.swapusage` every 5 s, and logs were grepped for warnings and fallbacks.

## 10. Actual measured results

See §4 and §4.1.

## 11. Before/after comparison

Not applicable (readiness only).

## 12. Limitations and uncertainty

- Memory readings are system-wide, so other running apps (the dashboard and another project's server on 8501) influence them.
- The 10 %-of-train smoke runs may underestimate peak memory late in training: mosaic closes for the last 10 epochs and validation uses batch 8.
- Monitoring continues during the full run.

## 13. Known unresolved issues

None blocking. The BatchNorm-batch difference is a documented comparison caveat.

## 14. Exact reproduction

```bash
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI"
curl -sSL -o models/pretrained/yolo26m.pt https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26m.pt
shasum -a 256 models/pretrained/yolo26m.pt   # 401cea9a...0b7
.venv/bin/python scripts/engineering/yolo26m_smoke.py inference
for b in 8 6 4; do .venv/bin/python scripts/engineering/yolo26m_smoke.py train --batch $b --fraction 0.1 --epochs 1; done
```

## 15. Conclusion

The readiness criteria in spec §7.5 are all met:
- the checkpoint loads;
- the smoke tests pass;
- the dataset configuration and class mapping are verified;
- memory is manageable at batch 4;
- the configuration is frozen and reproducible.

## 16. Recommended next step

Phase 6: run the full 30-epoch training with memory monitoring (REPORT-014).
