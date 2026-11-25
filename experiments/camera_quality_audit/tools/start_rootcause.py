"""Controlled test of the suspected start-failure cause. Synthetic camera only; production code and config are unchanged.

Arms (all use webrtc_probe_lifecycle_app.py, interleaved so time-related effects hit all of them):
  R_baseline               unchanged probe
  W_before                 150 ms delay plus one Streamlit yield point BEFORE webrtc_streamer (widens the suspected window)
  W_after                  the same delay and yield point AFTER webrtc_streamer (same run time, no wider window)
  N_before_no_fast_reruns  W_before with runner.fastReruns=false, set on this test server's command line only
  H_dashboard              the real app.py with a temporary events DB and evidence folder
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
ARMS = {"R_baseline": ([], 12), "W_before": (["--variant", "before"], 8), "W_after": (["--variant", "after"], 8),
        "N_before_no_fast_reruns": (["--variant", "before", "--no-fast-reruns"], 8), "H_dashboard": (["--app", "dashboard"], 12)}
out = []
for rnd in range(1, 13):
    names = [a for a, (_, n) in ARMS.items() if rnd <= n]
    names = names[rnd % len(names):] + names[:rnd % len(names)]
    for arm in names:
        if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
            print("STOPPED: lid closed", flush=True); sys.exit(2)
        tag = f"r_{arm}_{rnd}"
        p = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake", "--mode", "pipeline",
                              "--content", "moving", "--seconds", "7", "--tag", tag, "--launcher", "lifecycle", *ARMS[arm][0]],
                             cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            p.wait(timeout=100)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM); time.sleep(3)
        time.sleep(1)
        d = LOGS / tag
        b = json.loads((d / "browser.json").read_text()) if (d / "browser.json").exists() else {}
        samples = b.get("samples", [])
        real_video = next((s["t"] for s in samples if s["videos"] and s["videos"][0]["w"] > 2), None)
        recv = sum(json.loads(l).get("kind") == "recv" for l in (d / "server.jsonl").read_text().splitlines() if l.strip()) if (d / "server.jsonl").exists() else 0
        ok = real_video is not None if arm == "H_dashboard" else recv > 0
        click_ms = int(b["t_click"] * 1000) if b.get("t_click") else None
        events = [json.loads(l) for l in (d / "lifecycle.jsonl").read_text().splitlines() if l.strip()] if (d / "lifecycle.jsonl").exists() else []
        after = lambda text: [e["t"] - click_ms for e in events if text in e["message"] and click_ms and e["t"] >= click_ms]
        stacks = (d / "stacks.txt").read_text() if (d / "stacks.txt").exists() else ""
        out.append({"tag": tag, "arm": arm, "round": rnd, "ok": ok, "frames": recv, "first_real_video_s": real_video, "clicked_stop": b.get("clicked_stop"),
                    "control_reset_at_s": next((s["t"] for s in samples if not s["videos"]), None) if not b.get("clicked_stop") else None,
                    "orphan_reset_ms": after("not rendered"), "stop_reset_ms": after("Reset the stopped"), "worker_stopping_ms": after("Stopping worker"),
                    "worker_created_ms": after("Create a new worker"), "answer_rerun_ms": after("Rerun to send the SDP answer"),
                    "ice_stop_ms": after("stopping WebRTC worker"), "decoder_threads_at_3s": stacks.count("in decoder_worker"),
                    "process_threads_at_3s": stacks.count("in _run_worker_thread")})
        print(json.dumps({k: out[-1][k] for k in ("tag", "ok", "orphan_reset_ms", "stop_reset_ms", "worker_created_ms", "decoder_threads_at_3s")}), flush=True)
        (LOGS / "start_rootcause.json").write_text(json.dumps(out, indent=1))
print("done", flush=True)
