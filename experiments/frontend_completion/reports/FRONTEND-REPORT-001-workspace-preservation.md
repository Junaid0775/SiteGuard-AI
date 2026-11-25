# FRONTEND-REPORT-001 — Phase 0: workspace discovery, preservation snapshot and handoff review

**Status:** PASS. **Date:** 2026-11-23, 11:05–11:15 IST. **Specification:** `SiteGuard_AI_Frontend_Completion_Master_Specification.md`.

The specification file did not exist in the workspace. It was supplied in the chat and saved to the project root at 11:05 before any other change. In that copy, long bullet lists in §2.1, §2.3, §3.1, §4.1, §4.2 and §5–§10 were condensed into paragraphs; the substance is unchanged.

## 1. Workspace

| Item | Verified value |
|---|---|
| Repository root | `~/Desktop/471 Project/SiteGuard-AI/` (exists; current working directory) |
| Git | **Not a Git repository** (`fatal: not a git repository`). There is no branch and no diff. Change control uses file backups (§3) and integrity manifests (§5) |
| Entry point | `app.py`, a single Streamlit script (809 lines) with 8 pages selected by a sidebar radio |
| Launch command | `.venv/bin/streamlit run app.py`. Configuration in `.streamlit/config.toml`: headless, `maxUploadSize` 500 MB, XSRF protection on, usage statistics off |
| Runtime | `.venv` (uv): Python 3.12.16, Streamlit 1.67.0, Plotly 7.1.0, Ultralytics 8.4.215, torch 2.15.0 (MPS), streamlit-webrtc for the live camera |
| Running instance | The user's own dashboard is running on **http://localhost:8502** (PID 34056, `streamlit run app.py --server.port 8502 --server.address localhost`). It was not stopped. Streamlit re-reads `app.py` on the next rerun, so this instance will show code changes when it reruns. Development tests use a separate port (8599) |
| Other local servers (not this project) | 127.0.0.1:8000 and 127.0.0.1:8501 belong to `../472 Project` and were not touched |
| Frontend framework | Streamlit only. No separate frontend, API server or build chain. Theme in `.streamlit/config.toml` (light and dark palettes, orange accent); about 10 lines of inline CSS in `app.py` |
| Backend | Python modules under `src/`: `detection` (`PPEDetector`, model registry, image, video and live processors, annotation), `compliance`, `events` (`EventManager`, `EventStore`), `reporting`, `evaluation`, `training`, `utils` |
| Test command | `.venv/bin/python -m pytest -q` (Streamlit `AppTest` smoke tests in `tests/test_app.py` plus unit and integration tests) |

## 2. Mandatory ML reference documents

All six documents exist at the specified paths. They were written and checked earlier in this same working session, and their current contents were verified by SHA-256.

| Document | sha256 |
|---|---|
| `experiments/accuracy_improvement/reports/HANDOFF-ML-to-frontend.md` | `431512ea5860bc70…` |
| `…/REPORT-025-final-research-decision.md` | `f212910d1dcbc3d0…` |
| `…/REPORT-024-qualification-and-integration.md` | `310f4133d735a7e8…` |
| `…/REPORT-023-model-comparison-and-error-analysis.md` | `71f3eed14c2df892…` |
| `…/REPORT-022-training-experiment-matrix.md` | `91de087f779e0bc0…` |
| `experiments/accuracy_improvement/README.md` | `e7ef5e9cb1b98af2…` |

**Binding facts taken from them:**
- **Model loading:**
  - YOLO26n (`yolo26n_baseline`) is the active model and the fallback.
  - E3 is stored but not registered, so it cannot be selected.
  - Load models only through `PPEDetector()`.
  - On `status == "fallback"`, show a warning with `load_errors`; on `ModelNotFoundError` or `IncompatibleModelError`, show a blocking error.
- **Inference:** use `detector.image_size`.
- **Thresholds:** read-only in the UI; scores are labelled "detector confidence".
- **Live view:** the live panel is built from `LiveFrameProcessor.snapshot()`.
- **Events:** only `EventManager` / `EventStore` create events.
- **Metric wording:** always name the metric, the split and its size.

## 3. Preservation snapshot

**Backups** of the files expected to change, in `experiments/frontend_completion/backups/20261123-phase0/`:

| Original | Backup | sha256 |
|---|---|---|
| `app.py` | `app.py` | `569e58d8ecc47cb03e1aeda9898340710bf0191f2bab77d512f7b9cd18763d8e` |
| `.streamlit/config.toml` | `config.toml` and `streamlit_config.toml` (identical) | `125571ea63e64f7191a81a387f3916ae39c1ff9dc583200c980627bc49a6988d` |
| `README.md` | `README.md` | `f5dec9085306fa1669da3b381fb5a42e3a1666edfb2e68ac2fbc04ae0093f25a` |

**Files planned for change** (2026-11-23 11:10; refined in REPORT-003):
- `app.py`, `.streamlit/config.toml` and `README.md`;
- new UI helper modules under `src/ui/`;
- new focused UI tests under `tests/`;
- reports, logs and evidence under `experiments/frontend_completion/`.

**Protected and read-only:**
- the original dataset `../construction-ppe/`;
- all checkpoints under `models/` and `experiments/`;
- the E3 model card;
- `configs/settings.yaml` (thresholds, compliance, events, model registry);
- `outputs/siteguard_events.db` and `outputs/evidence/`;
- `experiments/accuracy_improvement/` (reports, annotation review, ledger);
- `src/compliance/`, `src/events/`, `src/detection/` (inference, registry, processors);
- `experiments/live_audit/webcam/` (private camera frames; never opened).

## 4. Checkpoint hashes (read only; nothing copied)

| File | sha256 |
|---|---|
| `models/trained/best.pt`: YOLO26n, **active and fallback** | `890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b` |
| `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt`: E3, not promoted | `590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6` |
| `…/yolo26m_e3_896_v1/model_card.json` | `f42a7e0a9ad061e522c4d4f2ce83469fd4b20d4b57561327cf0a78f75038dd71` |
| `experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt`: earlier YOLO26m | `399c4e5be335e3544afe185c7abb08d5fc894a382b891d970f71b94df3f1773f` |
| `models/pretrained/yolo26m.pt` | `401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7` |
| `models/pretrained/yolo26n.pt` | `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef` |

## 5. Integrity manifest

Command: `.venv/bin/python scripts/accuracy/integrity_manifest.py create frontend_phase0`

Output: `experiments/accuracy_improvement/manifests/20261123-110740_frontend_phase0/`, covering:
- dataset: 2,004 files;
- protected: 851 files;
- user data: 317 files (hashed locally only).

This is the reference for the Phase 6 verification.

## 6. Events database and evidence (read-only inspection)

- **Path:** `outputs/siteguard_events.db`, 36,864 bytes, last modified **2026-11-20 21:19:11**.
- **Read-only access:** opened only through `sqlite3.connect("file:…?mode=ro", uri=True)`. The modification time was unchanged afterwards (`logs/phase0_events_db_readonly.txt`).

| Table | Rows | Detail |
|---|---|---|
| `events` | 33 | no_gloves 10, no_helmet 12, no_vest 11; all `pending_review`; sources: image 2, live_camera 31; 2026-11-19T19:33:24 to 2026-11-20T21:19:07 |
| `inspections` | 6 | 2026-11-19T19:36:04 to 2026-11-20T21:19:11 |

**Evidence:** `outputs/evidence/` holds 125 files (21 MB). They were counted, not opened.

## 7. Baselines

| Check | Command | Result |
|---|---|---|
| Test suite | `.venv/bin/python -m pytest -q -p no:cacheprovider` | **PASS: 156 passed** in 15.3 s (`logs/phase0_baseline.txt`) |
| App startup | `.venv/bin/streamlit run app.py --server.port 8599 --server.address 127.0.0.1 --server.headless true`, then `curl /_stcore/health` and `GET /` | **PASS:** health `ok` after 2 s; `GET /` returned HTTP 200 (7,863 bytes); stopped with SIGINT (`logs/phase0_startup_8599.log`) |

## 8. Discrepancies and observations

1. **No specification file:** the specification was not in the workspace, so it was saved (see the header).
2. **No Git:** rollback uses the backups in §3.
3. **Running instance:** the user's running instance on port 8502 executes the current `app.py` on each rerun. Edits during Phase 3 become visible there on its next rerun.
4. **Editable thresholds (spec §5.9, §6.4, test 21; handoff §3.4):** the existing Settings page exposes **editable** detection, compliance and event thresholds. A "Save as defaults" button writes them to `configs/settings.yaml`. This contradicts the handoff and the specification, which both require read-only thresholds. Recorded for Phase 1 and resolved in the Phase 2 plan.

## 9. Files created or modified in Phase 0

- **Created:**
  - `SiteGuard_AI_Frontend_Completion_Master_Specification.md`;
  - `experiments/frontend_completion/` (`reports/`, `backups/20261123-phase0/`, `logs/`, `evidence/`);
  - this report;
  - the integrity manifest folder above.
- **Modified:** none.

## 10. Next phase

Phase 1, the architecture and feature audit. Prerequisites: met.
