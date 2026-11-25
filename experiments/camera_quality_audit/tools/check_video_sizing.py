"""Fix 3 check: how the real dashboard sizes the live video at 1440 px and 1024 px. Synthetic camera only.

Usage: check_video_sizing.py GUARD_MODE RUN_NAME
Each width gets a new server and browser. The video element is measured every second for 12 seconds while streaming.
A sample passes when the video is not upscaled, keeps its aspect ratio, fits its container, uses the available width up
to its own resolution, and the page has no horizontal overflow. One screenshot per width is saved (synthetic video and a
temporary events database, so no private frame can appear in it).
"""
import asyncio
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/camera_quality_audit/fixes/start_guard"))
import guard_regression as g  # noqa: E402

VIEWPORTS = ((1440, 900), (1024, 768))
SIZE_JS = f"""(() => {{
  const ifr = {g.FRAME}; const d = ifr && ifr.contentDocument; const v = d && d.querySelector('video');
  if (!v) return null;
  const r = v.getBoundingClientRect(), i = ifr.getBoundingClientRect();
  const c = ifr.closest('[data-testid="stColumn"]'); const main = document.querySelector('[data-testid="stMain"]');
  const root = document.documentElement;
  return {{streamW: v.videoWidth, streamH: v.videoHeight, cssW: r.width, cssH: r.height, iframeW: i.width, columnW: c ? c.getBoundingClientRect().width : null,
          objectFit: getComputedStyle(v).objectFit, pageOverflowX: root.scrollWidth > root.clientWidth, mainOverflowX: main ? main.scrollWidth > main.clientWidth : null,
          frameOverflowX: d.documentElement.scrollWidth > d.documentElement.clientWidth}};
}})()"""


def judge(s: dict) -> dict:
    aspect_stream, aspect_css = s["streamW"] / s["streamH"], s["cssW"] / s["cssH"]
    return {"not_upscaled": s["cssW"] <= s["streamW"] + 0.5 and s["cssH"] <= s["streamH"] + 0.5,
            "aspect_kept": abs(aspect_css / aspect_stream - 1) < 0.01,
            "fits_container": s["cssW"] <= s["iframeW"] + 0.5,
            "uses_available_width": s["cssW"] >= min(s["streamW"], s["iframeW"]) - 1,
            "not_cropped": s["objectFit"] == "contain",
            "no_horizontal_overflow": not (s["pageOverflowX"] or s["mainOverflowX"] or s["frameOverflowX"])}


async def check(mode: str, name: str, width: int, height: int) -> dict:
    tag = f"fix3_{name}_{width}"
    async with g.Harness(mode, "dashboard", tag) as h:
        await h.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
        await asyncio.sleep(1.5)
        started = await h.start()
        samples = []
        for _ in range(12):
            await asyncio.sleep(1.0)
            s = await h.js(SIZE_JS)
            if s and s["streamW"] > 2:
                samples.append(s | {"checks": judge(s)})
        kbps = await h.js("""(async () => { const pc = (window.__sgPcs || []).filter(p => p.connectionState === 'connected').pop(); if (!pc) return null;
          const read = async () => { let v = null; (await pc.getStats()).forEach(r => { if (r.type === 'inbound-rtp' && r.kind === 'video') v = r; }); return v; };
          const a = await read(); await new Promise(r => setTimeout(r, 5000)); const b = await read();
          return Math.round((b.bytesReceived - a.bytesReceived) * 8 / ((b.timestamp - a.timestamp) / 1000) / 1000); })()""")
        shot = await h.call("Page.captureScreenshot", {"format": "png"})
        (h.dir / f"dashboard_{width}x{height}.png").write_bytes(base64.b64decode(shot["data"]))
        await h.click("STOP", 3)
    failed = sorted({k for s in samples for k, v in s["checks"].items() if not v})
    return {"viewport": f"{width}x{height}", "started": started, "samples": len(samples), "passed": bool(started and len(samples) >= 10 and not failed), "failed_checks": failed,
            "stream_sizes": sorted({f"{s['streamW']}x{s['streamH']}" for s in samples}), "display_sizes": sorted({f"{round(s['cssW'])}x{round(s['cssH'])}" for s in samples}),
            "iframe_width": sorted({round(s["iframeW"]) for s in samples}), "column_width": sorted({round(s["columnW"]) for s in samples if s["columnW"]}), "return_video_kbps": kbps, "tag": tag}


async def main() -> None:
    mode, name = sys.argv[1], sys.argv[2]
    results = [await check(mode, name, w, h) for w, h in VIEWPORTS]
    (g.OUT / f"fix3_{name}.json").write_text(json.dumps(results, indent=1))
    for r in results:
        print(json.dumps(r))


if __name__ == "__main__":
    asyncio.run(main())
