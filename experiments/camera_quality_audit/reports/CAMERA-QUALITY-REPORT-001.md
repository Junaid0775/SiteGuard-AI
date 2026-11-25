# CAMERA-QUALITY-REPORT-001 — Camera image quality diagnostic audit

**Date:** 2026-11-23, 12:00–12:25 IST. **Status:** audit complete; **no fix implemented** (waiting for the owner's approval).

**Physical camera:** used with the owner's explicit approval ("camera ok"), for about 19 s in total:
- 12:14:01–12:14:05, OpenCV size check;
- 12:14:13–12:14:32, browser WebRTC run of about 15 s.

**Privacy:** only metadata (frame sizes, formats, bitrates, timings) was recorded. No camera frame was saved, read back, displayed or uploaded, and no event or evidence was written. Both camera processes exited afterwards, which releases the camera.

## 1. Summary

**The live dashboard shows a low-resolution, twice-compressed and then upscaled video. The cause is the WebRTC transport, not the camera and not YOLO.**

The MacBook camera delivers 1920 × 1080 natively, and 1280 × 720 on request. But the frames that reach the server, and therefore both YOLO and the screen, were measured at:

| Source | Requested | Frames received by the server |
|---|---|---|
| Physical camera | 1280 × 720 | **640 × 360 for the first 4 s, then 480 × 270** |
| Synthetic camera | 1280 × 720 | 640 × 360 for about 17 s, then 960 × 540; never 1280 × 720 in 30 s |

**Four confirmed causes:**
1. **Uplink downscaling by the browser's WebRTC encoder.** Chrome lowers the resolution it sends because the bandwidth estimate towards the Python WebRTC peer (aiortc) starts low and rises slowly.
2. **Second lossy encode on the way back.** The server re-encodes the annotated frame with aiortc's VP8 encoder: constant bitrate, starting at **500 kbit/s**, hard maximum **1.5 Mbit/s**. Measured: 0.25–1.4 Mbit/s.
3. **Upscaling in the page.** The browser shows the 480 × 270 or 640 × 360 stream in a box about 704 × 396 CSS px wide, an upscale of **1.1–1.47×**.
4. **Same input for YOLO and evidence.** YOLO and the saved evidence frames receive exactly these downscaled frames. Your own live sessions today produced evidence frames of 640 × 360 and 960 × 540.

## 2. Method and evidence

**Static audit** of the code paths (file and line references in §3).

**Runtime probes:**
- **Probe app:** `experiments/camera_quality_audit/tools/webrtc_probe_app.py`.
  - It calls `webrtc_streamer` with **exactly the arguments of `app.py`** (lines 414–421) and processes frames with the real `LiveFrameProcessor` and YOLO26n.
  - Events go to an `EventManager` with `store=None` and `save_evidence=False`.
  - aiortc's encoders are wrapped **in that process only**, to log codec, size and target bitrate.
- **Driver:** `tools/run_probe.py`, using the local Google Chrome in headless mode through the DevTools protocol.
- **Summary script:** `tools/summarize.py`.

| Run | Source | Processing | Duration | Logs |
|---|---|---|---|---|
| R1 `fake_identity` | Chrome fake camera: Y4M at 1280 × 720 made from dataset image `ultralytics-ppe-nov2026-022.jpg` (no person's camera) | Frame returned unchanged (transport only) | 20 s | `logs/fake_identity/` (`server.jsonl`, `browser.json`, `summary.json`) |
| R2 `fake_pipeline` | Same fake camera | Real pipeline: `LiveFrameProcessor` + YOLO26n + `draw_compliance` | 30 s | `logs/fake_pipeline/` |
| R3 `camera_opencv` | **Physical camera** through OpenCV/AVFoundation | Frame sizes only (20 frames per setting) | 4 s | `logs/camera_opencv/result.json` |
| R4 `camera_pipeline` | **Physical camera** through Chrome and WebRTC (dashboard path) | Real pipeline. **No pixel read back** | about 15 s | `logs/camera_pipeline/` |

**Additional evidence:**
- **Evidence frame sizes:** dimensions of the `outputs/evidence/` images, read from JPEG headers only, without opening the pixels.
- **Database:** the events database, read-only, to attribute today's evidence files.

## 3. Findings for each audit question

### Q1 — Camera initialisation (requested settings)

| Path | Code | Requested |
|---|---|---|
| **Dashboard (browser camera)** | `app.py:414-421`, `webrtc_streamer(..., media_stream_constraints={"video": {"width": {"ideal": 1280}, "height": {"ideal": 720}}, "audio": False}, rtc_configuration={"iceServers": []}, async_processing=True)` | width **ideal 1280**, height **ideal 720**. **No frame-rate constraint**, no pixel format (the browser chooses; WebRTC carries I420 / 4:2:0). These constraints set the browser's *capture* size only, not the size the WebRTC encoder sends |
| Test script only, not the dashboard | `scripts/engineering/realtime_eval.py:202-212`, `camera()`: `cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)`, then `CAP_PROP_FRAME_WIDTH/HEIGHT` = 1280 × 720 | 1280 × 720, BGR |
| Future server-side source (unused) | `src/detection/camera_processor.py:320-340`, `OpenCVFrameSource` | OpenCV default |

### Q2 — Actual frame size at runtime (measured)

| Measurement | Result |
|---|---|
| Physical camera, OpenCV, no request (R3) | **1920 × 1080**, BGR, about 31.7 fps measured (OpenCV reports 15 fps, which is wrong for AVFoundation) |
| Physical camera, OpenCV, 1280 × 720 requested | 1280 × 720, about 31.6 fps |
| **Physical camera, dashboard WebRTC path, received by the server (R4)** | **640 × 360 `yuv420p`** in seconds 0–4 (74 frames), then **480 × 270 `yuv420p`** in seconds 4–12 (221 frames); 20–30 fps |
| Synthetic 1280 × 720 camera, received by the server (R1, R2) | 640 × 360 for the first 16–17 s, then 960 × 540; **never 1280 × 720** |

**Browser capture size:** not read directly (the local preview track is not rendered). With the synthetic source fixed at 1280 × 720, frames still arrived at 640 × 360 or 960 × 540. That shows **the reduction happens in the WebRTC encoder, not in capture**. This is confirmed for the synthetic source and inferred for the physical camera.

### Q3 — Every transformation after capture (live path)

1. **Browser, capture to send:**
   - camera frames (NV12/I420, 4:2:0);
   - Chrome WebRTC encoder **downscales** (1280 × 720 to 640 × 360 or 480 × 270) according to its bandwidth estimate;
   - **VP8 encode**, lossy (negotiated codec confirmed: aiortc offers VP8 first and every server-side encode was VP8).
2. **Server receive** (aiortc, `streamlit_webrtc`): VP8 decode to `av.VideoFrame` in **`yuv420p`** at the received size.
3. **`app.py:408`** `newest.to_ndarray(format="bgr24")`: colour conversion yuv420p to BGR24 (chroma upsampling; no resize).
4. **`camera_processor.py:186-194`** `infer()`: `PPEDetector.detect()` with `model.predict(image_bgr, imgsz=640, …)` (`detector.py:164-181`). Ultralytics letterboxes a **copy** to 640 (480 × 270 is **upscaled** ×1.33; 640 × 360 is 1:1; 960 × 540 is downscaled). The original array is not changed.
5. **`camera_processor.py:196-205`** `render()`, which calls `annotate.draw_compliance` (`annotate.py:60-74`), which calls `draw_detections` (`annotate.py:46-57`, **`out = image.copy()`** at line 47): boxes and labels are drawn on a copy at the received size. No resize.
6. **`app.py:409`** `av.VideoFrame.from_ndarray(out, format="bgr24")`.
7. **Server send:**
   - aiortc `Vp8Encoder.encode` reformats BGR24 to **`yuv420p`** (`aiortc/codecs/vpx.py:185`), a second 4:2:0 chroma reduction;
   - **VP8 re-encode** at constant bitrate, `minrate = maxrate = target` (`vpx.py:204-218`), with `DEFAULT_BITRATE` 500 000, `MIN_BITRATE` 250 000 and `MAX_BITRATE` 1 500 000 (`vpx.py:16-18`). The target only changes on REMB feedback from the browser (`aiortc/rtcrtpsender.py:284-290`).
8. **Browser display:** VP8 decode, then the `<video>` element is **scaled by CSS** to the column width.

**Other paths:**
- **Evidence:** on an event, `EventManager` writes the annotated frame as **JPEG quality 85** at the received size (`src/events/event_manager.py:137-143`).
- **Image and Events pages:** `st.image` sends JPEG at quality 100 for photos (Streamlit `elements/lib/image_utils.py:97-125, 128-140`). It downsizes only images wider than the display, at most `MAXIMUM_CONTENT_WIDTH` 1460 px (lines 59, 185-212).

### Q4 — Is the original frame preserved separately from the YOLO input?

**Yes (confirmed).**
- The received frame (`packet.frame`) is passed read-only to `detect()`, and Ultralytics resizes a copy.
- Drawing uses `image.copy()`.
- R2 logged `out_is_input_object = false` for all 874 frames.
- But this "original" is already the **WebRTC-downscaled** frame (480 × 270 to 960 × 540), not the camera's 1280 × 720 or 1920 × 1080.

### Q5 — Does YOLO use a resized copy or modify the original?

**A resized (letterboxed) copy at `imgsz = 640`. The original is not modified (confirmed above).** The YOLO input is limited by the upstream WebRTC resolution. At 480 × 270, the model sees an upscaled low-detail image, which also limits detection of small PPE. This is consistent with the earlier live-audit accuracy findings (REPORT-009).

### Q6 — Are detection coordinates mapped correctly onto the frame?

**Yes, onto the frame actually received.**
- Ultralytics returns `boxes.xyxy` in the input frame's pixel coordinates.
- `tests/test_resolution_coordinates.py` (13 tests, passing; full suite 166 passed) verifies the mapping across resolutions, and that evidence images use source-frame coordinates.
- The boxes are drawn on the same frame they were computed on (`render()` refuses any other frame: `StaleResultError`).

### Q7 — Does annotation change dimensions or reduce quality unnecessarily?

**Dimensions:** unchanged; it draws on a copy at full received size.

**Quality, minor:**
- line thickness `max(2, round(width / 450))` (2 px at 480–960 px wide);
- label font scale `max(0.4, min(1.0, width / 1800))` (`annotate.py:48, 64-65`) gives 0.4, the minimum, on small frames;
- thin coloured lines and small text then go through 4:2:0 chroma reduction and low-bitrate VP8, so they blur and bleed.

Annotation is not a root cause; it amplifies the visible softness.

### Q8 — Streamlit rendering pipeline

- **Live page:** the live video does **not** use `st.image`. It is a `<video>` element inside the streamlit-webrtc component (0.79.1) playing the server's VP8 stream. Streamlit adds no JPEG encoding or resize to it.
- **Display:** the CSS box is set by the page layout. The video sits in the left column of `st.columns([3, 2])`. Measured box: **704 × 396 CSS px** at a 1440 × 900 window (probe layout; the dashboard column is similar).
- **Live status panel:** refreshes every 1 s (`@st.fragment(run_every=1.0)`) and does not touch the video.

### Q9 — Does the browser display the original resolution?

**No.** The `<video>` element's intrinsic size, `videoWidth × videoHeight` measured every second, equals the server's send size:

| Run | Displayed stream (intrinsic size) | On-screen box | Scaling |
|---|---|---|---|
| Physical camera | **640 × 360, then 480 × 270** | 704 × 396 | **upscaled 1.10×, then 1.47×** |
| Synthetic camera | 640 × 360 for about 17 s, then 960 × 540 | 704 × 396 | upscaled, then downscaled |

**Round-trip loss** (synthetic source, frame read back from the browser canvas):
- **33.8 dB PSNR** at 960 × 540 against the source;
- the server-received frame alone was about **37.8 dB** at 640 × 360 in steady state.

So both the uplink and the downlink VP8 encodes cost visible quality.

### Q10 — Source of the quality loss

| # | Finding | Status |
|---|---|---|
| C1 | **WebRTC uplink downscaling** from 1280 × 720 to 640 × 360 and **480 × 270** (physical camera) because of a low bandwidth estimate towards aiortc | **Confirmed by measurement.** The exact estimator behaviour inside Chrome is not instrumented (see U1) |
| C2 | **Second lossy encode** on the server: aiortc VP8, constant bitrate 0.5 Mbit/s rising slowly to the 1.5 Mbit/s cap | **Confirmed** (code `vpx.py:16-18, 204-218`; measured 0.25–1.4 Mbit/s, ramping from 500 to 1500 kbit/s over about 20 s) |
| C3 | **Display upscaling** of the 480 × 270 or 640 × 360 stream into about 704 px | **Confirmed by measurement** |
| C4 | 4:2:0 chroma reduction twice (encode and re-encode) blurs thin coloured annotation lines and text | **Confirmed in code**; visual effect not quantified separately |
| C5 | YOLO input and saved evidence share the reduced resolution | **Confirmed.** Today's live evidence images are 640 × 360 and 960 × 540 (header sizes; 2026-11-20 shows the same) |
| H1 | Real-camera content (noise, motion) makes Chrome drop to 480 × 270, while static synthetic content reaches 960 × 540 | **Hypothesis.** Consistent with WebRTC's balanced degradation |
| H2 | A longer session eventually reaches 1280 × 720 | **Hypothesis.** Partly supported by some 1280 × 720 evidence frames on 2026-11-20 |

**Not causes (verified):** camera hardware (1080p native), YOLO's resize (it works on a copy), coordinate mapping (tested), and annotation dimensions (unchanged).

## 4. Stage-by-stage comparison (physical camera, dashboard path; R4)

| Stage | Image dimensions | Image format | Compression | Transformation applied | Quality-loss risk |
|---|---|---|---|---|---|
| 1. Camera sensor (native) | 1920 × 1080 (R3) | NV12 / BGR via OpenCV | none | — | none |
| 2. Browser capture (`getUserMedia`, ideal 1280 × 720) | 1280 × 720 (requested; inferred) | I420 | none | sensor scaling | low |
| 3. Browser WebRTC send | **640 × 360, then 480 × 270** (measured on arrival) | VP8 (4:2:0) | **lossy, bandwidth-limited** | encoder **downscale** by 2.0–2.67× | **HIGH** |
| 4. Server decode (aiortc) | 480 × 270 | `yuv420p` | — (decode) | — | none (loss already incurred) |
| 5. `to_ndarray("bgr24")` (`app.py:408`) | 480 × 270 | BGR24 | none | yuv420p → BGR | low |
| 6. YOLO input (Ultralytics letterbox, copy) | 640 × 640 (content 640 × 360) | float tensor | none | **upscale ×1.33** + padding | medium (affects detection, not display) |
| 7. Annotation (`draw_compliance`, copy) | 480 × 270 | BGR24 | none | boxes and labels drawn (2 px lines, font 0.4) | low (amplifies later loss) |
| 8. `from_ndarray` → aiortc reformat (`vpx.py:185`) | 480 × 270 | `yuv420p` | none | BGR → 4:2:0 (second chroma reduction) | medium for coloured lines and text |
| 9. Server VP8 re-encode | 480 × 270 | VP8 | **lossy, CBR 0.5 → ≤ 1.5 Mbit/s** (measured 0.46–0.70 Mbit/s in R4) | — | **HIGH** |
| 10. Browser decode and `<video>` | intrinsic 480 × 270, shown in about 704 × 396 CSS px | RGB on screen | — | **CSS upscale ×1.47** | **HIGH (blur)** |
| 11. Evidence image (on event) | received size (today 640 × 360 and 960 × 540) | JPEG | quality 85 | — | medium (low-resolution evidence) |

## 5. Requested key values

| Question | Answer |
|---|---|
| Original camera frame resolution | **1920 × 1080** native. The dashboard requests 1280 × 720 |
| YOLO inference resolution | `imgsz` **640** letterbox. The source content is the received frame: **480 × 270 / 640 × 360** with the physical camera, so YOLO **upscales** it |
| Final dashboard image resolution | The `<video>` stream is **480 × 270** (640 × 360 at start), displayed in about **704 × 396** CSS px |
| Is the displayed image upscaled? | **Yes**, by about 1.1–1.47× with the physical camera |
| Does the implementation unnecessarily sacrifice quality? | **Yes.** On localhost the bandwidth is effectively unlimited, yet the WebRTC defaults reduce resolution and apply about 0.5–1.5 Mbit/s compression twice. Nothing in the application overrides them |
| Would a full-resolution display affect fps or memory? | **YOLO cost: small.** YOLO always runs at 640, and at 1280 × 720 frames the YOLO26n replay measured 20.3 ms mean (REPORT-024). **Conversions: about +2–4 ms** per 1280 × 720 frame (estimate). **Hypothesis to measure:** VP8 encoding at 1280 × 720 and higher bitrate costs more server CPU, perhaps 5–15 ms per frame. That could approach the 33 ms budget together with inference. **Memory:** 2.8 MB per 1280 × 720 BGR frame against 0.4 MB at 480 × 270, which is negligible with the latest-frame policy (1–2 frames in flight) |

## 6. Unresolved questions

- **U1. Chrome's bandwidth estimate.** Why does Chrome's estimate towards aiortc stay low on a loopback connection: slow REMB or TWCC feedback from aiortc, or Chrome's start bitrate? Answering it needs `chrome://webrtc-internals`, or `getStats()` on the sender, which is not accessible inside the component.
- **U2. Browser capture size.** The actual capture size of `getUserMedia` (`track.getSettings()`) was not read, because the local preview is not rendered.
- **U3. Longer sessions.** Whether long sessions with the physical camera reach 1280 × 720 (H2). Measuring it needs a longer camera session.
- **U4. Server CPU at higher quality.** VP8 encode time at 1280 × 720 at 3–6 Mbit/s on the M5 (§5).
- **U5. Browser differences.** Safari and other browsers were not tested; only headless Chrome was. The owner's browser is not known.

## 7. Recommended fix plan (not implemented; awaiting approval)

| Rank | Change | Impact | Risk | Notes |
|---|---|---|---|---|
| 1 | **Raise the server-side VP8 bitrate** for the returned stream: set aiortc's `vpx` `DEFAULT_BITRATE`/`MIN_BITRATE`/`MAX_BITRATE` (for example 2.5 / 1 / 8 Mbit/s) once at app start-up | High on blockiness and compression; does not fix resolution | Low. Localhost only; slightly more CPU (U4) | App-level setting before streams start; no library file edited. Measure with the same probe (R2/R4) |
| 2 | **Stop the uplink downscaling:** make the server advertise a high receive bandwidth (aiortc REMB/estimator start and maximum), or prefer resolution over frame rate (`degradationPreference: "maintain-resolution"` / `contentHint: "detail"`) if streamlit-webrtc exposes it | **High:** 1280 × 720 reaches both YOLO and the screen; better detection of small PPE and better evidence frames | Medium. Touches WebRTC internals and needs testing; inference input changes (re-check accuracy and fps) | Check the streamlit-webrtc 0.79.1 API first (U1). Fall back to a small, documented aiortc patch applied at runtime |
| 3 | **Avoid display upscaling:** limit the `<video>` width to its intrinsic size, or use a wider column (`video_html_attrs` style, layout `[3, 2]` → full-width video) | Medium (less blur); cosmetic | Low | UI-only |
| 4 | **Annotation legibility on small frames:** minimum font scale and line thickness based on the display size | Low–medium | Low | Does not change detections |
| 5 | **Local server-side capture** (the camera is on the same Mac as the server): `OpenCVFrameSource` at 1280 × 720 / 1920 × 1080; no WebRTC uplink; browser display through the existing pipeline | Highest possible fidelity | **High** before the deadline. Changes the camera-permission model and needs new tests | Consider after Tuesday |
| 6 | **Test tooling hygiene:** `scripts/engineering/realtime_eval.py` live paths (`webcam_replay`, `camera`) create `LiveFrameProcessor(..., store=None)`, but `EventManager` still saves evidence to `outputs/evidence/` (`event_manager.py:137-143`). Pass `save_evidence=False` (as the audit probe does) | Prevents test runs writing evidence | Low | See §8 |

**Verification for any fix:** rerun R1, R2 and R4 (and U3 with a longer session), checking:
- resolution received and displayed;
- bitrate and PSNR;
- processing ms and analysed fps;
- the full test suite.

## 8. Disclosure: evidence file written by an earlier test run (found during this audit)

- **File:** `outputs/evidence/EVT-20261123-031826-215199.jpg` (78 KB), created at **03:18:26 today**.
- **Cause:** it was written by `scripts/engineering/realtime_eval.py offline` during the ML Phase 7 replay test, while replaying the private webcam frames from `experiments/live_audit/webcam/` (§7, rank 6).
- **Database:** it is **not** in the events database, which was opened read-only. It is an orphan evidence image derived from private camera frames, and it stayed local.
- **Inaccurate earlier claims:** REPORT-024 §B8, REPORT-025 §12 and the ML handoff §1 said evidence was unchanged by the ML programme. That was inaccurate: the integrity tool reports changed or missing *listed* files and does not report *new* evidence files. The frontend phase (from the 11:07 manifest onward) did not change evidence.
- **Not touched in this audit:** the file was not opened, moved or deleted, because the audit must not change evidence. **Owner decision:** delete it, or keep it.
- **Other new evidence files today:** the five files from 11:47–11:48 belong to your own dashboard sessions (4 live events and 1 image event, all in the database).

**Audit integrity:**
- No source code, configuration, model, threshold, event logic, database or evidence was changed.
- New files are only under `experiments/camera_quality_audit/`, and the synthetic Y4M was created in a temporary folder.
- After the probe runs, the number of evidence files written since 12:00 was **0**.
