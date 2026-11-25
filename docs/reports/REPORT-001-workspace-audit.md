# REPORT-001 — Workspace Audit

**Date:** 2026-11-19 **Status:** Complete

## A. Task summary

- **Requested:** inspect the workspace, dataset, Python installation and hardware before implementing anything (spec §14).
- **Done:** inspected all of these and recorded a SHA-256 baseline of the original dataset.
- **Completion:** full.

## B. Findings

| Item | Finding |
|---|---|
| Workspace | `/Users/junaidahmad/Desktop/471 Project/` contains only `construction-ppe/` and a `.DS_Store`. There was no existing project code to preserve. Not a git repository. |
| Dataset location | `/Users/junaidahmad/Desktop/471 Project/construction-ppe/` |
| Dataset structure | `images/{train,val}`, `labels/{train,val}`, `data.yaml`, `LICENSE.txt` (CC BY 4.0), `manifest.jsonl` (1,000 entries with SHA-256 checksums), `README.md` |
| `data.yaml` | `path: construction-ppe` (relative, so it fails when run from other folders). `train: images/train`, `val: images/val`. 12 classes, 0 helmet … 11 no_vest. |
| Dataset README | Ultralytics Construction-PPE, Nov 2026, combines human-collected and generated images. 800 train / 200 val, no test split. Advises independent imagery for final evaluation, and that occlusion is not evidence of missing PPE. |
| Counts (re-verified) | 800/800 train images/labels, 200/200 val. 14,863 boxes. 0 malformed rows. 0 duplicate images. 0 manifest checksum mismatches. All 12 class IDs present. |
| Filename groups | `source-*` (293, wide scenes) and `ultralytics-ppe-nov2026-*` (707, close-ups). Not documented in the README. |
| Python | System default `python3` 3.10.11 (python.org). `/usr/bin/python3` 3.9.6. `uv` is installed and provides CPython 3.12.16. |
| Hardware | MacBook Air, Apple M5, 16 GB RAM (17,179,869,184 bytes), macOS 27.0.1, arm64. 695 GB disk free. |
| GPU backend | PyTorch MPS available (checked after install, in REPORT-002). |

## C. Files created

| File | Purpose |
|---|---|
| `SiteGuard-AI/data/dataset_baseline.sha256` | SHA-256 of all 2,004 original dataset files (`.DS_Store` excluded), used to prove the dataset is unchanged |

## D. Files modified

None. The original dataset was only read.

## E. Commands executed

```bash
ls -la "~/Desktop/471 Project" construction-ppe images labels
cat construction-ppe/{data.yaml,README.md}; head construction-ppe/LICENSE.txt
uname -a; sysctl -n machdep.cpu.brand_string hw.memsize; sw_vers
which -a python3; python3 --version; uv python list
python3 - (label/manifest/hash validation, read-only)
find construction-ppe -type f ! -name .DS_Store | xargs shasum -a 256 > dataset_baseline.sha256
```

## F. Testing and verification

| Test | Command | Result |
|---|---|---|
| Image/label pairing | stdlib script | PASS: 0 orphans |
| Label format | stdlib script | PASS: 0 bad rows |
| Manifest checksums | stdlib script | PASS: 0 mismatches |
| Duplicates | SHA-256 comparison | PASS: none |

## G. Model and dataset status

Dataset verified. No model yet.

## H. Errors and resolutions

None.

## I. Acceptance criteria

| Criterion | Status |
|---|---|
| Workspace and dataset inspected | PASS |
| data.yaml, README, LICENSE read | PASS |
| Python and hardware verified | PASS |
| Existing files needing preservation identified | PASS (only the dataset) |

## J. Remaining work

Environment setup, then everything else.

## K. Proposed plan (as executed)

1. Create `SiteGuard-AI/` next to the dataset, with a uv-managed Python 3.12 virtual environment.
2. Add a corrected dataset configuration and a symlink mirror, so Ultralytics cache files never land in the original dataset.
3. Fine-tune pretrained YOLO26n on MPS: 30 epochs, batch 8, image size 640.
4. While training runs, build the detector, compliance analyzer, events, dashboard and tests.
5. Label viewpoints visually, then train a separate frontal-only model for the viewpoint experiment.
6. Evaluate, test, document.
