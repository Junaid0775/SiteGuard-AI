"""Pools every saved start-test result into one summary for the start-failure diagnostic report.

Reads saved logs only. Starts nothing, touches no camera and writes only logs/start_failure_summary.json.
"""
import json
import math
import statistics
from pathlib import Path

LOGS = Path(__file__).resolve().parents[1] / "logs"
PLAIN_IMMEDIATE = {"original_40", "A_plain_immediate", "A2_plain"}
SERVER_WRAPPED = {"C_serverlog_immediate", "instrumented_immediate", "instrumented_delayed"}


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Fisher exact test on [[a, b], [c, d]]; two-sided by summing tables no more likely than the observed one."""
    n1, n2, k = a + b, c + d, a + c
    total = math.comb(n1 + n2, k)
    prob = lambda x: math.comb(n1, x) * math.comb(n2, k - x) / total
    observed = prob(a)
    return round(sum(p for x in range(max(0, k - n2), min(n1, k) + 1) if (p := prob(x)) <= observed * (1 + 1e-9)), 5)


def browser_evidence(tag: str) -> dict:
    path = LOGS / tag / "browser.json"
    if not path.exists():
        return {}
    b = json.loads(path.read_text())
    samples = b.get("samples", [])
    first = lambda test: next((s["t"] for s in samples if test(s)), None)
    cpu = [s["server_cpu_pct"] for s in samples if 2 <= s["t"] <= 4 and s.get("server_cpu_pct") is not None]
    return {"clicked_start": b.get("clicked_start"), "clicked_stop": b.get("clicked_stop"),
            "first_real_video_s": first(lambda s: s["videos"] and s["videos"][0]["w"] > 2),
            "placeholder_2x2_s": first(lambda s: s["videos"] and s["videos"][0]["w"] == 2 and s["videos"][0]["h"] == 2),
            "video_removed_s": first(lambda s: not s["videos"]) if not b.get("clicked_stop") else None,
            "server_cpu_2_to_4s": round(statistics.median(cpu), 1) if cpu else None}


rows = [{"tag": f"start_{x['setting']}_{x['round']}", "arm": "original_40", "setting": x["setting"], "round": x["round"], "ok": x["ok"]}
        for x in json.loads((LOGS / "start_reliability.json").read_text())]
for name in ("start_matrix.json", "start_matrix2.json"):
    rows += [{k: x.get(k) for k in ("tag", "arm", "setting", "round", "ok", "browser_stages_ms", "control_changes_ms")}
             for x in json.loads((LOGS / name).read_text())]
rows += [{"tag": x["tag"], "arm": f"instrumented_{x['condition']}", "setting": x["setting"], "round": x["round"], "ok": x["ok"]}
         for x in json.loads((LOGS / "start_diagnostics_analysis.json").read_text())]
for r in rows:
    r["evidence"] = browser_evidence(r["tag"])


def tally(selected: list) -> dict:
    failed = [r for r in selected if not r["ok"]]
    return {"starts": len(selected), "connected": len(selected) - len(failed), "failed": len(failed), "failed_tags": [r["tag"] for r in failed]}


arms = {arm: tally([r for r in rows if r["arm"] == arm]) for arm in dict.fromkeys(r["arm"] for r in rows)}
unwrapped = [r for r in rows if r["arm"] not in SERVER_WRAPPED]
wrapped = [r for r in rows if r["arm"] in SERVER_WRAPPED]
pools = {"plain_immediate": tally([r for r in rows if r["arm"] in PLAIN_IMMEDIATE]),
         "plain_delayed": tally([r for r in rows if r["arm"] == "B_plain_delayed"]),
         "server_not_wrapped": tally(unwrapped), "server_wrapped": tally(wrapped)}
by_bitrate = {s: tally([r for r in unwrapped if r["setting"] == s]) for s in ("library", "2.5M", "4M", "6M")}


def compare(x: dict, y: dict) -> float:
    return fisher_two_sided(x["failed"], x["connected"], y["failed"], y["connected"])


tests = {"A_immediate_vs_B_delayed": compare(arms["A_plain_immediate"], arms["B_plain_delayed"]),
         "plain_immediate_vs_plain_delayed": compare(pools["plain_immediate"], pools["plain_delayed"]),
         "server_not_wrapped_vs_wrapped": compare(pools["server_not_wrapped"], pools["server_wrapped"]),
         "library_vs_2.5M": compare(by_bitrate["library"], by_bitrate["2.5M"])}
cpu = {label: [r["evidence"]["server_cpu_2_to_4s"] for r in unwrapped if r["ok"] is want and r["evidence"].get("server_cpu_2_to_4s") is not None]
       for label, want in (("connected", True), ("failed", False))}
cpu_summary = {k: {"n": len(v), "median": statistics.median(v), "min": min(v), "max": max(v)} for k, v in cpu.items() if v}
failures = [{k: r.get(k) for k in ("tag", "arm", "setting", "round", "evidence", "browser_stages_ms", "control_changes_ms")} for r in rows if not r["ok"]]
summary = {"total_starts": len(rows), "arms": arms, "pools": pools, "unwrapped_by_bitrate": by_bitrate, "fisher_two_sided_p": tests,
           "server_cpu_pct_2_to_4s_after_start": cpu_summary, "failures": failures}
(LOGS / "start_failure_summary.json").write_text(json.dumps(summary, indent=1))

print("total", len(rows))
for k, v in arms.items():
    print(f"{k:26s} {v['connected']:>3}/{v['starts']:<3} failed {v['failed']}")
print("pools", {k: f"{v['failed']}/{v['starts']} failed" for k, v in pools.items()})
print("bitrate", {k: f"{v['failed']}/{v['starts']} failed" for k, v in by_bitrate.items()})
print("fisher", tests)
print("cpu", cpu_summary)
for f in failures:
    e = f["evidence"]
    print(f"{f['tag']:38s} real_video={e.get('first_real_video_s')} 2x2={e.get('placeholder_2x2_s')} removed={e.get('video_removed_s')} cpu2-4s={e.get('server_cpu_2_to_4s')}")
