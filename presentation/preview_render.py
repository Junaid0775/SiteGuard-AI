#!/usr/bin/env python3
"""Approximate PNG preview of the built deck (no LibreOffice available).

Reads the .pptx package directly and draws shapes, text, pictures, lines and bar
charts with Pillow. It is a layout check, not a PowerPoint renderer: fonts are
Pillow's default face, so text is a little wider than Avenir Next Condensed.
"""
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
EMU = 914400
DPI = 160

HERE = Path(__file__).resolve().parent
PPTX = HERE / "SiteGuard_AI_Presentation.pptx"
OUTDIR = HERE / "previews"


def col(el):
    if el is None:
        return None
    s = el.find(A + "srgbClr")
    if s is None:
        return None
    v = s.get("val")
    a = s.find(A + "alpha")
    alpha = int(a.get("val")) / 100000 if a is not None else 1.0
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), int(round(alpha * 255)))


FONTS = {}


def font(sz, face="", bold=False):
    """Use the real macOS faces so the preview matches the deck's proportions."""
    px = max(6, int(round(sz)))
    cond = "condensed" in (face or "").lower()
    key = (px, cond, bool(bold))
    if key in FONTS:
        return FONTS[key]
    path = ("/System/Library/Fonts/Avenir Next Condensed.ttc" if cond
            else "/System/Library/Fonts/Avenir Next.ttc")
    idx = 0
    try:
        for i in range(16):
            try:
                probe = ImageFont.truetype(path, px, index=i)
            except Exception:
                break
            nm = " ".join(probe.getname()).lower()
            if bold and "bold" in nm and "semi" not in nm:
                idx = i
                break
            if not bold and "regular" in nm:
                idx = i
                break
        f = ImageFont.truetype(path, px, index=idx)
    except Exception:
        f = ImageFont.load_default(size=px)
    FONTS[key] = f
    return f


def text_runs(sp):
    tx = sp.find(P + "txBody")
    if tx is None:
        return []
    out = []
    for p in tx.findall(A + "p"):
        runs = []
        for r in p.findall(A + "r"):
            t = r.find(A + "t")
            rp = r.find(A + "rPr")
            sz = float(rp.get("sz", "1800")) / 100 if rp is not None else 18.0
            c = col(rp.find(A + "solidFill")) if rp is not None else None
            face, bold = "", False
            if rp is not None:
                lat = rp.find(A + "latin")
                face = lat.get("typeface") if lat is not None else ""
                bold = rp.get("b") == "1"
            runs.append((t.text or "", sz, c, face, bold))
        if runs:
            algn = p.find(A + "pPr")
            out.append((runs, algn.get("algn") if algn is not None else "l"))
    return out


def wrap(runs, maxw, dr):
    words = []
    for txt, sz, c, face, bold in runs:
        f = font(sz * DPI / 72, face, bold)
        for i, w in enumerate(txt.replace("\n", " \n ").split(" ")):
            words.append((w, f, c, sz))
    lines, cur, curw = [], [], 0
    for w, f, c, sz in words:
        if w == "\n":
            lines.append(cur)
            cur, curw = [], 0
            continue
        wl = f.getlength(w)
        sp = f.getlength(" ")
        if cur and curw + wl > maxw:
            lines.append(cur)
            cur, curw = [(w, f, c, sz)], wl
        else:
            if cur:
                cur.append((" ", f, c, sz))
                curw += sp
            cur.append((w, f, c, sz))
            curw += wl
    if cur:
        lines.append(cur)
    return lines


def draw_text(im, dr, box, paras, anchor="t"):
    x0, y0, x1, y1 = box
    maxw = max(4, x1 - x0)
    rows = []
    for runs, al in paras:
        lines = wrap(runs, maxw, dr)
        for ln in lines:
            lh = max(max(sz for _, _, _, sz in ln) * DPI / 72 * 1.18, 6)
            rows.append((ln, al, lh))
    if not rows:
        return
    total = sum(r[2] for r in rows)
    y = y0
    if anchor == "ctr":
        y = y0 + (y1 - y0 - total) / 2
    elif anchor == "b":
        y = y1 - total
    for ln, al, h in rows:
        wsum = sum(f.getlength(t) for t, f, _, _ in ln)
        x = x0 + ((x1 - x0 - wsum) / 2 if al == "ctr" else
                  (x1 - x0 - wsum if al == "r" else 0))
        for t, f, c, sz in ln:
            if t.strip():
                dr.text((x, y), t, font=f, fill=c or (245, 242, 234, 255))
            x += f.getlength(t)
        y += h


def freeform_points(spPr, x, y, w, h):
    path = spPr.find(A + "custGeom/" + A + "pathLst/" + A + "path")
    if path is None:
        return None
    pw, ph = float(path.get("w", w)), float(path.get("h", h))
    pts = []
    for node in path:
        pt = node.find(A + "pt")
        if pt is not None:
            pts.append((x + float(pt.get("x")) / pw * w, y + float(pt.get("y")) / ph * h))
    return pts or None


def fill_of(spPr):
    if spPr is None:
        return None
    if spPr.find(A + "noFill") is not None:
        return None
    c = col(spPr.find(A + "solidFill"))
    if c:
        return c
    g = spPr.find(A + "gradFill")
    if g is not None:
        gs = g.findall(A + "gsLst/" + A + "gs")
        if gs:
            cs = [col(x) for x in gs]
            cs = [x for x in cs if x]
            if cs:
                return tuple(sum(v[i] for v in cs) // len(cs) for i in range(4))
    return None


def line_of(spPr):
    if spPr is None:
        return None, 0
    ln = spPr.find(A + "ln")
    if ln is None:
        return None, 0
    c = col(ln.find(A + "solidFill"))
    w = float(ln.get("w", "12700")) / 12700
    return c, max(1, int(round(w * DPI / 72)))


def blend(im, box, c):
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(im.width, x1), min(im.height, y1)
    if x1 <= x0 or y1 <= y0:
        return
    ov = Image.new("RGBA", (x1 - x0, y1 - y0), c)
    im.alpha_composite(ov, (x0, y0))


def _lerp(c0, c1, k):
    return tuple(int(round(c0[i] + (c1[i] - c0[i]) * k)) for i in range(4))


def grad_image(spPr, w, h):
    """Render a DrawingML linear gradient to a bitmap the size of the shape."""
    g = spPr.find(A + "gradFill") if spPr is not None else None
    if g is None:
        return None
    stops = []
    for s in g.findall(A + "gsLst/" + A + "gs"):
        c = col(s)
        if c:
            stops.append((float(s.get("pos", "0")) / 100000.0, c))
    if len(stops) < 2:
        return None
    stops.sort()
    strip = Image.new("RGBA", (256, 1))
    px = strip.load()
    for i in range(256):
        t = i / 255.0
        c = None
        if t <= stops[0][0]:
            c = stops[0][1]
        elif t >= stops[-1][0]:
            c = stops[-1][1]
        else:
            for j in range(len(stops) - 1):
                p0, c0 = stops[j]
                p1, c1 = stops[j + 1]
                if p0 <= t <= p1:
                    k = (t - p0) / (p1 - p0) if p1 > p0 else 0
                    c = _lerp(c0, c1, k)
                    break
        px[i, 0] = c or (0, 0, 0, 0)
    lin = g.find(A + "lin")
    try:
        ang = float(lin.get("ang", "0")) / 60000.0 if lin is not None else 0.0
    except (TypeError, ValueError):
        ang = 0.0
    a = ang % 360
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    if abs(a) < 2 or abs(a - 360) < 2:
        return strip.resize((w, h), Image.BILINEAR)
    if abs(a - 180) < 2:
        return strip.transpose(Image.FLIP_LEFT_RIGHT).resize((w, h), Image.BILINEAR)
    if abs(a - 90) < 2:
        return strip.transpose(Image.TRANSPOSE).resize((w, h), Image.BILINEAR)
    if abs(a - 270) < 2:
        return (strip.transpose(Image.TRANSPOSE).transpose(Image.FLIP_TOP_BOTTOM)
                .resize((w, h), Image.BILINEAR))
    side = int(max(w, h) * 1.6) + 2
    sq = strip.resize((side, side), Image.BILINEAR)
    rot = sq.rotate(-a, resample=Image.BICUBIC, expand=False)
    cx, cy = side // 2, side // 2
    return rot.crop((cx - w // 2, cy - h // 2, cx - w // 2 + w, cy - h // 2 + h))


def paint_shape(im, spPr, prst, pts, x, y, w, h, fl, lc, lw):
    """Composite a shape on its own layer so partial alpha stays partial."""
    pad = int(lw) + 3
    x0, y0 = int(x) - pad, int(y) - pad
    lw_, lh_ = int(w) + 2 * pad + 2, int(h) + 2 * pad + 2
    if lw_ <= 0 or lh_ <= 0:
        return
    layer = Image.new("RGBA", (lw_, lh_), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ox, oy = x0, y0
    gimg = grad_image(spPr, w, h)
    box = [x - ox, y - oy, x + w - ox, y + h - oy]

    def filled(shape_fn):
        if gimg is not None:
            mask = Image.new("L", layer.size, 0)
            shape_fn(ImageDraw.Draw(mask), 255)
            gw, gh = gimg.size
            px_, py_ = int(x - ox), int(y - oy)
            piece = mask.crop((px_, py_, px_ + gw, py_ + gh))
            layer.paste(gimg, (px_, py_), mask=piece)
        elif fl:
            shape_fn(d, fl)

    try:
        if pts:
            loc = [(px - ox, py - oy) for px, py in pts]
            filled(lambda dd, c: dd.polygon(loc, fill=c))
            if lc:
                d.line(loc + [loc[0]], fill=lc, width=lw or 1, joint="curve")
        elif prst == "ellipse":
            filled(lambda dd, c: dd.ellipse(box, fill=c))
            if lc:
                d.ellipse(box, outline=lc, width=lw or 1)
        elif prst == "roundRect":
            r = min(w, h) * 0.16
            filled(lambda dd, c: dd.rounded_rectangle(box, radius=r, fill=c))
            if lc:
                d.rounded_rectangle(box, radius=r, outline=lc, width=lw or 1)
        elif prst and "triangle" in prst:
            tri = [(x + w / 2 - ox, y - oy), (x + w - ox, y + h - oy),
                   (x - ox, y + h - oy)]
            filled(lambda dd, c: dd.polygon(tri, fill=c))
            if lc:
                d.polygon(tri, outline=lc)
        elif prst == "diamond":
            dia = [(x + w / 2 - ox, y - oy), (x + w - ox, y + h / 2 - oy),
                   (x + w / 2 - ox, y + h - oy), (x - ox, y + h / 2 - oy)]
            filled(lambda dd, c: dd.polygon(dia, fill=c))
            if lc:
                d.polygon(dia, outline=lc)
        else:
            filled(lambda dd, c: dd.rectangle(box, fill=c))
            if lc:
                d.rectangle(box, outline=lc, width=lw or 0)
    finally:
        im.alpha_composite(layer, (max(0, x0), max(0, y0)))


def draw_chart(im, dr, fr, z, chart_path):
    xfrm = fr.find(P + "xfrm")
    off, ext = xfrm.find(A + "off"), xfrm.find(A + "ext")
    x, y = float(off.get("x")) / EMU * DPI, float(off.get("y")) / EMU * DPI
    w, h = float(ext.get("cx")) / EMU * DPI, float(ext.get("cy")) / EMU * DPI
    root = ET.fromstring(z.read(chart_path))
    bar = root.find(".//" + C + "barChart")
    if bar is None:
        dr.rectangle([x, y, x + w, y + h], outline=(214, 162, 77, 120))
        return
    horiz = bar.find(C + "barDir").get("val") == "bar"
    sers = []
    for ser in bar.findall(C + "ser"):
        val_el = ser.find(C + "val")
        vals = [v.text for v in val_el.iter(C + "v")] if val_el is not None else []
        cols = []
        for dp in ser.findall(C + "dPt"):
            idx = int(dp.find(C + "idx").get("val"))
            cols.append((idx, col(dp.find(C + "spPr/" + A + "solidFill"))))
        sc = col(ser.find(C + "spPr/" + A + "solidFill"))
        sers.append(([float(v) for v in vals], sc, dict(cols)))
    first_cat = bar.find(C + "ser/" + C + "cat")
    cats = [v.text for v in first_cat.iter(C + "v")] if first_cat is not None else []
    if not cats:
        cats = [""] * len(sers[0][0])
    n = len(cats)
    if n == 0:
        return
    ns = len(sers)
    gutter = 0.95 * DPI if horiz else 0.0
    bottom = 0.35 * DPI
    px0, py0 = x + gutter, y + 0.05 * DPI
    px1, py1 = x + w - 0.1 * DPI, y + h - bottom
    vmax, vmin, major, numfmt = 1.0, 0.0, 0.25, "0.000"
    ax = root.find(".//" + C + "valAx")
    if ax is not None:
        for tag, setter in (("max", "vmax"), ("min", "vmin")):
            el = ax.find(C + "scaling/" + C + tag)
            if el is not None:
                try:
                    if setter == "vmax":
                        vmax = float(el.get("val"))
                    else:
                        vmin = float(el.get("val"))
                except (TypeError, ValueError):
                    pass
        el = ax.find(C + "majorUnit")
        if el is not None:
            try:
                major = float(el.get("val"))
            except (TypeError, ValueError):
                pass
        el = ax.find(C + "numFmt")
        if el is not None and el.get("formatCode"):
            numfmt = el.get("formatCode")

    def fmt_val(v):
        if "." in numfmt or "%" in numfmt:
            return f"{v:.3f}"
        return f"{int(round(v))}"

    span = (vmax - vmin) or 1.0
    steps = max(1, int(round(span / (major or span))))
    for g in range(steps + 1):
        gx = px0 + (px1 - px0) * g / steps
        dr.line([gx, py0, gx, py1], fill=(29, 39, 52, 255), width=1)
        dr.text((gx - 10, py1 + 4), fmt_val(vmin + g * (major or span)),
                font=font(9), fill=(119, 130, 142, 255))
    if horiz:
        band = (py1 - py0) / n
        for i in range(n):
            cy = py0 + band * (i + 0.5)
            cat = cats[n - 1 - i] if False else cats[i]
            dr.text((x, cy - 6), cat, font=font(10), fill=(174, 182, 191, 255))
            for si, (vals, sc, pts) in enumerate(sers):
                bh = band * 0.62 / ns
                by = cy - band * 0.31 + si * bh
                v = vals[i]
                c = pts.get(i) or sc or (214, 162, 77, 255)
                ex = px0 + (px1 - px0) * (min(v, vmax) - vmin) / span
                dr.rectangle([px0, by, ex, by + bh], fill=c)
                dr.text((ex + 3, by + bh / 2 - 6), fmt_val(v), font=font(9),
                        fill=(245, 242, 234, 255))
    else:
        band = (px1 - px0) / n
        for i in range(n):
            cx = px0 + band * (i + 0.5)
            off = (px1 - px0) / 120
            dr.text((cx - 14, py1 + 4), cats[i], font=font(9), fill=(174, 182, 191, 255))
            for si, (vals, sc, pts) in enumerate(sers):
                bw = band * 0.30
                bx = cx - bw * ns / 2 + si * bw
                v = vals[i]
                c = pts.get(i) or sc or (214, 162, 77, 255)
                ty = py1 - (py1 - py0) * (min(v, vmax) - vmin) / span
                dr.rectangle([bx, ty, bx + bw, py1], fill=c)
                dr.text((bx, max(py0, ty - 13)), fmt_val(v), font=font(8),
                        fill=(245, 242, 234, 255))


def render(pptx, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(pptx)
    names = sorted([n for n in z.namelist() if n.startswith("ppt/slides/slide")],
                   key=lambda n: int("".join(ch for ch in Path(n).stem if ch.isdigit())))
    pres = ET.fromstring(z.read("ppt/presentation.xml"))
    sz = pres.find(P + "sldSz")
    W = int(round(float(sz.get("cx")) / EMU * DPI))
    H = int(round(float(sz.get("cy")) / EMU * DPI))
    tmp = outdir / "_media"
    tmp.mkdir(exist_ok=True)

    for idx, name in enumerate(names, 1):
        im = Image.new("RGBA", (W, H), (11, 17, 25, 255))
        dr = ImageDraw.Draw(im)
        rels = {}
        relname = name.replace("slides/", "slides/_rels/") + ".rels"
        if relname in z.namelist():
            for rel in ET.fromstring(z.read(relname)):
                rels[rel.get("Id")] = rel.get("Target").replace("../", "ppt/")
        tree = ET.fromstring(z.read(name))
        for el in tree.find(P + "cSld").find(P + "spTree"):
            tag = el.tag.split("}")[1]
            if tag in ("sp", "cxnSp"):
                spPr = el.find(P + "spPr")
                if spPr is None:
                    continue
                xfrm = spPr.find(A + "xfrm")
                if xfrm is None:
                    continue
                off, ext = xfrm.find(A + "off"), xfrm.find(A + "ext")
                if off is None or ext is None:
                    continue
                x = float(off.get("x")) / EMU * DPI
                y = float(off.get("y")) / EMU * DPI
                w = float(ext.get("cx")) / EMU * DPI
                h = float(ext.get("cy")) / EMU * DPI
                fl = fill_of(spPr)
                lc, lw = line_of(spPr)
                if tag == "cxnSp":
                    if lc:
                        dr.line([x, y, x + w, y + h], fill=lc, width=lw)
                    continue
                geom = spPr.find(A + "prstGeom")
                pts = freeform_points(spPr, x, y, w, h)
                paint_shape(im, spPr, geom.get("prst") if geom is not None else None,
                            pts, x, y, w, h, fl, lc, lw)
                runs = text_runs(el)
                if runs:
                    bodyPr = el.find(P + "txBody/" + A + "bodyPr")
                    anc = bodyPr.get("anchor", "t") if bodyPr is not None else "t"
                    anchor = {"t": "t", "ctr": "ctr", "b": "b"}.get(anc, "t")
                    draw_text(im, dr, (x, y, x + w, y + h), runs, anchor=anchor)
            elif tag == "pic":
                spPr = el.find(P + "spPr")
                xfrm = spPr.find(A + "xfrm")
                off, ext = xfrm.find(A + "off"), xfrm.find(A + "ext")
                x = float(off.get("x")) / EMU * DPI
                y = float(off.get("y")) / EMU * DPI
                w = float(ext.get("cx")) / EMU * DPI
                h = float(ext.get("cy")) / EMU * DPI
                src = el.find(P + "blipFill/" + A + "blip").get(R + "embed")
                target = rels.get(src)
                if not target:
                    continue
                data = tmp / Path(target).name
                if not data.exists():
                    data.write_bytes(z.read(target))
                img = Image.open(data).convert("RGBA")
                sr = el.find(P + "blipFill/" + A + "srcRect")
                if sr is not None:
                    l = float(sr.get("l", 0)) / 100000
                    t = float(sr.get("t", 0)) / 100000
                    r = float(sr.get("r", 0)) / 100000
                    b = float(sr.get("b", 0)) / 100000
                    img = img.crop((int(img.width * l), int(img.height * t),
                                    int(img.width * (1 - r)), int(img.height * (1 - b))))
                img = img.resize((max(1, int(round(w))), max(1, int(round(h)))),
                                 Image.LANCZOS)
                im.alpha_composite(img, (int(round(x)), int(round(y))))
            elif tag == "graphicFrame":
                gc = el.find(A + "graphic/" + A + "graphicData/" + C + "chart")
                if gc is not None:
                    target = rels.get(gc.get(R + "id"))
                    if target:
                        draw_chart(im, dr, el, z, target)
        im.convert("RGB").save(outdir / f"slide-{idx:02d}.png")
        print("rendered", outdir / f"slide-{idx:02d}.png")


if __name__ == "__main__":
    render(PPTX, OUTDIR)
