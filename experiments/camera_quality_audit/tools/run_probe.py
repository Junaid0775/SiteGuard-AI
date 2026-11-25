"""Camera quality audit: drive the WebRTC probe app with the local Google Chrome (headless) and record metadata.

    # synthetic camera (no physical camera): Chrome's fake capture device plays a 1280x720 Y4M made from a dataset image
    .venv/bin/python experiments/camera_quality_audit/tools/run_probe.py --source fake --mode identity --seconds 20 --tag fake_identity
    .venv/bin/python experiments/camera_quality_audit/tools/run_probe.py --source fake --mode pipeline --seconds 20 --tag fake_pipeline
    # physical MacBook camera (only with the owner's explicit approval): metadata only, no pixels read back or saved
    .venv/bin/python experiments/camera_quality_audit/tools/run_probe.py --source camera --mode pipeline --seconds 12 --tag camera_pipeline

Records (experiments/camera_quality_audit/logs/<tag>/): server.jsonl (from the probe app: received frame size/format,
returned shape, encoder codec/bytes/target bitrate), browser.json (per second: the displayed <video> element's
intrinsic size videoWidth x videoHeight, its on-screen size, decoded/dropped frames). Only for --source fake a single
frame of the displayed video is read back (synthetic dataset image, never camera content) to compute the round-trip
PSNR. With --source camera no pixel is read back and nothing is saved.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import websockets

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "experiments" / "camera_quality_audit"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SOURCE_IMAGE = ROOT.parent / "construction-ppe" / "images" / "val" / "ultralytics-ppe-nov2026-022.jpg"

VIDEO_JS = """(() => [...document.querySelectorAll('video')].map(v => {
  const q = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : {};
  return {w: v.videoWidth, h: v.videoHeight, cw: v.clientWidth, ch: v.clientHeight, paused: v.paused,
          ready: v.readyState, decoded: q.totalVideoFrames || 0, dropped: q.droppedVideoFrames || 0,
          muted: v.muted, local: !!(v.srcObject && v.srcObject.getTracks && v.srcObject.getTracks().some(t => t.label))};
}))()"""
CLICK_JS = """((label) => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim().toUpperCase() === label);
  if (b) { b.click(); return true; } return false; })"""
GRAB_JS = """(() => { const v = [...document.querySelectorAll('video')].find(x => x.videoWidth > 0); if (!v) return null;
  const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext('2d').drawImage(v, 0, 0); return c.toDataURL('image/png'); })()"""


def make_y4m(path: Path, frames: int = 150) -> np.ndarray:
    """1280x720 I420 Y4M of one dataset image (letterboxed), repeated; returns the BGR reference as Chrome will see it."""
    src = cv2.imread(str(SOURCE_IMAGE))
    h, w = src.shape[:2]
    s = min(1280 / w, 720 / h)
    img = cv2.resize(src, (int(w * s) // 2 * 2, int(h * s) // 2 * 2), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((720, 1280, 3), np.uint8)
    y0, x0 = (720 - img.shape[0]) // 2, (1280 - img.shape[1]) // 2
    canvas[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
    i420 = cv2.cvtColor(canvas, cv2.COLOR_BGR2YUV_I420)
    with open(path, "wb") as f:
        f.write(b"YUV4MPEG2 W1280 H720 F30:1 Ip A1:1 C420jpeg\n")
        for _ in range(frames):
            f.write(b"FRAME\n" + i420.tobytes())
    return cv2.cvtColor(i420, cv2.COLOR_YUV2BGR_I420)  # reference after the unavoidable 4:2:0 step


def make_moving_y4m(path: Path, frames: int = 150) -> None:
    """Demanding synthetic camera: a dataset image panned about 4 px per frame with sensor-like noise; loops seamlessly."""
    src = cv2.imread(str(SOURCE_IMAGE))
    k = max(1.25 * 1280 / src.shape[1], 1.25 * 720 / src.shape[0])
    big = cv2.resize(src, None, fx=k, fy=k, interpolation=cv2.INTER_LINEAR)
    rng, (H, W) = np.random.default_rng(0), big.shape[:2]
    with open(path, "wb") as f:
        f.write(b"YUV4MPEG2 W1280 H720 F30:1 Ip A1:1 C420jpeg\n")
        for i in range(frames):
            phase = abs(i / (frames / 2) - 1)
            x, y = int((W - 1280) * phase), int((H - 720) * (1 - phase))
            noisy = np.clip(big[y:y + 720, x:x + 1280].astype(np.float32) + rng.normal(0, 3.0, (720, 1280, 3)), 0, 255).astype(np.uint8)
            f.write(b"FRAME\n" + cv2.cvtColor(noisy, cv2.COLOR_BGR2YUV_I420).tobytes())


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2))
    return 99.0 if mse == 0 else round(10 * np.log10(255.0 ** 2 / mse), 2)


async def drive(ws_url: str, url: str, seconds: float, grab: bool, out: Path, reference: np.ndarray | None,
                server_pid: int | None = None, screenshot: str | None = None, click_mode: str = "immediate",
                browser_log: bool = False, stack_on_stall: bool = False, stack_always: bool = False) -> dict:
    import psutil

    proc = psutil.Process(server_pid) if server_pid else None
    if proc:
        proc.cpu_percent(None)
    ws = await websockets.connect(ws_url, max_size=300 * 1024 * 1024, ping_interval=None)
    n = 0

    async def call(method, params=None):
        nonlocal n
        n += 1
        await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), 30))  # never hang on a stalled browser
            if m.get("id") == n:
                return m.get("result", m.get("error", {}))

    async def frame_ctx():
        tree = (await call("Page.getFrameTree"))["frameTree"]
        for child in tree.get("childFrames", []):
            if "webrtc" in child["frame"].get("url", "").lower() or "component" in child["frame"].get("url", "").lower():
                return (await call("Page.createIsolatedWorld", {"frameId": child["frame"]["id"]}))["executionContextId"]
        return None

    async def ev(expr, ctx_id):
        r = await call("Runtime.evaluate", {"expression": expr, "contextId": ctx_id, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    await call("Page.enable")
    ww, wh = (int(v) for v in os.environ.get("SG_PROBE_WINDOW", "1440,900").split(","))
    await call("Emulation.setDeviceMetricsOverride", {"width": ww, "height": wh, "deviceScaleFactor": 1, "mobile": False})
    if browser_log:  # passive browser-side connection log (start_diagnostics.INJECT); the server stays unchanged
        from start_diagnostics import INJECT
        await call("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT})
    await call("Page.navigate", {"url": url})
    ctx_id, t_end = None, time.time() + 60
    while ctx_id is None and time.time() < t_end:
        await asyncio.sleep(1)
        ctx_id = await frame_ctx()
    if ctx_id is None:
        raise RuntimeError("webrtc component iframe not found")
    if click_mode == "delayed":  # deliberate page-initialisation delay: script idle for 1 s, then 3 s more
        idle_since = None
        while time.time() < t_end:
            st = (await call("Runtime.evaluate", {"expression": "document.querySelector('[data-testid=\"stApp\"]')?.getAttribute('data-test-script-state')",
                                                  "returnByValue": True})).get("result", {}).get("value")
            if st == "notRunning":
                idle_since = idle_since or time.time()
                if time.time() - idle_since >= 1.0:
                    break
            else:
                idle_since = None
            await asyncio.sleep(0.05)
        await asyncio.sleep(3.0)
    clicked, t_click = False, None
    while not clicked and time.time() < t_end:
        t_click = time.time()
        clicked = bool(await ev(CLICK_JS + "('START')", ctx_id))
        await asyncio.sleep(0.5)
    started = time.time()
    samples, stack_times = [], []
    while time.time() - started < seconds:
        await asyncio.sleep(1)
        rec = {"t": round(time.time() - started, 1), "videos": await ev(VIDEO_JS, ctx_id)}
        if stack_on_stall and server_pid and rec["t"] >= 2 and len(stack_times) < 2 and (not rec["videos"] or rec["videos"][0]["w"] == 0):
            os.kill(server_pid, signal.SIGUSR1)  # no displayed frame 2+ s after START: dump all server thread stacks
            stack_times.append(rec["t"])
        if stack_always and server_pid and rec["t"] >= 3 and not stack_times:
            os.kill(server_pid, signal.SIGUSR1)  # one dump 3 s after START in every run: healthy and failed starts are comparable
            stack_times.append(rec["t"])
        if proc:
            rec["server_cpu_pct"] = proc.cpu_percent(None)  # % of one core since the previous sample
            rec["server_rss_mb"] = round(proc.memory_info().rss / 1e6, 1)
        samples.append(rec)
    result = {"clicked_start": clicked, "samples": samples, "t_click": t_click, "click_mode": click_mode, "stack_dumps_at_s": stack_times}
    if grab and reference is not None:
        data = await ev(GRAB_JS, ctx_id)
        if data:
            arr = cv2.imdecode(np.frombuffer(base64.b64decode(data.split(",", 1)[1]), np.uint8), cv2.IMREAD_COLOR)
            cv2.imwrite(str(out / "browser_displayed_frame_synthetic.png"), arr)  # synthetic dataset image only
            ref = reference if reference.shape[:2] == arr.shape[:2] else cv2.resize(reference, (arr.shape[1], arr.shape[0]), interpolation=cv2.INTER_AREA)
            result["browser_frame"] = {"w": arr.shape[1], "h": arr.shape[0], "psnr_vs_source": psnr(arr, ref)}
    if screenshot:  # synthetic source only: the page shows the dataset-image test feed, never a camera
        shot = await call("Page.captureScreenshot", {"format": "png"})
        Path(screenshot).write_bytes(base64.b64decode(shot["data"]))
        result["screenshot"] = screenshot
    result["clicked_stop"] = bool(await ev(CLICK_JS + "('STOP')", ctx_id))
    await asyncio.sleep(2)
    result["after_stop"] = await ev(VIDEO_JS, ctx_id)
    if browser_log:
        result["browser_events"] = (await call("Runtime.evaluate", {"expression": "window.__sgAll || []", "returnByValue": True})).get("result", {}).get("value") or []
    await ws.close()
    return result


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--source", choices=["fake", "camera"], required=True)
    a.add_argument("--mode", choices=["pipeline", "identity"], default="pipeline")
    a.add_argument("--seconds", type=float, default=20)
    a.add_argument("--tag", required=True)
    a.add_argument("--port", type=int, default=8611)
    a.add_argument("--bitrate", default="library", help="'library' or 'default:min:max' in bit/s (dashboard Fix 1)")
    a.add_argument("--html-attrs", action="store_true", help="use the dashboard's VIDEO_HTML_ATTRS (Fix 3)")
    a.add_argument("--window", default="1440,900")
    a.add_argument("--content", choices=["still", "moving"], default="still", help="synthetic camera content (--source fake)")
    a.add_argument("--app", choices=["probe", "dashboard"], default="probe",
                   help="dashboard = the real app.py with a temporary events DB and evidence folder (no production data)")
    a.add_argument("--click", choices=["immediate", "delayed"], default="immediate")
    a.add_argument("--browser-log", action="store_true", help="passive browser-side connection stage log")
    a.add_argument("--launcher", choices=["plain", "avfirst", "execonly", "stackdump", "lifecycle", "guard"], default="plain", help="import-order / launcher controls")
    a.add_argument("--guard-mode", choices=["off", "candidate", "production"], default="off", help="--launcher guard: live start guard under test")
    a.add_argument("--variant", choices=["none", "before", "after", "guard"], default="none", help="lifecycle launcher, probe only: 150 ms delay and yield point before/after webrtc_streamer")
    a.add_argument("--no-fast-reruns", action="store_true", help="set runner.fastReruns=false on this test server's command line only")
    a.add_argument("--diag-server", action="store_true", help="server-side connection stage log (webrtc_probe_diag_app.py)")
    a.add_argument("--screenshot", default=None, help="PNG path for a page screenshot at the end (--source fake only)")
    args = a.parse_args()
    out = AUDIT / "logs" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    server_log = out / "server.jsonl"
    server_log.write_text("")
    env = dict(os.environ, SG_PROBE_LOG=str(server_log), SG_PROBE_MODE=args.mode)
    env["SG_PROBE_BITRATE"] = args.bitrate
    os.environ["SG_PROBE_WINDOW"] = args.window
    if args.html_attrs:
        env["SG_PROBE_HTML_ATTRS"] = "1"
    reference = None
    chrome_flags = ["--use-fake-ui-for-media-stream"]  # grants the page's camera request without a prompt
    tmp = Path(tempfile.mkdtemp(prefix="sg-probe-"))
    if args.source == "fake" and args.content == "moving":
        y4m = Path(tempfile.gettempdir()) / "sg-moving-1280x720.y4m"  # shared by runs; removed after the benchmarks
        if not y4m.exists():
            make_moving_y4m(y4m)
        chrome_flags += ["--use-fake-device-for-media-stream", f"--use-file-for-fake-video-capture={y4m}"]
    elif args.source == "fake":
        y4m = tmp / "synthetic_1280x720.y4m"
        reference = make_y4m(y4m)
        ref_png = out / "synthetic_reference.png"
        cv2.imwrite(str(ref_png), reference)
        env["SG_PROBE_REFERENCE"] = str(ref_png)
        chrome_flags += ["--use-fake-device-for-media-stream", f"--use-file-for-fake-video-capture={y4m}"]
    if args.app == "dashboard":
        env["SITEGUARD_EVENTS_DB"] = str(tmp / "dashboard_test.db")
        env["SITEGUARD_EVIDENCE_DIR"] = str(tmp / "dashboard_test_evidence")
    app_file = str(ROOT / "app.py") if args.app == "dashboard" else str(AUDIT / "tools/webrtc_probe_app.py")
    if args.launcher != "plain":
        app_file = str(AUDIT / f"tools/webrtc_probe_{args.launcher}_app.py")
    if args.launcher == "guard":
        app_file = str(AUDIT / "fixes/start_guard/guard_test_app.py")
        env.update(SG_GUARD_MODE=args.guard_mode, SG_GUARD_TARGET=args.app, SG_GUARD_LOG=str(out / "lifecycle.jsonl"))
        (out / "lifecycle.jsonl").write_text("")
    if args.launcher == "stackdump":
        env["SG_PROBE_STACK_LOG"] = str(out / "stacks.txt")
    if args.launcher == "lifecycle":
        env.update(SG_PROBE_STACK_LOG=str(out / "stacks.txt"), SG_PROBE_LIFECYCLE_LOG=str(out / "lifecycle.jsonl"), SG_PROBE_VARIANT=args.variant,
                   SG_PROBE_TARGET=args.app)
        (out / "lifecycle.jsonl").write_text("")
    if args.diag_server:
        app_file = str(AUDIT / "tools/webrtc_probe_diag_app.py")
        env["SG_PROBE_STAGE_LOG"] = str(out / "stage.jsonl")
        (out / "stage.jsonl").write_text("")
    server = subprocess.Popen([str(ROOT / ".venv/bin/streamlit"), "run", app_file,
                               "--server.port", str(args.port), "--server.address", "127.0.0.1", "--server.headless", "true",
                               *(["--runner.fastReruns", "false"] if args.no_fast_reruns else [])],
                              cwd=ROOT, env=env, stdout=open(out / "probe_server.log", "w"), stderr=subprocess.STDOUT)
    chrome = None
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{args.port}/_stcore/health", timeout=1).read() == b"ok":
                    break
            except Exception:
                time.sleep(0.5)
        chrome = subprocess.Popen([CHROME, "--headless=new", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=9334",
                                   f"--user-data-dir={tmp / 'profile'}", "--autoplay-policy=no-user-gesture-required", *chrome_flags,
                                   "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        for _ in range(50):
            try:
                page = [t for t in json.loads(urllib.request.urlopen("http://127.0.0.1:9334/json/list", timeout=1).read()) if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        t0 = time.time()
        url = f"http://127.0.0.1:{args.port}/" + ("?page=Live%20Monitoring" if args.app == "dashboard" else "")
        shot = args.screenshot if args.source == "fake" else None
        result = asyncio.run(drive(page["webSocketDebuggerUrl"], url, args.seconds,
                                   args.source == "fake" and args.app == "probe", out, reference, server.pid, shot, args.click, args.browser_log, args.launcher in ("stackdump", "lifecycle")))  # never dump a healthy server: 5 of 48 such dumps crashed it
        result.update({"source": args.source, "mode": args.mode, "seconds": args.seconds, "wall_s": round(time.time() - t0, 1),
                       "bitrate": args.bitrate, "html_attrs": args.html_attrs, "window": args.window})
        (out / "browser.json").write_text(json.dumps(result, indent=1))
        print(json.dumps({k: v for k, v in result.items() if k != "samples"}, indent=1))
    finally:
        if chrome:
            chrome.terminate()
            chrome.wait(timeout=10)
        server.send_signal(signal.SIGINT)
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
        print("chrome exited:", None if chrome is None else chrome.returncode, "probe server exited:", server.returncode)
        shutil.rmtree(tmp, ignore_errors=True)  # temporary Y4M, Chrome profile and any temporary dashboard DB/evidence


if __name__ == "__main__":
    main()
