"""Phase 5 audit: per page x width checks (audit.js) with JPEG evidence, a keyboard focus walk, and the spinner at 360 px."""
import asyncio, base64, json, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from pathlib import Path
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import p4_probe as P

PAGES = ["Overview", "Live Monitoring", "Image Inspection", "Video Inspection", "Safety Events", "Analytics", "Model Evaluation", "Settings / About"]
SIZES = [(1920, 1080), (1600, 1000), (1440, 900), (1280, 800), (1024, 768), (820, 1180), (768, 1024), (430, 932), (390, 844), (360, 780)]
FOCUS_JS = r"""(() => { const a = document.activeElement; if (!a || a === document.body) return 'body';
  const on = e => { const s = getComputedStyle(e); return (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none'); };
  let ind = on(a), via = 'self';
  for (let p = a.parentElement, i = 0; !ind && p && i < 4; p = p.parentElement, i++) if (on(p)) { ind = true; via = p.dataset.testid || p.tagName.toLowerCase(); }
  const l = a.closest('label'); if (!ind && l && on(l)) { ind = true; via = 'label'; }
  return (a.dataset.testid || a.tagName.toLowerCase() + (a.type ? ':' + a.type : '')) + ' [' + ((a.getAttribute('aria-label') || a.innerText || a.closest('label')?.innerText || '') + '').trim().slice(0, 26).replace(/\s+/g, ' ') + '] visible-indicator=' + ind + (ind ? ' (' + via + ')' : ''); })()"""


async def browser(port):
    proc = subprocess.Popen([P.CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={port}",
                             f"--user-data-dir={tempfile.mkdtemp(prefix='sg-p5a-')}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            page = [t for t in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1).read()) if t["type"] == "page"][0]
            break
        except Exception:
            time.sleep(0.2)
    ws, call = await P.session(page["webSocketDebuggerUrl"])
    await call("Page.enable")
    return proc, ws, call


async def audit(base, out, js):
    proc, ws, call = await browser(9336)
    results = {}
    try:
        for w, h in SIZES:
            await call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": w < 768})
            for i, p in enumerate(PAGES, 1):
                await call("Page.navigate", {"url": f"{base}/?page={urllib.parse.quote(p)}"})
                await P.wait_rendered(call)
                await asyncio.sleep(2.5)
                res = json.loads(await P.js(call, js))
                results[f"{p}@{w}"] = res
                await P.js(call, "document.querySelectorAll('img,video,canvas[data-testid=\"stImage\"]').forEach(e => e.style.visibility='hidden')")
                shot = await call("Page.captureScreenshot", {"format": "jpeg", "quality": 80})
                slug = p.lower().replace(" / ", "_").replace(" ", "_")
                (out / f"{i:02d}_{slug}_{w}x{h}_redacted.jpg").write_bytes(base64.b64decode(shot["data"]))
                flags = {k: v for k, v in res.items() if k in ("pageOverflow", "clipped", "inputsCut", "metricCut", "beyondViewport", "panelOverflow") and v}
                print(f"{p:17s} {w:5d}  {json.dumps(flags) if flags else 'ok'}", flush=True)
        (out / "audit_results.json").write_text(json.dumps(results, indent=1))
    finally:
        await ws.close(); proc.terminate(); proc.wait(timeout=10)


async def focus(base):
    proc, ws, call = await browser(9337)
    try:
        await call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        for p in ("Overview", "Safety Events"):
            await call("Page.navigate", {"url": f"{base}/?page={urllib.parse.quote(p)}"})
            await P.wait_rendered(call); await asyncio.sleep(2.5)
            print("==", p)
            for n in range(1, 23):
                for t in ("keyDown", "keyUp"):
                    await call("Input.dispatchKeyEvent", {"type": t, "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
                await asyncio.sleep(0.25)
                print(f"  tab {n:2d}: {await P.js(call, FOCUS_JS)}", flush=True)
    finally:
        await ws.close(); proc.terminate(); proc.wait(timeout=10)


async def spinner(base, out):
    proc, ws, call = await browser(9338)
    try:
        await call("Emulation.setDeviceMetricsOverride", {"width": 360, "height": 780, "deviceScaleFactor": 1, "mobile": True})
        await call("Page.navigate", {"url": base})
        await asyncio.sleep(6)
        shot = await call("Page.captureScreenshot", {"format": "png"})
        (out / "spinner_three_dots_360.png").write_bytes(base64.b64decode(shot["data"]))
        print("animation:", await P.js(call, "getComputedStyle(document.querySelector('[data-testid=\"stSpinner\"] > div'), '::before').animationName"))
    finally:
        await ws.close(); proc.terminate(); proc.wait(timeout=10)


if __name__ == "__main__":
    mode, base = sys.argv[1], sys.argv[2]
    if mode == "audit":
        out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
        asyncio.run(audit(base, out, open(sys.argv[4]).read()))
    elif mode == "focus":
        asyncio.run(focus(base))
    else:
        asyncio.run(spinner(base, Path(sys.argv[3])))
