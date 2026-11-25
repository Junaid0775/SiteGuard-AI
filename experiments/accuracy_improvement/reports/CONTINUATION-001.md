# CONTINUATION-001 — Accuracy programme state at the start of Phase 4

**Written:** 2026-11-20 01:37 IST. **Specification:** `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md` (project root; reread it in full on continuation, as protocol rule 11 requires).

## 1. Where the programme stands

| Phase | Status | Report |
|---|---|---|
| 0 Discovery and integrity | Complete | `REPORT-018-discovery-and-integrity.md` |
| 1 Dataset quality and label policy | Complete. Human review pending (optional for Phases 2–4) | `REPORT-019-dataset-quality-and-label-policy.md` |
| 2 Evaluation protocol and splits | Complete. Locked test: 0 accesses | `REPORT-020-evaluation-protocol-and-splits.md` |
| 3 Data expansion, augmentation, small objects | Complete; training ablations moved to Phase 4 | `REPORT-021-data-expansion-and-augmentation.md` |
| **4 Training programme** | **Queued. Waiting for mains power** | — (REPORT-022 to be written) |
| 5–8 | Not started | — |

## 2. What is running

**Watcher:** `experiments/accuracy_improvement/training/start_phase4_when_on_power.sh`.
- Started with `nohup` at 01:35; PID 41040 at that time.
- It polls `pmset` every 60 s and does nothing on battery.
- On mains power it runs, under `caffeinate -dims`:
  `.venv/bin/python scripts/accuracy/run_matrix.py experiments/accuracy_improvement/training/matrix_phase4.yaml`
- Its log: `training/logs/runner_phase4.log`.

**Queue (in order):** E1_m640_base → E3_m896 → E6_m640_tiles → E4_m640_aug → E5_m640_clspw → E2_m640_long. Estimated total about 12–13 h on mains power, plus a dev evaluation after each run.

**Per-run state:** `experiments/accuracy_improvement/training/matrix_status.json`. Logs and memory/power monitors are in `training/logs/`; plans are in `training/configs/*.plan.json`; dev evaluations are in `evaluation/dev_<name>/summary.json`.

**Resuming:** re-running the same runner command skips finished runs and resumes interrupted ones from `weights/last.pt`.

**Stopping safely:** `pkill -INT -f run_matrix.py` (Ultralytics saves `last.pt` every epoch) and `pkill -f start_phase4_when_on_power.sh`.

**Keep the MacBook lid open:** closing the lid sleeps the machine even with `caffeinate`.

## 3. Key results so far

- **Identities:**
  - Active app checkpoint `models/trained/best.pt` = YOLO26n, sha256 `890dc61f…995b9b`.
  - Previous YOLO26m `experiments/yolo26m/training/yolo26m_e30_b4/weights/best.pt`, sha256 `399c4e5b…1773f`.
  - Both re-validated exactly.
- **Splits** (`splits/`):
  - train 640 / dev 200 (= original val) / **locked test 160** (whole groups; 47 real-scene + 8 generated prompt families).
  - Leakage checks: train↔test 0 shared groups, 0 near-duplicates, maximum embedding cosine 0.945.
  - Locked-test YAML is separate; the evaluator refuses it without a purpose and the frozen SHA-256; ledger `qualification/locked_test_access_log.csv` is empty.
- **Dev baselines (protocol v1):**

  | Model | Ultralytics mAP50 | P / R at conf 0.25 | Missing-PPE recall (helmet / gloves / goggle / boots / vest) |
  |---|---|---|---|
  | YOLO26m | 0.8311 | 0.885 / 0.828 | 0.715 / 0.700 / 0.476 / 0.691 / 0.692 |
  | YOLO26n | 0.7339 | 0.884 / 0.745 | — |

  - **Gap is in the real-scene family:** YOLO26m mAP50 0.628 there vs 0.906 on generated close-ups.
- **Small objects:**
  - 2,207 of 14,863 boxes are < 8 px at 640; only 36 at native resolution.
  - Inference at 896 with the 640-trained YOLO26m: dev mAP50 0.815 → 0.838; recall on < 8 px boxes 0.39 → 0.48.
  - Tiling: recall 0.53, but precision −0.07 and 144 ms per image.
- **Memory:** training at 896 / batch 4 = 9.7 GB (OK with guard); at 1024 / batch 4 = 12.7 GB (excluded).

## 4. Files modified so far (programme-wide)

- `src/training/train.py`: `--seed`, `--hyp`. Backward-compatible; pre-change copy in `manifests/train.py.before_phase3`.
- `tests/test_training_overrides.py`: new, 12 tests. **Suite: 136 passed.**
- `docs/ANNOTATION_POLICY.md`: new.
- `docs/IMPLEMENTATION_LOG.md`: rows 18–21.
- `SiteGuard_AI_YOLO26m_Accuracy_Improvement_Master_Specification.md`: verbatim copy of the specification.
- `experiments/training.log`: appended by the training runs.
- **Not modified:** app code, configs, compliance rules, thresholds, checkpoints, dataset, events DB, evidence.

## 5. Next tasks (in order)

1. When the queue finishes, compare E1–E6 on dev:
   - paired image bootstrap vs E1 (B = 1,000);
   - family and size strata;
   - missing-PPE recall; latency at the training size and at 640.
2. Define **E7 (combined)** from the ablations that helped. Then run **3 seeds** of the leading candidate if compute allows (otherwise state the uncertainty).
3. Write **REPORT-022**.
4. Phase 5: error analysis and **threshold choice on dev**.
5. Phase 6: freeze the candidate, then **one** locked-test evaluation.
6. Phase 7: integration, keeping YOLO26n as rollback, with tests and real-time measurements.
7. Phase 8: REPORT-025 and README.

## 6. Constraints that stay in force

- The original dataset is read-only.
- Never overwrite a checkpoint (`--no-promote` always).
- The locked test is never used for training or tuning.
- No silent changes to compliance, events or thresholds.
- Nothing is uploaded or published.
- Private webcam files stay local and are not opened.
- No human review is invented.
- Never claim 93–95 % without locked-test evidence.

## 7. Incident update — 2026-11-20 21:23–21:50 IST (overheating concern) — supersedes §2

- The charger was connected at 21:22:19 with the battery at 11 %. The watcher started **E1_m640_base** at 21:23:03, putting the GPU at about 96 % on this fanless MacBook Air.
- At the same time the battery fast-charged (11 % → 32 % by 21:37), and a video call was running.
- The user reported the Mac getting hot. Power log: unplugged at 21:37; training continued on battery.
- **Action:**
  - Watcher killed. Training interrupted at 21:49: SIGINT was not acted on within 60 s, so SIGTERM was used (rc −15).
  - **7 of 30 epochs complete**; `weights/last.pt` is kept for resuming.
  - GPU utilisation went from 97 % to 0 % within 6 s.
  - macOS thermal state afterwards: nominal.
  - No thermal event was logged for the day.
  - Battery condition Normal, maximum capacity 97 %, 79 cycles.
- **Nothing restarts automatically any more.** The status of E1 is `paused_overheating_concern`.
- **Runner hardened** (`scripts/accuracy/run_matrix.py`):
  - suspends training (SIGSTOP) at macOS thermal state "serious" and continues at "nominal";
  - stops at "critical";
  - waits for "nominal/fair" before starting a job;
  - escalates SIGINT to SIGTERM after 60 s.
- **Resuming Phase 4 requires an explicit user decision.**

## 8. Update — 2026-11-22 19:10 IST: deadline re-plan (user: "get it ready before Tuesday"; supersedes §2 and §5)

**Queue now running** (`nohup caffeinate -s ... run_matrix.py training/matrix_phase4.yaml`, log `training/logs/runner_phase4.log`):
- E1_m640_base (resumed at epoch 12) → E3_m896 → E5_m640_clspw → E4_m640_aug. Ends about 01:45 on Monday 23 Nov.
- **E6 (tiles) and E2 (60 epochs) were deferred** because of the deadline. The original six-run plan is kept in `training/matrix_phase4_original_6runs.yaml`.
- Guards:
  - thermal: SIGSTOP at "serious", SIGCONT at "nominal", stop at "critical";
  - pause while on battery;
  - memory pressure;
  - SIGINT escalates to SIGTERM after 60 s;
  - locked-test check.

**Stage 2 (pre-registered before any E3/E4/E5 result):** `scripts/accuracy/stage2_combined.py`, nohup.
- It waits for E1/E3/E5/E4, applies the rule in its docstring, and writes `training/stage2_decision.json` and `training/matrix_phase4_stage2.yaml`.
- It then trains the E7 seeds: 2 or 3 runs, reusing E3 or E1 as the seed-42 run if E7 has no additions.
- Expected end: about 07:30–10:30 on Monday.

**Tooling ready (validated on the existing baselines):**
- `scripts/accuracy/compare_candidates.py`: comparison table, paired image bootstrap against a reference, alert-threshold (0.50) metrics, threshold sweep. Reproduces the YOLO26m − YOLO26n result: mAP50 +0.083 [0.064, 0.100].
- `scripts/accuracy/error_sheets.py`: dev FN/FP manifest and contact sheets for the safety-critical classes.
- `scripts/accuracy/promote_candidate.py`: versioned copy, model card, registry entry, optional `--activate`, load check. Never touches `models/trained/best.pt`.
- `scripts/engineering/realtime_eval.py`: now `--model name=path@imgsz` and `--out`; defaults unchanged. Pre-change copy is in `manifests/`.

**Phase 7 integration code (done early; activation only after the gates):**
- `src/detection/model_registry.py` (new): registry, validation (SHA-256 against the card, class mapping, architecture, task), fallback, `SITEGUARD_MODEL` override.
- `src/detection/detector.py`: uses the registry; validated explicit loads; logs identity; `info()` has the key, status and errors.
- `configs/settings.yaml`: `model.active` / `fallback` / `registry`, with `yolo26n_baseline` active. The legacy key is kept.
- `app.py`: app log at `outputs/logs/siteguard_app.log`; sidebar shows the model identity and a fallback warning; Settings has the active-model selector; image size comes from the active entry.
- `tests/test_model_registry.py`: 14 tests. **Suite: 150 passed.**
- Pre-change copies of `detector.py`, `settings.yaml`, `app.py` and `realtime_eval.py` are in `experiments/accuracy_improvement/manifests/*.before_phase7`.

**Monday plan:**
1. Phase 5: compare all runs on dev (bootstrap against E1); error sheets; threshold sweep. Pre-register the gates and choose the candidate.
2. Phase 6: one locked-test evaluation of the frozen candidate, plus E1 as the reference.
3. Phase 7:
   - promote and activate if the gates pass;
   - real-time runs (`realtime_eval.py offline`, and camera with notice to the user);
   - full test suite.
4. Phase 8: REPORT-025 and README.
5. Reports to write: REPORT-022 (training), REPORT-023 (comparison and errors), REPORT-024 (qualification and integration).

**User data note:** `outputs/siteguard_events.db` gained 2 events on 2026-11-20 at 21:19 from the user's own image inspection in the dashboard. Not a programme action.

## 9. Final update — 2026-11-23 04:01 IST: programme complete (supersedes §5 and §8 "Monday plan")

- The user chose Option A at about 02:40: no further training; E3_m896 is the candidate. Stage 2 (E7 and its seeds) was cancelled before it started.
- Phases 5–8 are complete:
  - REPORT-022, REPORT-023, REPORT-024 and REPORT-025;
  - `experiments/accuracy_improvement/README.md`;
  - `reports/HANDOFF-ML-to-frontend.md`.
- **Locked test:** E3 has mAP50 0.847 and P/R 0.885/0.862 at 0.25; missing-PPE recall is 0.52–0.80. The promotion gates failed, so the candidate is **not promoted**.
- **Application state:** YOLO26n stays active and fallback; `configs/settings.yaml` is unchanged. The candidate is stored at `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/`, not registered.
- **Checks:** tests 156 passed; integrity OK.
- **Still open:**
  - physical-camera test (needs the user present);
  - human label review (178 cases);
  - the next-iteration work listed in REPORT-025 §11.
- Frontend redesign has not been started; it is postponed by the user.
