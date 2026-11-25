"""Phase 6 performance comparison: Phase 0 frontend (p0) vs current (p5), each an isolated copy with its own DB copy."""
import asyncio, json, os, signal, socket, statistics, subprocess, sys, tempfile, time, urllib.request
import websockets

S = sys.argv[1]
PY = "/Users/junaidahmad/Desktop/471 Project/SiteGuard-AI/.venv/bin/python"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGES = ["Overview", "Live Monitoring", "Image Inspection", "Video Inspection", "Safety Events", "Analytics", "Model Evaluation", "Settings / About"]
STATE = """(() => { if (window.__sgOld) return 'old'; const h = document.querySelector('h1'); if (!h) return 'none';
  if (document.querySelector('[data-testid="stStatusWidget"]')) return 'running';
  return h.innerText.trim() + '|' + document.querySelectorAll('[data-testid="stElementContainer"]').length; })()"""
RECALC = """(() => { const t = performance.now(); for (let i = 0; i < 20; i++) { document.body.classList.toggle('sg-perf-probe'); void document.body.offsetHeight; } return (performance.now() - t) / 20; })()"""
SCROLL = """(async () => { const c = [...document.querySelectorAll('[data-testid="stMain"], [data-testid="stAppViewContainer"]'), document.scrollingElement];
  const sc = c.find(e => e && e.scrollHeight > e.clientHeight + 10 && ['auto', 'scroll'].includes(getComputedStyle(e).overflowY)) || document.scrollingElement;
  const total = sc.scrollHeight - sc.clientHeight; let prev = performance.now(), maxGap = 0, gaps = [];
  for (const i of [...Array(61).keys(), ...[...Array(60).keys()].reverse()]) { sc.scrollTop = total * i / 60; await new Promise(r => requestAnimationFrame(r));
    const now = performance.now(); gaps.push(now - prev); prev = now; }
  gaps.sort((a, b) => a - b); return JSON.stringify({px: total, frames: gaps.length, p95: Math.round(gaps[Math.floor(gaps.length * .95)]), max: Math.round(gaps[gaps.length - 1])}); })()"""


def health(port):
    try:
        return urllib.request.urlopen(f"http://localhost:{port}/_stcore/health", timeout=0.5).read() == b"ok"
    except Exception:
        return False


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start(d, port):
    env = dict(os.environ, SITEGUARD_EVENTS_DB=f"{d}/tmp/events.db", SITEGUARD_EVIDENCE_DIR=f"{d}/tmp/evidence")
    env.pop("SITEGUARD_MODEL", None)
    t0 = time.perf_counter()
    proc = subprocess.Popen([PY, "-m", "streamlit", "run", "app.py", "--server.port", str(port), "--server.headless", "true",
                             "--server.address", "localhost", "--browser.gatherUsageStats", "false"], cwd=d, env=env,
                            stdout=open(f"{d}/tmp/server.log", "a"), stderr=subprocess.STDOUT)
    while not health(port):
        if proc.poll() is not None or time.perf_counter() - t0 > 90:
            raise RuntimeError("server did not start")
        time.sleep(0.05)
    return proc, time.perf_counter() - t0


def stop(proc, port):
    t0 = time.perf_counter()
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"exit": "killed after 20 s"}
    return {"seconds": round(time.perf_counter() - t0, 2), "exit_code": proc.returncode, "port_released": not port_open(port)}


async def browser(cdp_port):
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={cdp_port}",
                             f"--user-data-dir={tempfile.mkdtemp(prefix='sg-p6-')}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            page = [t for t in json.loads(urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/list", timeout=1).read()) if t["type"] == "page"][0]
            break
        except Exception:
            time.sleep(0.2)
    ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=300 * 1024 * 1024)
    events, n = [], 0

    async def call(method, params=None):
        nonlocal n
        n += 1
        my = n
        await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == my:
                return msg.get("result", {})
            if "method" in msg:
                events.append(msg)
    for d in ("Page", "Network", "Performance"):
        await call(f"{d}.enable")
    await call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    return proc, ws, call, events


async def js(call, expr):
    r = await call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    return r.get("result", {}).get("value")


async def metrics(call):
    return {m["name"]: m["value"] for m in (await call("Performance.getMetrics"))["metrics"]}


async def stable(call, title, t0, timeout=90):
    last, streak, first = None, 0, None
    while time.perf_counter() - t0 < timeout:
        v = await js(call, STATE)
        now = time.perf_counter()
        if isinstance(v, str) and "|" in v and title in v.split("|")[0]:
            if v == last:
                streak += 1
            else:
                last, streak, first = v, 1, now
            if streak >= 4:
                return first - t0
        else:
            last, streak = None, 0
        await asyncio.sleep(0.05)
    return None


async def load(call, port, page):
    await js(call, "window.__sgOld = true")
    t0 = time.perf_counter()
    await call("Page.navigate", {"url": f"http://localhost:{port}/?page={urllib.request.quote(page)}"})
    return await stable(call, page, t0)


async def switch(call, page):
    t0 = time.perf_counter()
    await js(call, f"[...document.querySelectorAll('[data-testid=\"stSidebar\"] [role=\"radiogroup\"] label')].find(l => l.innerText.includes({json.dumps(page)})).click()")
    return await stable(call, page, t0)


async def measure(version, port, cdp_port):
    d = f"{S}/perf/{version}"
    out = {"startup_s": [], "shutdown": []}
    for _ in range(3):
        proc, t = start(d, port)
        out["startup_s"].append(round(t, 2))
        out["shutdown"].append(stop(proc, port))
    proc, _ = start(d, port)
    bproc, ws, call, events = await browser(cdp_port)
    try:
        out["cold_first_render_s"] = round(await load(call, port, "Overview"), 2)
        out["full_load_s"], out["switch_s"], out["heap_mb"], out["dom_nodes"], out["recalc_ms"] = {}, {}, {}, {}, {}
        for p in PAGES:
            times = [await load(call, port, p) for _ in range(3)]
            out["full_load_s"][p] = round(statistics.median(times), 2)
            await asyncio.sleep(1.5)
            m = await metrics(call)
            out["heap_mb"][p], out["dom_nodes"][p] = round(m["JSHeapUsedSize"] / 1e6, 1), int(m["Nodes"])
            out["recalc_ms"][p] = round(statistics.median([await js(call, RECALC) for _ in range(3)]), 2)
        for p in PAGES:
            times = []
            for _ in range(3):
                await load(call, port, "Analytics" if p == "Overview" else "Overview")
                times.append(await switch(call, p))
            out["switch_s"][p] = round(statistics.median(times), 2)
        out["scroll"] = {}
        for p in ("Overview", "Model Evaluation"):
            await load(call, port, p)
            await asyncio.sleep(2)
            m0 = await metrics(call)
            s = json.loads(await js(call, SCROLL))
            m1 = await metrics(call)
            s.update({k: round((m1[k] - m0[k]) * 1000) for k in ("TaskDuration", "LayoutDuration", "RecalcStyleDuration")})
            out["scroll"][p] = s
        await load(call, port, "Live Monitoring")
        await asyncio.sleep(2)
        m0 = await metrics(call)
        await asyncio.sleep(10)
        m1 = await metrics(call)
        out["live_idle_10s_main_thread_ms"] = round((m1["TaskDuration"] - m0["TaskDuration"]) * 1000)
        events.clear()
        await load(call, port, "Overview")
        await asyncio.sleep(2)
        await js(call, "1")
        http = sum(e["params"].get("encodedDataLength", 0) for e in events if e["method"] == "Network.loadingFinished")
        wsb = sum(len(e["params"]["response"]["payloadData"]) for e in events if e["method"] == "Network.webSocketFrameReceived")
        out["overview_full_load_bytes"] = {"http_kb": round(http / 1024), "websocket_kb": round(wsb / 1024)}
        if version == "p5":
            events.clear()
            for p in PAGES[1:]:
                await switch(call, p)
            await js(call, "1")
            bg = lambda: [e for e in events if e["method"] == "Network.requestWillBeSent" and "siteguard_background" in e["params"]["request"]["url"]]
            out["background_requests_during_7_page_switches"] = len(bg())
            events.clear()
            for _ in range(3):
                await load(call, port, "Overview")
            await js(call, "1")
            ids = {e["params"]["requestId"] for e in bg()}
            resp = [e for e in events if e["method"] == "Network.responseReceived" and e["params"]["requestId"] in ids]
            cached = [e for e in events if e["method"] == "Network.requestServedFromCache" and e["params"]["requestId"] in ids]
            fin = [e["params"].get("encodedDataLength", 0) for e in events if e["method"] == "Network.loadingFinished" and e["params"]["requestId"] in ids]
            out["background_on_3_full_reloads"] = {"requests": len(ids), "statuses": sorted({r["params"]["response"]["status"] for r in resp}),
                                                   "served_from_cache": len(cached), "bytes_transferred": sum(fin)}
        out["server_rss_mb"] = round(int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(proc.pid)]).strip()) / 1024)
    finally:
        await ws.close()
        bproc.terminate()
        out["final_shutdown"] = stop(proc, port)
    return out


results = {}
for version, port, cdp_port in (("p0", 8618, 9340), ("p5", 8619, 9341)):
    results[version] = asyncio.run(measure(version, port, cdp_port))
    print(version, json.dumps(results[version]), flush=True)
json.dump(results, open(f"{S}/perf/results.json", "w"), indent=1)
