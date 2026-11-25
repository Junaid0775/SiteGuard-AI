"""Capture where the server is when a start stalls after connecting: dump all Python thread stacks 2 s and 4 s after START."""
import json, os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 36
out = []
for i in range(1, N + 1):
    if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
        print("STOPPED: lid closed", flush=True); sys.exit(2)
    setting, br = ("library", "library") if i % 2 else ("2.5M", "2500000:1250000:2500000")
    tag = f"s_{setting}_{i}"
    p = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake", "--mode", "pipeline", "--content", "moving",
                          "--seconds", "7", "--tag", tag, "--bitrate", br, "--launcher", "stackdump"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        p.wait(timeout=90)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM); time.sleep(3)
    time.sleep(1)
    d = LOGS / tag
    b = json.loads((d / "browser.json").read_text()) if (d / "browser.json").exists() else {}
    recv = sum(json.loads(l)["kind"] == "recv" for l in (d / "server.jsonl").read_text().splitlines() if l.strip()) if (d / "server.jsonl").exists() else 0
    out.append({"tag": tag, "setting": setting, "ok": recv > 0, "frames": recv, "stack_dumps_at_s": b.get("stack_dumps_at_s"), "clicked_stop": b.get("clicked_stop")})
    print(json.dumps(out[-1]), flush=True)
    (LOGS / "start_stacks.json").write_text(json.dumps(out, indent=1))
print("done", flush=True)
