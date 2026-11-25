# SiteGuard AI — Frontend Completion and Integration Master Specification

**Project:** SiteGuard AI — Intelligent Real-Time Construction Site PPE Compliance Monitoring System  
**Workspace:** `~/Desktop/471 Project/SiteGuard-AI/`  
**Execution environment:** macOS, MacBook Air M5, 16 GB unified memory  
**Current application:** Inspect the repository to confirm the actual entry point and architecture. The dashboard has historically been available at `http://localhost:8502` / `http://127.0.0.1:8502`, but do not assume this remains unchanged.  
**Deadline:** Complete a stable, demonstrable frontend and project handoff before Tuesday, 24 November 2026.  
**Implementation operator:** Claude Code in VS Code  
**Project owner:** User  
**Technical reviewer:** ChatGPT

> Local copy saved by Claude Code on 2026-11-23 from the specification supplied in the chat, so that the execution can be checked against it. The full text supplied by the project owner is reproduced below without change in substance; sections 0–13 follow.

---

## 0. EXECUTION DIRECTIVE

Read this entire Master Specification and the mandatory ML handoff documents before changing any files.

The ML research phase has finished. The task now is to complete the existing SiteGuard AI application presentation and frontend integration without destabilising the working ML pipeline, backend, event system, or data.

This is a time-constrained completion task. Prioritise a **complete, reliable, professional, demonstrable application** over unnecessary architectural changes, decorative features, or new ML experiments.

### 0.1 Non-negotiable model decisions

1. **YOLO26n remains the active/default application model.**
2. **YOLO26m E3 is NOT promoted.**
3. Do not add E3 to the user-facing model selector or make it selectable in the application.
4. Preserve E3 and all research artifacts as an experimental candidate only.
5. Do not describe E3 as production-qualified.
6. Do not change model thresholds, compliance rules, event logic, or model-selection policy as part of the frontend work.
7. Do not overwrite, rename, delete, or modify protected model checkpoints.

### 0.2 Mandatory technical reference documents

Read these exact files before implementation:

- `experiments/accuracy_improvement/reports/HANDOFF-ML-to-frontend.md`
- `experiments/accuracy_improvement/reports/REPORT-025-final-research-decision.md`
- `experiments/accuracy_improvement/reports/REPORT-024-qualification-and-integration.md`
- `experiments/accuracy_improvement/reports/REPORT-023-model-comparison-and-error-analysis.md`
- `experiments/accuracy_improvement/reports/REPORT-022-training-experiment-matrix.md`
- `experiments/accuracy_improvement/README.md`

If any path differs, locate the exact corresponding file within the project. Do not fabricate a replacement or assume its contents. Report missing files and continue only with verified available information.

The ML handoff is authoritative for model loading, model identity, frame processing, event ownership, thresholds, and metrics. If this specification appears to conflict with the handoff or existing tested code, stop and report the conflict before changing that behaviour.

### 0.3 Required execution sequence

Execute the following stages in order:

- Phase 0 — workspace discovery, preservation snapshot, and handoff review.
- Phase 1 — current architecture and feature audit.
- Phase 2 — frontend design and implementation plan.
- Phase 3 — frontend implementation using the least disruptive architecture.
- Phase 4 — integration and functional testing.
- Phase 5 — visual refinement, responsive checks, and performance checks.
- Phase 6 — final documentation, evidence, and handoff.

Generate a detailed report after each phase. Do not silently skip a phase. If time or context limits prevent completion, stop safely, preserve the workspace, and write a continuation report with exact remaining work.

---

## 1. PROJECT CONTEXT AND VERIFIED ML DECISIONS

The project is a local construction-site PPE monitoring system. It detects people, PPE, and explicit missing-PPE classes, and provides image, video, and live monitoring workflows plus safety-event review and analytics.

The latest ML report supplied by the project owner states:

### 1.1 Final held-back evaluation

E3 (YOLO26m, 896 px) was evaluated on 160 held-back images from the same dataset. These are not real construction-site footage.

| Metric | E3 result | Previously defined target |
|---|---:|---:|
| mAP50 | 0.847 | 0.93 |
| mAP50-95 | 0.644 | 0.80 stretch goal |
| Precision at application confidence 0.25 | 0.885 | 0.90 |
| Recall at application confidence 0.25 | 0.862 | 0.90 |
| no_helmet recall | 0.739 | 0.90 |
| no_gloves recall | 0.650 | 0.90 |
| no_goggle recall | 0.522 | 0.90 |
| no_boots recall | 0.796 | 0.90 |
| no_vest recall | 0.688 | 0.90 |

Other reported findings:

- E3 held-back mAP50 improvement over E1 (640 px): +0.021, reported 95% interval 0.003–0.040.
- E3 showed better development-set results than YOLO26n, but did not meet the predefined promotion criteria.
- Reported real-site photo mAP50 was 0.59 versus 0.95 on close-up images, indicating a significant generalisation gap.
- E3 was worse on artificially darkened images than YOLO26n.
- E3 replay performance: 24 analysed frames/second, 31 dropped frames out of 149, approximately 42 ms per frame.
- YOLO26n replay performance: 30 analysed frames/second, zero dropped frames, approximately 20 ms per frame.
- 178 suspect labels remain unreviewed.
- Longer-training, tiling, and combined experiments were not completed.
- Each setup was trained once; multi-seed robustness was not established.
- A physical-camera test remains pending unless separately verified as completed.

### 1.2 Model identity and status

**Active production/default model:**

- Key/architecture: YOLO26n (verify exact model metadata from the current implementation).
- Path: `models/trained/best.pt`
- Reported SHA-256 prefix/suffix: `890dc61f…995b9b`
- Status: unchanged and remains active.

**Experimental candidate:**

- E3 path: `models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt`
- Reported SHA-256 prefix/suffix: `590d7d6e…b6f60e6`
- Status: not promoted; not selectable in the application.

The complete hashes and exact model metadata must be read from the local model card/reports. Do not invent missing hash characters or display partial hashes as complete identities.

### 1.3 User-facing interpretation

The application must not imply that it catches every violation or guarantees worker safety. Use cautious language such as:

- “Potential PPE violation”
- “Potential safety event”
- “Detection result”
- “Needs review”
- “No potential violation detected in this frame” only where semantically correct and already supported by the application

Do not use statements such as:

- “100% safe”
- “All violations detected”
- “Guaranteed compliance”
- “Production-qualified model”
- “Accuracy: 84.7%” when the value is actually mAP50
- Any generic “accuracy percentage” that hides the actual metric.

When showing model evaluation metrics, state the exact metric, dataset/split, and sample size. Clearly distinguish the 160-image held-back dataset evaluation from real-site footage and from live camera validation.

---

## 2. PHASE 0 — WORKSPACE DISCOVERY AND PRESERVATION

### 2.1 Confirm workspace

Verify the repository root is `~/Desktop/471 Project/SiteGuard-AI/`. Record: current working directory; Git status and current branch, if Git is configured; whether there are uncommitted changes; application entry point and launch command; current Python/runtime environment; current dashboard URL/port, if running; existing frontend framework and component structure; existing backend/API or Streamlit architecture; existing test command(s). Do not assume Git is available or that the working tree is clean.

### 2.2 Preservation snapshot

Before editing:

1. Record the current Git diff/status, if available.
2. Create a timestamped list of files that will be modified.
3. Identify protected files and directories.
4. Record hashes of production and experimental model checkpoints without copying or modifying them.
5. Record the current test-suite result.
6. Record the current application startup result.
7. Record the current events database path and file metadata; do not open it in a write-capable mode for inspection.
8. Record the evidence directory and existing event/evidence counts using read-only methods, if possible.

Do not create unnecessary copies of large datasets or model weights. Keep any reports, screenshots, or logs inside an appropriate project documentation/evidence directory.

### 2.3 Protected assets

Treat the following as read-only unless the handoff explicitly authorises a narrowly scoped integration change: original dataset directory `~/Desktop/471 Project/construction-ppe/`; production model checkpoint `models/trained/best.pt`; E3 experimental checkpoint and its model card; existing events database and evidence files; existing annotation/review records; training experiment outputs, reports, logs, and checkpoints; existing compliance rules and event thresholds.

No dataset edits, checkpoint replacement, database migration, event deletion, event rewriting, or evidence cleanup is allowed in this task.

### 2.4 Phase 0 report

Create `experiments/frontend_completion/reports/FRONTEND-REPORT-001-workspace-preservation.md`. Include verified paths, current architecture, test baseline, application startup baseline, protected assets, hashes, Git status, and any discrepancies.

---

## 3. PHASE 1 — CURRENT ARCHITECTURE AND FEATURE AUDIT

Inspect the actual application before proposing a redesign.

### 3.1 Inspect existing modules

Locate and document the implementation of: application entry point and navigation; Overview/dashboard; Live monitoring; Image inspection; Video inspection; Safety events; Analytics; Model evaluation; Settings/About; model loader and `PPEDetector`; `LiveFrameProcessor` and its `snapshot()` method; `EventManager` and `EventStore`; image/video upload and validation; webcam lifecycle and cleanup; CSV export and evidence display; existing CSS/theme/component files; existing tests and fixtures. Use actual source paths and function/class names. Do not invent modules or assume all listed pages currently exist.

### 3.2 Feature inventory

For each feature, record: current status (working, partially working, broken, or not present); source file(s); backend/data dependency; current user workflow; existing tests; whether the feature needs visual changes, functional fixes, or no changes. Do not remove an existing feature merely because it is difficult to style.

### 3.3 Identify architecture constraints

Determine whether the current application is Streamlit-only, a separate frontend/backend architecture, or another arrangement.

**Architecture decision rule:**

- Prefer redesigning the existing frontend in place if it can meet the requirements safely and quickly.
- Do not migrate from Streamlit to React merely for appearance.
- A separate React frontend is permitted only if the current architecture demonstrably cannot support the required experience within the deadline, and the existing backend can be integrated without rewriting its domain logic.
- If a new frontend would introduce a second server, API contract, build chain, or deployment complexity that risks Tuesday delivery, retain the existing architecture.
- Do not rewrite the backend, inference engine, event system, or database to accommodate a visual redesign.

### 3.4 Phase 1 report

Create `experiments/frontend_completion/reports/FRONTEND-REPORT-002-architecture-and-feature-audit.md`. Include the page inventory, architecture diagram or concise data-flow description, existing component structure, defects, and recommended implementation approach.

---

## 4. PHASE 2 — DESIGN SYSTEM AND IMPLEMENTATION PLAN

### 4.1 Visual direction

Use a **dark industrial enterprise dashboard**: main surfaces charcoal / deep neutral grey; accent restrained safety orange; supporting colours neutral greys, white text, muted secondary text; status colours consistent and semantically meaningful (do not use colour as the only status indicator); typography a highly readable professional sans-serif; visual language precise, structured, technical, industrial, calm. Avoid neon, glowing gradients, excessive glassmorphism, decorative particle effects, oversized rounded cards, and generic AI landing-page aesthetics. The interface should feel like a credible industrial monitoring product.

### 4.2 Layout principles

Clear left navigation/sidebar with the project identity and page names. Main content area with consistent page title, concise description, and relevant controls. Consistent spacing, alignment, typography, border radius, and component density. Prioritise useful information over decorative cards. Tables should be readable and support empty/loading/error states. Charts must have labels, units, legends, and meaningful empty states. Avoid showing fabricated numbers, placeholder events, or fake camera feeds. Use icons consistently; icons must not replace accessible text labels for important actions. Maintain usable contrast and keyboard accessibility where supported by the framework. Ensure the interface remains usable at common laptop viewport sizes.

### 4.3 Core navigation

Preserve and improve the existing feature set. A sensible navigation order is: 1. Overview, 2. Live Monitoring, 3. Image Inspection, 4. Video Inspection, 5. Safety Events, 6. Analytics, 7. Model Evaluation, 8. Settings / About. Use the exact feature names and capabilities found during Phase 1. Do not expose a navigation item that leads to a non-functional page.

### 4.4 Design and implementation plan

Before substantial coding, write a concise implementation plan that specifies: pages and shared components to update; theme tokens and typography; existing framework components to reuse; any new dependencies and why they are necessary; backend contracts and data sources; responsive behaviour; testing plan; files expected to change; files explicitly not to change. Avoid adding dependencies unless they materially improve the result and are compatible with the current environment.

### 4.5 Phase 2 report and approval gate

Create `experiments/frontend_completion/reports/FRONTEND-REPORT-003-design-and-implementation-plan.md`. The report must include a file-level implementation plan. If the plan requires changing model loading, compliance logic, event ownership, thresholds, database schema, or protected checkpoints, stop and request project-owner approval before proceeding. Otherwise, proceed with the least disruptive implementation path.

---

## 5. PHASE 3 — FRONTEND IMPLEMENTATION

### 5.1 Global shell

Implement a consistent application shell: project identity SiteGuard AI; clear navigation; consistent page headers; shared spacing and typography; restrained orange accent; consistent button, input, table, card, badge, alert, and modal styles; loading, empty, success, warning, and error states; no fake status indicators. If a system status is unknown, display “Unknown” or omit it rather than assuming healthy.

### 5.2 Overview page

The Overview page should communicate the current system state using actual application data. Where supported by existing backend functions, show: current model status and identity; current monitoring/session state; recent safety events; event counts over a clearly stated time window; PPE-related event breakdown; recent activity; useful shortcuts to monitoring and inspection workflows. Rules: do not invent counts or trends; distinguish zero events from unavailable data; show the time window and source for aggregate figures; avoid presenting “zero events” as proof of a safe site; use cautious language — no detected event is not proof of full compliance.

### 5.3 Live Monitoring page

This page is safety-critical from a user-understanding perspective. Preserve the existing frame-processing and event pipeline. Use `LiveFrameProcessor.snapshot()` as the source for live performance/status metrics, in accordance with the ML handoff. Where exposed by the snapshot, show: frames received FPS; frames analysed FPS; frames rendered FPS; dropped frames; slow-end inference time / latency; processing errors; current session/camera state.

Requirements: never draw detections from an older frame over a newer frame; keep frame and detection coordinates aligned with the actual frame being displayed; show a clear “starting”, “running”, “paused”, “stopped”, or “error” state as supported; provide a clear stop/close action; ensure camera resources are released when monitoring ends, the page is left, or an exception occurs; do not start the camera automatically on page load; do not imply that the physical-camera test has passed unless it has been executed and recorded; do not save camera frames unless the existing approved application workflow explicitly requires it (the pending 30-second camera validation described in the ML report is expected to save no frames); explain that detections are advisory and potential events require review.

### 5.4 Image Inspection page

Preserve the existing image inspection workflow. Improve: upload/select affordance; supported-format guidance based on actual code; input image preview; processing/loading state; result image with aligned boxes/labels; clear detection summary; error handling for unsupported, corrupt, oversized, or unreadable files; a clear distinction between detector confidence and probability. Do not invent a new detection or compliance interpretation layer.

### 5.5 Video Inspection page

Preserve the existing video workflow. Improve: video selection/upload; supported-format guidance based on actual code; processing status/progress if available; result playback or output preview if already supported; summary of analysed frames and detected potential events, only when available; clear handling of decode errors, empty videos, unsupported codecs, and interrupted processing; avoid blocking the interface without feedback during long processing. Do not add unverified claims about real-time throughput to offline video processing.

### 5.6 Safety Events page

Use existing `EventManager` / `EventStore` ownership exactly as implemented. **Only `EventManager` / `EventStore` may create or merge events. The frontend must never create, merge, or rewrite events itself.** Improve: event list/table readability; filters only where supported by existing query logic; review status visibility; timestamp formatting and consistency; event detail/evidence viewing; clear distinction between potential violation, compliant evidence, uncertain status, and reviewed status, using the actual domain states; empty state when no events exist; clear errors if evidence is missing or unavailable. Do not: create synthetic events for visual demonstrations; delete or merge events from the frontend; change event persistence rules; change repeat-suppression behaviour; modify the events database or evidence directory; reclassify historical events through UI-only logic.

### 5.7 Analytics page

Use actual stored/derived application data. Possible visualisations, only where supported: events over time; PPE category breakdown; review status distribution; potential event counts; detection or processing trends. Every chart must: have a meaningful title; identify the metric and time range; have labelled axes/units; handle empty data; avoid implying statistical significance where none exists; avoid treating missing detections as confirmed compliance. Do not generate fabricated historical records to populate charts.

### 5.8 Model Evaluation page

Present model evaluation accurately and cautiously. Show the active model as YOLO26n. Show E3 only as a research result in a clearly labelled non-selectable research/evaluation context, if the existing report data is available and the page can distinguish it from the active model. Do not add E3 to the model selector. Do not expose a model promotion action. Show exact metric names: mAP50, mAP50-95, precision, recall, and per-class metrics where available. Identify the dataset/split and sample count beside the results. Clearly distinguish the 160-image held-back evaluation from real-site photo evaluation and live-camera tests. State that the held-back images came from the same dataset, not real-site footage. Clearly disclose known limitations: weak missing-PPE recall, real-site generalisation gap, dark-image weakness, unreviewed suspect labels, single training seed, and incomplete experiments. Do not call mAP50 “accuracy”. Do not present a benchmark as a guarantee of live-site performance. If the evaluation source data is not available in a reliable structured form, use a clearly sourced summary from the approved reports or omit the visualisation. Do not hardcode invented metrics.

### 5.9 Settings / About page

Preserve existing settings behaviour and read-only policy. Do not add E3 as a selectable model. Do not expose editable detection or compliance thresholds. Display thresholds as read-only information only if the existing system exposes them and the handoff permits their display. Show active model metadata using the supported detector/model metadata. Display the project name and concise purpose. Display the limitations/disclaimer. Show software/model information only when verified. Do not add controls that imply unsupported capabilities.

### 5.10 Shared states and accessibility

Every page that loads data or performs processing should have: loading state; empty state; error state with useful, non-sensitive explanation; success/completion state where appropriate. Use clear labels and text in addition to colour. Maintain readable contrast, visible focus, usable controls, and sensible tab order to the extent supported by the framework.

### 5.11 Implementation discipline

Keep changes scoped to frontend presentation and necessary integration adapters. Prefer small, coherent components over one giant page file. Reuse existing business logic. Do not duplicate inference or event logic in UI components. Do not perform long-running inference synchronously on the UI thread if the current architecture provides a background/session mechanism. Do not add unnecessary packages. Do not change the app's public behaviour without recording it. Do not remove working functionality to make the layout simpler. Do not commit, push, publish, deploy, or upload anything publicly.

---

## 6. MANDATORY ML HANDOFF INTEGRATION CONTRACT

The following requirements from `HANDOFF-ML-to-frontend.md` are mandatory. Read the complete handoff for exact method signatures, exceptions, configuration keys, and usage examples.

### 6.1 Model loading

Load the model only through `PPEDetector()`. Do not load checkpoint files directly from UI code. Show the model key, architecture, image size, and SHA identity using verified metadata. Show a visible warning when `status == "fallback"`. Show a blocking error on `ModelNotFoundError` or `IncompatibleModelError`. Never silently substitute a model without communicating fallback status. YOLO26n remains the default and active model. E3 must remain unavailable for selection.

### 6.2 Model switching

The frontend must not introduce a model-switching control for E3. If the existing system already supports another approved model-selection mechanism, preserve its contract and ensure the UI does not expand the available options beyond the project-owner-approved set. Where an authorised model setting is changed through an existing mechanism, follow the handoff exactly: write `model.active` only through the approved settings mechanism; clear the required caches; start a new live session; never modify the events database as a side effect. Do not invent a new model-switching API.

### 6.3 Image size and coordinates

Use `detector.image_size`. Never hard-code 640 in frontend inference calls. Respect the detector's output coordinate contract. Boxes returned in original-frame coordinates must be rendered against the corresponding original frame. Do not independently rescale boxes unless the handoff explicitly requires it.

### 6.4 Thresholds and labels

Detection and compliance thresholds are read-only in the UI. Do not change thresholds to make the dashboard appear better. Label scores as **“detector confidence”**, not probability. Do not imply a detector score is a calibrated probability.

### 6.5 Live frame processing

Build the live panel from `LiveFrameProcessor.snapshot()`. Show received, analysed, and rendered FPS; dropped frames; slow-end inference time; and errors where available. Never render stale detections on a newer frame. Respect the frame processor's lifecycle and thread-safety contract. Ensure proper cleanup on stop, navigation, and exceptions.

### 6.6 Event ownership

Only `EventManager` / `EventStore` create events. UI code must never create, merge, deduplicate, or rewrite events. UI may display and invoke existing supported review actions, but must not invent new event semantics. Never alter the event database schema or historical records.

### 6.7 Metric wording

Always state: exact metric name; dataset/split; number of images or samples; whether the result is from the same-dataset held-back test, development set, real-site photo subset, or live replay. Never use generic “accuracy %” or “production-qualified” wording.

---

## 7. PHASE 4 — INTEGRATION AND FUNCTIONAL TESTING

### 7.1 Baseline and regression

Run the full existing test suite before and after frontend changes. The latest ML handoff reports 156/156 tests passing. Verify the current baseline rather than assuming it remains true. Record: test command; total tests; passed/failed/skipped counts; failure details; whether failures existed before frontend changes. Do not alter tests merely to make them pass. If a test is genuinely obsolete, explain why and obtain approval before changing its assertion or deleting it.

### 7.2 Required functional tests

Test every existing page and workflow:

1. Application starts using the documented command.
2. Navigation between pages works.
3. Overview loads real data and handles empty data.
4. Image inspection works with a valid image.
5. Image inspection handles invalid/corrupt input.
6. Video inspection works with a supported video, if test fixtures exist.
7. Video inspection handles unsupported/corrupt input.
8. Live monitoring can start and stop through its supported workflow.
9. Live monitoring cleanup releases resources.
10. Live metrics reflect `LiveFrameProcessor.snapshot()`.
11. Stale-frame boxes are not rendered over newer frames.
12. Safety events display existing persisted data.
13. Event review actions use only existing supported APIs.
14. Analytics uses real data and handles empty datasets.
15. Model evaluation uses accurate metric names and source descriptions.
16. YOLO26n remains active by default.
17. E3 is not selectable.
18. Missing/incompatible model errors are handled as specified.
19. Fallback status is visible when applicable.
20. No UI path writes to the events database except existing approved event/review APIs.
21. No frontend threshold editing is possible.
22. CSV export works if it is an existing feature.
23. Application can be stopped and restarted without corrupting state.

Use existing test fixtures and safe temporary inputs. Do not create false safety events in the real events database.

### 7.3 Camera test

The ML handoff states a physical-camera test is pending. Do not claim it is complete unless the project owner explicitly authorises it and it is executed. Before any physical-camera test: tell the project owner exactly when it will start; explain that the camera will be active for approximately 30 seconds (or the actual approved duration); confirm whether frames are saved (the planned validation says frames are processed locally and not saved); wait for the owner's explicit approval; do not activate the camera automatically or in the background without that approval; after the test, verify the camera is released and document the result. If the owner is unavailable or does not approve, leave the physical-camera test marked pending. Do not block all other frontend work on this test.

### 7.4 Performance and stability

Check page load and interaction responsiveness. Ensure charts/tables do not freeze the app on larger event histories. Avoid repeatedly loading model weights during navigation. Respect existing model caching. Avoid memory leaks and unclosed camera/video resources. Verify that model loading failures produce clear messages. Do not claim 30 FPS for E3; it was reported at approximately 24 analysed FPS during recorded replay. YOLO26n replay performance was reported at 30 analysed FPS with zero dropped frames in the stated replay test; label this as a replay result, not a universal guarantee.

### 7.5 Phase 4 report

Create `experiments/frontend_completion/reports/FRONTEND-REPORT-004-integration-and-functional-tests.md`. Include all test commands, results, screenshots/evidence references, defects found, fixes, and outstanding limitations.

---

## 8. PHASE 5 — VISUAL REFINEMENT AND RESPONSIVE CHECKS

After functional integration passes: inspect every page at the normal laptop viewport; inspect narrower window sizes; check sidebar behaviour and page overflow; check tables and charts for clipping; check text hierarchy and contrast; check button/input consistency; check loading/empty/error states; check that the most important live monitoring information is visible without excessive scrolling; remove only genuine visual clutter (do not remove useful features); verify no placeholder content or debug widgets remain in the final demonstration path; confirm that the UI does not show E3 as active or selectable.

Take screenshots of the final major pages if the environment permits. Screenshots must be genuine captures of the running application, not mockups or generated illustrations.

Create `experiments/frontend_completion/reports/FRONTEND-REPORT-005-visual-review.md`. Include page-by-page review, viewport sizes, visual issues, corrections, and evidence paths.

---

## 9. PHASE 6 — DOCUMENTATION AND FINAL HANDOFF

### 9.1 README update

Update the existing project README carefully. Do not overwrite valuable existing ML documentation. The README should explain: project purpose and scope; main features actually implemented; system architecture at a high level; environment and dependencies; setup instructions for the current macOS environment, where applicable; exact commands to start the application; expected local URL/port, verified from the current configuration; model identity and active default (YOLO26n); how image, video, and live monitoring work; event review and CSV export, if supported; dataset and model evaluation methodology; exact evaluation metrics and their dataset/split/sample size; known limitations and responsible-use statement; physical camera test status; which experiments were not run; how to run tests; troubleshooting for common startup/model/camera issues. Do not publish local secrets, API keys, private user data, or absolute paths containing unnecessary personal information.

### 9.2 Final report

Create `experiments/frontend_completion/reports/FRONTEND-REPORT-006-final-handoff.md`. Include: 1. Executive summary. 2. What was implemented. 3. Pages and features completed. 4. Architecture decision and rationale. 5. Files changed. 6. Files deliberately not changed. 7. Test results. 8. Application startup verification. 9. Model status: YOLO26n active; E3 not promoted and not selectable. 10. ML metrics and limitations with exact dataset context. 11. Camera test status. 12. Known bugs and limitations. 13. Exact launch instructions. 14. Demonstration walkthrough. 15. Evidence and screenshot locations. 16. Deferred work. 17. Confirmation that no public push/deployment occurred. 18. Confirmation that protected checkpoints, original dataset, and events/evidence were not modified by frontend work, supported by verification.

### 9.3 Demonstration readiness checklist

The application is ready for demonstration only when: it starts reliably using documented instructions; YOLO26n loads as the active/default model; E3 is not selectable; model metadata and fallback/error states are handled correctly; all implemented navigation items work; image inspection is tested; video inspection is tested where supported; live monitoring starts/stops safely, or its pending camera status is disclosed; event list and evidence viewing work with existing data; analytics displays real data or honest empty states; model metrics are labelled correctly; no fake events or fake metrics are present; full regression tests pass, or remaining failures are documented and understood; README and final handoff report are complete; protected data/model hashes are verified unchanged; no public deployment or push has occurred.

Do not mark the project “fully complete” if a critical workflow is broken. Use a precise status such as “frontend complete; physical-camera validation pending”.

---

## 10. STRICT SCOPE EXCLUSIONS

Out of scope: further ML training or fine-tuning; new dataset collection or label correction; reviewing or changing the 178 suspect labels; model architecture changes; changing model thresholds; changing PPE association or compliance rules; changing event creation, persistence, suppression, or review semantics; database schema migration; replacing the current application backend; migrating frameworks solely for visual preference; adding cloud services; public GitHub push, deployment, hosting, or publication; creating synthetic safety events or fake dashboard metrics; making E3 selectable or default; claiming real-world reliability based only on the same-dataset held-back test. If any of these appears necessary, stop and ask the project owner before proceeding.

---

## 11. CHANGE CONTROL AND FAILURE HANDLING

### 11.1 Before each significant change

Identify the exact files to be edited. Confirm the change is within scope. Preserve existing behaviour. Add or update focused tests where appropriate. Avoid broad refactors.

### 11.2 If a test fails

1. Capture the exact failure. 2. Determine whether it is pre-existing or introduced by the change. 3. Reproduce it. 4. Fix only the responsible component. 5. Re-run the targeted test. 6. Re-run the full suite before declaring completion. 7. Document the fix and evidence. Do not hide failures, weaken assertions, or report a pass without actually running the test.

### 11.3 If the application breaks

Stop further feature work. Restore the last known working frontend state using the available version-control or backup mechanism. Do not restore or overwrite protected ML assets. Verify application startup and baseline tests. Document the failure and recovery. Continue only after the application is stable.

### 11.4 If the deadline becomes at risk

Prioritise in this order: 1. Preserve working application and model integration. 2. Fix broken existing workflows. 3. Complete the primary dashboard and navigation. 4. Ensure image/video/live workflows remain accessible. 5. Complete events and model status presentation. 6. Complete README and test report. 7. Add visual polish only after functional completion. Do not sacrifice core functionality, test integrity, or truthful reporting for decorative details.

---

## 12. REQUIRED REPORTING FORMAT

At the end of every phase, write the required report before proceeding. Each report must include: phase and completion status; date/time; files inspected; files created/modified; exact commands executed; test results; evidence paths; decisions and rationale; deviations from this specification; known issues; protected-asset verification; next phase and its prerequisites.

Use explicit status labels: `PASS` — verified and successful; `FAIL` — tested and unsuccessful; `BLOCKED` — cannot proceed due to a dependency or missing approval; `NOT RUN` — not executed; `NOT APPLICABLE` — genuinely irrelevant, with explanation. Never label an untested feature as passing.

---

## 13. FINAL INSTRUCTIONS TO CLAUDE CODE

Begin with Phase 0. Read the full ML handoff and research reports before touching the frontend. Do not start by replacing the application or rewriting the backend. Inspect the actual project and choose the least disruptive implementation approach.

The project owner's approved model decisions are final: YOLO26n remains active/default; E3 remains an experimental, non-selectable, not-promoted candidate; no changes to ML logic, thresholds, compliance rules, events, database, original dataset, or checkpoints.

Complete the frontend and integration with a professional dark industrial design using restrained orange accents. Preserve all working features. Use real application data only. Clearly disclose model limitations and evaluation context.

Work through all phases in order. Produce detailed reports and evidence after every phase. Run the full test suite and verify the application starts.

Do not push, publish, deploy, or upload the project publicly. Do not activate the physical camera without the project owner's explicit approval.

**The definition of success is a stable, polished, functional, locally runnable SiteGuard AI application with honest ML reporting and a complete handoff before Tuesday — not a visually impressive interface that breaks the system.**
