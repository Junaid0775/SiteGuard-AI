"""Does a raised return-video bitrate make WebRTC starts fail? Fresh server + fresh Chrome per start (synthetic camera).

A start counts as successful when the server received at least one frame within the run. Settings are interleaved, so
time-related effects hit all of them equally. The lid is checked before each start; a closed lid stops the test.
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
SETTINGS = {"library": "library", "2.5M": "2500000:1250000:2500000", "4M": "4000000:2000000:4000000", "6M": "6000000:3000000:6000000"}
ROUNDS, SECONDS = 10, 7
out = []
for rnd in range(1, ROUNDS + 1):
    names = list(SETTINGS)
    names = names[rnd % len(names):] + names[:rnd % len(names)]
    for name in names:
        if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
            print("STOPPED: lid closed", flush=True); sys.exit(2)
        tag = f"start_{name}_{rnd}"
        p = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake", "--mode", "pipeline",
                              "--content", "moving", "--seconds", str(SECONDS), "--tag", tag, "--bitrate", SETTINGS[name]], cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            p.wait(timeout=75)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM); time.sleep(3)
        time.sleep(1)
        lines = [json.loads(l) for l in (LOGS / tag / "server.jsonl").read_text().splitlines() if l.strip()]
        recv = sum(r["kind"] == "recv" for r in lines)
        log = (LOGS / tag / "probe_server.log").read_text(errors="ignore")
        out.append({"setting": name, "round": rnd, "ok": recv > 0, "frames": recv, "ice_completed": "ICE completed" in log or "completed" in log.lower(),
                    "dtls_connected": "State.CONNECTED" in log or "connected" in log.lower()})
        print(json.dumps(out[-1]), flush=True)
        (LOGS / "start_reliability.json").write_text(json.dumps(out, indent=1))
print("done", flush=True)
