"""Run a JS file against pages of the local dashboard at given widths: p5_eval.py BASE JSFILE WIDTH[,WIDTH] PAGE [PAGE...]"""
import asyncio, json, subprocess, sys, tempfile, time, urllib.parse, urllib.request
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import p4_probe as P


async def main(base, jsfile, widths, pages):
    code = open(jsfile).read()
    proc = subprocess.Popen([P.CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--remote-debugging-port=9335",
                             f"--user-data-dir={tempfile.mkdtemp(prefix='sg-p5-')}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                page = [t for t in json.loads(urllib.request.urlopen("http://127.0.0.1:9335/json/list", timeout=1).read()) if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        ws, call = await P.session(page["webSocketDebuggerUrl"])
        await call("Page.enable")
        for w in widths:
            h = 900 if w > 820 else 844
            await call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": w < 768})
            for p in pages:
                await call("Page.navigate", {"url": f"{base}/?page={urllib.parse.quote(p)}"})
                await P.wait_rendered(call)
                await asyncio.sleep(2.5)
                print(f"== {p} @ {w}: {await P.js(call, code)}", flush=True)
        await ws.close()
    finally:
        proc.terminate(); proc.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")], sys.argv[4:]))
