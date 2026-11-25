# SiteGuard AI — Evaluation

There are two separate evaluations. Keep them apart when reporting:

| | Standard validation | Viewpoint generalisation |
|---|---|---|
| Question | How accurate is the app's model on data like its training data? | Does a model trained only on frontal views work on side/overhead views it never saw? |
| Model | `models/trained/best.pt` (trained on all 800 train images) | A **separate** model trained only on the 527 frontal train images |
| Test data | Official val split (200 images) | Frontal val images vs held-out side / overhead / low-angle images |
| Script | `python -m src.evaluation.evaluate` | `python -m src.evaluation.viewpoint_evaluation …` |

Standard validation does **not** show viewpoint generalisation. The val split comes from the same sources and mix as the training split.

## 1. Metrics

- **Precision:** of the boxes the model predicted, the share that were correct. Ultralytics reports this at the confidence threshold that maximises F1.
- **Recall:** of the labelled boxes, the share the model found.
- **mAP50:** mean, over classes, of the average precision when a prediction counts as correct at IoU ≥ 0.5.
- **mAP50-95:** the same, averaged over IoU thresholds 0.50, 0.55 … 0.95. It is stricter and rewards precise boxes.

All numbers come from `model.val()` in Ultralytics 8.4.215. Validation uses `conf=0.001` to build the precision-recall curve, so it does not use the app's display threshold.

## 2. Standard validation

```bash
.venv/bin/python -m src.evaluation.evaluate
```

This writes `experiments/evaluation/trained_best/metrics.json` plus a confusion matrix and PR/F1 curves. The results are in §4.

## 3. Viewpoint experiment — procedure

1. **Labels.** Every image was labelled by visual inspection (docs/DATASET.md §6). The result is `data/viewpoint_metadata.csv`.
2. **Splits.** Run `python -m src.evaluation.viewpoint_evaluation prepare`:
   - train on `frontal` images from the train split (527);
   - validate during training on `frontal` images from the val split (112);
   - hold out every `side` (116), `overhead` (219) and `low_angle` (13) image from **both** splits. None is used for training, and a leakage check enforces this;
   - exclude `unclear` images (13).
3. **Train.** `python -m src.training.train --data data/generated/viewpoint/frontal_train.yaml --name viewpoint_frontal_only --no-promote`. Same settings as the main model; `--no-promote` keeps it out of the app.
4. **Evaluate.** `python -m src.evaluation.viewpoint_evaluation evaluate --weights experiments/viewpoint_frontal_only/weights/best.pt`. Results go to `experiments/viewpoint_results/`.
5. **Control groups.** Viewpoint is confounded with image style, so the script also evaluates:
   - frontal **close-ups** (val, 105) vs side **close-ups** (112): same style, different viewpoint;
   - frontal **wide scenes** (val, 7) vs overhead **wide scenes** (215). Only 7 frontal scenes exist, so this comparison is weak.
6. **Second model on the same images.** The main application model (trained on all 800 train images, all viewpoints) is evaluated on the **val-split** groups only (`--val-only`), because it has seen the train-split side and overhead images. This shows whether training on all viewpoints closes the gap.

One command runs steps 2–6: `zsh scripts/run_viewpoint_experiment.sh`. Set `SKIP_TRAINING=1` to reuse an existing frontal-only model. The results are in §5.

## 4. Standard validation — results

Command: `python -m src.evaluation.evaluate`. Run on 2026-11-19 with `models/trained/best.pt` (sha256 `890dc61f…`) at image size 640, on device mps. Data: official val split, 200 images, 2,961 boxes. Raw output: `experiments/evaluation/trained_best/metrics.json`.

| | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| **All classes** | **0.832** | **0.681** | **0.734** | **0.523** |

| Class | Val boxes | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|
| helmet | 294 | 0.901 | 0.775 | 0.825 | 0.627 |
| gloves | 381 | 0.842 | 0.735 | 0.793 | 0.601 |
| vest | 340 | 0.936 | 0.829 | 0.887 | 0.685 |
| boots | 481 | 0.812 | 0.682 | 0.771 | 0.572 |
| goggles | 139 | 0.829 | 0.921 | 0.924 | 0.561 |
| Person | 481 | 0.933 | 0.896 | 0.940 | 0.781 |
| no_helmet | 179 | 0.894 | 0.553 | 0.652 | 0.383 |
| no_goggle | 82 | 0.382 | 0.128 | 0.148 | 0.045 |
| no_gloves | 203 | 0.898 | 0.564 | 0.620 | 0.384 |
| no_boots | 178 | 0.839 | 0.673 | 0.748 | 0.574 |
| forklift | 73 | 0.801 | 0.794 | 0.807 | 0.585 |
| no_vest | 130 | 0.920 | 0.619 | 0.692 | 0.475 |

Inference speed on M5 / MPS: about 4–7 ms per 640-px image (model forward only).

**Interpretation**

- `Person` (0.94 mAP50) and the PPE-present classes are detected reliably.
- The **missing-PPE classes have high precision (≈0.84–0.92) but low recall (≈0.55–0.67)**: when the model says `no_helmet` it is usually right, but it misses about 45 % of labelled `no_helmet` cases. This is why SiteGuard reports *uncertain* rather than *compliant* when no PPE is seen. A missed `no_helmet` produces no event, so the system under-reports rather than over-reports.
- `no_goggle` is unusable (mAP50 0.148), with only 265 training boxes. Goggles are therefore **not** in the default required-PPE list.
- These numbers are in-distribution. The val split shares the sources and style of the training data, and the dataset README warns that independent imagery is needed for final evaluation.

Plots: `experiments/evaluation/trained_best/confusion_matrix_normalized.png`, `BoxPR_curve.png`, `BoxF1_curve.png`. They are also shown on the dashboard's *Model Evaluation* page.

## 5. Viewpoint experiment — results

**Model:** `experiments/viewpoint_frontal_only/weights/best.pt`. Trained only on the 527 frontal train images: 30 epochs, 14.7 min on MPS, same settings as the main model. The best epoch was 29, with frontal-val mAP50-95 0.6400 against 0.6392 for the last epoch. The frontal val set also chose the checkpoint, but that adds a negligible optimistic bias (< 0.001). Raw results are in `experiments/viewpoint_results/viewpoint_metrics_viewpoint_frontal_only.json`, with plots per group in `experiments/viewpoint_results/viewpoint_frontal_only/<group>/`. Run 2026-11-19.

### 5.1 Main comparison (frontal-only model)

| Test group | Images | Boxes | Precision | Recall | mAP50 | mAP50-95 | Frontal − group (mAP50-95) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Frontal (val, unseen) | 112 | 1,554 | 0.945 | 0.752 | 0.850 | **0.639** | — |
| Side (all, held out) | 116 | 1,050 | 0.938 | 0.789 | 0.853 | **0.678** | **−0.040** |
| Overhead (all, held out) | 219 | 4,849 | 0.517 | 0.325 | 0.334 | **0.185** | **+0.454** |
| Low angle (all, held out) | 13 | 187 | 0.635 | 0.352 | 0.366 | 0.185 | +0.454 (too few images) |
| All non-frontal (held out) | 348 | 6,086 | 0.741 | 0.408 | 0.472 | 0.297 | +0.342 |

### 5.2 Controls for the image-style confound (frontal-only model)

| Comparison | Group A | mAP50-95 | Group B | mAP50-95 | A − B |
|---|---|---:|---|---:|---:|
| Same style: close-ups | Frontal close-up val (105) | 0.673 | Side close-up, held out (112) | 0.699 | −0.026 |
| Same style: wide scenes | Frontal wide-scene val (**7**) | 0.341 | Overhead wide-scene, held out (215) | 0.177 | +0.164 |
| Same split: val only | Frontal val (112) | 0.639 | Side val (32) | 0.717 | −0.078 |
| Same split: val only | Frontal val (112) | 0.639 | Overhead val (53) | 0.227 | +0.412 |

### 5.3 Does training on all viewpoints help? (same val-split images, two models)

| Val group | Images | Frontal-only model | Main model (all views) | Change |
|---|---:|---:|---:|---:|
| Frontal | 112 | 0.639 | 0.644 | +0.005 |
| Frontal close-up | 105 | 0.673 | 0.675 | +0.002 |
| Frontal wide-scene | 7 | 0.341 | 0.380 | +0.039 |
| Side | 32 | 0.717 | 0.723 | +0.006 |
| Overhead | 53 | 0.227 | 0.309 | **+0.082** |
| Non-frontal | 88 | 0.324 | 0.392 | +0.068 |

Raw results: `experiments/viewpoint_results/viewpoint_metrics_main_model_all_views.json`.

### 5.4 Per-class mAP50-95 (frontal-only model)

| Class | Frontal val | Side (held out) | Overhead (held out) |
|---|---:|---:|---:|
| Person | 0.886 | 0.933 | 0.553 |
| helmet | 0.797 | 0.778 | 0.339 |
| vest | 0.843 | 0.879 | 0.422 |
| gloves | 0.692 | 0.722 | 0.148 |
| boots | 0.783 | 0.784 | 0.156 |
| goggles | 0.621 | 0.559 | 0.164 |
| no_helmet | 0.631 | 0.700 | 0.047 |
| no_vest | 0.627 | 0.748 | 0.085 |
| no_gloves | 0.464 | 0.639 | 0.091 |
| no_boots | 0.692 | 0.738 | 0.067 |
| no_goggle | 0.044 | 0.005 | 0.043 |
| forklift | 0.584 | 0.657 | 0.105 |

### 5.5 Findings

1. **Side views at eye level: no drop.** The side group scores slightly *higher* than frontal: +0.040 overall, and +0.026 when both are close-ups. Within this dataset, the model handles workers seen in profile or from behind as well as from the front.
2. **Overhead / elevated views: severe drop.** mAP50-95 falls from 0.639 to 0.185 (−0.454), and recall from 0.75 to 0.33. The **missing-PPE classes collapse** (for example `no_helmet` 0.631 → 0.047). On elevated CCTV views, SiteGuard's compliance layer would therefore raise very few potential-violation events. It would under-report, and most workers would show as *uncertain*.
3. **The overhead drop is not caused by camera angle alone.** The 7 frontal wide-scene images also score far below the close-ups (0.341 vs 0.673), so smaller objects and a different image style explain part of the drop. Overhead scenes still score lower again (0.177), which suggests viewpoint also matters. With only 7 frontal wide-scene images, the two effects cannot be separated reliably.
4. **Training on all viewpoints helps but does not close the gap.** The main model, which saw 166 overhead training images, improves overhead val from 0.227 to 0.309 (+0.082). It remains 0.335 below frontal.

**Answer to the research question.** A model trained on frontal images generalised well to **side** views at eye level, but **not** to **overhead / elevated CCTV-style** views (mAP50-95 0.639 → 0.185, −0.454, on 219 held-out images). Because overhead images in this dataset also show smaller workers in wider scenes, the result describes *overhead CCTV-style imagery* rather than an isolated effect of camera angle.

### 5.6 Limitations of the experiment

- Viewpoint labels are AI-assigned from thumbnails and not expert-verified (docs/DATASET.md §6).
- Only one training run (seed 42), so there are no confidence intervals. Differences below about 0.03 mAP50-95 should not be over-interpreted.
- The low-angle (13) and frontal wide-scene (7) groups are too small to be reliable.
- All images come from one dataset, partly generated. Results on real site cameras may differ.
- **Not tested:** higher input resolution (for example 1280 px) for small overhead objects, or tiling. Either is a likely improvement for elevated cameras.
