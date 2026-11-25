#!/usr/bin/env python3
"""Build SiteGuard_AI_Presentation.pptx — 10 slides, python-pptx only.

Design system: editorial night-shift. Ink ground, ivory type, one gold accent,
hairline rules instead of boxes, large scale contrast (8 pt caps against 90 pt
numbers). Every number comes from ../FACTS.md.
"""
import sys
import textwrap
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_MARK
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
OUT = HERE / "SiteGuard_AI_Presentation.pptx"

# ---------------------------------------------------------------- design tokens
W, H = 13.333, 7.5
LM, RM = 0.95, 0.75
CW = W - LM - RM                      # 11.633
TOP_RULE = 0.62
KICK_Y = 0.86
HEAD_Y = 1.12
BODY_Y = 2.45                         # content starts here (2-line headlines)
FOOT_Y = 6.98

INK = "0A0F16"
INK2 = "0E1520"
DEEP = "06090D"
GOLD = "D9A75C"
GOLD_DIM = "8C6B33"
AMBER = "E8A03C"
IVORY = "F5F2EA"
MUTED = "A8B2BE"
META = "77828E"
HAIR = "FFFFFF"
SLATE = "5E6B7A"

HEAD = "Avenir Next Condensed"
BODY = "Avenir Next"

BG = PROJECT / "assets/images/SiteGuard_AI_Cinematic_Construction_Background_1600h.png"
OVERVIEW = PROJECT / "experiments/frontend_redesign/evidence/reference_match/01_overview_1920x1080_redacted.png"
EVENTS = PROJECT / "experiments/frontend_redesign/evidence/reference_match/05_safety_events_1470x830_redacted.png"
INSPECT = PROJECT / "experiments/frontend_redesign/evidence/phase4_all_pages/full/full_image_inspection_result_1440.png"

SIZES = {str(BG): (2843, 1600), str(OVERVIEW): (1920, 1080),
         str(EVENTS): (1470, 830), str(INSPECT): (1440, 1531)}


def rgb(h):
    return RGBColor.from_string(h.replace("#", ""))


def _alpha(clr, a):
    el = etree.SubElement(clr, qn("a:alpha"))
    el.set("val", str(int(round(a * 100000))))


def solid(sh, hexc, alpha=None):
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(hexc)
    if alpha is not None:
        sf = sh.fill._xPr.find(qn("a:solidFill"))
        _alpha(sf.find(qn("a:srgbClr")), alpha)


def line(sh, hexc, w=1.0, alpha=None):
    sh.line.fill.solid()
    sh.line.color.rgb = rgb(hexc)
    sh.line.width = Pt(w)
    if alpha is not None:
        ln = sh._element.spPr.find(qn("a:ln"))
        _alpha(ln.find(qn("a:solidFill")).find(qn("a:srgbClr")), alpha)


def gradient(sh, c1, c2, angle=0, a1=None, a2=None):
    sh.fill.gradient()
    st = sh.fill.gradient_stops
    st[0].color.rgb = rgb(c1)
    st[0].position = 0.0
    st[1].color.rgb = rgb(c2)
    st[1].position = 1.0
    gs = sh.fill._xPr.find(qn("a:gradFill")).find(qn("a:gsLst")).findall(qn("a:gs"))
    if a1 is not None:
        _alpha(gs[0].find(qn("a:srgbClr")), a1)
    if a2 is not None:
        _alpha(gs[1].find(qn("a:srgbClr")), a2)
    sh.fill.gradient_angle = angle


def shape(slide, kind, x, y, w, h, fill=IVORY, alpha=None, edge=None, ew=1.0,
          ea=None, grad=None, radius=None, name=None):
    sh = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius is not None:
        sh.adjustments[0] = radius
    if grad is not None:
        gradient(sh, grad[0], grad[1], grad[2] if len(grad) > 2 else 0,
                 grad[3] if len(grad) > 3 else None, grad[4] if len(grad) > 4 else None)
    elif fill is None:
        sh.fill.background()
    else:
        solid(sh, fill, alpha)
    if edge is None:
        sh.line.fill.background()
    else:
        line(sh, edge, ew, ea)
    sh.shadow.inherit = False
    if name:
        sh.name = name
    return sh


def hair(slide, x, y, w, a=0.14, color=HAIR, t=0.008):
    sh = shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, t, fill=color, alpha=a)
    sh.line.fill.background()
    return sh


def vhair(slide, x, y, h, a=0.14):
    return shape(slide, MSO_SHAPE.RECTANGLE, x, y, 0.008, h, fill=HAIR, alpha=a)


def _runs(p, parts, size, font, color, bold, spc, italic):
    for part in parts:
        txt = part[0]
        col = part[1] if len(part) > 1 and part[1] else color
        bld = part[2] if len(part) > 2 else bold
        r = p.add_run()
        r.text = txt
        f = r.font
        f.name = font
        f.size = Pt(size)
        f.bold = bld
        f.italic = italic
        f.color.rgb = rgb(col)
        if spc:
            r._r.get_or_add_rPr().set("spc", str(int(spc * 100)))


def txt(slide, x, y, w, h, s, size=11, color=IVORY, font=BODY, bold=False,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0, spc=None,
        italic=False, wrap=True):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, ln in enumerate(str(s).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        _runs(p, [(ln,)], size, font, color, bold, spc, italic)
    return box


def rich(slide, x, y, w, h, parts, size=11, color=IVORY, font=BODY, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    _runs(p, parts, size, font, color, bold, None, False)
    return box


def label(slide, x, y, s, color=GOLD_DIM, size=7.8, w=4.0, align=PP_ALIGN.LEFT,
          spc=2.2):
    return txt(slide, x, y, w, 0.18, s, size, color, HEAD, bold=True,
               align=align, spc=spc)


# ------------------------------------------------------------------ background
def ground(slide, edge_glow=True):
    """Ink ground with a soft corner lift, so the black is never flat."""
    shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, H, fill=INK, name="bleed")
    g = shape(slide, MSO_SHAPE.RECTANGLE, -1, -2.5, W + 2, H + 4.2, fill=None,
              name="bleed")
    gradient(g, "17202C", "0A0F16", 45)
    if edge_glow:
        v = shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 4.4, H, fill=None, name="bleed")
        gradient(v, "0B1119", "0A0F16", 90, 0.0, 0.0)


def top(slide, chapter, n):
    shape(slide, MSO_SHAPE.DIAMOND, LM, 0.395, 0.155, 0.155, fill=None,
          edge=GOLD, ew=0.9)
    shape(slide, MSO_SHAPE.OVAL, LM + 0.058, 0.453, 0.04, 0.04, fill=GOLD)
    txt(slide, LM + 0.31, 0.385, 3.4, 0.18, "SITEGUARD AI", 8.2, GOLD, HEAD,
        bold=True, spc=2.6)
    txt(slide, W - RM - 4.6, 0.385, 4.6, 0.18, chapter, 8.2, META, HEAD,
        bold=True, align=PP_ALIGN.RIGHT, spc=2.4)
    hair(slide, LM, TOP_RULE, CW, 0.16)


def head(slide, kicker, headline, size=35, width=None, color=IVORY):
    txt(slide, LM, KICK_Y, 9.0, 0.18, kicker.upper(), 8.2, GOLD, HEAD, bold=True,
        spc=2.6)
    txt(slide, LM, HEAD_Y, width or CW + 0.4, 1.15, headline, size, color, HEAD,
        bold=True, spacing=0.92)


def foot(slide, n):
    hair(slide, LM, FOOT_Y, CW, 0.13)
    txt(slide, LM, FOOT_Y + 0.10, 5.4, 0.18,
        "JUNAID AHMAD \u00b7 12419395 \u00b7 471 PROJECT", 7.6, META, HEAD,
        bold=True, spc=1.9)
    rich(slide, W - RM - 1.4, FOOT_Y + 0.07, 1.4, 0.2,
         [(f"{n:02d}", GOLD, True), ("  / 10", META, False)],
         size=9.5, font=HEAD, align=PP_ALIGN.RIGHT)
    seg, gap = 0.155, 0.062
    total = 10 * seg + 9 * gap
    x0 = (W - total) / 2
    for i in range(10):
        act = i == n - 1
        shape(slide, MSO_SHAPE.RECTANGLE, x0 + i * (seg + gap), 7.28,
              seg, 0.045 if act else 0.022,
              fill=GOLD if act else HAIR, alpha=None if act else 0.16)


# --------------------------------------------------------------------- images
def crop_region(sw, sh, region, frame_aspect):
    l, t, r, b = region
    wp, hp = (r - l) * sw, (b - t) * sh
    aspect = wp / hp
    if aspect > frame_aspect:
        cut = (wp - hp * frame_aspect) / 2 / wp * (r - l)
        l, r = l + cut, r - cut
    else:
        cut = (hp - wp / frame_aspect) / 2 / hp * (b - t)
        t, b = t + cut, b - cut
    return l, t, 1 - r, 1 - b


def picture(slide, path, x, y, w, h, region=(0, 0, 1, 1), name=None):
    sw, sh = SIZES[str(path)]
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                   Inches(w), Inches(h))
    cl, ct, cr, cb = crop_region(sw, sh, region, w / h)
    pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = cl, ct, cr, cb
    if name:
        pic.name = name
    return pic


def scrim(slide, x, y, w, h, angle=0, a1=1.0, a2=0.0, color=INK):
    g = shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, fill=None, name="bleed")
    gradient(g, color, color, angle, a1, a2)
    return g


# --------------------------------------------------------------------- charts
def chart(slide, x, y, w, h, cats, series, colors, fmt="0.000", vmax=1.0,
          major=0.25, lab_size=7.5, cat_size=8.0, gap=32, color_cats=True,
          lab_color=IVORY, pos=XL_LABEL_POSITION.OUTSIDE_END):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(x), Inches(y),
                                Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = False
    ch.font.name = BODY
    ch.font.size = Pt(cat_size)
    ch.font.color.rgb = rgb(MUTED)
    try:
        ch.format.fill.background()
        ch.format.line.fill.background()
    except Exception:
        pass
    plot = ch.plots[0]
    plot.gap_width = gap
    plot.vary_by_categories = False
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = rgb(colors[0])
    ser.format.line.fill.background()
    if color_cats and len(colors) > 1 and isinstance(colors[1], (list, tuple)):
        for pi, c in enumerate(colors[1]):
            pt = ser.points[pi]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(c)
            pt.format.line.fill.background()
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = fmt
    dl.number_format_is_linked = False
    dl.position = pos
    dl.font.size = Pt(lab_size)
    dl.font.name = BODY
    dl.font.bold = False
    dl.font.color.rgb = rgb(lab_color)
    va = ch.value_axis
    va.minimum_scale = 0
    va.maximum_scale = vmax
    va.major_unit = major
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb("1D2734")
    va.major_gridlines.format.line.width = Pt(0.5)
    va.format.line.fill.background()
    va.major_tick_mark = XL_TICK_MARK.NONE
    va.minor_tick_mark = XL_TICK_MARK.NONE
    va.tick_labels.font.size = Pt(cat_size - 0.8)
    va.tick_labels.font.color.rgb = rgb(META)
    va.tick_labels.font.name = BODY
    va.tick_labels.number_format = "0.00" if "." in fmt else "0"
    va.tick_labels.number_format_is_linked = False
    ca = ch.category_axis
    ca.has_major_gridlines = False
    ca.format.line.fill.background()
    ca.major_tick_mark = XL_TICK_MARK.NONE
    ca.minor_tick_mark = XL_TICK_MARK.NONE
    ca.tick_labels.font.size = Pt(cat_size)
    ca.tick_labels.font.color.rgb = rgb(MUTED)
    ca.tick_labels.font.name = BODY
    return ch


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def tick_mark(slide, x, y, s=0.18, color=GOLD, w=1.5):
    c1 = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x),
                                    Inches(y + 0.58 * s), Inches(x + 0.33 * s),
                                    Inches(y + 0.94 * s))
    line(c1, color, w)
    c2 = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x + 0.33 * s),
                                    Inches(y + 0.94 * s), Inches(x + s),
                                    Inches(y + 0.10 * s))
    line(c2, color, w)


# ================================================================ deck build
def build():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    blank = prs.slide_layouts[6]

    # ------------------------------------------------------------ 01 · COVER
    s = prs.slides.add_slide(blank)
    shape(s, MSO_SHAPE.RECTANGLE, 0, 0, W, H, fill=INK, name="bleed")
    picture(s, BG, 7.42, 0, 5.913, H, region=(0.50, 0.0, 0.99, 1.0), name="bleed")
    scrim(s, 7.42, 0, 2.3, H, 0)
    scrim(s, 7.42, 5.1, 5.9, 2.4, 90, 0.0, 0.92)

    shape(s, MSO_SHAPE.DIAMOND, LM, 0.56, 0.19, 0.19, fill=None, edge=GOLD, ew=1.0)
    shape(s, MSO_SHAPE.OVAL, LM + 0.071, 0.631, 0.048, 0.048, fill=GOLD)
    txt(s, LM + 0.38, 0.56, 4.4, 0.2, "SITEGUARD AI", 8.6, GOLD, HEAD, bold=True,
        spc=2.8)
    txt(s, LM + 0.38, 0.78, 4.4, 0.2, "471 PROJECT \u00b7 FINAL REVIEW", 7.6, META,
        HEAD, bold=True, spc=2.2)

    txt(s, LM, 1.72, 6.0, 0.2, "COMPUTER VISION FOR CONSTRUCTION SAFETY", 8.6,
        GOLD, HEAD, bold=True, spc=2.6)
    txt(s, LM, 1.98, 6.3, 1.0, "SiteGuard AI", 66, IVORY, HEAD, bold=True,
        spacing=0.86)
    hair(s, LM, 3.14, 4.55, 1.0, GOLD, 0.018)
    txt(s, LM, 3.40, 5.55, 0.95,
        "AI-assisted PPE monitoring that runs on one laptop.", 19, MUTED, BODY,
        spacing=1.2)

    hair(s, LM, 5.58, 5.1, 0.16)
    cols = [("PRESENTED BY", "JUNAID AHMAD"), ("REG. NO.", "12419395"),
            ("DATE", "26 NOVEMBER 2026")]
    for i, (k, v) in enumerate(cols):
        x = LM + i * 1.83
        label(s, x, 5.74, k, META, 7.2, 1.7, spc=2.0)
        txt(s, x, 5.94, 1.72, 0.4, v, 10.5 if i < 2 else 9.5, IVORY, BODY,
            spacing=1.05)

    txt(s, W - 0.9 - 5.2, 6.94, 5.2, 0.2, "SAFER SITES \u00b7 SMARTER TOMORROW", 8,
        GOLD, HEAD, bold=True, align=PP_ALIGN.RIGHT, spc=2.4)
    notes(s, NOTES[0])

    # ------------------------------------------------------------- 02 · CASE
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "02 \u00b7 THE CASE", 2)
    head(s, "Why this exists", "A supervisor cannot watch\nevery worker, every second")
    blocks = [
        ("01", "THE EXPOSURE",
         "Helmets, vests and gloves get missed on busy sites, and manual checks only "
         "catch the moments somebody is looking."),
        ("02", "THE IDEA",
         "A camera model inspects every worker in frame and flags the ones that may "
         "be missing equipment."),
        ("03", "THE RULE",
         "The AI suggests; a person reviews and decides. Nothing is called a "
         "violation on its own."),
    ]
    for i, (num, lab, body) in enumerate(blocks):
        y = BODY_Y + i * 1.34
        txt(s, LM, y, 0.6, 0.2, num, 9, GOLD, HEAD, bold=True, spc=1.6)
        label(s, LM + 0.55, y + 0.005, lab, IVORY, 7.8, 4.4)
        txt(s, LM + 0.55, y + 0.28, 4.55, 0.9, body, 12, MUTED, BODY, spacing=1.28)
        if i < 2:
            hair(s, LM, y + 1.16, 5.05, 0.13)

    # right panel: what ships
    px, py, pw, ph = 6.95, BODY_Y, 5.4, 4.05
    g = shape(s, MSO_SHAPE.RECTANGLE, px, py, pw, ph, fill=None)
    gradient(g, "18212D", "0B1017", 120)
    shape(s, MSO_SHAPE.RECTANGLE, px, py, pw, ph, fill=None, edge=GOLD, ew=0.75,
          ea=0.30)
    label(s, px + 0.42, py + 0.30, "WHAT SHIPS ON DAY ONE", GOLD, 7.8, 4.2)
    hair(s, px + 0.42, py + 0.54, pw - 0.84, 0.12)
    items = ["12-class detector \u00b7 0.734 mAP50",
             "Helmet, vest and glove check per worker",
             "Annotated evidence saved per event",
             "Human review queue and CSV export",
             "Runs locally \u00b7 nothing is uploaded"]
    for i, it in enumerate(items):
        y = py + 0.72 + i * 0.56
        tick_mark(s, px + 0.44, y, 0.18, GOLD, 1.5)
        txt(s, px + 0.76, y, pw - 1.2, 0.26, it, 11, IVORY, BODY)
    txt(s, px + 0.42, py + ph - 0.44, pw - 0.9, 0.2,
        "DECISION SUPPORT, NOT A REPLACEMENT", 7.4, META, HEAD, bold=True, spc=1.8)
    foot(s, 2)
    notes(s, NOTES[1])

    # ----------------------------------------------------------- 03 · SYSTEM
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "03 \u00b7 THE SYSTEM", 3)
    head(s, "How it works", "From a camera frame to a reviewed\nevent in five steps")

    steps = [
        ("01", "INPUT", "A photo, a video file or the live webcam."),
        ("02", "DETECT", "YOLO26n finds people, PPE and missing PPE."),
        ("03", "LINK", "Geometry ties each item to the right worker."),
        ("04", "CONFIRM", "Three analysed frames; thirty-second filter."),
        ("05", "REVIEW", "Dashboard, evidence, human decision, CSV."),
    ]
    col = 2.39
    hair(s, LM, 3.06, CW, 0.22)
    for i, (num, title, body) in enumerate(steps):
        x = LM + i * col
        txt(s, x, BODY_Y - 0.10, 0.9, 0.44, num, 24, GOLD_DIM, HEAD, bold=True,
            spc=0.6)
        shape(s, MSO_SHAPE.OVAL, x - 0.045, 3.015, 0.09, 0.09, fill=GOLD)
        txt(s, x, 3.28, col - 0.35, 0.22, title, 11.5, IVORY, HEAD, bold=True,
            spc=2.0)
        txt(s, x, 3.56, col - 0.42, 0.95, body, 10.5, MUTED, BODY, spacing=1.25)

    hair(s, LM, 4.72, CW, 0.13)
    guards = [("0.50", "MISSING-PPE CONFIDENCE", "a box above this can become an event"),
              ("0.40", "PPE EVIDENCE CONFIDENCE", "a box above this counts as worn"),
              ("3 \u00b7 30 s", "FRAMES \u00b7 REPEAT FILTER", "before an event is raised")]
    for i, (val, lab, sub) in enumerate(guards):
        x = LM + i * 3.95
        txt(s, x, 4.94, 3.4, 0.5, val, 26, IVORY, HEAD, bold=True, spacing=0.9)
        label(s, x, 5.46, lab, GOLD, 7.2, 3.4, spc=1.8)
        txt(s, x, 5.66, 3.4, 0.22, sub, 9.5, META, BODY)
        if i:
            vhair(s, x - 0.45, 4.98, 0.95, 0.14)

    txt(s, LM, 6.24, 11.4, 0.5,
        "Geometry decides who is tested. Time decides whether an event exists. "
        "A person decides what it means.", 12.5, IVORY, BODY, italic=True)
    foot(s, 3)
    notes(s, NOTES[2])

    # ------------------------------------------------------------- 04 · DATA
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "04 \u00b7 THE DATA", 4)
    head(s, "What it learned from", "1,000 labelled images, 12 classes,\none clean split")

    label(s, LM, BODY_Y, "LABELLED IMAGES", META, 7.4, 3.0)
    txt(s, LM - 0.06, BODY_Y + 0.12, 4.0, 1.5, "1,000", 92, IVORY, HEAD,
        bold=True, spacing=0.82)
    hair(s, LM, 4.28, 3.95, 0.16)
    rows = [("800", "TRAINING IMAGES"), ("200", "VALIDATION IMAGES"),
            ("2,961", "LABELLED OBJECTS IN VALIDATION")]
    for i, (v, k) in enumerate(rows):
        y = 4.42 + i * 0.46
        txt(s, LM, y, 1.3, 0.3, v, 17, GOLD, HEAD, bold=True)
        label(s, LM + 1.28, y + 0.06, k, MUTED, 7.4, 3.1, spc=1.7)
        hair(s, LM, y + 0.40, 3.95, 0.10)

    txt(s, LM, 6.02, 3.9, 0.4,
        "Ultralytics Construction-PPE \u00b7 CC BY 4.0 \u00b7 read-only, "
        "checksum-verified.", 8.4, META, BODY, spacing=1.15)

    # class balance ledger
    cx = 5.55
    label(s, cx, BODY_Y - 0.02, "LABELLED OBJECTS PER CLASS \u00b7 VALIDATION",
          GOLD, 7.4, 5.6)
    txt(s, cx + 4.4, BODY_Y - 0.02, 2.2, 0.18, "2,961 TOTAL", 7.4, META, HEAD,
        bold=True, align=PP_ALIGN.RIGHT, spc=1.8)
    classes = [("Person", 481), ("boots", 481), ("gloves", 381), ("vest", 340),
               ("helmet", 294), ("no_gloves", 203), ("no_helmet", 179),
               ("no_boots", 178), ("goggles", 139), ("no_vest", 130),
               ("no_goggle", 82), ("forklift", 73)]
    for i, (nm, n) in enumerate(classes):
        colx = 5.55 if i < 6 else 9.05
        y = 2.62 + (i % 6) * 0.62
        col = (SLATE if nm in ("Person", "forklift") else
               (AMBER if nm.startswith("no_") else GOLD))
        txt(s, colx, y, 1.7, 0.18, nm, 8.8, IVORY, BODY)
        txt(s, colx + 1.95, y - 0.02, 1.05, 0.2, str(n), 9.6, col, BODY,
            bold=True, align=PP_ALIGN.RIGHT)
        shape(s, MSO_SHAPE.RECTANGLE, colx, y + 0.22, max(0.05, n / 481 * 2.5),
              0.045, fill=col, alpha=0.85)
    txt(s, cx, 6.34, 6.4, 0.4,
        "Gold is PPE present, amber is missing PPE: rarer in the data, and weaker "
        "on the model.", 9, META, BODY, spacing=1.15)
    foot(s, 4)
    notes(s, NOTES[3])

    # ------------------------------------------------------------ 05 · MODEL
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "05 \u00b7 THE MODEL", 5)
    head(s, "Model & training", "Small on purpose: 21 minutes\nto train, 20 ms to decide")

    spec = [("MODEL", "YOLO26n", "nano \u00b7 fine-tuned"),
            ("TRAINING", "21 min", "30 epochs \u00b7 batch 8"),
            ("INPUT", "640 px", "per analysed frame"),
            ("LIVE SPEED", "29.8 fps", "0 frames dropped")]
    for i, (lab, val, sub) in enumerate(spec):
        x = LM + i * 2.93
        label(s, x, BODY_Y, lab, GOLD, 7.4, 2.7)
        txt(s, x - 0.02, BODY_Y + 0.22, 2.7, 0.6, val, 34, IVORY, HEAD, bold=True,
            spacing=0.9)
        txt(s, x, BODY_Y + 0.74, 2.7, 0.22, sub, 9, META, BODY)
        if i:
            vhair(s, x - 0.28, BODY_Y - 0.02, 0.80, 0.12)

    hair(s, LM, 3.72, CW, 0.13)
    label(s, LM, 3.98, "WHY THE NANO MODEL", GOLD, 7.6, 4.4)
    txt(s, LM, 4.24, 4.75, 1.5,
        "A 30 fps camera gives 33 milliseconds per frame. Inference takes about 20, "
        "so live video stays smooth without dropping frames.", 13, IVORY, BODY,
        spacing=1.35)
    rich(s, LM, 5.16, 4.75, 0.3,
         [("2.57 M", GOLD, True), ("  parameters  \u00b7  best epoch ", MUTED, False),
          ("25", GOLD, True)], size=11, font=BODY)
    txt(s, LM, 5.92, 4.75, 0.5,
        "Recorded replay of 149 frames on a MacBook Air M5. Not a physical-camera "
        "test.", 8.4, META, BODY, spacing=1.2)

    # frame budget diagram
    bx, by, bw = 6.35, 4.06, 5.85
    label(s, bx, by, "TIME PER FRAME \u00b7 MILLISECONDS", GOLD, 7.4, 5.0)
    label(s, bx, by + 0.30, "CAMERA BUDGET AT 30 FPS", META, 7.0, 4.0, spc=1.6)
    shape(s, MSO_SHAPE.RECTANGLE, bx, by + 0.50, bw, 0.075, fill=IVORY, alpha=0.12)
    txt(s, bx + bw + 0.12, by + 0.42, 0.7, 0.2, "33.3", 8, MUTED, BODY)

    label(s, bx, by + 0.80, "YOLO26N MEAN INFERENCE", META, 7.0, 4.0, spc=1.6)
    shape(s, MSO_SHAPE.RECTANGLE, bx, by + 1.00, bw * 20.3 / 33.3, 0.075, fill=GOLD)
    txt(s, bx + bw * 20.3 / 33.3 + 0.12, by + 0.92, 1.3, 0.2, "20.3", 8, GOLD, BODY,
        bold=True)

    # p95 marker
    mx = bx + bw * 24.8 / 33.3
    shape(s, MSO_SHAPE.RECTANGLE, mx, by + 0.80, 0.012, 0.30, fill=IVORY, alpha=0.55)
    txt(s, mx + 0.10, by + 1.00, 1.4, 0.2, "p95 24.8", 7.6, MUTED, BODY)

    # axis
    hair(s, bx, by + 1.30, bw, 0.20)
    for t in (0, 10, 20, 30):
        tx = bx + bw * t / 33.3
        shape(s, MSO_SHAPE.RECTANGLE, tx, by + 1.28, 0.008, 0.06, fill=IVORY,
              alpha=0.30)
        txt(s, tx - 0.12, by + 1.38, 0.5, 0.18, str(t), 7.2, META, BODY)
    txt(s, bx + bw - 0.1, by + 1.38, 0.6, 0.18, "ms", 7.2, META, BODY)

    txt(s, bx, by + 1.70, 5.9, 0.4,
        "Mean 20.3 ms against a 33.3 ms budget; even p95 leaves headroom.",
        8.6, META, BODY)
    foot(s, 5)
    notes(s, NOTES[4])

    # ---------------------------------------------------------- 06 · ACCURACY
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "06 \u00b7 ACCURACY", 6)
    head(s, "Accuracy \u00b7 YOLO26n", "Strong on people and worn PPE.\nWeak on missing goggles.")

    label(s, LM, BODY_Y, "mAP50 \u00b7 12 CLASSES", META, 7.4, 3.6)
    txt(s, LM - 0.07, BODY_Y + 0.14, 4.2, 1.5, "0.734", 78, GOLD, HEAD, bold=True,
        spacing=0.84)
    txt(s, LM, 3.94, 3.9, 0.5,
        "Validation split \u00b7 200 images \u00b7 2,961 objects \u00b7 640 px",
        8.6, META, BODY, spacing=1.2)

    rows = [("PRECISION", "0.832", "how often a box is right"),
            ("RECALL", "0.681", "how much it finds"),
            ("mAP50-95", "0.523", "stricter overlap")]
    hair(s, LM, 4.62, 3.95, 0.13)
    for i, (k, v, sub) in enumerate(rows):
        y = 4.74 + i * 0.58
        label(s, LM, y + 0.04, k, IVORY, 7.4, 2.0, spc=1.8)
        txt(s, LM + 1.85, y - 0.04, 2.1, 0.3, v, 17, IVORY, HEAD, bold=True,
            align=PP_ALIGN.RIGHT)
        txt(s, LM, y + 0.24, 2.0, 0.2, sub, 8.2, META, BODY)
        if i < 2:
            hair(s, LM, y + 0.52, 3.95, 0.10)

    # class chart
    cx, cy, cw, chh = 5.35, 2.64, 7.2, 3.62
    label(s, cx, BODY_Y - 0.02, "mAP50 BY CLASS \u00b7 AMBER = MISSING PPE", GOLD,
          7.4, 6.0)
    cats = ["no_goggle", "no_gloves", "no_helmet", "no_vest", "no_boots", "boots",
            "gloves", "forklift", "helmet", "vest", "goggles", "Person"]
    vals = [0.148, 0.620, 0.652, 0.692, 0.748, 0.771, 0.793, 0.807, 0.825, 0.887,
            0.924, 0.940]
    cols = [AMBER if c.startswith("no_") else GOLD for c in cats]
    chart(s, cx - 0.16, cy, cw, chh, cats, [("mAP50", vals)], [GOLD, cols],
          fmt="0.000", vmax=1.0, major=0.25, lab_size=8.0, cat_size=9.0, gap=30,
          lab_color=INK, pos=XL_LABEL_POSITION.INSIDE_END)
    txt(s, cx, 6.40, 7.0, 0.24,
        "At the app's 0.25 confidence: precision 0.884, recall 0.745.", 8.4, META,
        BODY)
    foot(s, 6)
    notes(s, NOTES[5])

    # ------------------------------------------------------------- 07 · TEST
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "07 \u00b7 THE TEST", 7)
    head(s, "The bigger-model experiment",
         "A bigger model gained accuracy.\nIt lost the frame budget.")

    cols = [(0.95, 4.10, "METRIC", PP_ALIGN.LEFT, MUTED),
            (5.30, 2.20, "YOLO26N \u00b7 ACTIVE", PP_ALIGN.RIGHT, GOLD),
            (7.70, 2.20, "E3 \u00b7 YOLO26M", PP_ALIGN.RIGHT, MUTED),
            (10.10, 2.35, "GATE", PP_ALIGN.RIGHT, MUTED)]
    for x, w, t, al, c in cols:
        txt(s, x, BODY_Y, w, 0.22, t, 7.6, c, HEAD, bold=True, align=al, spc=2.0)
    hair(s, LM, 2.74, CW, 0.20)

    rows = [
        ("mAP50 \u00b7 validation, 200 images", "0.734", "0.854", None),
        ("mAP50 \u00b7 locked test, 160 images", "\u2014", "0.847", "0.93"),
        ("Recall at 0.25 \u00b7 locked test", "\u2014", "0.862", "0.90"),
        ("Precision at 0.25 \u00b7 locked test", "\u2014", "0.885", "0.90"),
        ("Frames per second \u00b7 149 frames", "29.8", "23.7", "30"),
        ("Frames dropped \u00b7 149 frames", "0", "31", None),
    ]
    for i, (metric, a, b, gate) in enumerate(rows):
        y = 2.92 + i * 0.50
        txt(s, LM, y + 0.06, 4.1, 0.24, metric, 10.5, IVORY, BODY)
        txt(s, 5.30, y, 2.2, 0.32, a, 17, IVORY, HEAD, bold=True,
            align=PP_ALIGN.RIGHT)
        txt(s, 7.70, y, 2.2, 0.32, b, 17,
            AMBER if (gate and float(b) < float(gate)) else IVORY, HEAD, bold=True,
            align=PP_ALIGN.RIGHT)
        if gate:
            met = float(b) >= float(gate) and not (gate == "30")
            txt(s, 10.10, y + 0.005, 2.35, 0.24, gate, 12, MUTED, HEAD, bold=True,
                align=PP_ALIGN.RIGHT)
            txt(s, 10.10, y + 0.26, 2.35, 0.2, "NOT MET", 7.0, AMBER, HEAD,
                bold=True, align=PP_ALIGN.RIGHT, spc=1.6)
        hair(s, LM, y + 0.44, CW, 0.10)

    txt(s, LM, 5.96, 7.15, 0.2,
        "YOLO26n was not run on the locked test; its figures are validation only.",
        7.6, META, BODY)

    # decision band
    hair(s, LM, 6.18, CW, 0.18)
    label(s, LM, 6.32, "DECISION", AMBER, 7.6, 1.6)
    txt(s, 2.05, 6.24, 10.4, 0.34,
        "Not promoted. YOLO26n stays active for real-time use.", 17, IVORY, HEAD,
        bold=True)
    foot(s, 7)
    notes(s, NOTES[6])

    # ---------------------------------------------------------- 08 · PRODUCT
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "08 \u00b7 THE PRODUCT", 8)
    head(s, "The application", "Eight pages, one review loop.\nNothing leaves the laptop.")

    calls = [("01", "Upload a site photo", "Boxes plus a status for every worker."),
             ("02", "Review each event", "Confirm, mark false positive, or dismiss."),
             ("03", "Live webcam", "About 30 frames per second on this machine."),
             ("04", "Local only", "No uploads, no cloud service, no account.")]
    for i, (num, lead, sub) in enumerate(calls):
        y = BODY_Y + i * 0.74
        txt(s, LM, y - 0.02, 0.4, 0.2, num, 8.4, GOLD, HEAD, bold=True, spc=1.4)
        txt(s, LM + 0.42, y - 0.06, 3.75, 0.24, lead, 11.5, IVORY, BODY, bold=True)
        txt(s, LM + 0.42, y + 0.20, 3.75, 0.24, sub, 9.2, MUTED, BODY)

    label(s, LM, 5.40, "EVIDENCE \u00b7 IMAGE INSPECTION", META, 7.0, 3.8, spc=1.8)
    shape(s, MSO_SHAPE.RECTANGLE, LM - 0.02, 5.58, 3.39, 1.17, fill=None,
          edge=GOLD, ew=0.75, ea=0.35)
    picture(s, INSPECT, LM, 5.60, 3.35, 1.13, region=(0.20, 0.30, 0.88, 0.70))
    txt(s, LM, 6.81, 3.5, 0.2, "Original and annotated result, from the real build.",
        6.9, META, BODY)

    # screen
    px, py, pw, ph = 4.86, 2.34, 7.64, 4.30
    shape(s, MSO_SHAPE.RECTANGLE, px - 0.02, py - 0.02, pw + 0.04, ph + 0.04,
          fill=None, edge=GOLD, ew=0.9, ea=0.45)
    picture(s, OVERVIEW, px, py, pw, ph, region=(0, 0, 1, 1))
    txt(s, W - RM - 4.6, 6.72, 4.6, 0.2,
        "SAFETY EVENTS PAGE \u00b7 PERSONAL DATA REDACTED", 7.0, META, HEAD,
        bold=True, align=PP_ALIGN.RIGHT, spc=1.6)
    foot(s, 8)
    notes(s, NOTES[7])

    # ------------------------------------------------------------ 09 · RISKS
    s = prs.slides.add_slide(blank)
    ground(s)
    top(s, "09 \u00b7 THE RISKS", 9)
    head(s, "What it cannot do", "The gaps are measured,\nwritten down and published")

    limits = [
        ("Missing-PPE recall is below 0.90 for every class.",
         "no_helmet 0.615 \u00b7 no_gloves 0.567 \u00b7 no_goggle 0.171 at confidence 0.25"),
        ("Real-site photos score 0.592 mAP50; close-ups 0.951.",
         "E3 on the locked test: 47 real-site images against 113 generated close-ups"),
        ("Overhead views collapse: 0.185 against 0.639 frontal.",
         "mAP50-95, frontal-only model, 219 held-out overhead images"),
        ("178 possibly wrong labels are still unreviewed.",
         "Dataset audit; no correction applied to the original labels"),
    ]
    for i, (lead, sub) in enumerate(limits):
        y = BODY_Y + i * 0.95
        shape(s, MSO_SHAPE.RECTANGLE, LM, y + 0.02, 0.035, 0.66,
              fill=AMBER if i < 3 else SLATE, alpha=0.85)
        txt(s, LM + 0.26, y - 0.04, 6.9, 0.3, lead, 12, IVORY, BODY, bold=True)
        txt(s, LM + 0.26, y + 0.28, 6.9, 0.26, sub, 9, META, BODY)
        if i:
            hair(s, LM, y - 0.09, 7.2, 0.10)

    txt(s, LM, 6.24, 7.2, 0.5,
        "It is a prototype on one public dataset, not a certified safety system. "
        "A missed detection raises no event.", 9.4, MUTED, BODY, spacing=1.3)

    # right: evidence chart
    cx, cy = 8.55, 2.66
    label(s, cx, BODY_Y - 0.02, "mAP50 BY IMAGE TYPE \u00b7 E3", GOLD, 7.2, 4.0)
    chart(s, cx - 0.14, cy, 4.15, 1.68, ["Real-site photos", "Close-ups"],
          [("mAP50", (0.592, 0.951))], [GOLD, [AMBER, GOLD]], fmt="0.000",
          vmax=1.25, major=0.25, lab_size=8.2, cat_size=8.2, gap=95)
    txt(s, cx, 4.42, 3.9, 0.2, "Locked test \u00b7 160 images", 7.6, META, BODY)

    # amber note
    ny = 4.86
    g = shape(s, MSO_SHAPE.RECTANGLE, cx - 0.14, ny, 4.1, 1.30, fill=None)
    gradient(g, "241B0E", "0C1017", 90)
    shape(s, MSO_SHAPE.RECTANGLE, cx - 0.14, ny, 0.03, 1.30, fill=AMBER)
    txt(s, cx + 0.18, ny + 0.20, 3.6, 0.24, "Published, not hidden.", 11, IVORY,
        HEAD, bold=True)
    txt(s, cx + 0.18, ny + 0.50, 3.6, 0.62,
        "Every gap on this slide is quoted from the project's own reports.",
        9, MUTED, BODY, spacing=1.25)
    foot(s, 9)
    notes(s, NOTES[8])

    # ---------------------------------------------------------- 10 · CLOSING
    s = prs.slides.add_slide(blank)
    shape(s, MSO_SHAPE.RECTANGLE, 0, 0, W, H, fill=INK, name="bleed")
    picture(s, BG, 0, 0, 5.25, H, region=(0.55, 0.0, 0.86, 1.0), name="bleed")
    scrim(s, 3.05, 0, 2.4, H, 0, 0.0, 1.0)
    scrim(s, 0, 0, 5.25, 1.45, 90, 0.62, 0.0)
    scrim(s, 0, 5.4, 5.25, 2.1, 90, 0.0, 0.92)

    shape(s, MSO_SHAPE.DIAMOND, LM, 0.56, 0.19, 0.19, fill=None, edge=GOLD, ew=1.0)
    shape(s, MSO_SHAPE.OVAL, LM + 0.071, 0.631, 0.048, 0.048, fill=GOLD)
    txt(s, LM + 0.38, 0.56, 3.2, 0.2, "SITEGUARD AI", 8.6, GOLD, HEAD, bold=True,
        spc=2.8)

    x0 = 6.25
    txt(s, x0, 1.34, 6.2, 0.18, "IN CLOSING", 8.2, GOLD, HEAD, bold=True, spc=2.6)
    txt(s, x0, 1.60, 6.4, 1.2, "A working prototype,\nand an honest map forward",
        30, IVORY, HEAD, bold=True, spacing=0.98)
    hair(s, x0, 2.86, 6.3, 0.16)

    label(s, x0, 3.02, "DELIVERED", GOLD, 7.4, 3.0)
    delivered = ["Local real-time system \u00b7 29.8 fps",
                 "8-page dashboard with review",
                 "A failed experiment, reported",
                 "205 automated tests"]
    for i, it in enumerate(delivered):
        y = 3.30 + i * 0.30
        tick_mark(s, x0, y - 0.01, 0.17, GOLD, 1.4)
        txt(s, x0 + 0.26, y, 3.1, 0.22, it, 9.8, IVORY, BODY)

    label(s, x0 + 3.55, 3.02, "NEXT", AMBER, 7.4, 3.0)
    onwards = ["Real-site and overhead data",
               "Review of the 178 labels",
               "A faster large model",
               "Multi-camera tracking"]
    for i, it in enumerate(onwards):
        y = 3.30 + i * 0.30
        shape(s, MSO_SHAPE.RECTANGLE, x0 + 3.55, y + 0.10, 0.06, 0.06, fill=AMBER)
        txt(s, x0 + 3.74, y, 3.0, 0.22, it, 9.8, MUTED, BODY)

    hair(s, x0, 4.72, 6.3, 0.16)
    txt(s, x0, 4.88, 6.2, 0.6, "Thank you.", 40, IVORY, HEAD, bold=True,
        spacing=0.9)
    txt(s, x0, 5.62, 6.3, 0.5,
        "Approve YOLO26n for this review. Put the next budget into real-site "
        "footage, not a bigger model.", 10.5, AMBER, BODY, spacing=1.25)
    hair(s, x0, 6.18, 6.3, 0.13)
    txt(s, x0, 6.32, 3.2, 0.2, "JUNAID AHMAD \u00b7 12419395", 8.2, GOLD, HEAD,
        bold=True, spc=1.8)
    txt(s, x0, 6.54, 6.3, 0.2,
        "Decision support only. A person reviews every potential event.", 8, META,
        BODY)
    txt(s, W - 0.9 - 5.2, 6.94, 5.2, 0.2, "10 / 10", 8.4, META, HEAD, bold=True,
        align=PP_ALIGN.RIGHT, spc=1.8)
    notes(s, NOTES[9])

    prs.save(str(OUT))
    return prs


# ====================================================================== notes
NOTES = [
    "Good morning. My name is JUNAID AHMAD, registration number 12419395, and this is my "
    "471 project: SiteGuard AI. It is a computer-vision prototype that looks at "
    "construction-site footage and points out workers who may be missing protective "
    "equipment: a hard hat, a high-visibility vest or gloves. The important word is may. "
    "It is decision support, so the model suggests something and a person decides. It "
    "runs entirely on this one laptop, so no photograph or camera frame ever leaves the "
    "machine. I will explain how it works, what it honestly measures, and then run it "
    "live. If asked: this is an academic prototype, not a certified safety product.",

    "Here is the problem. On a busy site, helmets, vests and gloves are easy to miss, and "
    "a supervisor cannot watch every camera every second. Manual checks only see the "
    "moments somebody is looking. My idea was a camera model that looks at "
    "every frame and flags likely missing equipment on each worker. The principle "
    "matters more than the model: the AI suggests, and a person decides. Nothing is "
    "called a violation on its own. It delivers the five items here: "
    "detection of workers plus eleven object types, per-worker checks for helmet, vest "
    "and gloves, saved evidence, human review with a CSV report, and fully local "
    "processing. If asked: it is an assistant for a supervisor, not a replacement.",

    "This is the pipeline in five steps. Input is a photo, a video file or the live "
    "webcam. The detector, YOLO26n, finds people, the PPE they wear, and explicit "
    "missing-PPE boxes. YOLO is a real-time object detector: it draws a box around each "
    "object it recognises. Step three links each box to the correct worker using "
    "geometry, so a helmet must fall inside that person's body area. Step four is "
    "patience: a problem must appear in three analysed frames before it becomes an "
    "event, and repeats are suppressed for thirty seconds, so a single flicker does not "
    "raise an alarm. Step five is human review. If asked: the worker "
    "labels are per frame, not identities, and nothing is uploaded.",

    "The data is the Ultralytics Construction-PPE dataset, released under CC BY 4.0, "
    "which allows reuse with attribution. It has one thousand labelled images: "
    "eight hundred for training and two hundred for validation. The validation set holds "
    "two thousand nine hundred and sixty-one labelled objects, so there is a real test "
    "to measure against. There are twelve classes, and the list on the right shows how "
    "uneven they are: Person and boots have four hundred and eighty objects each, "
    "while no_goggle has only eighty-two. Gold is PPE present, amber is missing PPE, "
    "grey is person and forklift. The app requires helmet, vest and gloves because those "
    "classes have enough examples. If asked: the original dataset is read-only and "
    "checksum-verified.",

    "I started from YOLO26n, the smallest current Ultralytics model, already trained on "
    "general images, and fine-tuned it on these twelve classes. That is transfer "
    "learning: the model keeps what it learned about shapes and edges, and I teach it "
    "the new classes. Training took thirty epochs, thirty passes over the "
    "training images, in twenty-one minutes on this laptop's Apple graphics processor, "
    "at six hundred and forty pixels and batch eight. I chose the nano model for speed. "
    "The diagram shows why: a thirty frames per second camera gives you thirty-three "
    "milliseconds per frame, and inference takes about twenty. A replay of one "
    "hundred and forty-nine frames dropped none. If asked: these are replay numbers, not "
    "a physical-camera test.",

    "Now the honest accuracy, all on the two-hundred-image validation split at six "
    "hundred and forty pixels. Precision is how often a detection is right: 0.832, so "
    "about eighty-three percent. Recall is how much labelled equipment it finds: 0.681. "
    "mAP50 measures box quality when a box counts as correct at fifty percent overlap, "
    "and mAP50-95 repeats that at stricter overlaps; both are averaged over the twelve "
    "classes. People and worn PPE are strong: Person 0.940, "
    "goggles 0.924, vest 0.887. The amber bars are the missing-PPE classes and they are "
    "weaker: no_helmet 0.652, no_gloves 0.620, and no_goggle only 0.148, which is why "
    "goggles are not required. If asked: at the app's 0.25 confidence, precision is "
    "0.884 and recall 0.745.",

    "Would a bigger model fix the missing-PPE weakness? I tested it properly. E3 is "
    "YOLO26m at eight hundred and ninety-six pixels. On the same two hundred validation "
    "images it wins: mAP50 0.854 against 0.734, recall 0.858 against 0.745. But that set "
    "also chose the model, so it flatters it. I then ran a locked test: one hundred and "
    "sixty images, two thousand four hundred and eighty objects, used once. E3 reached "
    "mAP50 0.847 against a target of 0.93 set in advance. Precision 0.885 and recall "
    "0.862, both short of 0.90. It also runs at 23.7 frames per second, dropping "
    "thirty-one frames. So it failed both gates. If asked: the gates were written "
    "before the test.",

    "This is the application: eight pages, from Overview to Settings. The large image is "
    "the real Safety Events page. The list on the left is the review loop: upload a "
    "photo and you get boxes plus a status for each worker; every event is reviewed by a "
    "person; the live webcam runs at about thirty frames per second; and nothing leaves "
    "this laptop. The small screenshot is Image Inspection, from the real build. Now the "
    "demonstration. I select Image Inspection, upload a site photo, and wait a moment. "
    "Here is the original and the annotated result. Then Safety Events, where "
    "the potential violations were recorded with evidence, ready for review. If asked: "
    "one image takes a fraction of a second.",

    "I want to be direct about what this model cannot do. Missing-PPE recall is below "
    "0.90 for every class: 0.615 for no_helmet, 0.567 for no_gloves, 0.171 for no_goggle. "
    "In plain words it misses many real cases, so the system under-reports rather than "
    "over-reports. Second, real-site photos score 0.592 mAP50 against 0.951 on generated "
    "close-ups, so the headline numbers are flattered by easy images. Third, an overhead "
    "camera view collapses to 0.185 against 0.639 frontal. Fourth, 178 labels may be "
    "wrong and have not been reviewed. And it is a prototype on one public dataset, not a "
    "certified safety system. If asked: a missed detection produces no event, so silence "
    "is never proof of compliance.",

    "To conclude. SiteGuard AI works today: a local real-time system at 29.8 frames per "
    "second, an eight-page dashboard with human review, an honest evaluation that "
    "includes a failed experiment, and 205 automated tests. The path forward is equally "
    "clear: more real-site and overhead data, a human review of those 178 labels, a "
    "faster large model so a bigger network fits the thirty-frames-per-second budget, and "
    "eventually multi-camera sites with worker tracking. The value here is not a perfect "
    "model; it is a complete, measured, honest system a supervisor could use as decision "
    "support. Thank you. I am happy to take questions. If asked: the next step is "
    "consented real-site footage used as a new, independent test set.",
]


# ===================================================================== check
def check(prs):
    bad = []
    n_slides = 0
    for i, slide in enumerate(prs.slides, 1):
        n_slides = i
        for sh in slide.shapes:
            if sh.left is None or sh.name == "bleed":
                continue
            l, t = sh.left / 914400, sh.top / 914400
            w, h = sh.width / 914400, sh.height / 914400
            if l < 0.20 or t < 0.0 or l + w > W - 0.20 or t + h > H - 0.10:
                bad.append(f"slide {i}: shape out of bounds "
                           f"({l:.2f},{t:.2f},{w:.2f},{h:.2f})")
            if sh.has_text_frame and sh.text_frame.text.strip():
                for p in sh.text_frame.paragraphs:
                    if not p.runs:
                        continue
                    size = (p.runs[0].font.size or Pt(16)).pt
                    font = p.runs[0].font.name or BODY
                    factor = 0.42 if font == HEAD else 0.49
                    cpl = max(1, int(w / (size * factor / 72.0)))
                    lines = max(1, len(textwrap.wrap(p.text, cpl)))
                    need = lines * size * 1.24 / 72.0 * (p.line_spacing or 1.0)
                    if need > h + 0.05:
                        bad.append(f"slide {i}: text may overflow "
                                   f"({need:.2f}in in {h:.2f}in) '{p.text[:44]}'")
        if not slide.has_notes_slide or not slide.notes_slide.notes_text_frame.text.strip():
            bad.append(f"slide {i}: missing notes")
    if n_slides != 10:
        bad.append(f"expected 10 slides, found {n_slides}")
    return bad


if __name__ == "__main__":
    prs = build()
    problems = check(prs)
    print(f"saved {OUT.name}: {len(prs.slides._sldIdLst)} slides")
    if problems:
        print("\nLAYOUT WARNINGS")
        for p in problems:
            print(" -", p)
    if not problems:
        print("layout check: clean")
