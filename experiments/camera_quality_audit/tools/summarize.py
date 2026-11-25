"""Summarise a probe run (server.jsonl + browser.json) into per-second statistics. Metadata only."""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

d = Path(sys.argv[1])
recs = [json.loads(l) for l in (d / "server.jsonl").read_text().splitlines() if l.strip()]
recv = [r for r in recs if r["kind"] == "recv"]
enc = [r for r in recs if r["kind"] == "encode"]
t0 = min(r["t"] for r in recs) if recs else 0
out = {"received_frames": len(recv), "encoded_frames": len(enc),
       "received_sizes": Counter(f'{r["w"]}x{r["h"]} {r["fmt"]}' for r in recv).most_common(),
       "encoded_sizes": Counter(f'{r["w"]}x{r["h"]} {r["codec"]} in={r["in_fmt"]}' for r in enc).most_common(),
       "queued>1": sum(r["queued"] > 1 for r in recv), "out_same_object": sum(r.get("out_is_input_object", False) for r in recv)}
sec = defaultdict(lambda: {"recv": 0, "recv_size": Counter(), "enc": 0, "bytes": 0, "target": [], "psnr": [], "proc": []})
for r in recv:
    s = sec[int(r["t"] - t0)]; s["recv"] += 1; s["recv_size"][f'{r["w"]}x{r["h"]}'] += 1
    if "psnr_vs_source" in r: s["psnr"].append(r["psnr_vs_source"])
    if "process_ms" in r: s["proc"].append(r["process_ms"])
for r in enc:
    s = sec[int(r["t"] - t0)]; s["enc"] += 1; s["bytes"] += r["bytes"]; s["target"].append(r["target_bitrate"])
rows = []
for k in sorted(sec):
    s = sec[k]
    rows.append({"s": k, "recv_fps": s["recv"], "recv_size": dict(s["recv_size"]), "enc_fps": s["enc"],
                 "out_kbps": round(s["bytes"] * 8 / 1000), "target_kbps": round(max(s["target"]) / 1000) if s["target"] else None,
                 "psnr_uplink": round(sum(s["psnr"]) / len(s["psnr"]), 2) if s["psnr"] else None,
                 "proc_ms_med": sorted(s["proc"])[len(s["proc"]) // 2] if s["proc"] else None})
out["per_second"] = rows
b = json.loads((d / "browser.json").read_text()) if (d / "browser.json").exists() else {}
out["browser_video"] = [{"t": x["t"], "v": [(v["w"], v["h"], v["cw"], v["ch"], v["decoded"], v["dropped"]) for v in (x["videos"] or [])]} for x in b.get("samples", [])]
out["browser_frame"] = b.get("browser_frame")
(d / "summary.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k not in ("per_second", "browser_video")}, indent=1))
for r in rows: print(r)
print("browser (w,h,clientW,clientH,decoded,dropped) every 4 s:", [x for x in out["browser_video"]][::4])
