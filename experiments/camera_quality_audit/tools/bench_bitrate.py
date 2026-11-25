"""Fix 1 benchmark: return-video VP8 bitrate settings with the synthetic camera (no physical camera).
Each setting runs twice: pipeline mode (real YOLO26n processing: fps, CPU, memory, encode time) and identity mode
(transport only: round-trip PSNR of the displayed frame against the synthetic source)."""
import json, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOGS = ROOT / "experiments/camera_quality_audit/logs"
SETTINGS = {"library_0.5": "library", "2.5M": "2500000:1250000:2500000", "4M": "4000000:2000000:4000000",
            "6M": "6000000:3000000:6000000", "8M": "8000000:4000000:8000000"}
SECONDS, STEADY_FROM = 26, 18  # uplink switches 640x360 -> 960x540 at ~16-17 s (REPORT-001); steady window = last 8 s


def pct(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))] if v else None


def analyse(tag):
    d = LOGS / tag
    recs = [json.loads(l) for l in (d / "server.jsonl").read_text().splitlines() if l.strip()]
    b = json.loads((d / "browser.json").read_text())
    t0 = min(r["t"] for r in recs if r["kind"] == "recv")
    steady = [r for r in recs if r["t"] - t0 >= STEADY_FROM]
    recv = [r for r in steady if r["kind"] == "recv"]
    enc = [r for r in steady if r["kind"] == "encode"]
    span = (max(r["t"] for r in steady) - min(r["t"] for r in steady)) if steady else 1
    samples = b.get("samples", [])
    cpu = [s["server_cpu_pct"] for s in samples if s.get("server_cpu_pct") is not None and s["t"] >= STEADY_FROM]
    vids = [s["videos"][0] for s in samples if s.get("videos")]
    first, last = (vids[0], vids[-1]) if vids else ({}, {})
    out = {
        "recv_size_steady": sorted({f'{r["w"]}x{r["h"]}' for r in recv}),
        "recv_fps": round(len(recv) / span, 1), "enc_fps": round(len(enc) / span, 1),
        "out_kbps": round(sum(r["bytes"] for r in enc) * 8 / span / 1000),
        "target_kbps_end": round(enc[-1]["target_bitrate"] / 1000) if enc else None,
        "enc_ms_median": pct([r["enc_ms"] for r in enc], 0.5), "enc_ms_p95": pct([r["enc_ms"] for r in enc], 0.95),
        "process_ms_median": pct([r["process_ms"] for r in recv if "process_ms" in r], 0.5),
        "process_ms_p95": pct([r["process_ms"] for r in recv if "process_ms" in r], 0.95),
        "server_cpu_pct_mean": round(statistics.mean(cpu), 1) if cpu else None,
        "server_rss_mb_max": max((s.get("server_rss_mb") or 0) for s in samples) if samples else None,
        "browser_decoded_fps": round((last.get("decoded", 0) - first.get("decoded", 0)) / max(1, samples[-1]["t"] - samples[0]["t"]), 1) if vids else None,
        "browser_dropped": last.get("dropped"), "browser_video_end": f'{last.get("w")}x{last.get("h")}' if vids else None,
        "psnr_uplink_steady": round(statistics.mean([r["psnr_vs_source"] for r in recv if "psnr_vs_source" in r]), 2) if any("psnr_vs_source" in r for r in recv) else None,
        "psnr_roundtrip_end": (b.get("browser_frame") or {}).get("psnr_vs_source"),
        "browser_frame_size": f'{(b.get("browser_frame") or {}).get("w")}x{(b.get("browser_frame") or {}).get("h")}' if b.get("browser_frame") else None,
    }
    return out


results = {}
for name, br in SETTINGS.items():
    for mode in ("pipeline", "identity"):
        tag = f"bench_{name}_{mode}"
        subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "experiments/camera_quality_audit/tools/run_probe.py"), "--source", "fake",
                        "--mode", mode, "--seconds", str(SECONDS), "--tag", tag, "--bitrate", br], cwd=ROOT, capture_output=True, timeout=240)
        try:
            results.setdefault(name, {})[mode] = analyse(tag)
        except Exception as exc:  # keep going; record the failure
            results.setdefault(name, {})[mode] = {"error": f"{type(exc).__name__}: {exc}"}
        print(name, mode, json.dumps(results[name][mode]), flush=True)
(LOGS / "bench_bitrate_results.json").write_text(json.dumps(results, indent=1))
print("done")
