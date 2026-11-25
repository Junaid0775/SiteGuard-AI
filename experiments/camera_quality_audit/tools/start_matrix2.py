"""Which part of the instrumented run hid the failure? Four interleaved arms, original driver, immediate click.

  A2  plain app (control, same time window)
  E   plain app + passive browser-side stage log (server untouched): gives the exact stage of a failed start
  D   plain app with PyAV/aiortc imported before OpenCV (import-order test)
  G   plain app through the same exec() launcher, no other change (launcher control)
Synthetic camera, fresh server and Chrome per start, no production code, no real database or evidence.
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
ARMS = {"A2_plain": [], "E_browser_log": ["--browser-log"], "D_av_first": ["--launcher", "avfirst"], "G_exec_only": ["--launcher", "execonly"]}
BITRATES = {"library": "library", "2.5M": "2500000:1250000:2500000"}
ROUNDS, SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 15, 7
out = []
for rnd in range(1, ROUNDS + 1):
    names = list(ARMS)
    names = names[rnd % 4:] + names[:rnd % 4]
    setting = "library" if rnd % 2 else "2.5M"
    for arm in names:
        if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
            print("STOPPED: lid closed", flush=True); sys.exit(2)
        tag = f"n_{arm}_{setting}_r{rnd}"
        p = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake", "--mode", "pipeline",
                              "--content", "moving", "--seconds", str(SECONDS), "--tag", tag, "--bitrate", BITRATES[setting], *ARMS[arm]], cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            p.wait(timeout=90)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM); time.sleep(3)
        time.sleep(1)
        d = LOGS / tag
        b = json.loads((d / "browser.json").read_text()) if (d / "browser.json").exists() else {}
        recv = [r for r in (json.loads(l) for l in (d / "server.jsonl").read_text().splitlines() if l.strip()) if r["kind"] == "recv"] if (d / "server.jsonl").exists() else []
        tc = b.get("t_click")
        samples = b.get("samples", [])
        r = {"tag": tag, "arm": arm, "setting": setting, "round": rnd, "ok": bool(recv), "frames": len(recv), "clicked_start": b.get("clicked_start"), "clicked_stop": b.get("clicked_stop"),
             "control_reset_at_s": next((x["t"] for x in samples if not x.get("videos")), None) if not b.get("clicked_stop") else None,
             "first_server_frame_ms": int(recv[0]["t"] * 1000 - tc * 1000) if recv and tc else None}
        if "browser_events" in b and tc:
            t0 = int(tc * 1000)
            ev = sorted([e for e in b["browser_events"] if e["t"] >= t0 - 50], key=lambda e: e["t"])
            f = lambda n, **w: next((e["t"] - t0 for e in ev if e["name"] == n and all(e.get(k) in (v if isinstance(v, tuple) else (v,)) for k, v in w.items())), None)
            r["browser_stages_ms"] = {"camera": f("gum_ok"), "pc_created": f("pc_created"), "offer_set": f("setLocalDescription_ok"), "gathering_complete": f("icegatheringstatechange", state="complete"),
                                      "answer_call": f("setRemoteDescription_call"), "answer_applied": f("setRemoteDescription_ok"), "remote_track": f("track"),
                                      "ice_checking": f("iceconnectionstatechange", state="checking"), "ice_connected": f("iceconnectionstatechange", state=("connected", "completed")),
                                      "dtls_connecting": f("connectionstatechange", state="connecting"), "peer_connected": f("connectionstatechange", state="connected"),
                                      "ice_disconnected": f("iceconnectionstatechange", state="disconnected"), "ice_failed": f("iceconnectionstatechange", state="failed"),
                                      "peer_failed": f("connectionstatechange", state="failed"), "video_element": f("video_element"), "first_frame": f("first_frame"), "pc_close": f("close_call")}
            r["browser_errors"] = [{"name": e["name"], "error": e.get("error")} for e in ev if e["name"].endswith("_err")][:3]
            r["control_changes_ms"] = [(e["t"] - t0, e["labels"]) for e in ev if e["name"] == "control"][:8]
        out.append(r)
        print(json.dumps({k: r.get(k) for k in ("tag", "ok", "control_reset_at_s", "first_server_frame_ms")}), flush=True)
        (LOGS / "start_matrix2.json").write_text(json.dumps(out, indent=1))
print("done", flush=True)
