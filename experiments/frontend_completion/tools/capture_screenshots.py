"""Genuine screenshots of the running SiteGuard AI dashboard with the local Google Chrome in headless mode.

    .venv/bin/python experiments/frontend_completion/tools/capture_screenshots.py --base http://127.0.0.1:8599 \
        --out experiments/frontend_completion/evidence/screenshots --width 1440 --height 900 [--redact-images]

Chrome is driven through its DevTools protocol (`websockets` client, already installed with Streamlit): open each
page through its ?page= deep link, wait until Streamlit has rendered, capture the viewport as PNG. Nothing is sent
anywhere except to the local Streamlit server. With --redact-images every <img>/<video> element (evidence frames,
camera) is hidden first; those copies are for review only and are labelled "_redacted".
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

import asyncio

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGES = ["Overview", "Live Monitoring", "Image Inspection", "Video Inspection",
         "Safety Events", "Analytics", "Model Evaluation", "Settings / About"]


async def capture(ws_url: str, jobs: list[tuple[str, Path]], width: int, height: int, wait: float, redact: bool) -> None:
    ws = await websockets.connect(ws_url, max_size=200 * 1024 * 1024)
    n = 0

    async def call(method: str, params: dict | None = None) -> dict:
        nonlocal n
        n += 1
        await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == n:
                return msg.get("result", {})

    await call("Page.enable")
    await call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
    for url, out in jobs:
        await call("Page.navigate", {"url": url})
        deadline = time.time() + wait
        while time.time() < deadline:  # wait for Streamlit to finish rendering (no running spinner, title present)
            r = await call("Runtime.evaluate", {"expression": "!!document.querySelector('h1') && "
                                                              "!document.querySelector('[data-testid=\"stStatusWidget\"]')",
                                                "returnByValue": True})
            if r.get("result", {}).get("value"):
                break
            await asyncio.sleep(0.5)
        await asyncio.sleep(2.5)  # let charts finish drawing
        if redact:
            await call("Runtime.evaluate", {"expression": "document.querySelectorAll('img,video,canvas[data-testid=\"stImage\"]')"
                                                          ".forEach(e => e.style.visibility='hidden')"})
        shot = await call("Page.captureScreenshot", {"format": "png"})
        out.write_bytes(base64.b64decode(shot["data"]))
        print("saved", out, flush=True)
    await ws.close()


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--base", default="http://127.0.0.1:8599")
    a.add_argument("--out", required=True)
    a.add_argument("--width", type=int, default=1440)
    a.add_argument("--height", type=int, default=900)
    a.add_argument("--wait", type=float, default=25.0)
    a.add_argument("--pages", nargs="*", default=PAGES)
    a.add_argument("--suffix", default="")
    a.add_argument("--redact-images", action="store_true")
    args = a.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="sg-chrome-")
    port = 9333
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                             "--no-default-browser-check", f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
                             f"--window-size={args.width},{args.height}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1).read())
                page = [t for t in targets if t.get("type") == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        jobs = []
        for i, p in enumerate(args.pages, start=1):
            slug = p.lower().replace(" / ", "_").replace(" ", "_")
            name = f"{PAGES.index(p) + 1:02d}_{slug}_{args.width}x{args.height}{args.suffix}{'_redacted' if args.redact_images else ''}.png"
            jobs.append((f"{args.base}/?page={urllib.parse.quote(p)}", out / name))
        asyncio.run(capture(page["webSocketDebuggerUrl"], jobs, args.width, args.height, args.wait, args.redact_images))
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
