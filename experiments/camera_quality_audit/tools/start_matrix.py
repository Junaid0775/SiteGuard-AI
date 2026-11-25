"""Repeat the failed 40-start condition with the ORIGINAL driver (run_probe.py), comparing three interleaved arms.

  A  plain, immediate click  (exact condition of the 40-start test)
  B  plain, delayed click    (Streamlit script idle for 1 s, then 3 s more, then START)
  C  server stage log, immediate click (adds aiortc connection and ICE-candidate logging on the server only)

Synthetic camera, fresh server and fresh Chrome per start, no production code, no real database or evidence.
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
ARMS = {"A_plain_immediate": [], "B_plain_delayed": ["--click", "delayed"], "C_serverlog_immediate": ["--diag-server"]}
BITRATES = {"library": "library", "2.5M": "2500000:1250000:2500000"}
ROUNDS, SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 20, 7


def jsonl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


out = []
for rnd in range(1, ROUNDS + 1):
    names = list(ARMS)
    names = names[rnd % 3:] + names[:rnd % 3]
    setting = "library" if rnd % 2 else "2.5M"
    for arm in names:
        if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
            print("STOPPED: lid closed", flush=True); sys.exit(2)
        tag = f"m_{arm}_{setting}_r{rnd}"
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
        recs, st = jsonl(d / "server.jsonl"), jsonl(d / "stage.jsonl")
        recv = [r for r in recs if r["kind"] == "recv"]
        tc = b.get("t_click")
        samples = b.get("samples", [])
        reset_s = next((x["t"] for x in samples if not x.get("videos")), None) if not b.get("clicked_stop") else None
        first_video_s = next((x["t"] for x in samples if x.get("videos") and x["videos"][0]["w"] > 0), None)
        rel = lambda name, **w: next((e["t"] - int(tc * 1000) for e in st if e["name"] == name and all(e.get(k) == v for k, v in w.items())), None) if tc else None
        cand = [e for e in st if e["name"] == "srv_addIceCandidate_call" and not e.get("end_of_candidates")]
        r = {"tag": tag, "arm": arm, "setting": setting, "round": rnd, "ok": bool(recv), "frames": len(recv), "clicked_start": b.get("clicked_start"), "clicked_stop": b.get("clicked_stop"),
             "control_reset_at_s": reset_s, "first_video_sample_s": first_video_s, "first_server_frame_ms": int(recv[0]["t"] * 1000 - tc * 1000) if recv and tc else None,
             "srv_offer_ms": rel("srv_setRemoteDescription_call"), "srv_answer_ms": rel("srv_setLocalDescription_ok"), "srv_ice_completed_ms": rel("srv_ice", state="completed"),
             "srv_ice_failed_ms": rel("srv_ice", state="failed"), "srv_connected_ms": rel("srv_connection", state="connected"), "srv_conn_failed_ms": rel("srv_connection", state="failed"),
             "srv_close_ms": rel("srv_close_call"), "candidates": len(cand), "mdns_candidates": sum(bool(e.get("mdns")) for e in cand),
             "candidate_errors": [e.get("error") for e in st if e["name"] == "srv_addIceCandidate_err"][:2]}
        out.append(r)
        print(json.dumps({k: r[k] for k in ("tag", "ok", "control_reset_at_s", "first_server_frame_ms", "srv_connected_ms", "candidates", "mdns_candidates")}), flush=True)
        (LOGS / "start_matrix.json").write_text(json.dumps(out, indent=1))
print("done", flush=True)
