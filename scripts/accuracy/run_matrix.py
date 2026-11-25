"""Sequential, resumable runner for the YOLO26m experiment matrix (specification §6, hardware safeguards §6.3).

    caffeinate -dims .venv/bin/python scripts/accuracy/run_matrix.py <matrix.yaml> [--only A,B] [--dry-run]

For every experiment in the matrix file (in order):
  * skipped if its dev evaluation already exists (resumable); resumed from weights/last.pt if training stopped
  * the plan (hypothesis, changed / fixed variables, expected trade-offs, success criteria, full arguments) is
    written to training/configs/<name>.plan.json BEFORE training; extra Ultralytics arguments to <name>.hyp.yaml
  * trains through the project entry point: python -m src.training.train ... --no-promote --project
    experiments/accuracy_improvement/training  (never writes models/trained/, never reuses a run folder)
  * one job at a time; memory pressure, swap, battery and power source are sampled every 30 s
    (training/logs/<name>_monitor.csv). Graceful stop (SIGINT; Ultralytics keeps last.pt) when system free memory
    stays below 6 % for 3 samples, or when running on battery below --min-battery-stop
  * refuses to start a job on battery below --min-battery-start
  * after training: checks that the run arguments never reference the locked test, then evaluates best.pt on dev
    with scripts/accuracy/evaluate.py at the training image size (evaluation/dev_<name>/)
Status of every experiment: training/matrix_status.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "experiments" / "accuracy_improvement"
TRAIN = AI / "training"
PY = str(ROOT / ".venv" / "bin" / "python")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def free_pct() -> float | None:
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    m = re.search(r"free percentage:\s*(\d+)%", out)
    return float(m.group(1)) if m else None


def swap_mb() -> float | None:
    out = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    m = re.search(r"used = ([\d.]+)M", out)
    return float(m.group(1)) if m else None


def power() -> tuple[bool, int | None]:
    out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    ac = "AC Power" in out
    m = re.search(r"(\d+)%", out)
    return ac, int(m.group(1)) if m else None


def thermal_state() -> int | None:
    """macOS thermal state (NSProcessInfo): 0 nominal, 1 fair, 2 serious, 3 critical. No sudo needed."""
    out = subprocess.run(["osascript", "-l", "JavaScript", "-e",
                          'ObjC.import("Foundation"); $.NSProcessInfo.processInfo.thermalState'],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def load_status() -> dict:
    p = TRAIN / "matrix_status.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_status(st: dict) -> None:
    (TRAIN / "matrix_status.json").write_text(json.dumps(st, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("--only", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-battery-start", type=int, default=40)
    ap.add_argument("--min-battery-stop", type=int, default=12)
    ap.add_argument("--allow-battery", action="store_true",
                    help="keep training when unplugged (default: suspend while on battery, continue on mains power)")
    a = ap.parse_args()
    m = yaml.safe_load(Path(a.matrix).read_text())
    defaults = m.get("defaults", {})
    only = set(a.only.split(",")) if a.only else None
    for d in ("configs", "logs"):
        (TRAIN / d).mkdir(parents=True, exist_ok=True)
    st = load_status()
    for exp in m["experiments"]:
        e = {**defaults, **exp}
        name = e["name"]
        if only and name not in only:
            continue
        run_dir = TRAIN / name
        eval_dir = AI / "evaluation" / f"dev_{name}"
        rec = st.get(name, {})
        if (eval_dir / "summary.json").exists() or (not e.get("evaluate", True) and (run_dir / "training_metadata.json").exists()):
            print(f"[{now()}] {name}: done, skipped", flush=True)
            continue
        while (thermal_state() or 0) >= 2 or (not a.allow_battery and not power()[0]):
            print(f"[{now()}] {name}: waiting for mains power and a cool Mac before starting", flush=True)
            time.sleep(120)
        ac, batt = power()
        if not ac and batt is not None and batt < a.min_battery_start:
            rec.update({"state": "waiting_for_mains_power", "at": now(), "battery": batt})
            st[name] = rec; save_status(st)
            print(f"[{now()}] {name}: on battery {batt}% < {a.min_battery_start}% - stopping the queue", flush=True)
            return
        hyp_path = None
        if e.get("hyp"):
            hyp_path = TRAIN / "configs" / f"{name}.hyp.yaml"
            hyp_path.write_text(yaml.safe_dump(e["hyp"], sort_keys=True))
        args = ["--weights", e["weights"], "--data", e["data"], "--epochs", str(e["epochs"]), "--imgsz", str(e["imgsz"]),
                "--batch", str(e["batch"]), "--patience", str(e["patience"]), "--seed", str(e["seed"]),
                "--fraction", str(e["fraction"]), "--name", name, "--project", str(TRAIN.relative_to(ROOT)), "--no-promote"]
        if hyp_path:
            args += ["--hyp", str(hyp_path.relative_to(ROOT))]
        resume = (run_dir / "weights" / "last.pt").exists() and not (run_dir / "training_metadata.json").exists()
        if (run_dir / "training_metadata.json").exists():
            cmd = None
        elif resume:
            cmd = [PY, "-m", "src.training.train", "--resume", str((run_dir / "weights" / "last.pt").relative_to(ROOT)), "--no-promote"]
        else:
            if run_dir.exists():
                moved = run_dir.with_name(f"{name}_incomplete_{datetime.now():%Y%m%d-%H%M%S}")
                run_dir.rename(moved)
                print(f"[{now()}] {name}: earlier incomplete folder kept as {moved.name}", flush=True)
            cmd = [PY, "-m", "src.training.train", *args]
        plan = {k: e.get(k) for k in ("hypothesis", "changed", "fixed", "expected", "success")}
        plan.update({"name": name, "arguments": args, "hyp": e.get("hyp", {}), "written": now(), "resume": resume})
        (TRAIN / "configs" / f"{name}.plan.json").write_text(json.dumps(plan, indent=2))
        if a.dry_run:
            print(" ".join(cmd or ["(training done)"]))
            continue
        if cmd:
            rec.update({"state": "training", "started": now(), "command": " ".join(cmd[1:])})
            st[name] = rec; save_status(st)
            print(f"[{now()}] {name}: {'resuming' if resume else 'training'}", flush=True)
            log = open(TRAIN / "logs" / f"{name}.log", "a")
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            mon = open(TRAIN / "logs" / f"{name}_monitor.csv", "a", newline="")
            w = csv.writer(mon)
            w.writerow(["time", "free_pct", "swap_mb", "ac_power", "battery_pct", "thermal_state", "suspended"])
            low, reason, suspended = 0, None, False
            while proc.poll() is None:
                time.sleep(30)
                f, s = free_pct(), swap_mb()
                ac, batt = power()
                th = thermal_state()
                # thermal / power guard: suspend training (SIGSTOP) at thermal state 'serious' or when unplugged,
                # continue (SIGCONT) on mains power once the state is back to 'nominal'; stop at 'critical'.
                # A fanless MacBook Air otherwise runs hot for hours under full GPU load (incident 2026-11-20).
                hot = th is not None and th >= 2
                unplugged = (not a.allow_battery) and not ac
                if (hot or unplugged) and not suspended and th != 3:
                    proc.send_signal(signal.SIGSTOP); suspended = True
                    why = f"thermal state {th}" if hot else "running on battery"
                    print(f"[{now()}] {name}: {why} - training suspended", flush=True)
                elif suspended and not hot and not unplugged and (th is None or th == 0):
                    proc.send_signal(signal.SIGCONT); suspended = False
                    print(f"[{now()}] {name}: mains power and nominal thermal state - training continued", flush=True)
                w.writerow([now(), f, s, ac, batt, th, suspended]); mon.flush()
                if th == 3 and reason is None:
                    reason = "stopped_thermal_critical"
                low = low + 1 if (f is not None and f < 6) else 0
                if low >= 3 and reason is None:
                    reason = "stopped_memory_pressure"
                elif not ac and batt is not None and batt < a.min_battery_stop and reason is None:
                    reason = "paused_low_battery"
                if reason:
                    print(f"[{now()}] {name}: {reason} - sending SIGINT", flush=True)
                    if suspended:
                        proc.send_signal(signal.SIGCONT)
                    proc.send_signal(signal.SIGINT)
                    try:
                        proc.wait(timeout=60)
                    except subprocess.TimeoutExpired:  # observed 2026-11-20: SIGINT not acted on within 60 s
                        proc.terminate()               # last.pt of the last completed epoch is kept
                    break
            proc.wait()
            mon.close(); log.close()
            rec.update({"returncode": proc.returncode, "train_finished": now()})
            if reason or proc.returncode != 0:
                rec["state"] = reason or "training_failed"
                st[name] = rec; save_status(st)
                print(f"[{now()}] {name}: {rec['state']} (rc {proc.returncode}) - stopping the queue", flush=True)
                return
        argsy = run_dir / "args.yaml"
        if argsy.exists() and ("images/test" in argsy.read_text() or "locked_test" in argsy.read_text()):
            rec.update({"state": "LOCKED_TEST_VIOLATION", "at": now()})
            st[name] = rec; save_status(st)
            raise SystemExit(f"{name}: training arguments reference the locked test")
        if e.get("evaluate", True):
            rec.update({"state": "evaluating", "eval_started": now()})
            st[name] = rec; save_status(st)
            r = subprocess.run([PY, "scripts/accuracy/evaluate.py", "--weights", str((run_dir / "weights" / "best.pt").relative_to(ROOT)),
                                "--split", "dev", "--out", str(eval_dir.relative_to(ROOT)), "--imgsz", str(e["imgsz"])],
                               cwd=ROOT, capture_output=True, text=True)
            (TRAIN / "logs" / f"{name}_eval.log").write_text(r.stdout + r.stderr)
            if r.returncode != 0:
                rec.update({"state": "evaluation_failed", "at": now()})
                st[name] = rec; save_status(st)
                return
            rec["dev_summary"] = json.loads((eval_dir / "summary.json").read_text())
        rec.update({"state": "done", "finished": now()})
        st[name] = rec; save_status(st)
        print(f"[{now()}] {name}: done", flush=True)


if __name__ == "__main__":
    main()
