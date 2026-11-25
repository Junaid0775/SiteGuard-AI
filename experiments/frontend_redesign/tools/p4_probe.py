"""Phase 4 probe: per-step timing, full-page captures, image-upload flow and spinner check (local servers only)."""
import asyncio, base64, json, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from pathlib import Path
import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


async def session(ws_url):
    ws = await websockets.connect(ws_url, max_size=300 * 1024 * 1024)
    n = 0

    async def call(method, params=None):
        nonlocal n
        n += 1
        await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == n:
                return msg.get("result", msg.get("error", {}))
    return ws, call


async def js(call, expr):
    r = await call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    return r.get("result", {}).get("value")


async def wait_rendered(call, timeout=90, text=None):
    t0 = time.time()
    cond = ("!!document.querySelector('h1') && !document.querySelector('[data-testid=\"stStatusWidget\"]')"
            + (f" && document.body.innerText.includes({json.dumps(text)})" if text else ""))
    while time.time() - t0 < timeout:
        if await js(call, cond):
            return time.time() - t0
        await asyncio.sleep(0.5)
    return None


async def shot(call, out, width, height, full=False, redact=True):
    if redact:
        await js(call, "document.querySelectorAll('img,video,canvas[data-testid=\"stImage\"]').forEach(e => e.style.visibility='hidden')")
    if full:
        h = await js(call, "Math.max(...['stMain','stAppViewContainer'].map(t => document.querySelector(`[data-testid=${t}]`)?.scrollHeight || 0), document.documentElement.scrollHeight)")
        await call("Emulation.setDeviceMetricsOverride", {"width": width, "height": int(min(max(h, height), 9000)), "deviceScaleFactor": 1, "mobile": False})
        await asyncio.sleep(2.5)
        if redact:
            await js(call, "document.querySelectorAll('img,video,canvas[data-testid=\"stImage\"]').forEach(e => e.style.visibility='hidden')")
    t = time.time()
    r = await call("Page.captureScreenshot", {"format": "png"})
    Path(out).write_bytes(base64.b64decode(r["data"]))
    await call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
    return time.time() - t


async def main(mode, base, out_dir, extra):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="sg-probe-")
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                             "--remote-debugging-port=9334", f"--user-data-dir={profile}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                page = [t for t in json.loads(urllib.request.urlopen("http://127.0.0.1:9334/json/list", timeout=1).read()) if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        ws, call = await session(page["webSocketDebuggerUrl"])
        await call("Page.enable"); await call("DOM.enable")
        W, H = 1440, 900
        await call("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})
        if mode == "timing":
            for p in extra:
                for blur in (True, False):
                    t0 = time.time()
                    await call("Page.navigate", {"url": f"{base}/?page={urllib.parse.quote(p)}"})
                    t_nav = time.time() - t0
                    rendered = await wait_rendered(call)
                    if not blur:
                        await js(call, "document.head.insertAdjacentHTML('beforeend','<style>*{backdrop-filter:none!important}</style>')")
                    await asyncio.sleep(1.0)
                    t_eval = time.time(); await js(call, "1"); t_eval = time.time() - t_eval
                    t_shot = await shot(call, out / f"timing_{p[:6]}_{'blur' if blur else 'noblur'}.png", W, H)
                    print(f"{p:18s} blur={blur!s:5s} navigate={t_nav:5.1f}s rendered={rendered} eval={t_eval:5.2f}s screenshot={t_shot:6.1f}s", flush=True)
        elif mode == "full":
            for p in extra:
                await call("Page.navigate", {"url": f"{base}/?page={urllib.parse.quote(p)}"})
                r = await wait_rendered(call)
                await asyncio.sleep(2.5)
                slug = p.lower().replace(" / ", "_").replace(" ", "_")
                t = await shot(call, out / f"full_{slug}_1440_redacted.png", W, H, full=True)
                print(p, "rendered", r, "shot", round(t, 1), flush=True)
        elif mode == "upload":
            image = extra[0]
            await call("Page.navigate", {"url": f"{base}/?page=Image%20Inspection"})
            print("rendered", await wait_rendered(call), flush=True)
            doc = await call("DOM.getDocument", {"depth": -1})
            node = await call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "input[type=file]"})
            await call("DOM.setFileInputFiles", {"nodeId": node["nodeId"], "files": [image]})
            print("result", await wait_rendered(call, 120, text="Compliance analysis"), flush=True)
            await asyncio.sleep(3)
            t = await shot(call, out / "full_image_inspection_result_1440.png", W, H, full=True, redact=False)
            print("shot", round(t, 1), flush=True)
        elif mode == "spinner":
            await call("Page.navigate", {"url": base})
            await asyncio.sleep(6)
            html = await js(call, "document.querySelector('[data-testid=\"stSpinner\"]')?.outerHTML.slice(0, 900)")
            print("SPINNER DOM:", html, flush=True)
            await shot(call, out / "spinner_three_dots_1440.png", W, H, redact=False)
            await call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
            print("reduced-motion animation:", await js(call, "getComputedStyle(document.querySelector('[data-testid=\"stSpinner\"] > div'), '::before').animationName"), flush=True)
            await call("Emulation.setEmulatedMedia", {"features": []})
            print("normal animation:", await js(call, "getComputedStyle(document.querySelector('[data-testid=\"stSpinner\"] > div'), '::before').animationName"), flush=True)
        await ws.close()
    finally:
        proc.terminate(); proc.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
