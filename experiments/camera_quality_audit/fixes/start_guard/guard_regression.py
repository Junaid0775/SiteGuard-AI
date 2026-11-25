"""Regression scenarios for the live-video start guard. Synthetic camera only; temporary database and evidence folder.

Usage: guard_regression.py --mode off|candidate|production --target dashboard|probe [--scenarios a,b] [--repeat N]
Each scenario gets a new Streamlit server and a new headless Chrome. Chrome's fake camera device is forced, so the
physical camera cannot be opened. Results are written to logs/guard/.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / "experiments/camera_quality_audit/logs/guard"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
Y4M = Path(tempfile.gettempdir()) / "sg-moving-1280x720.y4m"
PORT, CDP_PORT = 8612, 9335

INJECT = r"""(() => {
  if (window === window.top) return;
  const top = window.top;
  top.__sgTracks = top.__sgTracks || []; top.__sgPcs = top.__sgPcs || [];
  const Native = window.RTCPeerConnection;
  if (Native) {
    const Wrapped = function (...a) {
      if (top.__sgBreakIce) { top.__sgBreakIce = false; a[0] = Object.assign({}, a[0] || {}, {iceTransportPolicy: 'relay'}); }
      const pc = new Native(...a); top.__sgPcs.push(pc); return pc;
    };
    Wrapped.prototype = Native.prototype; Object.setPrototypeOf(Wrapped, Native); window.RTCPeerConnection = Wrapped;
  }
  const md = navigator.mediaDevices;
  if (md && md.getUserMedia) {
    const gum = md.getUserMedia.bind(md);
    md.getUserMedia = c => {
      if (top.__sgFailGum) { top.__sgFailGum = false; return Promise.reject(new DOMException('Test: camera unavailable', 'NotReadableError')); }
      return gum(c).then(s => { s.getTracks().forEach(t => top.__sgTracks.push(t)); return s; });
    };
  }
})();"""
FRAME = "[...document.querySelectorAll('iframe')].find(i => /webrtc|component/i.test(i.src || ''))"
STATE_JS = f"""(() => {{
  const ifr = {FRAME}; let d = null; try {{ d = ifr && ifr.contentDocument; }} catch (e) {{}}
  const v = d && d.querySelector('video');
  const q = v && v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : null;
  const labels = d ? [...d.querySelectorAll('button')].map(b => (b.innerText || '').trim().toUpperCase()).filter(x => x === 'START' || x === 'STOP') : [];
  const radio = [...document.querySelectorAll('[data-testid="stSidebar"] input[type=radio]')].find(r => r.checked);
  return {{component: !!ifr, labels, video: v ? {{w: v.videoWidth, h: v.videoHeight, decoded: q ? q.totalVideoFrames : 0}} : null,
    tracks: (window.__sgTracks || []).map(t => t.readyState), pcs: (window.__sgPcs || []).map(p => p.connectionState),
    page: radio ? (radio.closest('label') || {{}}).innerText : null,
    text: d ? (d.body.innerText || '').slice(0, 200) : ''}};
}})()"""
CLICK_JS = f"""((label) => {{ const ifr = {FRAME}; const d = ifr && ifr.contentDocument;
  const b = d && [...d.querySelectorAll('button')].find(x => x.innerText.trim().toUpperCase() === label);
  if (b && !b.disabled) {{ b.click(); return true; }} return false; }})"""
NAV_JS = """((name) => { const l = [...document.querySelectorAll('[data-testid="stSidebar"] label')].find(x => x.innerText.trim() === name);
  if (l) { l.click(); return true; } return false; })"""


class Harness:
    def __init__(self, mode: str, target: str, tag: str, app_path: str | None = None) -> None:
        self.mode, self.target, self.tag, self.app_path = mode, target, tag, app_path
        self.dir = OUT / tag
        self.natural_failures = 0
        self.console: list = []
        self.start_failures: list = []

    async def __aenter__(self) -> "Harness":
        try:
            return await self._launch()
        except BaseException:  # __aexit__ does not run when __aenter__ fails, and a leftover server would block every later scenario
            await self.__aexit__()
            raise

    async def _launch(self) -> "Harness":
        for port in (PORT, CDP_PORT):
            with socket.socket() as sock:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"port {port} is already in use")
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="sg-guard-"))
        self.log, self.status_path, self.cmd_path = self.dir / "lifecycle.jsonl", self.dir / "status.json", self.dir / "cmd.json"
        self.log.write_text("")
        env = dict(os.environ, SG_GUARD_MODE=self.mode, SG_GUARD_TARGET=self.target, SG_GUARD_LOG=str(self.log), SG_GUARD_STATUS=str(self.status_path),
                   SG_GUARD_CMD=str(self.cmd_path), SG_PROBE_LOG=str(self.dir / "server.jsonl"), SG_PROBE_MODE="pipeline", SG_PROBE_BITRATE="library",
                   SITEGUARD_EVENTS_DB=str(self.tmp / "test.db"), SITEGUARD_EVIDENCE_DIR=str(self.tmp / "evidence"))
        if self.app_path:
            env["SG_GUARD_APP"] = str(self.app_path)
        self.server = subprocess.Popen([str(ROOT / ".venv/bin/streamlit"), "run", str(HERE / "guard_test_app.py"), "--server.port", str(PORT),
                                        "--server.address", "127.0.0.1", "--server.headless", "true"], cwd=ROOT, env=env,
                                       stdout=open(self.dir / "server.log", "w"), stderr=subprocess.STDOUT)
        for _ in range(80):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=1).read() == b"ok":
                    break
            except Exception:
                time.sleep(0.25)
        self.chrome = subprocess.Popen([CHROME, "--headless=new", "--no-first-run", "--no-default-browser-check", f"--remote-debugging-port={CDP_PORT}",
                                        f"--user-data-dir={self.tmp / 'profile'}", "--autoplay-policy=no-user-gesture-required", "--use-fake-ui-for-media-stream",
                                        "--use-fake-device-for-media-stream", f"--use-file-for-fake-video-capture={Y4M}", "about:blank"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        for _ in range(60):
            try:
                page = [t for t in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=1).read()) if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        self.ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024, ping_interval=None)
        self.n = 0
        await self.call("Page.enable")
        await self.call("Runtime.enable")
        await self.call("Log.enable")
        await self.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        await self.call("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT})
        await self.call("Page.navigate", {"url": f"http://127.0.0.1:{PORT}/" + ("?page=Live%20Monitoring" if self.target == "dashboard" else "")})
        ok, _ = await self.wait(lambda s: s["labels"] == ["START"], 60)
        if not ok:
            raise RuntimeError("START button did not appear")
        await asyncio.sleep(1.0)
        return self

    async def __aexit__(self, *exc) -> None:
        if getattr(self, "ws", None):
            try:
                await self.ws.close()
            except Exception:
                pass
        if getattr(self, "chrome", None):
            self.chrome.terminate()
            try:
                self.chrome.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.chrome.kill()
        if getattr(self, "server", None):
            self.server.send_signal(signal.SIGINT)
            try:
                self.server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.server.kill()
        if getattr(self, "tmp", None):
            shutil.rmtree(self.tmp, ignore_errors=True)
        for _ in range(40):  # the next scenario needs both ports free
            with socket.socket() as a, socket.socket() as b:
                if a.connect_ex(("127.0.0.1", PORT)) != 0 and b.connect_ex(("127.0.0.1", CDP_PORT)) != 0:
                    break
            await asyncio.sleep(0.25)

    async def call(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            m = json.loads(await asyncio.wait_for(self.ws.recv(), 30))
            if m.get("id") == self.n:
                return m.get("result", m.get("error", {}))
            event, params = m.get("method"), m.get("params", {})
            if event == "Runtime.exceptionThrown":
                self.console.append(("exception", str(params.get("exceptionDetails", {}).get("exception", {}).get("description") or params.get("exceptionDetails", {}).get("text"))[:240]))
            elif event == "Runtime.consoleAPICalled" and params.get("type") in ("error", "warning"):
                self.console.append((params["type"], " ".join(str(a.get("value") or a.get("description") or "") for a in params.get("args", []))[:240]))
            elif event == "Log.entryAdded" and params.get("entry", {}).get("level") in ("error", "warning"):
                self.console.append(("log", params["entry"].get("text", "")[:240]))

    async def js(self, expr: str):
        return (await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})).get("result", {}).get("value")

    async def state(self) -> dict:
        return await self.js(STATE_JS) or {"component": False, "labels": [], "video": None, "tracks": [], "pcs": [], "page": None, "text": ""}

    def status(self) -> dict:
        try:
            return json.loads(self.status_path.read_text())
        except (OSError, ValueError):
            return {}

    def events(self) -> list:
        return [json.loads(l) for l in self.log.read_text().splitlines() if l.strip()]

    def count(self, text: str) -> int:
        return sum(text in e["message"] for e in self.events())

    def command(self, **cmd) -> None:
        tmp = self.cmd_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cmd))
        tmp.replace(self.cmd_path)

    async def wait(self, predicate, timeout: float, interval: float = 0.1):
        t0 = time.time()
        while time.time() - t0 < timeout:
            s = await self.state()
            if predicate(s):
                return True, round(time.time() - t0, 2)
            await asyncio.sleep(interval)
        return False, round(time.time() - t0, 2)

    async def click(self, label: str, timeout: float = 10) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if await self.js(CLICK_JS + f"('{label}')"):
                return True
            await asyncio.sleep(0.1)
        return False

    async def navigate(self, name: str) -> bool:
        return bool(await self.js(NAV_JS + f"('{name}')"))

    async def advancing(self) -> bool:
        a = await self.state()
        if not a["video"]:
            return False
        await asyncio.sleep(1.2)
        b = await self.state()
        return bool(b["video"]) and b["video"]["w"] > 2 and b["video"]["decoded"] - a["video"]["decoded"] >= 10

    async def streaming(self, timeout: float = 15) -> bool:
        ok, _ = await self.wait(lambda s: s["video"] and s["video"]["w"] > 2 and s["video"]["decoded"] > 3, timeout)
        return ok and await self.advancing()

    async def start(self) -> bool:
        """Press START. With the guard off, one natural failure is retried so that control scenarios can reach their test step."""
        for attempt in range(2 if self.mode == "off" else 1):
            if not await self.click("START"):
                return False
            if await self.streaming():
                return True
            record = {"attempt": attempt + 1, "state": await self.state(), "workers_created": self.count("Create a new worker"), "console": self.console[-12:]}
            self.start_failures.append(record)
            (self.dir / f"start_failure_{len(self.start_failures)}.json").write_text(json.dumps(record, indent=1))
            if self.mode == "off" and attempt == 0:
                self.natural_failures += 1
                await self.wait(lambda s: s["labels"] == ["START"], 12)
        return False

    async def released(self, timeout: float = 15) -> dict:
        """Browser camera stopped and no peer connection open; server has no worker, decoder or processing thread.

        A connection in state "new" never opened a transport. The library's frontend leaves one such idle object after a
        camera error, with the guard on or off, so it does not count as an open connection.
        """
        browser, t_browser = await self.wait(lambda s: all(t == "ended" for t in s["tracks"]) and not any(p in ("connecting", "connected", "disconnected") for p in s["pcs"]) and not (s["video"] and s["video"]["w"] > 2), timeout)
        t0, server = time.time(), False
        while time.time() - t0 < timeout:
            st = self.status()
            if st and st.get("workers") == 0 and st.get("decoders") == 0 and st.get("processors") == 0:
                server = True
                break
            await asyncio.sleep(0.1)
        return {"camera_and_connection_closed": browser, "server_resources_released": server, "browser_s": t_browser, "server_s": round(time.time() - t0, 2)}

    def worker_running(self) -> bool:
        st = self.status()
        return (st.get("workers"), st.get("decoders"), st.get("processors")) == (1, 1, 1) and st.get("pc_states") == ["connected"]

    def no_server_exception(self) -> bool:
        text = (self.dir / "server.log").read_text(errors="ignore")
        return "Traceback" not in text


async def stop_and_check(h: Harness, checks: dict, prefix: str = "") -> None:
    checks[prefix + "stop_clicked"] = await h.click("STOP", 5)
    rel = await h.released()
    checks[prefix + "camera_and_connection_closed"] = rel["camera_and_connection_closed"]
    checks[prefix + "server_resources_released"] = rel["server_resources_released"]
    checks[prefix + "button_back_to_start"] = (await h.wait(lambda s: s["labels"] == ["START"], 8))[0]


async def scenario_jump(h: Harness) -> tuple[dict, dict]:
    """Requirement 1: a forced run-count jump on a live connection."""
    c: dict = {"stream_started": await h.start()}
    created = h.count("Create a new worker")
    h.command(cmd="jump")
    await asyncio.sleep(2.5)
    c["video_still_advancing"] = await h.advancing()
    c["server_worker_still_running"] = h.worker_running()
    c["no_library_reset"] = h.count("not rendered") == 0
    c["no_replacement_worker"] = h.count("Create a new worker") == created
    info = {"jumps_seen_by_guard": sum(e.get("logger") == "guard" for e in h.events())}
    if await h.click("STOP", 1):
        await h.released()
    return c, info


async def scenario_rerun_burst(h: Harness) -> tuple[dict, dict]:
    """Requirement 5: 40 forced reruns, 25 ms apart, on a live connection."""
    c: dict = {"stream_started": await h.start()}
    created = h.count("Create a new worker")
    h.command(cmd="rerun", n=40, interval_ms=25)
    await asyncio.sleep(3.0)
    c["video_still_advancing"] = await h.advancing()
    c["server_worker_still_running"] = h.worker_running()
    c["no_library_reset"] = h.count("not rendered") == 0
    c["no_replacement_worker"] = h.count("Create a new worker") == created
    info = {"jumps_seen_by_guard": sum(e.get("logger") == "guard" for e in h.events())}
    await stop_and_check(h, c)
    return c, info


async def scenario_navigate(h: Harness) -> tuple[dict, dict]:
    """Requirement 2: leaving Live Monitoring stops the connection; returning gives a clean, startable page."""
    c: dict = {"stream_started": await h.start()}
    c["navigated_away"] = await h.navigate("Safety Events")
    c["page_changed"] = (await h.wait(lambda s: (s["page"] or "").strip() == "Safety Events" and not s["component"], 15))[0]
    rel = await h.released(timeout=45)
    c["camera_and_connection_closed"] = rel["camera_and_connection_closed"]
    c["server_resources_released"] = rel["server_resources_released"]
    await asyncio.sleep(0.5)
    c["navigated_back"] = await h.navigate("Live Monitoring")
    c["back_shows_start"] = (await h.wait(lambda s: s["labels"] == ["START"], 20))[0]
    await asyncio.sleep(1.0)
    c["restart_works"] = await h.start()
    await stop_and_check(h, c, "after_restart_")
    return c, {"browser_release_s": rel["browser_s"], "server_release_s": rel["server_s"], "resets_logged": h.count("not rendered")}


async def scenario_rapid_navigation(h: Harness) -> tuple[dict, dict]:
    """Leave and return within about 150 ms: the page must end in a usable state either way."""
    c: dict = {"stream_started": await h.start()}
    await h.navigate("Safety Events")
    await asyncio.sleep(0.15)
    await h.navigate("Live Monitoring")
    await asyncio.sleep(7.0)
    s = await h.state()
    survived = s["labels"] == ["STOP"] and await h.advancing()
    if not survived:
        if s["labels"] == ["STOP"]:
            await h.click("STOP", 3)
        c["back_to_start_when_not_streaming"] = (await h.wait(lambda x: x["labels"] == ["START"], 12))[0]
        await asyncio.sleep(1.0)
        c["restart_works"] = await h.start()
    await stop_and_check(h, c, "final_")
    return c, {"stream_survived_rapid_flip": survived}


async def scenario_stop(h: Harness) -> tuple[dict, dict]:
    """Requirement 3: STOP releases the camera and WebRTC resources."""
    c: dict = {"stream_started": await h.start(), "worker_running_before_stop": False}
    c["worker_running_before_stop"] = h.worker_running()
    t0 = time.time()
    await stop_and_check(h, c)
    return c, {"stop_to_released_s": round(time.time() - t0, 2)}


async def scenario_cycles(h: Harness, cycles: int = 10) -> tuple[dict, dict]:
    """Requirement 4: repeated START and STOP in one browser session."""
    results, rss = [], []
    for _ in range(cycles):
        cycle: dict = {"stream_started": await h.start()}
        await stop_and_check(h, cycle)
        results.append(all(cycle.values()))
        rss.append(h.status().get("rss_mb"))
        await asyncio.sleep(0.5)
    st = h.status()
    c = {"all_cycles_passed": all(results), "no_workers_left": st.get("workers") == 0, "no_decoders_left": st.get("decoders") == 0, "no_processors_left": st.get("processors") == 0}
    return c, {"cycles": cycles, "passed": sum(results), "rss_mb_first": rss[0], "rss_mb_last": rss[-1], "threads_end": st.get("threads")}


async def scenario_fail_camera(h: Harness) -> tuple[dict, dict]:
    """Requirement 6: the camera is unavailable on the first attempt."""
    await h.js("window.__sgFailGum = true")
    await h.click("START")
    await asyncio.sleep(3.0)
    s = await h.state()
    c: dict = {"first_attempt_did_not_stream": not (s["video"] and s["video"]["w"] > 2)}
    if s["labels"] == ["STOP"]:
        await h.click("STOP", 3)
    c["back_to_start"] = (await h.wait(lambda x: x["labels"] == ["START"], 10))[0]
    await asyncio.sleep(1.0)
    c["retry_streams"] = await h.start()
    await stop_and_check(h, c, "after_retry_")
    return c, {"text_after_failure": s["text"][:120], "browser_connection_states_at_end": (await h.state())["pcs"]}


async def scenario_fail_ice(h: Harness) -> tuple[dict, dict]:
    """Requirement 6: ICE cannot connect on the first attempt (browser limited to relay candidates, and no relay exists)."""
    await h.js("window.__sgBreakIce = true")
    await h.click("START")
    await asyncio.sleep(1.0)
    returned, secs = await h.wait(lambda x: x["labels"] == ["START"], 25)
    c: dict = {"first_attempt_did_not_stream": not ((await h.state())["video"] or {}).get("w", 0) > 2}
    manual = False
    if not returned:
        manual = await h.click("STOP", 3)
    c["back_to_start"] = (await h.wait(lambda x: x["labels"] == ["START"], 12))[0]
    await asyncio.sleep(1.0)
    c["retry_streams"] = await h.start()
    await stop_and_check(h, c, "after_retry_")
    return c, {"returned_to_start_by_itself": returned, "seconds_waited": secs, "manual_stop_used": manual}


async def scenario_fail_drop(h: Harness) -> tuple[dict, dict]:
    """Requirement 6: the server connection drops after connecting (the visible form of the original failure)."""
    c: dict = {"stream_started": await h.start()}
    h.command(cmd="drop")
    returned, secs = await h.wait(lambda x: x["labels"] == ["START"], 15)
    c["button_returned_to_start"] = returned
    released = await h.released(timeout=10)
    c["resources_released_after_drop"] = released["camera_and_connection_closed"] and released["server_resources_released"]
    await asyncio.sleep(1.0)
    c["retry_streams"] = await h.start()
    await stop_and_check(h, c, "after_retry_")
    return c, {"seconds_to_start_button": secs}


SCENARIOS = {"jump": scenario_jump, "rerun_burst": scenario_rerun_burst, "navigate": scenario_navigate, "rapid_navigation": scenario_rapid_navigation,
             "stop": scenario_stop, "cycles": scenario_cycles, "fail_camera": scenario_fail_camera, "fail_ice": scenario_fail_ice, "fail_drop": scenario_fail_drop}
DASHBOARD_ONLY = {"navigate", "rapid_navigation"}


async def run_one(name: str, mode: str, target: str, rep: int, prefix: str = "", app_path: str | None = None) -> dict:
    tag = f"{prefix}{mode}_{target}_{name}_{rep}"
    t0 = time.time()
    try:
        async with Harness(mode, target, tag, app_path) as h:
            checks, info = await SCENARIOS[name](h)
            checks["no_server_exception"] = h.no_server_exception()
            natural = h.natural_failures
            start_failures = [{"workers_created": x["workers_created"], "text": x["state"]["text"][:100], "labels": x["state"]["labels"]} for x in h.start_failures]
    except Exception as exc:
        return {"tag": tag, "scenario": name, "mode": mode, "target": target, "repeat": rep, "passed": False, "error": f"{type(exc).__name__}: {exc}", "checks": {}, "info": {}}
    return {"tag": tag, "scenario": name, "mode": mode, "target": target, "repeat": rep, "passed": all(checks.values()), "checks": checks, "info": info,
            "natural_start_failures_retried": natural, "start_failures": start_failures, "seconds": round(time.time() - t0, 1)}


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--mode", choices=["off", "candidate", "production"], required=True)
    a.add_argument("--target", choices=["dashboard", "probe"], default="dashboard")
    a.add_argument("--scenarios", default=",".join(SCENARIOS))
    a.add_argument("--repeat", type=int, default=1)
    a.add_argument("--out", default=None)
    a.add_argument("--tag-prefix", default="", help="keeps these logs separate from earlier runs")
    a.add_argument("--app-path", default=None, help="run this copy of app.py, for the rollback check")
    args = a.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / (args.out or f"regression_{args.mode}_{args.target}.json")
    results = []
    for rep in range(1, args.repeat + 1):
        for name in args.scenarios.split(","):
            if name in DASHBOARD_ONLY and args.target != "dashboard":
                continue
            r = asyncio.run(run_one(name, args.mode, args.target, rep, args.tag_prefix, args.app_path))
            results.append(r)
            out.write_text(json.dumps(results, indent=1))
            failed = [k for k, v in r["checks"].items() if not v]
            print(json.dumps({"tag": r["tag"], "passed": r["passed"], "failed_checks": failed, "error": r.get("error"), "info": r["info"]}), flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
