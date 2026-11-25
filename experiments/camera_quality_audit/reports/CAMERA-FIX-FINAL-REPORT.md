# Camera Fix Programme — Final Report

**Report ID:** CAMERA-FIX-FINAL-REPORT (covers the start guard, Fix 1, Fix 2 and Fix 3; follows CAMERA-START-FAILURE-DIAGNOSTIC-001)
**Completed:** 24 November 2026 (IST)
**Validation type:** All results are **automated tests with Chrome's synthetic camera**. **No physical-camera validation was performed.** It needs the separately approved, consensual test.

## 1. Status

| Category | Items |
|---|---|
| **Implemented and verified (automated, synthetic camera)** | Start guard; Fix 1 return bitrate 4 Mbit/s; Fix 2 uplink resolution hints (all seven gates passed); Fix 3 video sizing at 1440 px and 1024 px; Fix 4 overlays and Fix 6 evidence isolation (earlier reports 002 and 003) |
| **Implemented but not fully verified** | Every change above on a **physical webcam** and with **real user clicks**; Fix 2 in browsers other than Chrome (they ignore the hints) |
| **Deferred** | Fix 5 (as approved) |
| **Remaining risks** | Section 7 |

Final automated state: **189 tests passed**; final regression **9 of 9** scenarios; final natural starts **12 of 12**; evidence (131 files), events database, YOLO26n and E3 checkpoints unchanged.

## 2. Files changed

| File | Change |
|---|---|
| `src/ui/live_video.py` | Start guard (`protect_live_stream`, `mark_live_component_absent`, `clear_live_component_absent`, version gate `guard_supported`); `RETURN_VIDEO_BITRATE` 2.5 → **4 Mbit/s** (min 2, max 4) and the false "4-8 Mbit/s unstable" comment removed; Fix 2 `configure_uplink_hints` / `applied_uplink_hints` with `UPLINK_HINTS_KBPS = {start 2500, min 1500, max 4000}` |
| `app.py` | Imports; one marker line for runs that do not render the video (`page != "Live Monitoring" or _err is not None`); guard call before `webrtc_streamer`, marker clear after it, marker set in its error branch; `configure_uplink_hints()` after `configure_return_video_bitrate()`; Live layout wrapped in `st.container(key="sg-live-layout")`; Fix 1 comment updated |
| `src/ui/theme.py` | Below 1200 px the Live status panel moves under the video (CSS scoped to `.st-key-sg-live-layout`) |
| `tests/test_live_start_guard.py` (new) | 11 tests against the real library context code, plus an AppTest that other pages keep the library reset active |
| `tests/test_uplink_hints.py` (new) | 3 tests: hints reach the aiortc SDP answer, rollback removes them, idempotence |

Not changed: models, thresholds, compliance rules, event persistence, database, evidence, dataset. Diagnostic tools and logs are under `experiments/camera_quality_audit/` (`fixes/start_guard/`, `tools/`, `logs/`); the application imports none of them.

## 3. Start guard

**Cause fixed:** streamlit-webrtc 0.79.1 misreads a jump in Streamlit's finished-run count during START as a page change and stops its own worker (diagnostic report 001).

**Design:** just before `webrtc_streamer`, the guard sets the library's stored run count to `None`, its own "no previous render" state, so that one check is skipped. Any run that does not render the video (another page, no usable model, component error) sets a marker that keeps the library's reset fully active. On any other library version the guard does nothing.

**Phase 1–2, isolated copy** (source patched in memory, production untouched):

| Test | Guard off (control) | Guard on |
|---|---|---|
| Forced run-count jump on a live stream | Stream stopped, reset logged | Stream kept, 3 of 3 |
| 40 forced reruns 25 ms apart | Passed | Passed, 3 of 3 |
| Leave page, return, restart | Passed | Passed, 3 of 3 (server released 0.0–0.3 s) |
| Leave and return within 150 ms | Recovered by restart | Recovered by restart, 3 of 3 |
| STOP releases camera, connection and server threads | Passed | Passed, 3 of 3 (0.51 s) |
| 10 START/STOP cycles | 10 of 10 | 10 of 10, 3 of 3 (RSS +2–4 MB) |
| Camera unavailable, then retry | Retry streams | Retry streams, 3 of 3 |
| ICE cannot connect, then retry | Needs STOP, then retry streams | Same, 3 of 3 |
| Server connection dropped, then retry | START back after 5.9 s, retry streams | Same, 3 of 3 |
| Natural starts, test page | 15 of 16 (1 reset failure) | **40 of 40** (3 real jumps survived) |
| Natural starts, real dashboard | 16 of 16, plus 1 natural reset failure seen in a control scenario | **24 of 24** |

**Phase 3, production:** 186 tests passed (175 before plus 11 new); regression **27 of 27**; natural dashboard starts **30 of 30** (4 real jumps survived); STOP stress **30 of 30**. Rollback check: the backup `app.py` reproduces the original failure on a forced jump, and passed 30 of 30 STOP runs.

## 4. Fix 1 — return-video bitrate

Selection rule, written before the confirmation runs (`fixes/fix1_selection_rule.txt`): the lowest setting with ≥ 29 fps and ≤ 3 dropped frames in every run, ≤ 5 percentage points more CPU than the library default, and less than 1 dB gain per extra Mbit/s from the next step.

| Setting (3 valid runs each, moving content) | Actual kbit/s | Received / shown fps | Dropped | Encode p95 | Server CPU |
|---|---|---|---|---|---|
| Library default (before) | 1,453–1,491 | 30.0–30.2 / 29.6–30.0 | 0, 31, 0 | 2.71 ms | 37.9 % |
| 2.5 Mbit/s | 2,500–2,512 | 30.0–30.1 / 29.6–30.0 | 0, 0, 2 | 3.11 ms | 38.9 % |
| **4 Mbit/s (chosen)** | 4,015–4,035 | 30.0–30.1 / 29.8–29.9 | 1, 0, 0 | 3.57 ms | 39.7 % (+1.8) |
| 6 Mbit/s | 6,002–6,033 | 30.0–30.2 / 29.6–29.8 | 0, 1, 0 | 4.08 ms | 41.2 % |
| 8 Mbit/s | 8,022–8,046 | 30.1–30.2 / 29.6–29.8 | 0, 0, 0 | 4.42 ms | 41.7 % |

Quality: return-video PSNR on moving annotated video rises 22.9 → 24.5 dB from 2.5 to 4 Mbit/s; further steps add 0.62 and 0.33 dB per Mbit/s. On a still image the round trip improves from 32.6–33.2 dB (library) to about 37.0 dB. Every setting up to 8 Mbit/s was stable; the earlier "unstable" claim came from a benchmark invalidated by sleep. The real dashboard now receives **4.0–4.2 Mbit/s** of return video (library cap 1.5 Mbit/s).

## 5. Fix 3 — video sizing

| Viewport | Before this phase | After |
|---|---|---|
| 1440 × 900 | 640 × 360 stream shown at 640 × 360 | Unchanged; a 1280 × 720 stream is shown at 645 × 363 (column width) |
| 1024 × 768 | Shown at **368 × 207** beside the status panel | Status panel stacks below; shown at **564 × 317** |

Every sample at both widths: never upscaled, aspect ratio kept, `object-fit: contain` (nothing cropped), no horizontal overflow.

## 6. Fix 2 — uplink resolution (merged; all gates passed)

| Gate | Result |
|---|---|
| G1 Received resolution | **1280 × 720 in 100 %** of 3,024 server frames (4 runs); without hints 640 × 360 |
| G2 Coordinate alignment | `tests/test_resolution_coordinates.py` passes, including 1280 × 720 frames |
| G3 Automated tests | 189 passed |
| G4 FPS and drops | 30.1 fps received, 29.8–30.1 shown; dropped 0, 33, 1, 1 (median 1; a similar single outlier, 31, occurred with the library default) |
| G5 CPU and memory | CPU about 40 → 55 % of one core (+15 points); RSS about 724 → 804 MB (+80 MB); thermal state nominal |
| G6 Stability | 12 of 12 dashboard starts with hints, then 9 of 9 regression scenarios and 12 of 12 starts on final code |
| G7 Rollback | `configure_uplink_hints(enabled=False)` removes every hint from the SDP answer (automated test) |

Effect: YOLO input, displayed video and evidence images now come from 1280 × 720 frames instead of 640 × 360. YOLO still runs at 640.

## 7. Remaining risks

1. **No physical-camera validation.** A real webcam, lighting and human click timing may behave differently, including resolution and CPU load.
2. **Rare START no-op, cause unknown.** In 2 of about 600 test starts, START produced no connection attempt at the server; once, a second press in the same page also failed. It occurred both without the guard (rollback copy) and with it, and did not recur in 60 dedicated starts. A page reload is the likely recovery but was not tested.
3. **Library coupling.** The guard uses one private attribute of streamlit-webrtc 0.79.1. It disables itself on other versions, and a test fails on upgrade so it is re-validated.
4. **Fix 2 is Chrome-specific** and adds about 15 points of CPU on a fanless laptop. Evidence JPEGs will be larger because they come from 1280 × 720 frames.
5. **Pre-existing behaviour kept:** after an ICE failure the operator must press STOP before retrying. After a camera error, the library leaves one unused browser connection object, which carries no media.
6. **The dashboard on port 8502 started before all of these fixes** and must be restarted. Until then it may show old behaviour or an import error.

## 8. Rollback

Backups are in `experiments/camera_quality_audit/fixes/backups/`; restart the dashboard after any rollback.

- **Fix 2 only:** restore `app.py.before_fix2` → `app.py` and `live_video.py.before_fix2` → `src/ui/live_video.py`, then delete `tests/test_uplink_hints.py`. Without restoring files, remove the `configure_uplink_hints()` call in `page_live`.
- **Fix 3 narrow layout only:** restore `theme.py.before_fix3_final` → `src/ui/theme.py` (the container key is then harmless).
- **Fix 1 bitrate only:** set `RETURN_VIDEO_BITRATE` back to `{"default": 2_500_000, "min": 1_250_000, "max": 2_500_000}`.
- **Everything from this programme, back to before the guard:** restore `app.py.before_start_guard`, `live_video.py.before_start_guard` and `theme.py.before_fix3_final`, then delete `tests/test_live_start_guard.py` and `tests/test_uplink_hints.py`.
- **Back to before all camera fixes:** `app.py.before_camera_fixes`, plus the Fix 4 and Fix 6 backups listed in reports 002 and 003.

## 9. Preservation checks

Evidence: 131 files match their saved SHA-256 list. Events database: hash unchanged. YOLO26n `890dc61f…` and E3 `590d7d6e…` unchanged; E3 remains unselectable. Thresholds and compliance rules not touched. Nothing was pushed or deployed. The physical camera was never opened.
