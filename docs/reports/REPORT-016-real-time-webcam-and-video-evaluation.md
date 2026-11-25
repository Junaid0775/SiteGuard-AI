# REPORT-016 — Real-Time Webcam and Video Evaluation (YOLO26n and YOLO26m)

**Date:** 2026-11-19 (23:10–23:25 IST) **Spec:** §10 (Phase 8) **Evidence:** `experiments/engineering_phase/final_validation/`
**Status:** Complete, except the browser/WebRTC display measurement. That needs you at the browser (§13).
**Power state during these runs:** battery, about 33 %, Low Power Mode off, no thermal warnings (`pmset`). This matters; see §10.7.

---

## 1. Executive summary

Results are reported separately per category, never as one combined number.

| Category | YOLO26n | YOLO26m |
|---|---|---|
| **Physical camera** (MacBook camera → OpenCV → `LiveFrameProcessor`, 12 s, no frames saved) | Capture 29.93 fps; **analysed 29.94 fps**; 0 / 359 dropped; inference 18.7 ms mean / 24.2 ms p95; received → rendered p95 24.7 ms | Capture 30.07 fps; **analysed 30.05 fps**; 1 / 361 dropped; inference 26.9 ms mean / 28.4 ms p95; received → rendered p95 28.7 ms |
| **Webcam replay** (149 real frames at their captured 29.8 fps timing; raw) | 0 dropped; 29.8 fps analysed; 23.8 ms mean; flicker 0.11 appear/frame; 0 class flips | 0 dropped; 29.8 fps; 27.8 ms; flicker 0.18 appear/frame; 0.007 class flips/frame |
| Webcam replay, **displayed** accuracy on 10 labelled frames (one indoor scene) | P 0.40 / R 0.33 | P 0.38 / R 0.33 |
| **Offline video** (270-frame clip, every frame) | 2.7 s (100 fps offline); 16 events; integrity all PASS | 6.9 s (39 fps offline); 19 events; integrity all PASS |
| **Motion** (pans, R1 policy, 600 frames per speed) | Displayed P 0.80–0.81, R 0.53–0.60 | P 0.83–0.84, **R 0.67–0.72** |
| **Synthetic low light / blur** (val at 720p) | Dark mAP50-95 0.422; blur 17 px 0.374 | Dark **0.460**; blur **0.457** |

- **Stale boxes:** 0 on every displayed frame, for both models. This is the R1 invariant (tested, REPORT-012).
- **Both models keep up with a 30 fps camera on this Mac.** YOLO26m does so with a thin margin: about 27 ms of a 33 ms frame budget.

## 2. Objective

Spec §10: evaluate real-time behaviour separately from offline mAP, covering performance, stability, displayed quality and video integrity, for both models.

## 3. Initial state

R1/R2 implemented (REPORT-012). Both checkpoints validated (REPORT-014/015).

## 4. Technical investigation — methodology

| Category | Material | Method |
|---|---|---|
| 1. Standard validation images | 200 val images | REPORT-015 |
| 2. Uploaded site images | The same val images through `inspect_image` (the image-upload path); identical to the harness (60/60, REPORT-009) | REPORT-015 operating point |
| 3. Uploaded site video | `data/test_media/test_site_clip.mp4` (270 frames, 15 fps, 1280×720; a slideshow of 6 val images, **not real CCTV**) | `process_video(frame_stride=1, imgsz 640)` plus integrity checks |
| 4. Webcam-style indoor scene | 149 frames captured earlier from the MacBook camera (1280×720, 29.8 fps; one person reclining indoors, no PPE, near-static, about 0.5–1 m from the camera; indoor lamp lighting). 10 frames labelled manually (every 15th; REPORT-009 §5.6). | Replayed at the captured timestamps by a producer thread into a latest-frame consumer (same policy as the streamlit-webrtc worker), raw and VP8 at 1 Mbps |
| 5. Motion | 40 val images × 15-frame pans at 0 / 10 / 20 px per frame | Displayed detections scored against the moved GT |
| 6. Low light | **No real low-light footage exists.** Val images darkened (×0.5 + noise 4; ×0.25 + noise 8) and blurred (17 px) | Audit transforms (REPORT-009) |
| Physical camera | MacBook Air camera, live, 12 s per model | OpenCV AVFoundation capture thread → `process_latest`. Measured: camera capture FPS, analysed/rendered FPS, latency, drops, memory. **No frames saved.** |

**Metric definitions:**
- **Analysed FPS:** inference completions per second, measured.
- **Rendered FPS:** frames returned for display per second.
- **Camera capture FPS:** frames delivered by the camera thread.
- **Frame received → rendered:** monotonic time from a frame reaching SiteGuard to its annotated image being returned. Browser display time is **not observable** server-side.
- **Displayed-result age:** for every displayed frame, time since its source frame was received. Equal to received → rendered here, because every frame was analysed.
- **Flicker:** boxes appearing or disappearing between consecutive analysed frames, per frame, with same-class IoU ≥ 0.5 matching.
- **Class flip:** a box overlapping (IoU ≥ 0.5) a previous box of a different class.
- **Jitter:** 1 − IoU of matched boxes.
- **Stale-box rate:** displayed frames whose boxes come from another frame.

## 5. Files inspected

`src/detection/{camera_processor,video_processor}.py`, the capture metadata, labels and frame logs.

## 6. Files modified / created

**No existing file was modified.** Created:
- `scripts/engineering/realtime_eval.py`;
- `experiments/engineering_phase/final_validation/{realtime_video,realtime_webcam_replay,realtime_motion,realtime_low_light,realtime_camera}.json`, `latency_explanation_probe.json`, `video_runs/` (annotated outputs, frame logs, evidence) and logs.

## 7. Engineering decisions and alternatives

- **Physical camera through OpenCV, not the browser.** Measures real camera capture, inference and render rates without a browser. The browser/WebRTC path needs a person and remains a separate manual test.
- **Webcam replay at captured timestamps.** The same frames go through both models under identical timing.
- **Low light:** synthetic only. This is explicitly stated, not presented as field data.

## 8. Implementation details

`realtime_eval.py offline` runs the video, webcam-replay, motion and low-light categories for each model. `realtime_eval.py camera` runs the physical camera.

## 9. Testing methodology

Real model outputs. Manual labels where accuracy is claimed. Integrity checks computed from the frame log and the output container.

## 10. Actual measured results

### 10.1 Physical camera (`realtime_camera.json`)

| | YOLO26n | YOLO26m |
|---|---:|---:|
| Camera capture FPS | 29.93 | 30.07 |
| Frames received / dropped (superseded) / analysed / rendered | 359 / 0 / 359 / 359 | 361 / 1 / 360 / 360 |
| Analysed FPS / rendered FPS | 29.94 / 29.94 | 30.05 / 30.05 |
| Inference ms, mean / median / p95 / max | 18.69 / 18.06 / 24.16 / 33.47 | 26.89 / 26.64 / 28.43 / 51.66 |
| Received → rendered ms, median / p95 / max | 18.59 / 24.68 / 34.02 | 26.84 / 28.73 / 52.17 |
| Errors | 0 | 0 |
| System free memory before → after | 68 → 69 % | 68 → 62 % |

### 10.2 Webcam replay (`realtime_webcam_replay.json`; 149 frames, timing 29.8 fps)

| Stream / model | Dropped | Analysed FPS | Inference ms (mean / p95) | Rx → render p95 | Appear / disappear per frame | Class flips per frame | Mean abs Δconf | Box jitter |
|---|---:|---:|---|---:|---|---:|---:|---:|
| raw / n | 0 | 29.77 | 23.78 / 30.31 | 30.8 | 0.115 / 0.108 | 0.000 | 0.019 | 0.012 |
| raw / m | 0 | 29.77 | 27.79 / 35.87 | 36.1 | 0.182 / 0.182 | 0.007 | 0.018 | 0.029 |
| VP8 1 Mbps / n | 0 | 29.80 | 24.76 / 30.22 | 30.8 | 0.101 / 0.095 | 0.000 | 0.018 | 0.013 |
| VP8 1 Mbps / m | 0 | 29.76 | 27.88 / 35.32 | 35.7 | 0.209 / 0.209 | 0.000 | 0.019 | 0.038 |

**Displayed accuracy on the 10 labelled frames** (30 GT: Person, no_helmet, no_vest; conf 0.25):

| Stream / model | TP / FP / FN | P / R | FP types |
|---|---|---|---|
| raw / n | 10 / 15 / 20 | 0.40 / 0.33 | localization 15 |
| raw / m | 10 / 16 / 20 | 0.38 / 0.33 | background 9, localization 7 |
| VP8 / n | 11 / 15 / 19 | 0.42 / 0.37 | localization 15 |
| VP8 / m | 10 / 16 / 20 | 0.38 / 0.33 | background 9, localization 7 |

- **Stale-box occurrence: 0 / 149** for every run. **Incorrect frame association: 0.** Every displayed frame carried detections of its own source frame (R1 invariant, enforced by `render()` and tested).
- On this indoor scene, YOLO26m is *less stable* than YOLO26n: more appearing/disappearing boxes and more jitter. It also introduces **background** false positives (9) where YOLO26n's errors were mislocalisations only.
- Neither model is usable on this close-range scene at 640 (REPORT-009 §5.6: object scale is outside the training range). **One scene; not generalisable.**

### 10.3 Offline video (`realtime_video.json`; 270 frames, 15 fps, 1280×720; every frame analysed)

| Check / value | YOLO26n | YOLO26m |
|---|---|---|
| Frames in / out | 270 / 270 | 270 / 270 |
| FPS in / out; size in / out | 15 / 15; 1280×720 / 1280×720 | same |
| Source frame order strictly increasing (frame log) | PASS | PASS |
| Boxes only from their source frame (`boxes_from_frame == frame_index`) | PASS | PASS |
| Event times map to a unique source frame (stored at 0.01 s resolution; max offset 0.05 frame, tolerance 0.075) | PASS | PASS |
| Event wall-clock timestamps monotonic; evidence images exist | PASS (16/16) | PASS (19/19) |
| Processing time / offline analysed FPS | 2.7 s / 100.1 fps | 6.9 s / 39.1 fps |
| Inference ms, mean / p95 | 8.50 / 11.61 | 24.46 / 25.38 |
| Events | 16 | 19 |

The first integrity run reported `event_times_on_frame_grid = False`. The cause was an over-strict check (exact frame-grid equality) against media times that `event_manager.py` rounds to 0.01 s. The corrected check is recorded in the same JSON.

### 10.4 Motion (`realtime_motion.json`; displayed boxes under the R1 policy, imgsz 640)

| Speed (px/frame) | YOLO26n P / R | YOLO26m P / R |
|---:|---|---|
| 0 | 0.795 / 0.532 | 0.830 / 0.668 |
| 10 | 0.813 / 0.564 | 0.835 / 0.698 |
| 20 | 0.804 / 0.597 | 0.836 / 0.720 |

Displayed precision is flat across speeds for both models, because R1 removed the stale-box penalty. YOLO26m has higher recall at every speed (+0.12 to +0.14).

### 10.5 Synthetic low light and blur (`realtime_low_light.json`; 200 val images at 720p)

| Condition | YOLO26n mAP50-95 / R | YOLO26m mAP50-95 / R |
|---|---|---|
| Clean 720p | 0.517 / 0.746 | 0.614 / 0.827 |
| Dim (×0.5, noise 4) | 0.505 / 0.728 | 0.597 / 0.819 |
| Dark (×0.25, noise 8) | 0.422 / 0.632 | 0.460 / 0.663 |
| Blur 17 px | 0.374 / 0.578 | 0.457 / 0.657 |

YOLO26m keeps its lead under degradation. The relative drop from clean to dark is similar or larger for m (−25 % against −18 %).

### 10.6 Memory

- Physical camera: free memory 68 → 62 % with YOLO26m, against 68 → 69 % with YOLO26n.
- Inference-time MPS driver memory: about 1.2 GB (m) vs about 0.1 GB (n) (REPORT-015).
- Training: covered in REPORT-014.

### 10.7 Power state affects real-time latency (`latency_explanation_probe.json`)

On battery, the same model on the same frames gave a median of **7.6 ms in a tight loop but 25.5 ms when paced at 30 fps**. Content made no difference (webcam 7.63 / 25.53 ms; clip 7.68 / 25.83 ms). macOS lowers GPU and CPU clocks during the idle gaps between paced frames.

The earlier R1 paced test (REPORT-012 §10.3, 21:07) measured about 8 ms per frame, most likely on mains power (not recorded at the time). The physical-camera and replay numbers above are therefore **battery numbers**. Both models were measured under the same conditions, back to back.

## 11. Before/after comparison

- **Pipeline before/after R1:** REPORT-012. Here, the stale-box rate is 0 for both models, and every frame is analysed at the camera rate.
- **Model before/after (n → m):** §1. More recall and robustness under motion and degradation; less stable on the indoor scene; a thinner real-time margin.

## 12. Limitations and uncertainty

- The browser/WebRTC end-to-end display rate and latency were **not measured** (needs a person at the browser).
- The webcam material is one indoor scene with one person: not a construction site.
- The video clip is a slideshow of val images, not real footage.
- Low light is synthetic.
- The physical-camera test ran without a browser. On battery, latency depends on the power state.

## 13. Known unresolved issues

**Manual browser test (please do this on mains power):**
1. Open http://localhost:8502 → Live Monitoring → START.
2. Note the caption: model, 640 px, analysed FPS, inference median/p95, received → rendered p95, dropped.
3. Walk across the frame and check that the boxes stay on you.
4. STOP, then START, and confirm a new session with nothing left over.

The dashboard currently runs YOLO26n (production).

## 14. Exact reproduction

```bash
.venv/bin/python scripts/engineering/realtime_eval.py offline
.venv/bin/python scripts/engineering/realtime_eval.py camera --seconds 12     # turns the camera on; saves no frames
pmset -g batt                                                                # record the power source
```

## 15. Conclusion

- **The application pipeline is real-time capable on the M5 with either model:** 30 fps analysed, at most 1 dropped frame, 0 stale boxes, every integrity check passing.
- **YOLO26m** gives clearly better detection under motion and degradation. It uses about 27 ms of the 33 ms frame budget on battery, with more GPU memory, and on the single indoor webcam scene it was slightly less stable.
- **Neither model** solves close-range indoor webcam scenes.

## 16. Recommended next step

Final decision and report (REPORT-017). Run the manual browser test in §13 when convenient.
