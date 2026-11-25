"""Why do some WebRTC starts never connect? Instrumented immediate-click versus delayed-click comparison.

    caffeinate -i .venv/bin/python experiments/camera_quality_audit/tools/start_diagnostics.py --rounds 6

Synthetic camera only (Chrome's fake device playing the moving Y4M). Fresh server and fresh Chrome per start, as in the
40-start test. Production code is not modified and the real database and evidence are not used.

Conditions
  immediate  same timing as start_reliability.py: click START as soon as the button exists
  delayed    wait until Streamlit reports script state notRunning for 1 continuous second, then 3 s more, then click

Every start records, in milliseconds after the click: camera acquired, browser peer connection, offer, ICE gathering, offer
and answer at the server, answer in the browser, ICE and DTLS connected, remote track, first server frame, first displayed
frame; plus video-control resets (STOP back to START without a STOP click) and Streamlit script runs around the click.
Outputs: logs/diag/<tag>/{server.jsonl,stage.jsonl,events.json} and logs/start_diagnostics.json. No frame is saved.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "experiments" / "camera_quality_audit"
LOGS = AUDIT / "logs"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
Y4M = Path(tempfile.gettempdir()) / "sg-moving-1280x720.y4m"
PORT, DEBUG_PORT = 8612, 9335
SETTINGS = {"library": "library", "2.5M": "2500000:1250000:2500000", "4M": "4000000:2000000:4000000", "6M": "6000000:3000000:6000000"}

INJECT = r"""
(() => {
  const where = window === window.top ? 'top' : 'iframe';
  const sink = () => { try { const t = window.top; if (!t.__sgAll) t.__sgAll = []; return t.__sgAll; }
                       catch (e) { if (!window.__sgLocal) window.__sgLocal = []; return window.__sgLocal; } };
  const log = (name, extra) => { try { sink().push(Object.assign({name, where, t: Date.now()}, extra || {})); } catch (e) {} };
  log('frame_start', {path: location.pathname});
  window.addEventListener('pagehide', () => log('frame_unload', {path: location.pathname}));
  document.addEventListener('click', e => {
    const b = e.target && e.target.closest && e.target.closest('button');
    if (b) log('button_click', {label: (b.innerText || '').trim(), disabled: !!b.disabled});
  }, true);
  if (where === 'top') {
    let last;
    setInterval(() => {
      const el = document.querySelector('[data-testid="stApp"]');
      const s = el ? el.getAttribute('data-test-script-state') : null;
      if (s !== last) { log('script_state', {state: s}); last = s; }
    }, 50);
    return;
  }
  const Native = window.RTCPeerConnection;
  if (Native) {
    const Wrapped = function (...a) {
      const pc = new Native(...a);
      window.__sgPc = (window.__sgPc || 0) + 1;
      const id = window.__sgPc;
      log('pc_created', {pc: id});
      const on = (ev, get) => pc.addEventListener(ev, () => log(ev, {pc: id, state: get()}));
      on('signalingstatechange', () => pc.signalingState);
      on('icegatheringstatechange', () => pc.iceGatheringState);
      on('iceconnectionstatechange', () => pc.iceConnectionState);
      on('connectionstatechange', () => pc.connectionState);
      pc.addEventListener('track', e => log('track', {pc: id, kind: e.track.kind}));
      for (const m of ['createOffer', 'setLocalDescription', 'setRemoteDescription', 'close']) {
        const orig = pc[m].bind(pc);
        pc[m] = (...args) => {
          log(m + '_call', {pc: id, type: args[0] && args[0].type});
          const r = orig(...args);
          if (r && r.then) r.then(() => log(m + '_ok', {pc: id}), err => log(m + '_err', {pc: id, error: String(err)}));
          return r;
        };
      }
      return pc;
    };
    Wrapped.prototype = Native.prototype;
    Object.setPrototypeOf(Wrapped, Native);
    window.RTCPeerConnection = Wrapped;
  }
  const md = navigator.mediaDevices;
  if (md && md.getUserMedia) {
    const gum = md.getUserMedia.bind(md);
    md.getUserMedia = c => { log('gum_call');
      return gum(c).then(s => { const v = s.getVideoTracks()[0]; const st = v && v.getSettings ? v.getSettings() : {};
        log('gum_ok', {w: st.width, h: st.height, fps: st.frameRate}); return s; },
        e => { log('gum_err', {error: String(e)}); throw e; }); };
  }
  const seen = new WeakSet();
  let lastLabels, lastVideos;
  setInterval(() => {
    document.querySelectorAll('video').forEach(v => {
      if (seen.has(v)) return;
      seen.add(v);
      log('video_element');
      v.addEventListener('loadedmetadata', () => log('video_metadata', {w: v.videoWidth, h: v.videoHeight}));
      if (v.requestVideoFrameCallback) v.requestVideoFrameCallback((now, m) => log('first_frame', {w: m.width, h: m.height}));
    });
    const labels = [...document.querySelectorAll('button')].map(b => (b.innerText || '').trim())
      .filter(x => /^(START|STOP)$/i.test(x)).join(',');
    const n = document.querySelectorAll('video').length;
    if (labels !== lastLabels) { log('control', {labels}); lastLabels = labels; }
    if (n !== lastVideos) { log('video_count', {n}); lastVideos = n; }
  }, 100);
})();
"""

CLICK_JS = """((label) => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim().toUpperCase() === label);
  if (b) { b.click(); return true; } return false; })"""
HAS_JS = "[...document.querySelectorAll('button')].some(x => x.innerText.trim().toUpperCase() === 'START')"


def now_ms() -> int:
    return int(time.time() * 1000)


async def drive(ws_url: str, url: str, condition: str, seconds: float) -> dict:
    ws = await websockets.connect(ws_url, max_size=100 * 1024 * 1024, ping_interval=None)
    n = 0

    async def call(method, params=None):
        nonlocal n
        n += 1
        await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), 30))
            if m.get("id") == n:
                return m.get("result", m.get("error", {}))

    async def frame_ctx():
        tree = (await call("Page.getFrameTree")).get("frameTree", {})
        for child in tree.get("childFrames", []):
            u = child["frame"].get("url", "").lower()
            if "webrtc" in u or "component" in u:
                return (await call("Page.createIsolatedWorld", {"frameId": child["frame"]["id"]})).get("executionContextId")
        return None

    async def ev(expr, ctx_id=None):
        p = {"expression": expr, "returnByValue": True, "awaitPromise": True}
        if ctx_id is not None:
            p["contextId"] = ctx_id
        return (await call("Runtime.evaluate", p)).get("result", {}).get("value")

    await call("Page.enable")
    await call("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT})
    await call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    t_nav = now_ms()
    await call("Page.navigate", {"url": url})
    ctx_id, deadline = None, time.time() + 45
    while ctx_id is None and time.time() < deadline:  # same 1-second polling as the 40-start test
        await asyncio.sleep(1)
        ctx_id = await frame_ctx()
    if ctx_id is None:
        return {"error": "component iframe not found", "t_nav": t_nav}
    while time.time() < deadline and not await ev(HAS_JS, ctx_id):
        await asyncio.sleep(0.1)
    t_button = now_ms()
    t_idle = None
    if condition == "delayed":
        idle_since = None
        while time.time() < deadline:
            state = await ev("document.querySelector('[data-testid=\"stApp\"]')?.getAttribute('data-test-script-state')")
            if state == "notRunning":
                idle_since = idle_since or time.time()
                if time.time() - idle_since >= 1.0:
                    break
            else:
                idle_since = None
            await asyncio.sleep(0.05)
        t_idle = now_ms()
        await asyncio.sleep(3.0)
        ctx_id = await frame_ctx() or ctx_id
    script_at_click = await ev("document.querySelector('[data-testid=\"stApp\"]')?.getAttribute('data-test-script-state')")
    t_click = now_ms()
    clicked = bool(await ev(CLICK_JS + "('START')", ctx_id))
    await asyncio.sleep(seconds)
    video = await ev("(()=>{const f=[...document.querySelectorAll('iframe')].map(i=>{try{return i.contentDocument}catch(e){return null}}).filter(Boolean);"
                     "const v=f.flatMap(d=>[...d.querySelectorAll('video')])[0];return v?{w:v.videoWidth,h:v.videoHeight,ready:v.readyState}:null})()")
    frame_id_ctx = await frame_ctx() or ctx_id
    t_stop = now_ms()
    stopped = bool(await ev(CLICK_JS + "('STOP')", frame_id_ctx))
    await asyncio.sleep(1.2)
    events = await ev("window.__sgAll || []") or []
    await ws.close()
    return {"t_nav": t_nav, "t_button": t_button, "t_idle": t_idle, "t_click": t_click, "t_stop": t_stop, "clicked": clicked, "stopped": stopped,
            "script_state_at_click": script_at_click, "video_at_end": video, "events": events}


def classify(run: dict, stage_events: list[dict], server_recs: list[dict]) -> dict:
    """Times are ms after the click. The failure stage is the first step of the chain that never happened."""
    t0 = run["t_click"]
    ev = sorted([e for e in run["events"] if e["t"] >= t0 - 50] + [e for e in stage_events if e["t"] >= t0 - 50], key=lambda e: e["t"])

    def first(name, **want):
        for e in ev:
            if e["name"] == name and all(e.get(k) in (v if isinstance(v, tuple) else (v,)) for k, v in want.items()):
                return e["t"] - t0
        return None

    recv = [r for r in server_recs if r.get("kind") == "recv"]
    chain = [("start_click_seen", first("button_click", label="START")),
             ("camera_acquired", first("gum_ok")),
             ("browser_pc_created", first("pc_created")),
             ("offer_created", first("setLocalDescription_ok")),
             ("ice_gathering_complete", first("icegatheringstatechange", state="complete")),
             ("offer_reached_server", first("srv_setRemoteDescription_call")),
             ("answer_created_on_server", first("srv_setLocalDescription_ok")),
             ("answer_applied_in_browser", first("setRemoteDescription_ok")),
             ("ice_connected", first("iceconnectionstatechange", state=("connected", "completed"))),
             ("peer_connected", first("connectionstatechange", state="connected")),
             ("remote_track", first("track")),
             ("first_server_frame", int(recv[0]["t"] * 1000) - t0 if recv else None),
             ("first_displayed_frame", first("first_frame"))]
    failed_at = next((k for k, v in chain if v is None), None)
    labels = [(e["t"] - t0, e["labels"]) for e in ev if e["name"] == "control"]
    stop_click = first("button_click", label="STOP")
    resets = [t for (t, l), (_, prev) in zip(labels[1:], labels) if "STOP" in prev.upper() and l.upper() == "START" and (stop_click is None or t < stop_click)]
    script_runs = [{"name": e["name"], "t": e["t"] - t0, **({"exc": e["exc"]} if "exc" in e else {}),
                    **({"playing": e.get("playing"), "signalling": e.get("signalling")} if e["name"] == "script_end" else {})}
                   for e in stage_events if e["name"].startswith("script_") and -6000 <= e["t"] - t0 <= 4000]
    return {"ok": failed_at is None and len(recv) > 0, "failed_at": failed_at, "times_ms": dict(chain), "server_frames": len(recv),
            "control_resets_ms": resets, "browser_pc_close_ms": first("close_call"), "server_pc_close_ms": first("srv_close_call"),
            "browser_errors": [e for e in ev if e["name"].endswith("_err")][:3], "script_runs_around_click": script_runs,
            "connection_time_ms": dict(chain).get("peer_connected"), "first_frame_time_ms": dict(chain).get("first_displayed_frame")}


def one_start(tag: str, bitrate: str, condition: str, seconds: float) -> dict:
    out = LOGS / "diag" / tag
    out.mkdir(parents=True, exist_ok=True)
    for f in ("server.jsonl", "stage.jsonl"):
        (out / f).write_text("")
    tmp = Path(tempfile.mkdtemp(prefix="sg-probe-"))
    env = dict(os.environ, SG_PROBE_LOG=str(out / "server.jsonl"), SG_PROBE_STAGE_LOG=str(out / "stage.jsonl"),
               SG_PROBE_MODE="pipeline", SG_PROBE_BITRATE=bitrate)
    server = subprocess.Popen([str(ROOT / ".venv/bin/streamlit"), "run", str(AUDIT / "tools/webrtc_probe_diag_app.py"), "--server.port", str(PORT),
                               "--server.address", "127.0.0.1", "--server.headless", "true"], cwd=ROOT, env=env,
                              stdout=open(out / "probe_server.log", "w"), stderr=subprocess.STDOUT)
    chrome = None
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=1).read() == b"ok":
                    break
            except Exception:
                time.sleep(0.5)
        chrome = subprocess.Popen([CHROME, "--headless=new", "--no-first-run", "--no-default-browser-check", f"--remote-debugging-port={DEBUG_PORT}",
                                   f"--user-data-dir={tmp / 'profile'}", "--autoplay-policy=no-user-gesture-required", "--use-fake-ui-for-media-stream",
                                   "--use-fake-device-for-media-stream", f"--use-file-for-fake-video-capture={Y4M}", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        for _ in range(50):
            try:
                page = [t for t in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=1).read()) if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        run = asyncio.run(asyncio.wait_for(drive(page["webSocketDebuggerUrl"], f"http://127.0.0.1:{PORT}/", condition, seconds), 90))
        if "error" in run:
            return {"ok": False, "failed_at": "harness: " + run["error"]}
        stage_events = [json.loads(l) for l in (out / "stage.jsonl").read_text().splitlines() if l.strip()]
        server_recs = [json.loads(l) for l in (out / "server.jsonl").read_text().splitlines() if l.strip()]
        (out / "events.json").write_text(json.dumps({"run": run, "stage": stage_events}, indent=0))
        r = classify(run, stage_events, server_recs)
        r.update(clicked=run["clicked"], stopped=run["stopped"], script_state_at_click=run["script_state_at_click"],
                 button_after_nav_ms=run["t_button"] - run["t_nav"], click_after_nav_ms=run["t_click"] - run["t_nav"],
                 click_after_button_ms=run["t_click"] - run["t_button"], video_at_end=run["video_at_end"])
        return r
    except Exception as exc:
        return {"ok": False, "failed_at": f"harness: {type(exc).__name__}: {exc}"}
    finally:
        if chrome:
            chrome.terminate()
            try:
                chrome.wait(timeout=10)
            except subprocess.TimeoutExpired:
                chrome.kill()
        server.send_signal(signal.SIGINT)
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--rounds", type=int, default=6)
    a.add_argument("--seconds", type=float, default=7)
    a.add_argument("--settings", nargs="*", default=list(SETTINGS))
    args = a.parse_args()
    if not Y4M.exists():
        raise SystemExit(f"{Y4M} missing: run one --content moving probe first")
    results, path = [], LOGS / "start_diagnostics.json"
    for rnd in range(1, args.rounds + 1):
        order = [(s, c) for s in args.settings for c in ("immediate", "delayed")]
        order = order[rnd % len(order):] + order[:rnd % len(order)]  # rotate, so time effects do not favour one condition
        for setting, condition in order:
            if '"AppleClamshellState" = Yes' in subprocess.run("ioreg -r -k AppleClamshellState -d 4", shell=True, capture_output=True, text=True).stdout:
                print("STOPPED: lid closed", flush=True)
                path.write_text(json.dumps({"complete": False, "runs": results}, indent=1))
                sys.exit(2)
            tag = f"{setting}_{condition}_r{rnd}"
            r = one_start(tag, SETTINGS[setting], condition, args.seconds)
            r.update(tag=tag, setting=setting, condition=condition, round=rnd)
            results.append(r)
            print(json.dumps({k: r.get(k) for k in ("tag", "ok", "failed_at", "connection_time_ms", "first_frame_time_ms", "control_resets_ms", "script_state_at_click")}), flush=True)
            path.write_text(json.dumps({"complete": False, "runs": results}, indent=1))
            time.sleep(1)
    path.write_text(json.dumps({"complete": True, "runs": results}, indent=1))
    print("done", flush=True)


if __name__ == "__main__":
    main()
