# REPORT-012 — Live Pipeline R1 (Frame Synchronisation) and R2 (Inference Size 640)

**Date:** 2026-11-19 (20:58–21:10 IST, from file timestamps) **Spec:** §4 (Phase 2, R1) and §5 (Phase 3, R2)
**Status:** R1 and R2 are implemented and tested. Physical-camera integration is the only part left, and it needs you at the browser (§13).

---

## 1. Executive summary

**R1 — stale boxes.**
- Every frame now has a session ID, a frame ID and a receive timestamp. Every result carries its source frame ID and inference timestamps.
- `render()` refuses to draw a result on any other frame.
- Live monitoring uses streamlit-webrtc's queued-frames callback with a **latest-frame policy**: superseded frames are dropped and **counted exactly**.
- Live and offline video now analyse **every frame** by default. When a skip interval is configured:
  - live shows the last correctly annotated frame as it was;
  - video writes the frame without boxes, tagged "not analysed".
- Camera restart or stop starts a new session and discards in-flight results. Inference errors show the raw frame and don't block.

Measured on 600 labelled moving frames (real model, real ground truth):
- Stale-box frames: **400 → 0**.
- Displayed precision at 20 px/frame motion: **0.362 → 0.804** (imgsz 640).
- A mutation check shows the new tests **fail on the pre-change code** and pass on the new code.

**R2 — resolution parity.**
- Live inference now uses the single authoritative `inference.image_size` (640), the same as image and video.
- Cost: **+0.76 ms** median per frame on MPS (7.03 → 7.79 ms).
- Benefit on the same moving frames: recall **+0.09 to +0.10** (e.g. 0.474 → 0.564 at 10 px/frame).
- Coordinate restoration is verified for 6 frame shapes and resolutions, and for real-model alignment on portrait, square, down-scaled and up-scaled variants.

**Tests:** 105 passed = 77 existing + 26 new + the 2 mutation-check tests. pytest collected the mutation-check file from `experiments/` and it passes on the new code; collection was later restricted to `tests/` with `pytest.ini`. The checkpoint and dataset are unchanged.

**Measured behaviour change to note:** events have the same rule (3 analysed frames, 30 s cooldown), but because every frame is now analysed they fire earlier. On the 15 fps test clip the first event moves from 0.67 s to 0.13 s, the median shift is −0.54 s, and 15 of 16 events match one-to-one (§11).

## 2. Objective

Spec §4: correct frame/result synchronisation, bounded latest-frame queueing, a safe session lifecycle and measurable latency.
Spec §5: live inference at 640 through one authoritative configuration, with verified coordinate transforms.

## 3. Initial project state

Traced in REPORT-010 §4.3:
- **Live:** analysed when `n % 3 == 1`; otherwise `draw_compliance(new_frame, last_result)` (`camera_processor.py:96`, old). imgsz from `live.image_size = 480`. No frame IDs or timestamps.
- **Video:** analysed when `k % 5 == 0`; otherwise boxes of frame `k − (k mod 5)` drawn on frame `k` (`video_processor.py:116`, old).
- **streamlit-webrtc 0.79.1 async mode:** the worker drains its input queue and calls `video_frame_callback` with the newest frame only, dropping the others silently. When no new output is ready it re-sends the last output frame.

## 4. Technical investigation

| Question (spec §4.1) | Finding |
|---|---|
| Architecture | WebRTC (aiortc) receive → streamlit-webrtc `AsyncVideoProcessTrack` worker thread → user callback → output deque → `recv()` re-sends the last output when none is new |
| Concurrency owner | The library's single worker thread runs our callback. The Streamlit script thread only reads `snapshot()` (lock-protected). |
| Queues | Library `_in_queue` is an unbounded `queue.Queue`, but it is drained on every iteration. Our buffers were already bounded (`deque(maxlen=20)`). |
| Where stale boxes arose | Only in SiteGuard's skip logic (live and video). The library itself never pairs results with other frames. |
| Correct hook for counting drops | `queued_video_frames_callback`: the library passes *all* frames queued since the last call (`models.py:69`, `process.py:120`) |

## 5. Files inspected

`app.py` (Live, Video and Settings pages; `default_cfg`), `src/detection/{camera_processor,video_processor,detector,annotate}.py`, `src/events/event_manager.py`, `configs/settings.yaml`, `.venv/…/streamlit_webrtc/{process.py,models.py,component.py}`, `.venv/…/ultralytics/{engine/predictor.py, data/augment.py (LetterBox), utils/ops.py (scale_boxes)}`.

## 6. Files modified

The pre-change copies are in `experiments/engineering_phase/baseline/source_snapshot_20261119-204914.tar.gz`.

| File | Previous behaviour | New behaviour | Reason |
|---|---|---|---|
| `src/detection/camera_processor.py` | Analyse every 3rd frame; draw the last result on new frames; no IDs or timing | **Rewritten:** `FramePacket` / `DetectionPacket` (session ID, frame ID, timestamps); `render()` enforces source identity (`StaleResultError`); `process_latest()` drops and counts superseded frames; `every_n > 1` holds the last annotated frame; `reset_session()` / `close()`; bounded timing buffers; `snapshot()` reports latency (mean/median/p95/max) and measured received/analysed/rendered FPS. The public API (`process`, `snapshot`, `events`, `stats`) is unchanged. | R1 |
| `src/detection/video_processor.py` | Stride 5; boxes of the last analysed frame on skipped frames | Every frame by default; with stride N > 1 the frames in between are written **without boxes**, tagged "not analysed"; per-frame integrity log `<output>.frames.csv` (index, time, analysed, boxes_from_frame, detections, inference ms); summary gives the sampling policy, not-analysed count and inference latency | R1 |
| `app.py` | `video_frame_callback`; live imgsz `cfg["live_image_size"]` (480); live resolution slider | `queued_video_frames_callback` → `process_latest` (latest-frame policy, exact drop count); live imgsz = `cfg["image_size"]`; processor `close()` on stop; Live panel shows measured analysed FPS, model, imgsz, inference median/p95, receive-to-render p95, received/rendered FPS, dropped frames and errors; Settings shows the live size as read-only "same as images"; Video page explains the sampling policy and shows inference latency | R1/R2; minimal UI (spec §16) |
| `configs/settings.yaml` | `live.image_size: 480`, `live.process_every_n_frames: 3`, `video.frame_stride: 5`, NMS comment "ignored" | `live.image_size: null` (use `inference.image_size` = 640), `process_every_n_frames: 1`, `frame_stride: 1`, corrected NMS comment (IoU **is** used) | R1/R2, K4 |
| `tests/test_app.py` | Video flow expected 12 analysed frames (stride 5) | Expects 60 (every frame, the new default) | Intended behaviour change |

**New files:**
- `tests/test_frame_sync.py` (13 tests)
- `tests/test_resolution_coordinates.py` (13 tests)
- `scripts/engineering/measure_r1_r2.py`
- evidence under `experiments/engineering_phase/{pipeline_r1,resolution_r2}/`

## 7. Engineering decisions and alternatives

| Decision | Alternatives considered | Why |
|---|---|---|
| Synchronous inference inside the library's worker callback, plus the latest-frame policy | A separate inference thread with frame/result queues | The library already provides one worker thread and freshest-frame semantics. A second thread would add synchronisation risk and gain nothing at about 8 ms per frame (spec §4.1: don't add a new concurrency design). |
| `queued_video_frames_callback` | Keep `video_frame_callback` and estimate drops from pts gaps | Gives *exact* drop counts. Superseded frames are not even decoded to numpy. |
| Default: analyse every frame | Keep every 3rd frame | Measured cost is 7.8 ms per frame (24 % of a 33 ms budget). Skipping isn't needed on the M5. |
| Skip mode shows the held annotated frame | Show the new frame without boxes | A raw frame makes boxes blink on and off at 1/N. The held frame keeps every box on its own image; the cost is display age (measured: mean 1 frame at N = 3). |
| Video skip mode tags frames "not analysed" | Duplicate the analysed frames | The output must keep the source frame order and timing (spec §4.4: never silently skip offline frames). |
| One authoritative size: `live.image_size: null` | Keep a separate live slider | Spec §5: one source of truth. Overriding is still possible for documented experiments. |

## 8. Implementation details

- **Frame identity:** `FramePacket(session_id = uuid4[:12], frame_id = itertools.count(1), received_at = time.monotonic(), media_time_s = pts·time_base, frame)`. Dropped frames consume IDs in arrival order. `DetectionPacket(session_id, source_frame_id, inference_started_at, inference_completed_at, detections, compliance, error)`.
- **Rendering:** `render(packet, result)` checks session ID and source frame ID → `draw_compliance(packet.frame, result.compliance)`. If inference failed, it returns the frame without boxes.
- **Session safety:** after inference, the result is discarded if the session changed or the processor was closed in the meantime (no events, no stats). `reset_session()` clears the held frame, last result and EventManager state. The app calls `close()` on stop and creates a new processor on the next start.
- **Thread safety:** one lock guards ID allocation, stats and held-frame state. Inference and drawing run outside it. `draw_compliance` copies the frame, so the input is never mutated.
- **Timing:** monotonic clock. Recorded per frame: received, inference start and end, render complete. Bounded windows (600 samples) give mean/median/p95/max and measured rates. Browser display time can't be observed server-side, so the measured interval is *received-by-SiteGuard → rendered (returned for encoding)*.

## 9. Testing methodology

- **Unit tests (deterministic frames, mocked detector, no camera)**, in `tests/test_frame_sync.py`. The fake detector's box position encodes the frame it saw, so stale rendering shows up in the pixels. It covers:
  - own box only;
  - `render` refusing a foreign result;
  - a slow result for N while N+1 arrives (threaded);
  - latest-frame drops counted (50 queued frames → 49 dropped, only #50 analysed);
  - 1,000 unique, increasing IDs, unique across sessions;
  - bounded buffers;
  - held-frame policy;
  - restart during in-flight inference (result discarded, nothing leaks);
  - inference exception without blocking;
  - stop and `OpenCVFrameSource.close` releasing capture;
  - latency and rates measured;
  - video frames carrying only their own boxes, at stride 1 and 3, cross-checked against the frame log.
- **R2 tests** (`tests/test_resolution_coordinates.py`):
  - settings parity;
  - live processor at 640;
  - the dashboard's processor at 640 (AppTest);
  - the Ultralytics LetterBox → `scale_boxes` round trip for 720×1280, 1280×720, 1000×1000, 480×640, 2160×3840 and 1350×1080 (tolerance one letterboxed pixel);
  - real-model alignment with ground truth for landscape, portrait-crop, square-crop, 640-px and 2,560-px variants of 3 val images (all boxes in bounds; ≥ 30 % of GT matched; median matched IoU ≥ 0.7);
  - evidence image at source-frame size, with the worker-box outline at the exact coordinates.
- **Mutation check:** the stale-box tests were run against the *pre-change* modules from the snapshot (`pipeline_r1/mutation_check_old_code_test.py`).
- **Measurements:** `scripts/engineering/measure_r1_r2.py` (real model, val ground truth).

## 10. Actual measured results

### 10.1 Tests

| Suite | Result |
|---|---|
| Full suite after R1/R2 (`pipeline_r1/pytest_after_r1_r2.xml`) | **105 passed**, 0 failed, 0 skipped, 11.2 s. That is 103 in `tests/` (77 existing + 26 new) plus 2 mutation-check tests collected from `experiments/`. |
| New R1 tests | 13/13 pass |
| New R2 tests | 13/13 pass |
| Mutation check, old code | **2 failed**: "STALE: frame 1 boxes drawn on frame 2"; "STALE boxes on frames [1, 2, 3, 4, 6, 7, 8, 9]" |
| Mutation check, new code | 2 passed |

### 10.2 Displayed-box accuracy under motion

`pipeline_r1/displayed_accuracy.json`. 40 val images × 15-frame pans = 600 displayed frames per cell. Conf 0.25, IoU 0.5 matching against moved ground truth.

| imgsz | Speed (px/frame) | Old: every 3rd + stale boxes | New: every frame | New: every 3rd, held frame |
|---:|---:|---|---|---|
| 480 | 0 | P 0.800 R 0.433, stale 400 | P 0.800 R 0.433, stale 0 | P 0.800 R 0.433, stale 0, age 1.0 frame |
| 480 | 10 | P **0.508** R 0.305, stale 400 | P **0.790** R 0.474, stale 0 | P 0.789 R 0.473, stale 0 |
| 480 | 20 | P **0.375** R 0.241, stale 400 | P **0.804** R 0.516, stale 0 | P 0.808 R 0.516, stale 0 |
| 640 | 0 | P 0.795 R 0.532, stale 400 | P 0.795 R 0.532, stale 0 | P 0.795 R 0.532, stale 0 |
| 640 | 4 | P 0.709 R 0.476, stale 400 | P 0.810 R 0.545, stale 0 | P 0.813 R 0.545, stale 0 |
| 640 | 10 | P **0.494** R 0.346, stale 400 | P **0.813** R 0.564, stale 0 | P 0.808 R 0.564, stale 0 |
| 640 | 20 | P **0.362** R 0.271, stale 400 | P **0.804** R 0.597, stale 0 | P 0.805 R 0.597, stale 0 |

- **R1 effect** (old vs new, same imgsz): the stale-box rate goes from 66.7 % to 0 %. Displayed precision no longer falls with motion.
- **R2 effect** (480 vs 640, new policy): recall rises by +0.099 (static), +0.084 (4 px/frame), +0.090 (10), +0.081 (20). Precision is similar.
- Rows are comparable only within the same speed (the crop window narrows with speed). The images are the harder wide-scene val images, so absolute recall is lower than the all-val figure.

### 10.3 Real-time paced stream

`pipeline_r1/realtime_latency.json`. 300 frames at 1280×720 delivered at 30 fps by a producer thread. The consumer behaves like the library worker. Real YOLO26n on MPS.

| Configuration | Received | Dropped (superseded) | Analysed | Held | Analysed FPS | Rendered FPS |
|---|---:|---:|---:|---:|---:|---:|
| every 3rd frame, 480 (old live settings, new held policy) | 300 | 2 | 100 | 198 | 10.1 | 30.2 |
| **every frame, 640 (new default)** | 300 | **0** | **300** | 0 | **30.0** | 30.0 |
| every frame, 640, +40 ms simulated extra load | 300 | 169 (counted) | 131 | 0 | 13.0 | 13.0 |

The third row shows the drop accounting under overload: no stale boxes and no queue growth. For the "every frame, 640" row: receive-to-render median 8.0 ms, p95 8.7 ms.

### 10.4 Latency cost of R2 (live callback, MPS, 200 frames at 720p; `resolution_r2/latency_480_vs_640.json`)

| imgsz | Inference ms (mean / median / p95 / max) | Receive → render ms (median / p95) | Max throughput |
|---:|---|---|---:|
| 480 | 7.54 / 7.03 / 11.10 / 24.9 | 7.27 / 11.41 | 126 fps |
| **640** | 7.83 / **7.79** / 8.18 / 9.46 | 8.02 / 8.66 | 121 fps |

The median cost is +0.76 ms per frame. The 480 run's higher p95 and max are warm-up and jitter outliers, not a property of 480.

### 10.5 Offline video (270-frame test clip, 15 fps, 1280×720; `pipeline_r1/video_before_after.json`)

| Run | Analysed | Not analysed (tagged) | Frames with reused boxes | Time | Events | Repeats suppressed |
|---|---:|---:|---:|---:|---:|---:|
| Pre-R1, stride 5 (old code) | 54 | — | **216** | 0.9 s* | 16* | 105* |
| New, stride 5 (explicit sampling) | 54 | 216 | **0** | 0.87 s | 16 | 105 |
| **New, stride 1 (default)** | **270** | 0 | **0** | 2.52 s | 16 | 738 |

\*Same analysed frames and event logic as "new, stride 5". The pre-R1 rendering of the 216 skipped frames follows from the old code.

The output keeps the source size (1280×720) and fps (15). The frame log records `boxes_from_frame == frame_index` for every analysed frame.

## 11. Before/after comparison

| Aspect | Before | After |
|---|---|---|
| Stale-box rate (live, every 3rd) | 66.7 % of displayed frames | **0 %** (enforced by `render`; tested; mutation-checked) |
| Stale boxes in video (stride 5) | 216 / 270 frames | 0 |
| Live inference size | 480 | **640** (= image = video) |
| Live analysis rate (30 fps source) | ~10 fps (every 3rd) | **30.0 fps** measured |
| Dropped-frame accounting | Silent (library) | Exact counter, shown in the dashboard |
| Latency visibility | Last inference ms only | Inference and receive→render mean/median/p95/max; received/analysed/rendered FPS |
| Event timing (persistence = 3 analysed frames) | 3 analysed frames ≈ 15 source frames at stride 5 / ≈ 9 at every-3rd | 3 consecutive frames. Video: first event 0.67 s → 0.13 s, median shift −0.54 s, 15/16 events matched (`video_event_agreement.json`) |

**Behaviour change for your attention:** the persistence rule and its threshold are *unchanged* (spec §11). Its effective time window is now shorter (about 0.1 s at 30 fps live), so a brief false missing-PPE detection can raise an event sooner than before. Making persistence time-based (e.g. ≥ 0.3 s) would be a compliance-rule change. It needs its own controlled experiment and your approval, so it was **not** done.

## 12. Limitations and uncertainty

- The motion test uses synthetic pans of still val images.
- The real-time test uses a producer thread, not a browser, so WebRTC encode/decode and browser display time are not included.
- Receive-to-render is a server-side interval.
- The latency figures come from one machine, at one thermal state.

## 13. Known unresolved issues

- **Physical-camera integration test (needs you):** open http://localhost:8502 → Live Monitoring → START → allow the camera. Then check:
  - the caption shows 640 px and analysed FPS near your camera rate;
  - "dropped (superseded)" stays low;
  - boxes follow your movement without lag;
  - STOP then START shows a new session with nothing left over.
- **Event-timing change** (§11): decision pending.
- The webcam domain-shift model errors (REPORT-009 §5.6) are not addressed by R1/R2. They are pipeline-independent.

## 14. Exact reproduction

```bash
cd "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI"
.venv/bin/python -m pytest -q                                   # 105 tests
.venv/bin/python -m pytest tests/test_frame_sync.py tests/test_resolution_coordinates.py -q
.venv/bin/python scripts/engineering/measure_r1_r2.py           # writes pipeline_r1/*.json, resolution_r2/*.json
# mutation check against the pre-change code:
mkdir /tmp/mut && tar -xzf experiments/engineering_phase/baseline/source_snapshot_20261119-204914.tar.gz -C /tmp/mut
cp -R src tests configs data /tmp/mut/ && tar -xzf experiments/engineering_phase/baseline/source_snapshot_20261119-204914.tar.gz \
   -C /tmp/mut src/detection/camera_processor.py src/detection/video_processor.py configs/settings.yaml
cp experiments/engineering_phase/pipeline_r1/mutation_check_old_code_test.py /tmp/mut/tests/test_old_stale.py
(cd /tmp/mut && rm -f tests/test_frame_sync.py && "$OLDPWD/.venv/bin/python" -m pytest tests/test_old_stale.py -q)   # expect 2 failed
```

## 15. Conclusion

- **R1 is accepted** against spec §4.7. Source-frame association is enforced and tested, stale boxes are eliminated (400 → 0 per 600 moving frames; 216 → 0 per 270 video frames), the queue is bounded with drops counted, the lifecycle is safe on restart, stop and errors, latency is measurable, and compliance/event tests pass. The remaining item is the browser-camera check.
- **R2 is accepted** against spec §5. Live, image and video all use 640 from one setting, coordinate transforms are verified, and the latency impact was measured (+0.76 ms median).

## 16. Recommended next step

Phase 4, the dataset quality and annotation audit (REPORT-011), then YOLO26m readiness (REPORT-013). In parallel, please run the physical-camera check in §13 when convenient.
