"""Fix 1 benchmark, version 2 (synthetic camera only). Replaces bench_bitrate.py, whose 4/6/8 Mbit/s runs were invalidated
by system sleep (lid closed at 12:46). Every run is checked: lid open before and after, and no gap > 2 s between the
1-second browser samples. An invalid run is retried once and is never used in the comparison. Run under caffeinate -i."""
import json, os, signal, statistics, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
CONTENT = sys.argv[1] if len(sys.argv) > 1 else "still"   # still | moving
MODES = ("pipeline", "identity") if CONTENT == "still" else ("pipeline",)   # PSNR needs a still reference
PREFIX = "b2" if CONTENT == "still" else "b3"
OUT = LOGS / ("bench_bitrate_results_v2.json" if CONTENT == "still" else "bench_bitrate_results_v3_moving.json")
SETTINGS = {"library": "library", "2.5M": "2500000:1250000:2500000", "4M": "4000000:2000000:4000000",
            "6M": "6000000:3000000:6000000", "8M": "8000000:4000000:8000000"}
SECONDS, STEADY_FROM, REPEATS = 26, 18, 2
# Overrides for later confirmation runs, so that earlier result files are never overwritten.
PREFIX = os.environ.get("SG_BENCH_PREFIX", PREFIX)
OUT = Path(os.environ["SG_BENCH_OUT"]) if os.environ.get("SG_BENCH_OUT") else OUT
REPEATS = int(os.environ.get("SG_BENCH_REPEATS", REPEATS))
if os.environ.get("SG_BENCH_SETTINGS"):
    SETTINGS = {k: SETTINGS[k] for k in os.environ["SG_BENCH_SETTINGS"].split(",")}
EXTRA_ARGS = os.environ.get("SG_BENCH_EXTRA", "").split()


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def lid_open():
    return '"AppleClamshellState" = Yes' not in sh("ioreg -r -k AppleClamshellState -d 4")


def machine():
    return {"thermal": sh("osascript -l JavaScript -e 'ObjC.import(\"Foundation\"); $.NSProcessInfo.processInfo.thermalState'").strip(),
            "power": "AC" if "AC Power" in sh("pmset -g batt") else "battery"}


def pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))] if v else None


def analyse(tag):
    d = LOGS / tag
    if not (d / "browser.json").exists():
        return {"valid": False, "reason": "no browser.json"}
    recs = [json.loads(l) for l in (d / "server.jsonl").read_text().splitlines() if l.strip()]
    b = json.loads((d / "browser.json").read_text())
    samples = b.get("samples", [])
    t = [s["t"] for s in samples]
    max_gap = max((y - x for x, y in zip(t, t[1:])), default=99)
    recv_all = [r for r in recs if r["kind"] == "recv"]
    if not recv_all or len(samples) < SECONDS - 2 or max_gap > 2.0:
        return {"valid": False, "reason": f"samples={len(samples)} max_gap={max_gap:.1f}s recv={len(recv_all)}"}
    t0 = recv_all[0]["t"]
    steady = [r for r in recs if r["t"] - t0 >= STEADY_FROM]
    recv, enc = [r for r in steady if r["kind"] == "recv"], [r for r in steady if r["kind"] == "encode"]
    span = max(r["t"] for r in steady) - min(r["t"] for r in steady)
    ss = [s for s in samples if s["t"] >= STEADY_FROM and s.get("videos")]
    first, last = ss[0]["videos"][0], ss[-1]["videos"][0]
    dt = max(ss[-1]["t"] - ss[0]["t"], 1)
    bf = b.get("browser_frame") or {}
    near = [r["psnr_vs_source"] for r in recv_all if "psnr_vs_source" in r and r["t"] >= recv_all[-1]["t"] - 3 and r["w"] == bf.get("w")]
    uplink = round(statistics.mean(near), 2) if near else None
    return {"valid": True, "max_gap_s": round(max_gap, 1), "recv_sizes": sorted({f'{r["w"]}x{r["h"]}' for r in recv}),
            "recv_fps": round(len(recv) / span, 1), "enc_fps": round(len(enc) / span, 1),
            "out_kbps": round(sum(r["bytes"] for r in enc) * 8 / span / 1000), "target_kbps_end": round(enc[-1]["target_bitrate"] / 1000),
            "enc_ms_median": pct([r["enc_ms"] for r in enc], .5), "enc_ms_p95": pct([r["enc_ms"] for r in enc], .95),
            "process_ms_median": pct([r["process_ms"] for r in recv if "process_ms" in r], .5),
            "process_ms_p95": pct([r["process_ms"] for r in recv if "process_ms" in r], .95),
            "server_cpu_pct": round(statistics.mean(s["server_cpu_pct"] for s in ss), 1), "server_rss_mb": max(s["server_rss_mb"] for s in samples),
            "browser_fps": round((last["decoded"] - first["decoded"]) / dt, 1), "browser_dropped_steady": last["dropped"] - first["dropped"],
            "browser_size": f'{last["w"]}x{last["h"]}', "psnr_uplink": uplink, "psnr_roundtrip": bf.get("psnr_vs_source"),
            "downlink_loss_db": round(uplink - bf["psnr_vs_source"], 2) if uplink is not None and bf.get("psnr_vs_source") else None}


def run(tag, bitrate, mode):
    p = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake",
                          "--mode", mode, "--seconds", str(SECONDS), "--tag", tag, "--bitrate", bitrate, "--content", CONTENT, *EXTRA_ARGS], cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        p.wait(timeout=120)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)
        time.sleep(3)
    time.sleep(2)


results = []
for rep in range(1, REPEATS + 1):
    for name, bitrate in SETTINGS.items():
        for mode in MODES:
            for attempt in (1, 2):
                if not lid_open():
                    print("STOPPED: lid closed", flush=True)
                    OUT.write_text(json.dumps({"complete": False, "runs": results}, indent=1))
                    sys.exit(2)
                tag = f"{PREFIX}_{name}_{mode}_r{rep}_a{attempt}"
                m0 = machine()
                run(tag, bitrate, mode)
                r = analyse(tag)
                r["valid"] = r["valid"] and lid_open()
                r.update(setting=name, mode=mode, repeat=rep, attempt=attempt, tag=tag, machine_before=m0, machine_after=machine())
                results.append(r)
                print(json.dumps({k: r.get(k) for k in ("setting", "mode", "repeat", "attempt", "valid", "reason", "recv_fps", "browser_fps", "browser_dropped_steady", "recv_sizes", "out_kbps", "enc_ms_median", "server_cpu_pct", "downlink_loss_db")}), flush=True)
                OUT.write_text(json.dumps({"complete": False, "runs": results}, indent=1))
                if r["valid"]:
                    break
OUT.write_text(json.dumps({"complete": True, "runs": results}, indent=1))
print("done", flush=True)
