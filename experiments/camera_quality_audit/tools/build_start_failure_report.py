"""Builds CAMERA-START-FAILURE-DIAGNOSTIC-001.md from the saved start-test logs.

Reads logs, checkpoints and evidence files only, and writes only that report, so every number in it can be regenerated.
The assertions stop the build if the logs no longer match the figures quoted in the prose.
"""
import hashlib
import json
import math
import re
import statistics as S
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[1]
ROOT = AUDIT.parents[1]
LOGS = AUDIT / "logs"
OUT = AUDIT / "reports" / "CAMERA-START-FAILURE-DIAGNOSTIC-001.md"
YOLO26N_SHA = "890dc61fd024b247eda19753a1787a5b9ac16ff0236b2f72e06ae6814c995b9b"
E3_SHA = "590d7d6e8510f3c121ee74df38bf10028b67b212cd35c50da0916bce9f6b60e6"


def load(name: str):
    return json.loads((LOGS / name).read_text())


def fisher(a: int, b: int, c: int, d: int) -> float:
    n1, n2, k = a + b, c + d, a + c
    total = math.comb(n1 + n2, k)
    prob = lambda x: math.comb(n1, x) * math.comb(n2, k - x) / total
    observed = prob(a)
    return sum(p for x in range(max(0, k - n2), min(n1, k) + 1) if (p := prob(x)) <= observed * (1 + 1e-9))


def table(header: list, rows: list) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def failed(rows: list) -> int:
    return sum(not x["ok"] for x in rows)


def med_range(values: list) -> str:
    return f"{S.median(values):.0f} ({min(values)}–{max(values)})"


orig = load("start_reliability.json")
diag = load("start_diagnostics_analysis.json")
matrix = load("start_matrix.json") + load("start_matrix2.json")
stacks = load("start_stacks.json")
rc1 = load("start_rootcause.json")
rc2 = load("start_rootcause2.json")
summary = load("start_failure_summary.json")
for x in rc1:
    x["valid"] = x["clicked_stop"] is not None
rc = rc1 + rc2
valid = [x for x in rc if x["valid"]]
void_tags = [x["tag"] for x in rc if not x["valid"]]
arm = lambda rows, name: [x for x in rows if x["arm"] == name]
v_arm = lambda name: arm(valid, name)

ordinary = orig + [x for x in matrix if x["arm"] in ("A_plain_immediate", "B_plain_delayed", "A2_plain", "D_av_first", "E_browser_log", "G_exec_only")] \
    + stacks + v_arm("R_baseline") + v_arm("R2_baseline")
assert (len(ordinary), failed(ordinary)) == (190, 23)
reset_active = [x for x in valid if x["arm"] != "G_guard"]
reset_failed = [x for x in reset_active if not x["ok"]]
assert (len(reset_active), len(reset_failed)) == (75, 3)
assert all(x["orphan_reset_ms"] for x in reset_failed) and not any(x["orphan_reset_ms"] for x in reset_active if x["ok"])
guard = v_arm("G_guard")
rescued = [x for x in guard if any(e["worker_alive"] for e in x["guard_suppressed"])]
assert (len(guard), failed(guard), len(rescued)) == (24, 0, 4) and all(x["ok"] for x in rescued)
assert all(e["gap"] == 1 for x in rescued for e in x["guard_suppressed"]) and {x["frames"] for x in rescued} <= {68, 69}
assert all("not rendered for 1 script runs" in (LOGS / x["tag"] / "lifecycle.jsonl").read_text() for x in reset_failed)
probe_base = v_arm("R_baseline") + v_arm("R2_baseline")
dash = v_arm("H_dashboard") + v_arm("H2_dashboard")
assert (len(probe_base), failed(probe_base), len(dash), failed(dash)) == (26, 3, 27, 0)
dash_upper = 100 * (1 - 0.025 ** (1 / len(dash)))
p_assoc = fisher(3, 0, 0, 72)
p_rescue = fisher(3, 0, 0, 4)
tests = summary["fisher_two_sided_p"]
pools = summary["pools"]
cpu = summary["server_cpu_pct_2_to_4s_after_start"]
bitrate = summary["unwrapped_by_bitrate"]

# Section 3: the 40 starts.
labels = {"library": "Library default", "2.5M": "2.5 Mbit/s", "4M": "4 Mbit/s", "6M": "6 Mbit/s"}
grid = []
for s, label in labels.items():
    by_round = {x["round"]: x for x in orig if x["setting"] == s}
    grid.append([label, *(by_round[r]["frames"] if by_round[r]["ok"] else "**FAIL**" for r in range(1, 11)),
                 f"{sum(x['ok'] for x in by_round.values())}/10"])
grid_table = table(["Return bitrate", *(f"R{r}" for r in range(1, 11)), "Connected"], grid)

# Section 4.1: the five failures of the 40.
rows = []
for f in [x for x in summary["failures"] if x["arm"] == "original_40"]:
    e = f["evidence"]
    log = (LOGS / f["tag"] / "probe_server.log").read_text(errors="ignore")
    assert (LOGS / f["tag"] / "server.jsonl").stat().st_size == 0
    rows.append([f"{labels[f['setting']]}, round {f['round']}", "Yes", "0", "None", f"{e['server_cpu_2_to_4s']} %", f"{e['placeholder_2x2_s']:.0f} s",
                 f"{e['video_removed_s']:.0f} s", len(re.findall(r"Traceback|Exception|Error", log))])
five_table = table(["Failed start", "START clicked", "Server frames", "Real video", "Server CPU, 2–4 s", "2×2 placeholder at", "Video removed by", "Server errors"], rows)

# Section 4.2: exact browser stages.
e_fail = [x for x in matrix if x["arm"] == "E_browser_log" and not x["ok"]]
stage_rows = []
for label, key in (("Peer connection created", "pc_created"), ("Camera stream acquired", "camera"), ("Offer set", "offer_set"), ("ICE gathering complete", "gathering_complete"),
                   ("Answer applied, remote track received", "answer_applied"), ("ICE connected", "ice_connected"), ("Peer (DTLS) connected", "peer_connected"),
                   ("Video element created", "video_element"), ("**ICE disconnected**", "ice_disconnected"), ("First-frame event (2×2 placeholder)", "first_frame")):
    stage_rows.append([label, *(f"{x['browser_stages_ms'][key]:,}" for x in e_fail)])
stage_rows.append(["**Button returned to START**", *(f"{[t for t, c in x['control_changes_ms'] if c == 'START'][0]:,}" for x in e_fail)])
stage_rows.append(["Browser closed the connection", *(f"{x['browser_stages_ms']['pc_close']:,}" for x in e_fail)])
stage_table = table(["Stage (ms after START)", *(f"{labels[x['setting']]}, round {x['round']}" for x in e_fail)], stage_rows)
gaps = [x["browser_stages_ms"]["ice_disconnected"] - x["browser_stages_ms"]["peer_connected"] for x in e_fail]

# Section 4.3: server lifecycle.
rows = [[f"{'Root cause 1' if x['arm'] == 'R_baseline' else 'Root cause 2'}, round {x['round']}", x["worker_created_ms"][0], x["answer_rerun_ms"][0], f"**{x['orphan_reset_ms'][0]}**", x["worker_stopping_ms"][0],
         x["ice_stop_ms"][0], f"{x['decoder_threads_at_3s']} / {x['process_threads_at_3s']}"] for x in reset_failed]
life_table = table(["Failed start", "Worker created", "Answer rerun", "Reset logged", "Worker stopping", "Server ICE closed", "Decoder / processing threads"], rows)
healthy = [x for x in rc1 if x["valid"] and x["ok"]]
assert {x["decoder_threads_at_3s"] for x in healthy} == {1} and {x["process_threads_at_3s"] for x in healthy} == {1}
for tag in ("s_2.5M_4", "s_library_5"):
    text = (LOGS / tag / "stacks.txt").read_text()
    assert "decoder_worker" not in text and "_run_worker_thread" not in text

# Section 5: click timing.
a_arm, b_arm = arm(matrix, "A_plain_immediate"), arm(matrix, "B_plain_delayed")
click_table = table(["Comparison", "Immediate click: failed", "Delayed click: failed", "Fisher exact p"], [
    ["Same batch (arms A and B)", f"{failed(a_arm)} of {len(a_arm)}", f"{failed(b_arm)} of {len(b_arm)}", f"{tests['A_immediate_vs_B_delayed']:.2f}"],
    ["All plain-probe starts", f"{pools['plain_immediate']['failed']} of {pools['plain_immediate']['starts']}", f"{pools['plain_delayed']['failed']} of {pools['plain_delayed']['starts']}",
     f"{tests['plain_immediate_vs_plain_delayed']:.2f}"],
    ["With browser and server logging", f"0 of {sum(x['condition'] == 'immediate' for x in diag)}", f"0 of {sum(x['condition'] == 'delayed' for x in diag)}", "not applicable"]])

# Section 6: connection times.
rows = []
for label, key in (("Browser peer connection created", "browser_pc_created"), ("Camera acquired", "camera_acquired"), ("Offer created", "offer_created"),
                   ("Offer reached server", "offer_reached_server"), ("Answer created on server", "answer_created_on_server"), ("Answer applied in browser", "answer_applied_in_browser"),
                   ("ICE connected", "ice_connected"), ("**Connection established (peer connected)**", "peer_connected"), ("**First frame displayed**", "first_displayed_frame"),
                   ("First frame finished by the server pipeline", "first_server_frame")):
    rows.append([label, *(med_range([x["times_ms"][key] for x in diag if x["condition"] == c]) for c in ("immediate", "delayed"))])
time_table = table(["Stage", "Immediate click, median (range), ms", "Delayed click, median (range), ms"], rows)
e_ok = [x for x in matrix if x["arm"] == "E_browser_log" and x["ok"]]
earliest_after_stop = min(t for x in e_ok for t, c in x["control_changes_ms"] if c == "START")
reset_times = [[t for t, c in x["control_changes_ms"] if c == "START"][0] for x in e_fail]
assert not any(x["control_resets_ms"] for x in diag)
control_table = table(["Group", "Starts", "Button returned to START before STOP was clicked"], [
    ["Browser and server logging, connected", len(diag), "0"],
    ["Browser log, connected", len(e_ok), f"0 (earliest return {earliest_after_stop:,} ms, after the 7 s STOP click)"],
    ["Browser log, failed", len(e_fail), f"{len(e_fail)}, at {min(reset_times):,}–{max(reset_times):,} ms"]])

# Section 7: decisive test.
decisive = table(["Group", "Valid starts", "Connected", "Failed", "Reset condition occurred", "Outcome of those starts"], [
    ["Unchanged test page", len(probe_base), len(probe_base) - failed(probe_base), failed(probe_base), "3 (reset ran)", "All 3 failed"],
    ["Same page, reset blocked", len(guard), len(guard), 0, "4 (reset blocked)", "All 4 connected and delivered 68–69 frames in 3 s"],
    ["Real dashboard", len(dash), len(dash), 0, "0", "Not applicable"]])
worker_ms = {n: S.median([x["worker_created_ms"][0] for x in v_arm(n)]) for n in ("R_baseline", "R2_baseline", "H_dashboard", "H2_dashboard", "W_before", "N_before_no_fast_reruns")}

# Appendix A: every batch.
batches = [("Original 40", "Four bitrates, immediate click", orig),
           ("Logged", "Browser and server logging, immediate click", [x for x in diag if x["condition"] == "immediate"]),
           ("Logged", "Browser and server logging, delayed click", [x for x in diag if x["condition"] == "delayed"]),
           ("Repeat 1", "A: plain test page, immediate click", a_arm), ("Repeat 1", "B: plain test page, delayed click", b_arm),
           ("Repeat 1", "C: server connection logging, immediate click", arm(matrix, "C_serverlog_immediate")),
           ("Repeat 2", "A2: plain test page, immediate click", arm(matrix, "A2_plain")), ("Repeat 2", "D: PyAV and aiortc imported before OpenCV", arm(matrix, "D_av_first")),
           ("Repeat 2", "E: browser connection log", arm(matrix, "E_browser_log")), ("Repeat 2", "Exec launcher", arm(matrix, "G_exec_only")),
           ("Stack capture", "Thread dump when a start stalls", stacks),
           ("Root cause 1", "Library lifecycle log", arm(rc1, "R_baseline")), ("Root cause 1", "150 ms delay and yield before the component", arm(rc1, "W_before")),
           ("Root cause 1", "Same delay and yield after the component", arm(rc1, "W_after")), ("Root cause 1", "Delay before the component, fast reruns off", arm(rc1, "N_before_no_fast_reruns")),
           ("Root cause 1", "Real dashboard", arm(rc1, "H_dashboard")),
           ("Root cause 2", "Library lifecycle log", arm(rc2, "R2_baseline")), ("Root cause 2", "Reset blocked in the test copy", arm(rc2, "G_guard")),
           ("Root cause 2", "Real dashboard", arm(rc2, "H2_dashboard"))]
rows, totals = [], [0, 0, 0, 0]
for batch, what, xs in batches:
    good = [x for x in xs if x.get("valid", True)]
    row = [len(xs), len(xs) - len(good), len(good) - failed(good), failed(good)]
    totals = [t + r for t, r in zip(totals, row)]
    rows.append([batch, what, *row])
rows.append(["**Total**", "", *(f"**{t}**" for t in totals)])
assert totals == [336, 5, 308, 23]
batch_table = table(["Batch", "Condition", "Starts", "Void", "Connected", "Failed"], rows)

# Appendix B: every failed start.
batch_of = {"start": "Original 40", "m": "Repeat 1", "n": "Repeat 2", "s": "Stack capture", "r": "Root cause 1", "t": "Root cause 2"}
reset_tags = {x["tag"] for x in reset_failed}
rows = []
for x in ordinary:
    if x["ok"]:
        continue
    tag = x.get("tag") or f"start_{x['setting']}_{x['round']}"
    b = json.loads((LOGS / tag / "browser.json").read_text())
    removed = next((s["t"] for s in b["samples"] if not s["videos"]), None) if not b.get("clicked_stop") else None
    evidence = "Reset logged, no worker threads" if tag in reset_tags else "No worker threads in stack dump" if tag.startswith("s_") \
        else "Browser stage log, same pattern" if tag.startswith("n_E_") else "Same pattern"
    rows.append([f"`{tag}`", batch_of[tag.split("_")[0]], "0", f"{removed:.0f} s" if removed else "Test ended at 3 s", evidence])
assert len(rows) == 23
failure_table = table(["Start", "Batch", "Frames", "Video removed by", "Evidence"], rows)

# Section 10: preservation.
files = [p for base in ("src", "tests", "scripts", ".streamlit") for p in (ROOT / base).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
files += [ROOT / "app.py", *ROOT.glob("requirements*.txt")]
first_test = (LOGS / "start_2.5M_1").stat().st_mtime
assert not [p for p in files if p.stat().st_mtime > first_test]
newest = max(files, key=lambda p: p.stat().st_mtime)
from datetime import datetime
newest_text = datetime.fromtimestamp(newest.stat().st_mtime).strftime("%d %B %H:%M:%S")
first_text = datetime.fromtimestamp(first_test).strftime("%d %B %H:%M:%S")
manifest = [l.split(None, 1) for l in (AUDIT / "fixes/phase1/other_evidence_after.sha256").read_text().splitlines() if l.strip()]
assert len(manifest) == 131 and all(sha256(ROOT / p.strip()) == h for h, p in manifest)
assert sum(1 for p in (ROOT / "outputs/evidence").iterdir() if p.is_file()) == 131
assert sha256(ROOT / "models/trained/best.pt") == YOLO26N_SHA
assert sha256(ROOT / "models/trained/yolo26m_accuracy_candidate/yolo26m_e3_896_v1/best.pt") == E3_SHA
db = ROOT / "outputs/siteguard_events.db"
assert db.stat().st_mtime < first_test
db_text = datetime.fromtimestamp(db.stat().st_mtime).strftime("%d %B %H:%M:%S")
dataset_changed = sum(1 for p in (ROOT.parent / "construction-ppe").rglob("*") if p.is_file() and p.stat().st_mtime > first_test)
assert dataset_changed == 0

report = f"""# Camera Start-Failure Diagnostic Report

**Report ID:** CAMERA-START-FAILURE-DIAGNOSTIC-001
**Completed:** 24 November 2026 (IST)
**Status:** Diagnostic complete. No fix has been applied. Awaiting approval.
**Scope:** Why some live-video starts failed during the Fix 1 reliability test. Production code, thresholds, compliance logic, evidence, models and the dataset were not changed.

## 1. Summary

**Cause.** The failed starts come from a timing race in `streamlit-webrtc` 0.79.1. Pressing START causes several Streamlit script reruns in quick succession. The library detects a page change by comparing Streamlit's count of finished runs between two renders of the video component. During this burst the count can jump by two even though the user stayed on the page. The library treats that jump as a page change and stops its own live connection, about 0.44 seconds after START.

**What a user sees.** The video stays blank. About 5.5 seconds later the button returns to START. No error message appears.

**How often.** On the diagnostic test page, {failed(ordinary)} of {len(ordinary)} ordinary starts failed ({100 * failed(ordinary) / len(ordinary):.1f} %). The real dashboard had 0 failures in {len(dash)} valid starts. That result does not prove the dashboard is immune: the true rate could still be as high as {dash_upper:.1f} % (95 % upper limit).

**Why this cause is established.**

- All 3 failures with library lifecycle logging recorded the reset and the worker stop. None of the 72 connected starts recorded it (Fisher exact p = {p_assoc:.1e}).
- With the reset blocked in a test copy, 4 starts that would have been reset all stayed connected and delivered video. All 3 starts where the reset ran failed (p = {p_rescue:.3f}).
- Failed starts have no decoder or processing thread on the server. All 42 connected starts checked have one of each.

**What is ruled out.** Automation click timing, Streamlit page initialisation, WebRTC connection setup, return-video bitrate, import order and the launcher (Section 7).

**What is not verified.**

- The physical camera and real human clicks were not tested.
- Only 3 of the {failed(ordinary)} failures have the reset in their log. The other {failed(ordinary) - 3} have the same pattern, but they ran before this logging existed.
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

{grid_table}

**Result: 35 of 40 connected.** The 5 failures are spread across all four bitrates and five different rounds.

## 4. Failure stage

**Failure stage: after the WebRTC connection is established, before the first frame reaches the processing callback.** Sections 4.1 to 4.3 show how directly each failure supports this.

### 4.1 The five failures in the original 40

These starts ran before stage logging existed, so their stage is inferred from the pattern they share with the later logged failures.

{five_table}

In all five, START was clicked and a video element appeared with no picture. The server received and encoded no frames and logged no exception. Its CPU use stayed near {cpu['failed']['median']} %, against a median of {cpu['connected']['median']} % in connected starts. A 2×2 placeholder appeared at the 5-second sample, and the video element had gone by the 6-second sample.

### 4.2 Exact browser stages

Three failures were captured with a browser connection log.

{stage_table}

ICE and DTLS both connected. ICE then reported `disconnected` {min(gaps):,}–{max(gaps):,} ms after the connection was established. The browser recorded no `failed` state and no error.

### 4.3 Exact server stages

Three failures were captured with the library's own lifecycle messages.

{life_table}

Each failed start logged this sequence:

```text
Context for key=siteguard-live was not rendered for 1 script runs; resetting stale state.
Stopping worker during context reset.
ICE state=closed -> stopping WebRTC worker
```

A separate smoke run, not counted above, logged the same sequence at 455 ms. Two more failures from the stack-capture test had no decoder or processing thread in either of their two thread dumps. The server event loop was idle in those dumps, so a blocked or overloaded server is ruled out for those starts.

## 5. Immediate click and delayed click

The delayed click waited until the Streamlit script had been idle for 1 second, then waited 3 more seconds. Arms A and B repeated the library-default and 2.5 Mbit/s conditions. The logged batch repeated all four bitrates with 6 immediate and 6 delayed starts each. Its server logging suppressed the failure (Section 8), so arms A and B are the fair comparison.

{click_table}

**Result.** A delayed click still failed once, with the same pattern, so click timing alone does not explain the failure. Fewer delayed starts failed, but the difference is not statistically significant. These samples cannot show whether a delay reduces the rate.

## 6. Connection time, first-frame time and control resets

Timings come from the 48 starts with browser and server logging. All 48 connected.

{time_table}

The browser shows video before the first server-processed frame. Until the first model result is ready, the library returns the camera frame without overlays, so the first displayed frame can be unannotated.

**Video-control resets:**

{control_table}

## 7. Origin of the failures

| Candidate | Verdict | Evidence |
|---|---|---|
| Automation timing | **Not the cause** | A deliberately delayed click also failed. Immediate and delayed results do not differ significantly (p = {tests['A_immediate_vs_B_delayed']:.2f} and {tests['plain_immediate_vs_plain_delayed']:.2f}). |
| Streamlit page initialisation | **Not the cause** | The failed delayed start was clicked after the script had been idle for 1 second and a further 3-second wait. The race happens during the reruns after START. |
| WebRTC connection setup | **Not the cause** | ICE and DTLS connected in every failure with a browser log. |
| Return-video bitrate | **Not the cause** | Failed: library default {bitrate['library']['failed']} of {bitrate['library']['starts']}, 2.5 Mbit/s {bitrate['2.5M']['failed']} of {bitrate['2.5M']['starts']}, 4 Mbit/s {bitrate['4M']['failed']} of {bitrate['4M']['starts']}, 6 Mbit/s {bitrate['6M']['failed']} of {bitrate['6M']['starts']}. Library against 2.5 Mbit/s: p = {tests['library_vs_2.5M']:.2f}. |
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

{decisive}

The reset condition occurred at a similar rate with and without the block (3 of {len(probe_base)} and 4 of {len(guard)} starts). Only its outcome changed.

## 8. Limits and unexplained results

1. **Log confirmation covers 3 failures.** The other {failed(ordinary) - 3} failures have the same pattern and two of them show no worker threads, so the same cause is likely. Their cause was not individually confirmed.
2. **The rescue evidence is small.** Four rescued starts against three failed ones gives p = {p_rescue:.3f}. The logged stop sequence is the stronger evidence.
3. **The real dashboard has not shown the failure.** It had 0 failures in {len(dash)} valid starts, while the test page had {failed(probe_base)} in {len(probe_base)}. The dashboard creates its worker later (median {worker_ms['H_dashboard']:.0f}–{worker_ms['H2_dashboard']:.0f} ms against {worker_ms['R_baseline']:.0f}–{worker_ms['R2_baseline']:.0f} ms), which may reduce exposure. This was not tested.
4. **Physical camera and human timing were not tested.** A physical-camera test needs separate consent.
5. **Server logging wrappers suppressed the failure, for an unknown reason.** Wrapped servers failed {pools['server_wrapped']['failed']} of {pools['server_wrapped']['starts']} starts, against {pools['server_not_wrapped']['failed']} of {pools['server_not_wrapped']['starts']} without them (p = {tests['server_not_wrapped_vs_wrapped']:.5f}). The wrappers may shift the rerun timing.
6. **The delay experiment was inconclusive.** A 150 ms delay before the component was meant to widen the race window. It also moved worker creation to a median of {worker_ms['W_before']:.0f} ms and gave Streamlit more time to update its run count, so it may have narrowed the window instead. No failure occurred in that arm, its control arm, or the arm with `runner.fastReruns = false`. These arms do not show that turning fast reruns off fixes the failure.
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
| Production code and configuration | Modification times of `app.py`, `src/`, `tests/`, `scripts/`, `.streamlit/` and requirements | No file changed after the first start test ({first_text}). Newest: `{newest.relative_to(ROOT)}`, {newest_text} |
| Evidence | SHA-256 of all {len(manifest)} files against the saved list | All match |
| Events database | Modification time | Unchanged since {db_text} |
| YOLO26n checkpoint | SHA-256 | Matches `{YOLO26N_SHA[:16]}…` |
| E3 checkpoint | SHA-256 | Matches `{E3_SHA[:16]}…`. Still experimental and not selectable |
| Original dataset | Files modified since the first start test | {dataset_changed} |
| Physical camera | Test configuration | Not used. All starts used a synthetic video |

**Side effects of this investigation:**

- Diagnostic tools and logs were added under `experiments/camera_quality_audit/`. The application imports none of them.
- A thread dump on a running server crashed the temporary test server in 5 of 48 starts. Those 5 starts are marked void and excluded: {", ".join(f"`{t}`" for t in void_tags)}. macOS saved 5 crash reports for those test servers. Later dumps ran only on stalled servers.
- A temporary 207 MB synthetic video remains in the system temporary folder for the remaining benchmarks. It will be removed when they finish.

## Appendix A. All start tests

{batch_table}

Void starts are the 5 described in Section 10. Smoke runs are not counted.

## Appendix B. All {failed(ordinary)} failed starts

"Same pattern" means START was clicked, the server received no frames, the video showed no real picture, and the video element was removed about 6 seconds after START.

{failure_table}
"""
OUT.write_text(report)
print(f"written {OUT.relative_to(ROOT)}: {len(report.splitlines())} lines; dashboard upper limit {dash_upper:.1f} %; p_assoc {p_assoc:.2e}; p_rescue {p_rescue:.3f}; newest {newest.name} {newest_text}")
