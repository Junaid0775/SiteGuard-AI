# REPORT-003 — Dataset Configuration and Viewpoint Metadata

**Date:** 2026-11-19 **Status:** Complete

## A. Task summary

- **Requested:** a corrected dataset configuration that resolves from any directory and keeps the 12-class mapping. Re-validate image/label correspondence, check for corrupt or duplicate images, and prepare viewpoint metadata without automatic labelling.
- **Done:** all of the above. The original dataset is untouched.
- **Completion:** full.

## B. Technical implementation

- `configs/dataset.yaml` stores the dataset location *relative to the project root*. `src/utils/paths.py` resolves it to an absolute path. The `SITEGUARD_DATASET_DIR` environment variable can override it.
- `src/utils/dataset_tools.py`:
  - `validate_dataset()` runs read-only checks: pairing, label format, class range, OpenCV decode of every image, SHA-256 duplicates and manifest checksums.
  - `build_mirror()` creates `data/dataset_mirror/` with symbolic links to every original image and label. Ultralytics writes `labels/*.cache` next to the labels it reads, so without the mirror it would add files to the original dataset.
  - `write_dataset_yaml()` writes `data/generated/dataset_resolved.yaml` with an absolute `path` and the 12 names.
- **Viewpoint metadata:** every image was viewed on numbered contact sheets (`scripts/make_contact_sheets.py`). Codes were typed into `data/viewpoint_sheets/codes.txt` and converted by `scripts/build_viewpoint_metadata.py` into `data/viewpoint_metadata.csv`.
- **Viewpoint splits** (`src/evaluation/viewpoint_evaluation.py prepare`): frontal-train 527, frontal-val 112, and held-out side 116, overhead 219 and low-angle 13. A built-in leakage check confirms that no held-out image is in the training list.

## C. Files created

| File | Purpose |
|---|---|
| `configs/dataset.yaml` | Corrected, portable dataset config (12 classes unchanged) |
| `src/utils/paths.py` | Central path resolution and settings loader |
| `src/utils/dataset_tools.py` | Validation, mirror and YAML generation |
| `data/dataset_mirror/` | Symlink mirror (2,000 links, plus Ultralytics caches) |
| `data/generated/dataset_resolved.yaml` | Absolute-path YAML for training |
| `data/generated/dataset_validation.json` | Validation result |
| `scripts/make_contact_sheets.py`, `data/viewpoint_sheets/*.jpg`, `index.csv` | Viewing aid for manual labelling |
| `data/viewpoint_sheets/codes.txt` | Hand-entered viewpoint codes |
| `scripts/build_viewpoint_metadata.py`, `data/viewpoint_metadata.csv` | Viewpoint table (filename, split, viewpoint, image group, method) |
| `data/generated/viewpoint/*.txt, *.yaml, group_counts.json` | Viewpoint experiment splits |

## D. Files modified

None in the original dataset.

## E. Commands executed

```bash
.venv/bin/python -m src.utils.dataset_tools
.venv/bin/python scripts/make_contact_sheets.py
.venv/bin/python scripts/build_viewpoint_metadata.py
.venv/bin/python -m src.evaluation.viewpoint_evaluation prepare
```

## F. Testing and verification

| Test | Command | Result |
|---|---|---|
| Path resolves from another cwd | `pytest tests/test_dataset.py::test_dataset_path_resolves_from_any_cwd` | PASS |
| Class mapping equals original data.yaml | `…::test_class_mapping_matches_original_data_yaml` | PASS |
| Resolved YAML absolute and existing | `…::test_resolved_yaml_uses_absolute_existing_paths` | PASS |
| Mirror links point at originals | `…::test_mirror_links_point_to_original_files` | PASS |
| Label parsing (valid and 6 invalid cases) | `…::test_parse_*` | PASS |
| Full dataset validation (800/200, 14,863, 12 classes) | `…::test_full_dataset_validation` | PASS |
| Cache files not in original dataset | `find construction-ppe -newer …` after the smoke training | PASS (no new files) |

## G. Model and dataset status

Class mapping: 0 helmet, 1 gloves, 2 vest, 3 boots, 4 goggles, 5 Person, 6 no_helmet, 7 no_goggle, 8 no_gloves, 9 no_boots, 10 forklift, 11 no_vest.

Viewpoint distribution: frontal 639, side 116, overhead 219, low_angle 13, unclear 13.

## H. Errors and resolutions

None.

## I. Acceptance criteria

| Criterion | Status |
|---|---|
| Original dataset not modified | PASS |
| Separate corrected config under `configs/` | PASS |
| 12-class mapping preserved exactly | PASS |
| Image/label correspondence re-validated | PASS |
| Duplicate and corrupt checks | PASS (0 / 0) |
| Viewpoint metadata CSV with filename, viewpoint and split | PASS |
| No automatic viewpoint labelling | PASS (manual visual codes) |

## J. Remaining work and known limitations

- The viewpoint labels come from an AI assistant viewing thumbnails. A human spot-check is recommended (see docs/DATASET.md §6).
- Viewpoint is confounded with image group: overhead images are almost all wide scenes.

## K. Next task

Model training (REPORT-004).
