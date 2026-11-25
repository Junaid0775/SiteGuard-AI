"""Natural start test of the guard: many ordinary starts, no forced events. Synthetic camera only.

Each start uses a new server and a new Chrome, through the same driver as the earlier start-failure tests. Arms are
interleaved so that time-related effects reach all of them. A start counts as connected when the server received frames
(test page) or the browser showed real video (dashboard).
Usage: guard_natural.py GUARD_MODE RUN_NAME [PROBE_GUARD_STARTS] [PROBE_OFF_STARTS] [DASHBOARD_GUARD_STARTS] [DASHBOARD_OFF_STARTS]
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
MODE, NAME = sys.argv[1], sys.argv[2]
N_GUARD, N_OFF, N_DASH, N_DASH_OFF = (int(x) for x in (sys.argv[3:7] + ["40", "16", "24", "16"][len(sys.argv[3:7]):]))
ARMS = {"probe_guard": (MODE, "probe", N_GUARD), "probe_off": ("off", "probe", N_OFF), "dashboard_guard": (MODE, "dashboard", N_DASH), "dashboard_off": ("off", "dashboard", N_DASH_OFF)}
rounds = max(N_GUARD, N_OFF, N_DASH, N_DASH_OFF)
counts = {a: 0 for a in ARMS}
out = []
for rnd in range(1, rounds + 1):
    names = [a for a, (_, _, n) in ARMS.items() if counts[a] < n and (rnd - 1) * n // rounds != rnd * n // rounds]
    names = names[rnd % max(1, len(names)):] + names[:rnd % max(1, len(names))]
    for arm in names:
        if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
            print("STOPPED: lid closed", flush=True); sys.exit(2)
        counts[arm] += 1
        guard_mode, target, _ = ARMS[arm]
        tag = f"g_{NAME}_{arm}_{counts[arm]}"
        p = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake", "--mode", "pipeline", "--content", "moving",
                              "--seconds", "3", "--tag", tag, "--launcher", "guard", "--guard-mode", guard_mode, "--app", target],
                             cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            p.wait(timeout=100)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM); time.sleep(3)
        time.sleep(1)
        d = LOGS / tag
        b = json.loads((d / "browser.json").read_text()) if (d / "browser.json").exists() else {}
        samples = b.get("samples", [])
        real = next((s["t"] for s in samples if s["videos"] and s["videos"][0]["w"] > 2), None)
        recv = sum(json.loads(l).get("kind") == "recv" for l in (d / "server.jsonl").read_text().splitlines() if l.strip()) if (d / "server.jsonl").exists() else 0
        events = [json.loads(l) for l in (d / "lifecycle.jsonl").read_text().splitlines() if l.strip()] if (d / "lifecycle.jsonl").exists() else []
        jumps = [e for e in events if e.get("logger") == "guard"]
        out.append({"tag": tag, "arm": arm, "mode": guard_mode, "target": target, "n": counts[arm], "valid": bool(b), "ok": (real is not None if target == "dashboard" else recv > 0) if b else None,
                    "frames": recv, "real_video_s": real, "library_resets": sum("not rendered" in e["message"] for e in events),
                    "jumps_protected": sum(bool(e.get("protected")) for e in jumps), "jumps_with_live_worker": sum(bool(e.get("worker_alive")) for e in jumps)})
        print(json.dumps({k: out[-1][k] for k in ("tag", "valid", "ok", "library_resets", "jumps_protected")}), flush=True)
        (LOGS / f"guard/natural_{NAME}.json").write_text(json.dumps(out, indent=1))
print("done", flush=True)
