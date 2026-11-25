"""Re-analyse the saved raw logs of start_diagnostics.py (no new run).

Correction to the first classifier: START/STOP clicks cannot be read from the page's click listener, because Chrome reuses the
iframe's initial about:blank window, so that listener stayed on the discarded document (the RTCPeerConnection and camera
wrappers live on the window and are unaffected). The click time and result therefore come from the harness (t_click, clicked),
and a control reset is a change back to START between the START click and the harness's own STOP click.
"""
import json, statistics as st, sys
from collections import Counter
from pathlib import Path

LOGS = Path(__file__).resolve().parents[1] / "logs"
CHAIN = ("camera_acquired", "browser_pc_created", "offer_created", "offer_reached_server", "answer_created_on_server", "answer_applied_in_browser",
         "ice_connected", "peer_connected", "remote_track", "first_server_frame", "first_displayed_frame")


def analyse(tag, setting, condition, rnd):
    d = LOGS / "diag" / tag
    if not (d / "events.json").exists():
        return {"tag": tag, "setting": setting, "condition": condition, "round": rnd, "ok": False, "failed_at": "harness: no events.json"}
    raw = json.loads((d / "events.json").read_text())
    run, stage = raw["run"], raw["stage"]
    t0, t_stop = run["t_click"], run["t_stop"]
    ev = sorted([e for e in run["events"] + stage if e["t"] >= t0 - 50], key=lambda e: e["t"])

    def first(name, **want):
        for e in ev:
            if e["name"] == name and all(e.get(k) in (v if isinstance(v, tuple) else (v,)) for k, v in want.items()):
                return e["t"] - t0
        return None

    recv = [r for r in (json.loads(l) for l in (d / "server.jsonl").read_text().splitlines() if l.strip()) if r.get("kind") == "recv"]
    times = {"camera_acquired": first("gum_ok"), "browser_pc_created": first("pc_created"), "offer_created": first("setLocalDescription_ok"),
             "offer_reached_server": first("srv_setRemoteDescription_call"), "answer_created_on_server": first("srv_setLocalDescription_ok"),
             "answer_applied_in_browser": first("setRemoteDescription_ok"), "ice_connected": first("iceconnectionstatechange", state=("connected", "completed")),
             "peer_connected": first("connectionstatechange", state="connected"), "remote_track": first("track"),
             "first_server_frame": int(recv[0]["t"] * 1000) - t0 if recv else None, "first_displayed_frame": first("first_frame")}
    failed_at = None if run["clicked"] else "start_click_had_no_target"
    failed_at = failed_at or next((k for k in CHAIN if times[k] is None), None)
    resets = [e["t"] - t0 for e in ev if e["name"] == "control" and e["labels"].upper() == "START" and t0 < e["t"] < t_stop - 20]
    closes = [e["t"] - t0 for e in ev if e["name"] == "close_call" and e["t"] < t_stop - 20]
    srv_closes = [e["t"] - t0 for e in ev if e["name"] == "srv_close_call" and e["t"] < t_stop - 20]
    state_at_click = run["script_state_at_click"]
    srv_runs = [e for e in stage if e["name"].startswith("script_") and -1500 <= e["t"] - t0 <= 12000]
    return {"tag": tag, "setting": setting, "condition": condition, "round": rnd, "ok": failed_at is None and bool(recv), "failed_at": failed_at, "times_ms": times,
            "server_frames": len(recv), "control_resets_ms": resets, "browser_close_before_stop_ms": closes, "server_close_before_stop_ms": srv_closes,
            "script_state_at_click": state_at_click, "click_after_nav_ms": t0 - run["t_nav"], "click_after_button_ms": t0 - run["t_button"],
            "interrupted_script_runs_after_click": sum(1 for e in srv_runs if e["name"] == "script_interrupted" and e["t"] >= t0),
            "script_runs_after_click": sum(1 for e in srv_runs if e["name"] == "script_start" and e["t"] >= t0), "browser_errors": [e for e in ev if e["name"].endswith("_err")][:2],
            "gum": next(({"w": e.get("w"), "h": e.get("h"), "fps": e.get("fps")} for e in ev if e["name"] == "gum_ok"), None)}


src = json.loads((LOGS / "start_diagnostics.json").read_text())["runs"]
runs = [analyse(r["tag"], r["setting"], r["condition"], r["round"]) for r in src]
(LOGS / "start_diagnostics_analysis.json").write_text(json.dumps(runs, indent=1))
for c in ("immediate", "delayed"):
    rr = [r for r in runs if r["condition"] == c]; ok = [r for r in rr if r["ok"]]
    print(f"\n{c}: connected {len(ok)}/{len(rr)}", {s: f'{sum(r["ok"] for r in rr if r["setting"]==s)}/{sum(1 for r in rr if r["setting"]==s)}' for s in ("library", "2.5M", "4M", "6M")})
    print("  failed at:", dict(Counter(r["failed_at"] for r in rr if not r["ok"])))
    print("  script state at click, all:", dict(Counter(r["script_state_at_click"] for r in rr)), "| failed:", dict(Counter(r["script_state_at_click"] for r in rr if not r["ok"])))
    print("  click after page navigation, median ms:", st.median(r["click_after_nav_ms"] for r in rr), "| control resets:", sum(bool(r["control_resets_ms"]) for r in rr))
    for k in CHAIN:
        v = [r["times_ms"][k] for r in ok if r["times_ms"].get(k) is not None]
        if v: print(f"    {k:28s} n={len(v):2d} median {st.median(v):6.0f}  min {min(v):5d}  max {max(v):5d} ms")
print("\nFAILED STARTS")
for r in runs:
    if not r["ok"]:
        print(json.dumps({k: r.get(k) for k in ("tag", "failed_at", "script_state_at_click", "click_after_nav_ms", "control_resets_ms", "browser_close_before_stop_ms", "server_close_before_stop_ms", "script_runs_after_click", "interrupted_script_runs_after_click", "browser_errors")}), "reached:", {k: v for k, v in r.get("times_ms", {}).items() if v is not None})
