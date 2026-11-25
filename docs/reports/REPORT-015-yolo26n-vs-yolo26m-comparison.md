# REPORT-015 — Controlled YOLO26n vs YOLO26m Comparison

**Date:** 2026-11-19 (23:00–23:10 IST) **Spec:** §9 (Phase 7)
**Evidence:** `experiments/yolo26m/benchmarks/{comparison.json, per_class_comparison.csv}`, `experiments/yolo26m/predictions/visual_comparison/`, `experiments/{engineering_phase/baseline/yolo26n, yolo26m/validation}/`
**Status:** Complete. The production checkpoint was not switched.
**Correction (2026-11-19, final report check):** §1 had given the YOLO26m missing-PPE recall values from the Ultralytics-val recall column (0.687 / 0.687 / 0.427) instead of the app threshold. §1 now gives the app-threshold values from `operating_point.json`. No other numbers changed.

---

## 1. Executive summary

Both models were evaluated with the same procedure: the same 200 val images and 2,961 labels, the same 12-class mapping, imgsz 640, the same thresholds and evaluator, on the same machine.

| Metric | YOLO26n | YOLO26m | Absolute change | Relative change |
|---|---:|---:|---:|---:|
| Precision (Ultralytics val) | 0.8322 | 0.8909 | +0.0587 | +7.1 % |
| Recall | 0.6809 | 0.7773 | +0.0964 | +14.2 % |
| mAP50 | 0.7339 | 0.8311 | +0.0972 | +13.2 % |
| mAP50-95 | 0.5227 | 0.6195 | **+0.0968** | **+18.5 %** |

- **Uncertainty:** a paired bootstrap over images gives a mAP50-95 difference of **+0.093, 95 % CI [0.081, 0.103]**. YOLO26m was better in 100 % of the 1,000 resamples.
- **Per class:** every one of the 12 classes improved in AP50-95, by +0.044 to +0.157.
- **Missing-PPE recall** at the app threshold (conf 0.25, NMS IoU 0.5; `operating_point.json`) rose for every missing-PPE class: no_helmet 0.615 → 0.715, no_gloves 0.567 → 0.700, no_goggle 0.171 → 0.476, no_boots 0.674 → 0.691, no_vest 0.623 → 0.692.
- **Cost:** synchronised latency on identical 720p frames went from **8.0 ms to 25.0 ms** (125 → 40 fps sequentially). The model has 8.6× the parameters (2.54 M → 21.79 M) and an 8.1× larger file (5.4 → 44.0 MB). MPS memory after inference went from about 0.1 GB to about 1.2 GB.
- **Not improved:** the real webcam close-range scene at 640 (P 0.40 → 0.385, R 0.333 → 0.333, one scene), and a few crowded scenes (2 of 16 visual examples were worse).

## 2. Objective

Spec §9: a fair, controlled comparison of overall, per-class and visual results, with latency, size and memory, plus an uncertainty estimate.

## 3. Initial state

- YOLO26n production checkpoint (REPORT-010 baseline).
- YOLO26m trained and verified (REPORT-014).

## 4. Technical investigation — controls

| Controlled item | Setting |
|---|---|
| Images / labels | Identical: official val split, 200 images, 2,961 boxes; loaded by the same code |
| Classes | 12, identical mapping (verified in both checkpoints) |
| Inference size | 640 |
| Primary metric settings | Ultralytics val defaults (conf 0.001, NMS IoU 0.7, max_det 300, batch 8) |
| Operating-point settings | Conf 0.25, NMS IoU 0.5, per-class NMS: the app's settings |
| Evaluator | Ultralytics `val()`, plus the audit evaluator (Ultralytics matching rule + `ap_per_class`; 13 unit tests) |
| Device | MPS, fp32, same machine, run back-to-back with no other heavy job |
| Tuning | **None** for either model. Thresholds are unchanged and no secondary optimisation was done. |
| Unavoidable differences | Training batch 4 (m) vs 8 (n), with the same nominal batch 64. Each model's own val-based checkpoint selection. |

## 5. Files inspected

The validation outputs of both models; `per_class_comparison.csv`; `comparison.json`.

## 6. Files modified / created

**No existing file was modified.** Created: `scripts/engineering/compare_models.py`, and the evidence files listed in the header.

## 7. Engineering decisions and alternatives

- **Primary vs operating point:** Ultralytics val is the primary metric, because it is comparable with the historical numbers. The operating point is reported separately because it reflects what the app shows.
- **Bootstrap:** paired over images, so both models are scored on each identical resample. It uses the audit evaluator at NMS 0.5; that is why its point values (0.514 / 0.607) differ slightly from the Ultralytics val figures (0.523 / 0.620).
- **Visual examples** were selected by fixed rules, not chosen by hand:
  - easy = highest YOLO26n recall; difficult = lowest;
  - most small boxes; most persons; first overhead and side images (AI-assisted viewpoint labels); darkest;
  - most YOLO26n false positives; images where YOLO26n produced contradicting boxes.

## 8. Implementation details

`compare_models.py` loads both saved prediction sets, compares the Ultralytics metrics, and writes a per-class CSV. It also runs:
- the paired bootstrap (B = 1,000, seed 0);
- **synchronised latency**: `PPEDetector.detect()` copies the boxes to numpy, which forces the MPS work to complete. 60 frames at 1280×720 from the test clip and 60 full-resolution val images, after warm-up;
- load time (median of 5 loads) and MPS driver memory;
- the visual sheets plus a per-box CSV;
- webcam-style evaluations.

## 9. Testing methodology

Same images, labels and code path for both models. Model loading for both checkpoints is covered by `tests/test_model_loading.py`.

## 10. Actual measured results

### 10.1 Operating point (conf 0.25, NMS IoU 0.5)

| | YOLO26n | YOLO26m |
|---|---:|---:|
| Precision | 0.884 | 0.885 |
| Recall | 0.745 | **0.828** |
| F1 | 0.809 | 0.856 |
| TP / FP / FN | 2206 / 289 / 755 | 2452 / 319 / 509 |
| FP per image | 1.45 | 1.60 |
| FP types: localization / wrong class / background / duplicate | 137 / 93 / 53 / 6 | 151 / 74 / **89** / 5 |
| Contradicting box pairs | 33 | **16** |

YOLO26m finds 246 more objects for 30 more false boxes. It confuses classes less (wrong class 93 → 74, contradictions halved), but produces more background false positives (53 → 89).

### 10.2 Bootstrap (paired, 1,000 resamples)

| Difference (m − n) | Point | 95 % CI | Share of resamples where m is better |
|---|---:|---|---:|
| mAP50 | +0.085 | [0.065, 0.101] | 1.000 |
| mAP50-95 | +0.093 | [0.081, 0.103] | 1.000 |
| Recall at conf 0.25 | +0.083 | [0.069, 0.096] | 1.000 |

### 10.3 Per class (Ultralytics val; FP/FN at the operating point)

| Class | Val inst. | AP50 n→m | AP50-95 n→m (Δ) | P n→m | R n→m | FP n→m | FN n→m | Verdict |
|---|---:|---|---|---|---|---|---|---|
| helmet | 294 | 0.825→0.916 | 0.627→0.743 (+0.117) | 0.901→0.938 | 0.776→0.881 | 29→22 | 62→30 | improved |
| gloves | 381 | 0.793→0.889 | 0.601→0.737 (+0.137) | 0.842→0.906 | 0.735→0.835 | 48→48 | 99→61 | improved |
| vest | 340 | 0.887→0.920 | 0.685→0.753 (+0.068) | 0.936→0.952 | 0.829→0.875 | 13→13 | 55→40 | improved |
| boots | 481 | 0.771→0.849 | 0.572→0.659 (+0.087) | 0.812→0.828 | 0.682→0.790 | 80→**103** | 137→88 | improved (more FP) |
| goggles | 139 | 0.924→0.967 | 0.561→0.718 (+0.157) | 0.829→0.940 | 0.921→0.957 | 13→9 | 9→6 | improved |
| Person | 481 | 0.940→0.975 | 0.781→0.863 (+0.082) | 0.933→0.954 | 0.897→0.948 | 23→23 | 47→21 | improved |
| no_helmet | 179 | 0.652→0.756 | 0.383→0.477 (+0.094) | 0.894→**0.858** | 0.553→0.687 | 17→24 | 69→51 | improved (precision −0.036) |
| no_goggle | 82 | 0.148→0.531 | 0.045→0.182 (+0.137) | 0.382→0.789 | 0.128→0.427 | 16→16 | 68→43 | **too few instances** (< 100) for a confident conclusion; still weak |
| no_gloves | 203 | 0.620→0.765 | 0.384→0.484 (+0.100) | 0.898→0.880 | 0.564→0.687 | 19→22 | 88→61 | improved |
| no_boots | 178 | 0.748→0.805 | 0.574→0.659 (+0.085) | 0.839→0.868 | 0.673→0.714 | 15→20 | 58→55 | improved |
| forklift | 73 | 0.807→0.848 | 0.585→0.639 (+0.055) | 0.801→0.879 | 0.795→0.836 | 10→11 | 14→13 | too few instances |
| no_vest | 130 | 0.692→0.753 | 0.475→0.519 (+0.044) | 0.920→0.899 | 0.619→0.692 | 6→8 | 49→40 | improved (smallest gain) |

No class regressed in AP. Precision fell slightly for no_helmet, no_gloves and no_vest, and the FP counts rose for boots (+23), no_helmet (+7) and no_boots (+5).

**no_goggle:** recall tripled, but AP50-95 is still only 0.18. The causes from REPORT-010/011 (tiny boxes, eyeglasses ambiguity, incomplete labels) remain, so a larger model only partly addresses them.

### 10.4 Small PPE objects (recall at the operating point, boxes < 1 % of image area; `stratified_recall.csv`)

| Class (small boxes) | GT | YOLO26n | YOLO26m |
|---|---:|---:|---:|
| helmet | 202 | 0.693 | **0.852** |
| no_helmet | 130 | 0.469 | 0.631 |
| gloves | 340 | 0.709 | 0.821 |
| no_gloves | 200 | 0.565 | 0.695 |
| boots | 340 | 0.609 | 0.750 |
| no_boots | 149 | 0.644 | 0.678 |
| goggles | 128 | 0.938 | 0.969 |
| no_goggle | 82 | 0.171 | 0.476 |
| vest | 178 | 0.708 | 0.792 |
| no_vest | 59 | 0.203 | **0.356** |
| Person | 186 | 0.758 | 0.898 |

The largest gains are on small objects. Small no_vest and no_goggle remain poor with both models.

### 10.5 Webcam-style scenes (`comparison.json → webcam_style`)

| Set | YOLO26n P / R | YOLO26m P / R |
|---|---|---|
| Webcam-style head-and-torso crops of 164 val images (1,168 GT) | 0.910 / 0.870 (mAP50-95 0.613) | 0.913 / **0.920** (mAP50-95 0.662) |
| Real webcam, 10 labelled frames, **one indoor scene**, imgsz 640 | 0.400 / 0.333 | 0.385 / 0.333 |
| Same, imgsz 320 | 0.968 / 1.000 | 0.806 / 0.967 |

YOLO26m does **not** fix the close-range scale problem (REPORT-009 §5.6) on the real frames at 640. Both models mislocalise the oversized head and torso boxes. The sample is one scene and must not be generalised.

### 10.6 Latency, size and memory (`comparison.json → latency_memory`; MPS, fp32, synchronised wall clock)

| | YOLO26n | YOLO26m | Ratio |
|---|---:|---:|---:|
| Per frame, 1280×720, mean / median / p95 | 8.00 / 7.91 / 9.14 ms | 25.04 / 25.02 / 25.52 ms | 3.1× |
| Sequential throughput, 720p | 125.0 fps | 39.9 fps | 0.32× |
| Per image, full-resolution val, mean / median / p95 | 14.63 / 8.83 / 17.41 ms | 33.31 / 28.72 / 35.86 ms | about 2.3× |
| Parameters (unfused) | 2,539,232 | 21,791,392 | 8.6× |
| File size | 5,443,013 B | 44,029,401 B | 8.1× |
| Load time (median of 5) | 0.011 s | 0.018 s | — |
| MPS driver memory after inference | 100.5 MB | 1,213.5 MB | about 12× |

The first detect after load took 0.70 s for n, which included first-time MPS initialisation in the process, and 0.26 s for m. The full-resolution maxima (118 / 115 ms) are single outliers.

### 10.7 Visual comparison (16 rule-selected images; `visual_comparison/*.jpg`, `visual_examples.csv`, `per_image_summary.csv`)

By TP − FP per image: **YOLO26m better on 11, worse on 2, equal on 3.**

| Category | Images | Outcome (n → m: TP / FP / FN) |
|---|---|---|
| Easy | 2 | m removed 1 and 2 FPs; equal TP |
| Difficult | 2 | 4/4/19 → 8/4/15; 3/0/14 → 4/0/13 (both still poor) |
| Small objects | 2 | 35/6/24 → 48/10/11; 46/5/15 → 53/9/8 |
| Crowded (occlusion proxy) | 1 | 11/3/26 → 14/8/23 (**worse** by TP − FP) |
| Overhead | 2 | equal; better |
| Side | 1 | equal (8/0/0) |
| Low light (darkest) | 2 | 16/7/10 → 22/4/4; 2 FP removed |
| False-positive heavy | 2 | FP 7 → 4 and 7 → 3 |
| Conflicting boxes | 2 | 16/5/8 → 15/8/9 (**worse**); equal |

Every box is listed with its predicted class, confidence, best-matching GT class, IoU and correctness in `visual_examples.csv`.

## 11. Before/after comparison

See §1 and §10. This compares models; the pipeline changes (R1/R2) were reported separately in REPORT-012 and are not attributed to either model.

## 12. Limitations and uncertainty

- **200 val images, in-distribution**, partly generated imagery. The bootstrap captures image-sampling uncertainty only, not training-seed variance (one run per model) or domain shift.
- The val set also selected each model's checkpoint (best epoch).
- no_goggle (82) and forklift (73) have fewer than 100 val instances.
- The real-webcam result is a single scene. Latency is from one machine at one thermal state.

## 13. Known unresolved issues

- YOLO26m costs about 3× the inference time and about 12× the GPU memory.
- More background false positives.
- no_goggle and small no_vest remain weak.
- The close-range webcam scale problem is unchanged.

## 14. Exact reproduction

```bash
.venv/bin/python scripts/engineering/evaluate_model.py --weights models/trained/best.pt --name yolo26n --out experiments/engineering_phase/baseline/yolo26n
.venv/bin/python scripts/engineering/evaluate_model.py --weights experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt --name yolo26m --out experiments/yolo26m/validation
.venv/bin/python scripts/engineering/compare_models.py
```

## 15. Conclusion

On this dataset, YOLO26m is **measurably and consistently better** than YOLO26n:
- +0.097 mAP50-95 on Ultralytics val; the paired bootstrap (audit evaluator, NMS IoU 0.5) gives +0.093, 95 % CI [0.081, 0.103];
- every class improved;
- the biggest gains are on small PPE and the missing-PPE classes.

It costs about 3× the latency. Whether that fits real-time use is tested in REPORT-016. **Production remains YOLO26n** until you approve a switch.

## 16. Recommended next step

Real-time webcam and video evaluation of both models (REPORT-016), then the final decision (REPORT-017).
