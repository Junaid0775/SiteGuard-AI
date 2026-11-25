import json, statistics, sys
from pathlib import Path
d = Path(sys.argv[1])
recs = [json.loads(l) for l in (d / "server.jsonl").read_text().splitlines() if l.strip()]
b = json.loads((d / "browser.json").read_text())
recv = [r for r in recs if r["kind"] == "recv"]; enc = [r for r in recs if r["kind"] == "encode"]
t0 = recv[0]["t"]; per10 = {}
for r in recv: per10.setdefault(int((r["t"] - t0) // 10) * 10, []).append(r)
s = b["samples"]; cpu = [x["server_cpu_pct"] for x in s if x.get("server_cpu_pct") is not None][2:]
v0, v1 = s[0]["videos"][0], s[-1]["videos"][0]
out = {"recv_per_10s": {k: (len(v), sorted({f'{x["w"]}x{x["h"]}' for x in v})) for k, v in per10.items()},
       "process_ms_med_p95": (sorted(r["process_ms"] for r in recv)[len(recv)//2], sorted(r["process_ms"] for r in recv)[int(len(recv)*0.95)]) if "process_ms" in recv[0] else None,
       "enc_ms_med_p95": (sorted(r["enc_ms"] for r in enc)[len(enc)//2], sorted(r["enc_ms"] for r in enc)[int(len(enc)*0.95)]),
       "out_kbps_mean": round(sum(r["bytes"] for r in enc) * 8 / (enc[-1]["t"] - enc[0]["t"]) / 1000),
       "cpu_mean_max": (round(statistics.mean(cpu), 1), max(cpu)), "rss_max_mb": max(x["server_rss_mb"] for x in s),
       "browser_decoded_fps": round((v1["decoded"] - v0["decoded"]) / (s[-1]["t"] - s[0]["t"]), 1), "browser_dropped": v1["dropped"],
       "end_size": (v1["w"], v1["h"]), "browser_frame": b.get("browser_frame")}
print(json.dumps(out))
(d / "stability.json").write_text(json.dumps(out, indent=1))
