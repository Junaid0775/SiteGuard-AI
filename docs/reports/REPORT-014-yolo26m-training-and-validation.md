# REPORT-014 — YOLO26m Training and Validation

**Date:** 2026-11-19 (training 21:22:30–22:57:30 IST; validation 22:58–23:00) **Spec:** §8 (Phase 6)
**Run folder:** `experiments/yolo26m/training/yolo26m_e30_b4/` **Status:** Training completed (exit 0) and the checkpoint is verified. **Not promoted:** `models/trained/best.pt` is unchanged (sha256 `890dc61f…`).

---

## 1. Executive summary

- YOLO26m trained for the full 30 epochs in **94.6 min** (5,673.7 s; mean 189.7 s per epoch) on MPS at batch 4. There were no warnings, CPU fallbacks or errors.
- The best epoch by validation fitness was **epoch 30**. Validation losses were still falling at the end, so there is no sign of overfitting; 30 epochs is probably not the optimum.
- **Independent re-validation** with the same procedure as YOLO26n (`scripts/engineering/evaluate_model.py`, Ultralytics val defaults on the 200 val images): **P 0.8909, R 0.7773, mAP50 0.8311, mAP50-95 0.6195**.
- **Memory:** system free memory never fell below 18 % (median 26 %). MPS memory peaked at 6.86 GB (Ultralytics reading). Swap *decreased* from 5.86 GB to 3.93 GB.

## 2. Objective

Spec §8: train YOLO26m in its isolated folder with the frozen configuration (REPORT-013), monitor it, verify the checkpoint and validate it.

## 3. Initial state

Configuration frozen in `experiments/yolo26m/configs/train_config.json`. Pretrained `models/pretrained/yolo26m.pt` (sha256 `401cea9a…`).

## 4. Technical investigation — monitoring

### 4.1 Learning curves (`results.csv`, `results.png`)

| Epoch | train box | train cls | val box | val cls | val mAP50-95 |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.200 | 2.566 | 1.044 | 1.455 | 0.493 |
| 5 | 1.162 | 0.831 | 1.009 | 0.714 | 0.558 |
| 10 | 1.127 | 0.691 | 0.978 | 0.605 | 0.576 |
| 15 | 1.050 | 0.597 | 0.954 | 0.581 | 0.588 |
| 20 | 0.959 | 0.518 | 0.908 | 0.532 | 0.612 |
| 25 | 0.894 | 0.449 | 0.895 | 0.516 | 0.614 |
| 30 | 0.834 | 0.407 | 0.872 | 0.505 | **0.620** |

Training and validation losses both decrease monotonically, so there is no divergence (no overfitting). The mosaic close at epoch 21 coincides with the step from 0.588 to 0.612.

The checkpoint was chosen by **validation fitness**, not by training loss. Note that, as for YOLO26n, the val set both selects the checkpoint and reports the metrics: the best epoch is the last one, and the val set does both jobs for **both** models equally.

### 4.2 Memory and stability (`logs/memory_during_training.csv`, 189 samples every 30 s; training log)

| Item | Value |
|---|---|
| System free memory min / median | 18 % / 26 % |
| Swap start / max / end | 5,855 / 5,855 / 3,931 MB (no growth) |
| MPS memory (Ultralytics GPU_mem) median / max | 6.54 / 6.86 GB |
| Warnings / fallbacks / unsupported ops | none |
| Exit code | 0 (`TRAIN_EXIT=0`) |

During the run, `caffeinate -dims -w 34481` kept the Mac awake at your request, and exited with training.

## 5. Files inspected

The run folder, the training log, the memory CSV and the checkpoint metadata.

## 6. Files modified / created

**No existing file was modified.**

| Created | Content |
|---|---|
| `experiments/yolo26m/training/yolo26m_e30_b4/` | `weights/best.pt`, `weights/last.pt`, `args.yaml`, `results.csv`, `results.png`, `confusion_matrix*.png`, `Box{F1,P,PR,R}_curve.png`, train/val batch images, `training_metadata.json` |
| `experiments/yolo26m/logs/train_yolo26m_e30_b4.log`, `memory_during_training.csv` | Full log and memory samples |
| `experiments/yolo26m/validation/` | `metrics_ultralytics.json`, `operating_point.json`, `confusion_matrix*.csv`, `stratified_recall.csv`, `latency.json`, `predictions_conf0.001.npz`, `examples/`, `ultralytics_val/`, `checkpoint_verification.json`, `run_config.json` |

## 7. Engineering decisions and alternatives

| Decision | Alternative | Reason |
|---|---|---|
| Stop at 30 epochs as frozen | Extend because the curve is still rising | Changing the schedule after seeing val results would bias the comparison (spec rule 9). Recorded as future work. |
| No promotion to production | Copy best.pt to `models/trained/` | Spec rule 18 requires explicit approval |

## 8. Implementation details

- **Command:** `.venv/bin/python -m src.training.train --weights models/pretrained/yolo26m.pt --epochs 30 --batch 4 --no-promote --project experiments/yolo26m/training --name yolo26m_e30_b4`
- **Effective arguments:** `args.yaml`, matching REPORT-013 §8. Batch 4 (validation 8), nominal batch 64, AdamW lr 0.000625, seed 42, deterministic.

## 9. Testing methodology

- **Checkpoint verification** (`checkpoint_verification.json`): exists; loads; yolo26m.yaml; nc 12; names equal `configs/dataset.yaml`; test inference on MPS gives 58 boxes; sha256; distinct from YOLO26n.
- **Independent validation:** the identical `evaluate_model.py` procedure used for the YOLO26n baseline.
- **Tests:** `tests/test_model_loading.py` now also covers YOLO26m (see REPORT-017).

## 10. Actual measured results

| Checkpoint fact | Value |
|---|---|
| Path | `experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt` |
| sha256 | `399c4e5be335e3544afe185c7abb08d5fc894a382b891d970f71b94df3f1773f` (last.pt: `54129897…596f`) |
| Size / parameters (unfused) | 44,029,401 bytes / 21,791,392 |
| Classes | 12; mapping equals the dataset (PASS) |
| Distinct from YOLO26n | yes (`890dc61f…` ≠ `399c4e5b…`) |
| Created / Ultralytics version | 2026-11-19T22:57:18+05:30 / 8.4.215 |

**Validation (Ultralytics defaults: conf 0.001, NMS IoU 0.7, imgsz 640, batch 8, mps; 200 images, 2,961 instances):** P 0.8909, R 0.7773, mAP50 0.8311, mAP50-95 0.6195. The training-time val at epoch 30 was 0.893 / 0.777 / 0.831 / 0.620, so the two agree.

**Operating point (conf 0.25, NMS IoU 0.5):** P 0.885, R 0.828, F1 0.856; TP 2452, FP 319, FN 509; contradicting pairs 16.

Per-class results and the comparison are in REPORT-015.

## 11. Before/after comparison

See REPORT-015 for the comparison with YOLO26n.

## 12. Limitations and uncertainty

- One training run (seed 42); run-to-run variance is not measured.
- Validation is in-distribution (same sources as train).
- The val set also selected the checkpoint (best = last epoch).

## 13. Known unresolved issues

- The learning curve had not plateaued at 30 epochs.
- Batch 4 differs from YOLO26n's batch 8 (BatchNorm statistics), though the nominal batch is the same.

## 14. Exact reproduction

```bash
.venv/bin/python -m src.training.train --weights models/pretrained/yolo26m.pt --epochs 30 --batch 4 --no-promote \
    --project experiments/yolo26m/training --name yolo26m_e30_b4
.venv/bin/python scripts/engineering/evaluate_model.py --weights experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt \
    --name yolo26m --out experiments/yolo26m/validation
```

## 15. Conclusion

YOLO26m trained stably within acceptable memory on the M5, and the checkpoint is valid, distinct and preserved. Validation mAP50-95 is 0.6195.

## 16. Recommended next step

The controlled comparison with YOLO26n (REPORT-015), then real-time validation (REPORT-016).
