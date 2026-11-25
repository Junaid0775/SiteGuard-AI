# Camera Start-Failure Diagnostic Report

**Report ID:** CAMERA-START-FAILURE-DIAGNOSTIC-001
**Completed:** 24 November 2026 (IST)
**Status:** Diagnostic complete. No fix has been applied. Awaiting approval.
**Scope:** Why some live-video starts failed during the Fix 1 reliability test. Production code, thresholds, compliance logic, evidence, models and the dataset were not changed.

## 1. Summary

**Cause.** The failed starts come from a timing race in `streamlit-webrtc` 0.79.1. Pressing START causes several Streamlit script reruns in quick succession. The library detects a page change by comparing Streamlit's count of finished runs between two renders of the video component. During this burst the count can jump by two even though the user stayed on the page. The library treats that jump as a page change and stops its own live connection, about 0.44 seconds after START.

**What a user sees.** The video stays blank. About 5.5 seconds later the button returns to START. No error message appears.

**How often.** On the diagnostic test page, 23 of 190 ordinary starts failed (12.1 %). The real dashboard had 0 failures in 27 valid starts. That result does not prove the dashboard is immune: the true rate could still be as high as 12.8 % (95 % upper limit).

**Why this cause is established.**

- All 3 failures with library lifecycle logging recorded the reset and the worker stop. None of the 72 connected starts recorded it (Fisher exact p = 1.5e-05).
- With the reset blocked in a test copy, 4 starts that would have been reset all stayed connected and delivered video. All 3 starts where the reset ran failed (p = 0.029).
- Failed starts have no decoder or processing thread on the server. All 42 connected starts checked have one of each.

**What is ruled out.** Automation click timing, Streamlit page initialisation, WebRTC connection setup, return-video bitrate, import order and the launcher (Section 7).

**What is not verified.**

- The physical camera and real human clicks were not tested.
- Only 3 of the 23 failures have the reset in their log. The other 20 have the same pattern, but they ran before this logging existed.
- Pressing START again after a failed start was not tested.

**Decision needed.** Section 9 asks whether to add a small guard to the Live Monitoring page.

| Requested item | Section |
|---|---|
| 1. Complete results of all 40 starts | 3 |
| 2. Exact failure stage of each failed start | 4 |
| 3. Failed conditions repeated with a deliberate delay | 5 |
| 4. Immediate-click and delayed-click comparison | 5 |
| 5. Connection time, first-frame time and control resets | 6 |
| 6. Origin of the failures | 7 |
| 7. No production code changes | 10 |

## 2. Test method

- Every start used a new Streamlit server and a new headless Chrome session.
- The camera was Chrome's fake device playing a synthetic moving video. The physical camera was never used, and no camera frame was saved.
- On the test page, a start counts as connected when the server received at least one frame. On the real dashboard, it counts as connected when the browser displayed real video.
- The test page calls `webrtc_streamer` with the same arguments as the dashboard. The dashboard runs used a temporary events database and a temporary evidence folder.
- The macOS power log shows no sleep or wake event after 22:21 on 23 November, before the first start.
- All times are milliseconds after the START click unless stated otherwise.

## 3. Results of the original 40 starts

Each cell shows the frames the server received in the 7-second run. **FAIL** means none. Settings were interleaved so that time-related effects reached all of them.

| Return bitrate | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | Connected |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Library default | 189 | 190 | 189 | **FAIL** | 188 | 189 | 189 | 188 | 187 | **FAIL** | 8/10 |
| 2.5 Mbit/s | 187 | **FAIL** | 189 | 187 | 189 | 185 | 190 | 191 | 188 | 189 | 9/10 |
| 4 Mbit/s | 188 | 188 | 188 | 188 | 189 | **FAIL** | 189 | 189 | 188 | 188 | 9/10 |
| 6 Mbit/s | 188 | 187 | 189 | 189 | 185 | 186 | 188 | **FAIL** | 187 | 188 | 9/10 |

**Result: 35 of 40 connected.** The 5 failures are spread across all four bitrates and five different rounds.

## 4. Failure stage

**Failure stage: after the WebRTC connection is established, before the first frame reaches the processing callback.** Sections 4.1 to 4.3 show how directly each failure supports this.

### 4.1 The five failures in the original 40

These starts ran before stage logging existed, so their stage is inferred from the pattern they share with the later logged failures.

| Failed start | START clicked | Server frames | Real video | Server CPU, 2–4 s | 2×2 placeholder at | Video removed by | Server errors |
|---|---|---|---|---|---|---|---|
| 2.5 Mbit/s, round 2 | Yes | 0 | None | 0.5 % | 5 s | 6 s | 0 |
| Library default, round 4 | Yes | 0 | None | 0.4 % | 5 s | 6 s | 0 |
| 4 Mbit/s, round 6 | Yes | 0 | None | 0.6 % | 5 s | 6 s | 0 |
| 6 Mbit/s, round 8 | Yes | 0 | None | 0.6 % | 5 s | 6 s | 0 |
| Library default, round 10 | Yes | 0 | None | 0.4 % | 5 s | 6 s | 0 |

In all five, START was clicked and a video element appeared with no picture. The server received and encoded no frames and logged no exception. Its CPU use stayed near 0.5 %, against a median of 36.8 % in connected starts. A 2×2 placeholder appeared at the 5-second sample, and the video element had gone by the 6-second sample.

### 4.2 Exact browser stages

Three failures were captured with a browser connection log.

| Stage (ms after START) | Library default, round 1 | 2.5 Mbit/s, round 4 | Library default, round 11 |
|---|---|---|---|
| Peer connection created | 85 | 82 | 89 |
| Camera stream acquired | 151 | 146 | 155 |
| Offer set | 156 | 150 | 160 |
| ICE gathering complete | 281 | 279 | 287 |
| Answer applied, remote track received | 418 | 376 | 418 |
| ICE connected | 425 | 383 | 427 |
| Peer (DTLS) connected | 440 | 397 | 440 |
| Video element created | 467 | 386 | 468 |
| **ICE disconnected** | 5,500 | 5,450 | 5,490 |
| First-frame event (2×2 placeholder) | 5,507 | 5,468 | 5,496 |
| **Button returned to START** | 5,565 | 5,485 | 5,567 |
| Browser closed the connection | 6,002 | 5,952 | 5,993 |

ICE and DTLS both connected. ICE then reported `disconnected` 5,050–5,060 ms after the connection was established. The browser recorded no `failed` state and no error.

### 4.3 Exact server stages

Three failures were captured with the library's own lifecycle messages.

| Failed start | Worker created | Answer rerun | Reset logged | Worker stopping | Server ICE closed | Decoder / processing threads |
|---|---|---|---|---|---|---|
| Root cause 1, round 11 | 186 | 192 | **430** | 430 | 431 | 0 / 0 |
| Root cause 2, round 10 | 157 | 200 | **441** | 441 | 442 | 0 / 0 |
| Root cause 2, round 11 | 157 | 200 | **436** | 436 | 436 | 0 / 0 |

Each failed start logged this sequence:

```text
Context for key=siteguard-live was not rendered for 1 script runs; resetting stale state.
Stopping worker during context reset.
ICE state=closed -> stopping WebRTC worker
```

A separate smoke run, not counted above, logged the same sequence at 455 ms. Two more failures from the stack-capture test had no decoder or processing thread in either of their two thread dumps. The server event loop was idle in those dumps, so a blocked or overloaded server is ruled out for those starts.

## 5. Immediate click and delayed click

The delayed click waited until the Streamlit script had been idle for 1 second, then waited 3 more seconds. Arms A and B repeated the library-default and 2.5 Mbit/s conditions. The logged batch repeated all four bitrates with 6 immediate and 6 delayed starts each. Its server logging suppressed the failure (Section 8), so arms A and B are the fair comparison.

| Comparison | Immediate click: failed | Delayed click: failed | Fisher exact p |
|---|---|---|---|
| Same batch (arms A and B) | 5 of 20 | 1 of 20 | 0.18 |
| All plain-probe starts | 10 of 75 | 1 of 20 | 0.45 |
| With browser and server logging | 0 of 24 | 0 of 24 | not applicable |

**Result.** A delayed click still failed once, with the same pattern, so click timing alone does not explain the failure. Fewer delayed starts failed, but the difference is not statistically significant. These samples cannot show whether a delay reduces the rate.

## 6. Connection time, first-frame time and control resets

Timings come from the 48 starts with browser and server logging. All 48 connected.

| Stage | Immediate click, median (range), ms | Delayed click, median (range), ms |
|---|---|---|
| Browser peer connection created | 68 (61–86) | 83 (58–84) |
| Camera acquired | 134 (125–152) | 148 (128–149) |
| Offer created | 138 (130–157) | 153 (133–154) |
| Offer reached server | 185 (174–204) | 199 (162–202) |
| Answer created on server | 188 (177–206) | 202 (164–205) |
| Answer applied in browser | 405 (391–423) | 418 (398–449) |
| ICE connected | 410 (397–426) | 424 (402–452) |
| **Connection established (peer connected)** | 422 (412–441) | 438 (414–465) |
| **First frame displayed** | 590 (566–611) | 599 (574–626) |
| First frame finished by the server pipeline | 1296 (1261–1343) | 1235 (1217–1271) |

The browser shows video before the first server-processed frame. Until the first model result is ready, the library returns the camera frame without overlays, so the first displayed frame can be unannotated.

**Video-control resets:**

| Group | Starts | Button returned to START before STOP was clicked |
|---|---|---|
| Browser and server logging, connected | 48 | 0 |
| Browser log, connected | 12 | 0 (earliest return 7,566 ms, after the 7 s STOP click) |
| Browser log, failed | 3 | 3, at 5,485–5,567 ms |

## 7. Origin of the failures

| Candidate | Verdict | Evidence |
|---|---|---|
| Automation timing | **Not the cause** | A deliberately delayed click also failed. Immediate and delayed results do not differ significantly (p = 0.18 and 0.45). |
| Streamlit page initialisation | **Not the cause** | The failed delayed start was clicked after the script had been idle for 1 second and a further 3-second wait. The race happens during the reruns after START. |
| WebRTC connection setup | **Not the cause** | ICE and DTLS connected in every failure with a browser log. |
| Return-video bitrate | **Not the cause** | Failed: library default 10 of 62, 2.5 Mbit/s 6 of 58, 4 Mbit/s 1 of 10, 6 Mbit/s 1 of 10. Library against 2.5 Mbit/s: p = 0.43. |
| Import order, launcher | **Not the cause** | Each variant still failed 2 of 15 starts. |
| **`streamlit-webrtc` rerun handling** | **Cause** | The reset was logged in all 3 logged failures and in none of 72 connected starts. Blocking it kept all 4 affected starts connected. |

### Mechanism

1. Pressing START makes the browser send several quick updates to Streamlit. Each update requests a script rerun.
2. On each render, the library stores Streamlit's count of finished script runs. A later render that finds the count more than one higher is treated as a return from another page (`streamlit_webrtc/component.py`, around line 331).
3. Streamlit increments that count when it sends a run's "finished" message to the browser (`streamlit/runtime/runtime.py`, around line 892), not when the next run starts. During the burst of reruns the count can therefore jump by two between two renders, although the user never left the page. Every logged reset reported exactly this jump ("not rendered for 1 script runs").
4. The library calls `_reset_context`, which stops the live worker and closes the server's connection.
5. The browser receives no media. It reports ICE `disconnected` after about 5 seconds and returns the button to START.

The logs and library source confirm steps 2, 4 and 5 and the size of the jump in step 3. The exact order of runs that produces the jump was not captured.

### Decisive test

The test ran the same page with and without the reset, interleaved with the real dashboard.

| Group | Valid starts | Connected | Failed | Reset condition occurred | Outcome of those starts |
|---|---|---|---|---|---|
| Unchanged test page | 26 | 23 | 3 | 3 (reset ran) | All 3 failed |
| Same page, reset blocked | 24 | 24 | 0 | 4 (reset blocked) | All 4 connected and delivered 68–69 frames in 3 s |
| Real dashboard | 27 | 27 | 0 | 0 | Not applicable |

The reset condition occurred at a similar rate with and without the block (3 of 26 and 4 of 24 starts). Only its outcome changed.

## 8. Limits and unexplained results

1. **Log confirmation covers 3 failures.** The other 20 failures have the same pattern and two of them show no worker threads, so the same cause is likely. Their cause was not individually confirmed.
2. **The rescue evidence is small.** Four rescued starts against three failed ones gives p = 0.029. The logged stop sequence is the stronger evidence.
3. **The real dashboard has not shown the failure.** It had 0 failures in 27 valid starts, while the test page had 3 in 26. The dashboard creates its worker later (median 238–244 ms against 185–188 ms), which may reduce exposure. This was not tested.
4. **Physical camera and human timing were not tested.** A physical-camera test needs separate consent.
5. **Server logging wrappers suppressed the failure, for an unknown reason.** Wrapped servers failed 0 of 68 starts, against 18 of 140 without them (p = 0.00094). The wrappers may shift the rerun timing.
6. **The delay experiment was inconclusive.** A 150 ms delay before the component was meant to widen the race window. It also moved worker creation to a median of 436 ms and gave Streamlit more time to update its run count, so it may have narrowed the window instead. No failure occurred in that arm, its control arm, or the arm with `runner.fastReruns = false`. These arms do not show that turning fast reruns off fixes the failure.
7. **Code from before the camera fixes was not retested.** The failing path is in the library and does not use the Fix 1, 3, 4 or 6 code, but no pre-fix run was made.
8. **Retry was not tested.** The report cannot say that pressing START again always recovers.

## 9. Decision needed

**Option A (recommended): add a narrow start guard to the Live Monitoring page.** A jump in the run count while the user stays on Live Monitoring would no longer count as a page change. Real page changes would still reset the component. The change is small and leaves detection, compliance, thresholds and event handling untouched. It depends on one private attribute of the pinned `streamlit-webrtc==0.79.1`, so it must be rechecked on any library upgrade.

Before merging, Option A would have to pass repeated starts on the real dashboard, leaving and returning to the page, repeated START and STOP, the full test suite and a rollback check.

**Option B: make no code change and document the issue.** If the video stays blank, the operator waits for the button to return to START and presses it again. This retry has not been tested.

Option A is recommended because the failure is silent and could occur during a live demonstration.

**Work still waiting after this decision:**

- Finalise Fix 1 and correct the inaccurate "4-8 Mbit/s unstable" comment in `src/ui/live_video.py`. That statement came from a benchmark invalidated by laptop sleep.
- Verify Fix 3 at 1440 px and 1024 px.
- Test Fix 2 against its merge gates, or leave it unmerged.
- Run the full test suite and write the final report.
- Restart the dashboard on port 8502 when requested. It started at 11:46 on 23 November, before the camera fixes were written, so it may not be running all of them.

## 10. Preservation checks and side effects

| Item | Check | Result |
|---|---|---|
| Production code and configuration | Modification times of `app.py`, `src/`, `tests/`, `scripts/`, `.streamlit/` and requirements | No file changed after the first start test (23 November 22:50:02). Newest: `app.py`, 23 November 14:46:30 |
| Evidence | SHA-256 of all 131 files against the saved list | All match |
| Events database | Modification time | Unchanged since 23 November 12:23:01 |
| YOLO26n checkpoint | SHA-256 | Matches `890dc61fd024b247…` |
| E3 checkpoint | SHA-256 | Matches `590d7d6e8510f3c1…`. Still experimental and not selectable |
| Original dataset | Files modified since the first start test | 0 |
| Physical camera | Test configuration | Not used. All starts used a synthetic video |

**Side effects of this investigation:**

- Diagnostic tools and logs were added under `experiments/camera_quality_audit/`. The application imports none of them.
- A thread dump on a running server crashed the temporary test server in 5 of 48 starts. Those 5 starts are marked void and excluded: `r_W_after_3`, `r_W_before_6`, `r_R_baseline_7`, `r_H_dashboard_9`, `r_R_baseline_12`. macOS saved 5 crash reports for those test servers. Later dumps ran only on stalled servers.
- A temporary 207 MB synthetic video remains in the system temporary folder for the remaining benchmarks. It will be removed when they finish.

## Appendix A. All start tests

| Batch | Condition | Starts | Void | Connected | Failed |
|---|---|---|---|---|---|
| Original 40 | Four bitrates, immediate click | 40 | 0 | 35 | 5 |
| Logged | Browser and server logging, immediate click | 24 | 0 | 24 | 0 |
| Logged | Browser and server logging, delayed click | 24 | 0 | 24 | 0 |
| Repeat 1 | A: plain test page, immediate click | 20 | 0 | 15 | 5 |
| Repeat 1 | B: plain test page, delayed click | 20 | 0 | 19 | 1 |
| Repeat 1 | C: server connection logging, immediate click | 20 | 0 | 20 | 0 |
| Repeat 2 | A2: plain test page, immediate click | 15 | 0 | 15 | 0 |
| Repeat 2 | D: PyAV and aiortc imported before OpenCV | 15 | 0 | 13 | 2 |
| Repeat 2 | E: browser connection log | 15 | 0 | 12 | 3 |
| Repeat 2 | Exec launcher | 15 | 0 | 13 | 2 |
| Stack capture | Thread dump when a start stalls | 24 | 0 | 22 | 2 |
| Root cause 1 | Library lifecycle log | 12 | 2 | 9 | 1 |
| Root cause 1 | 150 ms delay and yield before the component | 8 | 1 | 7 | 0 |
| Root cause 1 | Same delay and yield after the component | 8 | 1 | 7 | 0 |
| Root cause 1 | Delay before the component, fast reruns off | 8 | 0 | 8 | 0 |
| Root cause 1 | Real dashboard | 12 | 1 | 11 | 0 |
| Root cause 2 | Library lifecycle log | 16 | 0 | 14 | 2 |
| Root cause 2 | Reset blocked in the test copy | 24 | 0 | 24 | 0 |
| Root cause 2 | Real dashboard | 16 | 0 | 16 | 0 |
| **Total** |  | **336** | **5** | **308** | **23** |

Void starts are the 5 described in Section 10. Smoke runs are not counted.

## Appendix B. All 23 failed starts

"Same pattern" means START was clicked, the server received no frames, the video showed no real picture, and the video element was removed about 6 seconds after START.

| Start | Batch | Frames | Video removed by | Evidence |
|---|---|---|---|---|
| `start_2.5M_2` | Original 40 | 0 | 6 s | Same pattern |
| `start_library_4` | Original 40 | 0 | 6 s | Same pattern |
| `start_4M_6` | Original 40 | 0 | 6 s | Same pattern |
| `start_6M_8` | Original 40 | 0 | 6 s | Same pattern |
| `start_library_10` | Original 40 | 0 | 6 s | Same pattern |
| `m_A_plain_immediate_library_r1` | Repeat 1 | 0 | 6 s | Same pattern |
| `m_A_plain_immediate_2.5M_r4` | Repeat 1 | 0 | 6 s | Same pattern |
| `m_A_plain_immediate_library_r7` | Repeat 1 | 0 | 6 s | Same pattern |
| `m_B_plain_delayed_2.5M_r12` | Repeat 1 | 0 | 6 s | Same pattern |
| `m_A_plain_immediate_library_r13` | Repeat 1 | 0 | 6 s | Same pattern |
| `m_A_plain_immediate_2.5M_r20` | Repeat 1 | 0 | 6 s | Same pattern |
| `n_E_browser_log_library_r1` | Repeat 2 | 0 | 6 s | Browser stage log, same pattern |
| `n_D_av_first_library_r1` | Repeat 2 | 0 | 6 s | Same pattern |
| `n_D_av_first_library_r3` | Repeat 2 | 0 | 6 s | Same pattern |
| `n_E_browser_log_2.5M_r4` | Repeat 2 | 0 | 6 s | Browser stage log, same pattern |
| `n_G_exec_only_2.5M_r8` | Repeat 2 | 0 | 6 s | Same pattern |
| `n_E_browser_log_library_r11` | Repeat 2 | 0 | 6 s | Browser stage log, same pattern |
| `n_G_exec_only_library_r15` | Repeat 2 | 0 | 6 s | Same pattern |
| `s_2.5M_4` | Stack capture | 0 | 6 s | No worker threads in stack dump |
| `s_library_5` | Stack capture | 0 | 6 s | No worker threads in stack dump |
| `r_R_baseline_11` | Root cause 1 | 0 | 6 s | Reset logged, no worker threads |
| `t_R2_baseline_10` | Root cause 2 | 0 | Test ended at 3 s | Reset logged, no worker threads |
| `t_R2_baseline_11` | Root cause 2 | 0 | Test ended at 3 s | Reset logged, no worker threads |
