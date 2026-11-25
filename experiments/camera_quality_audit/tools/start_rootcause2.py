"""Decisive test of the suspected start-failure cause. Synthetic camera only; production code and config are unchanged.

Arms (interleaved):
  R2_baseline   unchanged probe, with streamlit-webrtc's own lifecycle messages logged
  G_guard       the same probe, except that the library's orphan-context reset cannot fire; every would-be reset is logged
  H2_dashboard  the real app.py with a temporary events DB and evidence folder
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
ARMS = {"R2_baseline": ([], 16), "G_guard": (["--variant", "guard"], 24),
        "H2_dashboard": (["--app", "dashboard"], 16)}
out = []
for rnd in range(1, 25):
    names = [a for a, (_, n) in ARMS.items() if rnd <= n]
    names = names[rnd % len(names):] + names[:rnd % len(names)]
    for arm in names:
        if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
            print("STOPPED: lid closed", flush=True); sys.exit(2)
        tag = f"t_{arm}_{rnd}"
        p = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake", "--mode", "pipeline",
                              "--content", "moving", "--seconds", "3", "--tag", tag, "--launcher", "lifecycle", *ARMS[arm][0]],
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
        ok = real_video is not None if arm == "H2_dashboard" else recv > 0
        click_ms = int(b["t_click"] * 1000) if b.get("t_click") else None
        events = [json.loads(l) for l in (d / "lifecycle.jsonl").read_text().splitlines() if l.strip()] if (d / "lifecycle.jsonl").exists() else []
        after = lambda text: [e["t"] - click_ms for e in events if text in e["message"] and click_ms and e["t"] >= click_ms]
        stacks = (d / "stacks.txt").read_text() if (d / "stacks.txt").exists() else ""
        out.append({"tag": tag, "arm": arm, "round": rnd, "ok": ok, "frames": recv, "first_real_video_s": real_video, "clicked_stop": b.get("clicked_stop"),
                    "control_reset_at_s": next((s["t"] for s in samples if not s["videos"]), None) if not b.get("clicked_stop") else None,
                    "orphan_reset_ms": after("not rendered"), "stop_reset_ms": after("Reset the stopped"), "worker_stopping_ms": after("Stopping worker"),
                    "worker_created_ms": after("Create a new worker"), "answer_rerun_ms": after("Rerun to send the SDP answer"),
                    "ice_stop_ms": after("stopping WebRTC worker"), "decoder_threads_at_3s": stacks.count("in decoder_worker"),
                    "process_threads_at_3s": stacks.count("in _run_worker_thread"), "valid": bool(b),
                    "guard_suppressed": [{"ms": e["t"] - click_ms, "worker_alive": e["worker_alive"], "gap": e["gap"]} for e in events if e.get("logger") == "guard" and click_ms and e["t"] >= click_ms]})
        print(json.dumps({k: out[-1][k] for k in ("tag", "valid", "ok", "frames", "orphan_reset_ms", "guard_suppressed")}), flush=True)
        (LOGS / "start_rootcause2.json").write_text(json.dumps(out, indent=1))
print("done", flush=True)
