#!/usr/bin/env python3
"""
Generates every SVG used by the profile README.

Each asset is emitted twice - once for GitHub's dark theme, once for light -
and the README picks between them with <picture media="(prefers-color-scheme)">.
Everything is self-hosted: no badge services, no external fonts, no runtime
requests. Animation is pure SMIL so it plays inside GitHub's <img> sandbox.

    python3 assets/src/build.py              # normal, animated build
    STATIC=1 python3 assets/src/build.py     # freeze at final frame (for review)

STATIC mode exists because headless screenshots don't advance SMIL clocks, so
it's the only way to eyeball what a reader actually ends up looking at.
"""

import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, ".."))
STATIC = os.environ.get("STATIC") == "1"

ICONS = json.load(open(os.path.join(HERE, "icons.json")))

MONO = "ui-monospace,'SFMono-Regular','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "'Inter','Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif"

# Monospace advance width as a fraction of font-size. Every measured string in
# this file is mono, so layout math stays exact regardless of which fallback
# font the viewer's machine actually resolves.
CW = 0.60

DARK = dict(
    name="dark",
    bg="#0B0F14", surface="#111823",
    border="#1E2A38", grid="#161F2B",
    text="#E6EDF3", muted="#8B98A9", dim="#5A6675",
    accent="#4EE1A0", accent2="#58A6FF", accent3="#F5B544", down="#F4737B",
    glow="0.16",
)

LIGHT = dict(
    name="light",
    bg="#FFFFFF", surface="#F6F8FA",
    border="#D8DEE6", grid="#EDF1F5",
    text="#0D1117", muted="#59636E", dim="#8C949E",
    accent="#0E9F6E", accent2="#0969DA", accent3="#9A6700", down="#CF222E",
    glow="0.10",
)


# ---------------------------------------------------------------- utilities

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def tw(s, size):
    """Rendered width of a monospace string."""
    return len(s) * size * CW


def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb2hex(r, g, b):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(c)))) for c in (r, g, b))


def _lum(h):
    r, g, b = (c / 255 for c in _hex2rgb(h))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _mix(h, target, t):
    r, g, b = _hex2rgb(h)
    tr, tg, tb = _hex2rgb(target)
    return _rgb2hex(r + (tr - r) * t, g + (tg - g) * t, b + (tb - b) * t)


def brand(slug, pal):
    """Brand colour, nudged only as far as legibility on this theme requires."""
    hexv = "#" + ICONS[slug]["hex"]
    l = _lum(hexv)
    if pal["name"] == "dark":
        if l < 0.06:
            return _mix(hexv, "#FFFFFF", 0.80)
        if l < 0.18:
            return _mix(hexv, "#FFFFFF", 0.45)
    else:
        if l > 0.72:
            return _mix(hexv, "#000000", 0.45)
        if l > 0.55:
            return _mix(hexv, "#000000", 0.22)
    return hexv


def icon(slug, x, y, size, color):
    """Place a 24x24 simple-icons path at (x, y) scaled to `size`."""
    s = size / 24.0
    return (f'<g transform="translate({x:.2f},{y:.2f}) scale({s:.4f})">'
            f'<path d="{ICONS[slug]["path"]}" fill="{color}"/></g>')


# ----------------------------------------------------- animation primitives
#
# Two rules hold everywhere below:
#
#   1. The *base* attribute value is always the finished state. Anything that
#      ignores SMIL - a static rasteriser, an exported still, a reader that
#      strips animation - gets the fully composed card rather than a blank one.
#   2. Stagger delays are therefore encoded as a held first segment in
#      keyTimes rather than as begin="Ns", because a real begin offset would
#      show the base (finished) value first and then snap back to hide it.
#
# Every helper also collapses to a plain finished state when STATIC is set.

def _hold(begin, dur):
    """(total duration, keyTime at which the real motion starts)."""
    total = begin + dur
    return total, (begin / total if total else 0.0)


def gin(begin, dy=8, dur=0.7):
    """Open a <g> that fades and rises into place."""
    if STATIC:
        return "<g>"
    total, k = _hold(begin, dur)
    return (f'<g>'
            f'<animate attributeName="opacity" values="0;0;1" '
            f'keyTimes="0;{k:.4f};1" dur="{total:.2f}s" begin="0s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 {dy};0 {dy};0 0" keyTimes="0;{k:.4f};1" dur="{total:.2f}s" '
            f'begin="0s" fill="freeze" calcMode="spline" '
            f'keySplines="0 0 1 1;0.22 1 0.36 1"/>')


def fade(begin, dur=0.8):
    """Open a <g> that only fades in."""
    if STATIC:
        return "<g>"
    total, k = _hold(begin, dur)
    return (f'<g><animate attributeName="opacity" values="0;0;1" '
            f'keyTimes="0;{k:.4f};1" dur="{total:.2f}s" begin="0s" fill="freeze"/>')


def grow(attr, final, dur, begin, start=0):
    """(attribute, child-animation) pair easing `attr` from start to final."""
    if STATIC:
        return f'{attr}="{final}"', ""
    total, k = _hold(begin, dur)
    return (f'{attr}="{final}"',
            f'<animate attributeName="{attr}" values="{start};{start};{final}" '
            f'keyTimes="0;{k:.4f};1" dur="{total:.2f}s" begin="0s" fill="freeze" '
            f'calcMode="spline" keySplines="0 0 1 1;0.22 1 0.36 1"/>')


def steps(begin, dur, frames):
    """Discrete step-through of `frames`, held on frames[0] for `begin`."""
    total, k = _hold(begin, dur)
    kt = [0.0, k] + [k + (1 - k) * i / (len(frames) - 1) for i in range(1, len(frames))]
    vals = [frames[0]] + list(frames)
    return (f'<animate attributeName="{{attr}}" values="{";".join(vals)}" '
            f'keyTimes="{";".join(f"{v:.4f}" for v in kt)}" dur="{total:.2f}s" '
            f'begin="0s" fill="freeze" calcMode="discrete"/>')


def blink(begin, dur=1.1):
    if STATIC:
        return ""
    return (f'<animate attributeName="opacity" values="1;1;0;0;1" dur="{dur}s" '
            f'begin="{begin}s" repeatCount="indefinite"/>')


def pulse_op(dur=2.2, lo="0.25"):
    if STATIC:
        return ""
    return (f'<animate attributeName="opacity" values="1;{lo};1" dur="{dur}s" '
            f'repeatCount="indefinite"/>')


# ------------------------------------------------------------ custom glyphs
# Hand-drawn 24x24 marks for the things simple-icons doesn't carry (or that
# aren't products at all - the category markers).

GLYPHS = {
    # a cloud, standing in for AWS
    "cloud": "M6.8 19q-2.4 0-4.1-1.7Q1 15.6 1 13.2q0-2.1 1.3-3.7 1.3-1.6 3.4-2 .5-2.5 2.5-4.1Q10.2 1.8 12.8 1.8q3 0 5.1 2.1 2.1 2.1 2.1 5.1v.5q1.8.2 3 1.5Q24 12.4 24 14.3q0 2-1.4 3.4Q21.2 19 19.2 19zm0-2h12.4q1.2 0 2-.8.8-.8.8-2t-.8-2q-.8-.8-2-.8h-1.9V9q0-2.2-1.5-3.7Q14.3 3.8 12.1 3.8q-2.2 0-3.7 1.5Q6.9 6.8 6.9 9h-.2q-1.6 0-2.7 1.2Q3 11.4 3 13.1q0 1.6 1.1 2.75Q5.2 17 6.8 17z",
    # six-fold spark, standing in for OpenAI
    "spark": "M12 1.4l1.7 5.3 4.6-3-3 4.6 5.3 1.7-5.3 1.7 3 4.6-4.6-3L12 22.6l-1.7-5.3-4.6 3 3-4.6L3.4 14l5.3-1.7-3-4.6 4.6 3z",
    # database cylinder, for SQL
    "db": "M12 1.5c-4.7 0-8.5 1.3-8.5 3v15c0 1.7 3.8 3 8.5 3s8.5-1.3 8.5-3v-15c0-1.7-3.8-3-8.5-3zm0 2c3.9 0 6.5 1 6.5 1s-2.6 1-6.5 1-6.5-1-6.5-1 2.6-1 6.5-1zm6.5 4.2v3.6s-2.6 1-6.5 1-6.5-1-6.5-1V7.7c1.7.8 4.2 1.3 6.5 1.3s4.8-.5 6.5-1.3zm0 6v3.6s-2.6 1-6.5 1-6.5-1-6.5-1v-3.6c1.7.8 4.2 1.3 6.5 1.3s4.8-.5 6.5-1.3zm0 6v1.3s-2.6 1-6.5 1-6.5-1-6.5-1v-1.3c1.7.8 4.2 1.3 6.5 1.3s4.8-.5 6.5-1.3z",
    # a decision tree, for XGBoost
    "trees": ('<g fill="none" stroke="{c}" stroke-width="2.2" stroke-linecap="round">'
              '<path d="M12 8L6 15.6"/><path d="M12 8L18 15.6"/></g>'
              '<circle cx="12" cy="4.6" r="3.1" fill="{c}"/>'
              '<circle cx="4.8" cy="18.8" r="3.1" fill="{c}"/>'
              '<circle cx="19.2" cy="18.8" r="3.1" fill="{c}"/>'),
    # graded bars, for LangSmith / evaluation
    "eval": ('<g fill="{c}"><rect x="2.4" y="13" width="4.2" height="8.6" rx="1.2"/>'
             '<rect x="9.9" y="9" width="4.2" height="12.6" rx="1.2"/>'
             '<rect x="17.4" y="15.4" width="4.2" height="6.2" rx="1.2"/></g>'
             '<path d="M14.2 5.6L17 8.4L22.4 2.6" fill="none" stroke="{c}" '
             'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'),
    # three linked nodes, category marker for agentic work
    "agents": "M12 1.6a3.4 3.4 0 00-1 6.65v2.02L6.9 12.9a3.4 3.4 0 101 1.73l4.1-2.37 4.1 2.37a3.4 3.4 0 101-1.73L13 10.27V8.25A3.4 3.4 0 0012 1.6zm0 2a1.4 1.4 0 110 2.8 1.4 1.4 0 010-2.8zM4.6 15.2a1.4 1.4 0 110 2.8 1.4 1.4 0 010-2.8zm14.8 0a1.4 1.4 0 110 2.8 1.4 1.4 0 010-2.8z",
    # stacked layers, category marker for ML/DL
    "layers": "M12 1.7L1.3 7.4 12 13.1l10.7-5.7zm0 2.3l6.4 3.4L12 10.8 5.6 7.4zM3.5 11.2l-2.2 1.2L12 18.1l10.7-5.7-2.2-1.2L12 15.7zm0 4.6l-2.2 1.2L12 22.7l10.7-5.7-2.2-1.2L12 20.3z",
    # server rack, category marker for infra
    "rack": "M2.5 2.5h19a1.5 1.5 0 011.5 1.5v5a1.5 1.5 0 01-1.5 1.5h-19A1.5 1.5 0 011 9V4a1.5 1.5 0 011.5-1.5zm.5 2v4h18v-4zm-.5 9h19a1.5 1.5 0 011.5 1.5v5a1.5 1.5 0 01-1.5 1.5h-19A1.5 1.5 0 011 20v-5a1.5 1.5 0 011.5-1.5zm.5 2v4h18v-4zm2-9.5h2v2h-2zm0 9.5h2v2h-2zm13-9.5h2v2h-2zm0 9.5h2v2h-2z",
    # candlesticks, category marker for markets
    "candles": "M4 1.8h2.4v3.1h1.7v10.4H6.4v3.1H4v-3.1H2.3V4.9H4zm6.8 3.6h2.4v3.1h1.7v10.4h-1.7v3.1h-2.4v-3.1H9.1V8.5h1.7zm6.8-3.6H20v3.1h1.7v8.6H20v3.1h-2.4v-3.1h-1.7V4.9h1.7z",
    # heartbeat, category marker for clinical AI
    "pulse": "M1 11.4h4.7l2.1-5.2a1 1 0 011.9.1l3.1 10.3 2.2-5.5a1 1 0 01.93-.63H23v2h-6.4l-3.2 8a1 1 0 01-1.87-.08L8.4 9.6l-1.35 3.4a1 1 0 01-.93.63H1z",
    # envelope, for the email link chip
    "mail": ('<rect x="1.6" y="4.6" width="20.8" height="14.8" rx="2.6" fill="none" '
             'stroke="{c}" stroke-width="2"/>'
             '<path d="M3.2 7.2L12 13.6L20.8 7.2" fill="none" stroke="{c}" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'),
    # the "in" wordmark, for the LinkedIn chip
    "linkedin": ('<circle cx="4.4" cy="4.6" r="2.7" fill="{c}"/>'
                 '<rect x="2.1" y="9.1" width="4.6" height="12.5" rx="0.7" fill="{c}"/>'
                 '<rect x="9.4" y="9.1" width="4.4" height="12.5" rx="0.7" fill="{c}"/>'
                 '<path d="M13.8 15.3a2.9 2.9 0 015.8 0v6.3h4.3v-7.1a6.2 6.2 0 '
                 '00-10.1-4.8z" fill="{c}"/>'),
}


def glyph(name, x, y, size, color):
    """Draw a 24x24 glyph. Values are either raw path data (filled) or a full
    SVG fragment with `{c}` where the colour goes - some marks only read at
    16px if they're built from strokes rather than a single filled outline."""
    s = size / 24.0
    frag = GLYPHS[name]
    inner = (frag.format(c=color) if frag.lstrip().startswith("<")
             else f'<path d="{frag}" fill="{color}"/>')
    return f'<g transform="translate({x:.2f},{y:.2f}) scale({s:.4f})">{inner}</g>'


def defs(pal, extra=""):
    return f'''<defs>
<style>
.m{{font-family:{MONO}}}
.s{{font-family:{SANS}}}
</style>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">
  <circle cx="1.5" cy="1.5" r="1.1" fill="{pal['grid']}"/>
</pattern>
<linearGradient id="accentbar" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{pal['accent']}"/>
  <stop offset="1" stop-color="{pal['accent2']}"/>
</linearGradient>
<linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{pal['border']}" stop-opacity="1"/>
  <stop offset="1" stop-color="{pal['border']}" stop-opacity="0"/>
</linearGradient>
{extra}
</defs>'''


def frame(w, h, pal, r=18):
    """Card background shared by every asset."""
    return (f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="{r}" '
            f'fill="{pal["bg"]}" stroke="{pal["border"]}" stroke-width="1.5"/>'
            f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="{r}" '
            f'fill="url(#dots)" opacity="0.55"/>')


def header(pal, w, cmd, title, pad=46):
    """The `$ command` + title block every card opens with."""
    return (f'<text class="m" x="{pad}" y="46" font-size="12.5" fill="{pal["dim"]}">'
            f'<tspan fill="{pal["accent"]}">$</tspan> {esc(cmd)}</text>'
            f'<text class="s" x="{pad}" y="76" font-size="26" font-weight="700" '
            f'fill="{pal["text"]}">{esc(title)}</text>'
            f'<line x1="{pad}" y1="94" x2="{w - pad}" y2="94" stroke="url(#fade)" '
            f'stroke-width="1"/>')


def svg(w, h, body, pal, extra_defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img">'
            f'{defs(pal, extra_defs)}{body}</svg>')


# ------------------------------------------------------------------- hero

def build_hero(pal):
    W, H = 1200, 470
    x0 = 58
    b = [frame(W, H, pal)]

    extra = (f'<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">'
             f'<stop offset="0" stop-color="{pal["accent"]}" stop-opacity="{pal["glow"]}"/>'
             f'<stop offset="1" stop-color="{pal["accent"]}" stop-opacity="0"/>'
             f'</radialGradient>')
    b.append('<ellipse cx="944" cy="205" rx="330" ry="235" fill="url(#glow)"/>')

    # -- typed prompt line
    prompt, sep, cmd, fs = "manan@dev", ":~$ ", "whoami", 15
    px = x0
    b.append(f'<text class="m" x="{px}" y="82" font-size="{fs}" fill="{pal["accent"]}">{prompt}</text>')
    px += tw(prompt, fs)
    b.append(f'<text class="m" x="{px:.1f}" y="82" font-size="{fs}" fill="{pal["dim"]}">{esc(sep)}</text>')
    px += tw(sep, fs)
    cw_, n = tw(cmd, fs), len(cmd)
    widths = [f"{cw_ * i / n:.1f}" for i in range(n + 1)]
    curxs = [f"{px + cw_ * i / n:.1f}" for i in range(n + 1)]

    if STATIC:
        b.append(f'<text class="m" x="{px:.1f}" y="82" font-size="{fs}" fill="{pal["text"]}">{cmd}</text>')
        b.append(f'<rect x="{px + cw_:.1f}" y="68" width="8.5" height="17" fill="{pal["accent"]}"/>')
    else:
        b.append(f'<clipPath id="typ"><rect x="{px:.1f}" y="66" width="{cw_:.1f}" height="22">'
                 + steps(0.35, 0.9, widths).format(attr="width")
                 + '</rect></clipPath>')
        b.append(f'<g clip-path="url(#typ)"><text class="m" x="{px:.1f}" y="82" '
                 f'font-size="{fs}" fill="{pal["text"]}">{cmd}</text></g>')
        b.append(f'<rect x="{px + cw_:.1f}" y="68" width="8.5" height="17" fill="{pal["accent"]}">'
                 + steps(0.35, 0.9, curxs).format(attr="x") + blink(1.35) + '</rect>')

    # -- name
    b.append(f'{gin(0.9, 10)}<text class="s" x="{x0}" y="176" font-size="66" '
             f'font-weight="800" letter-spacing="1.5" fill="{pal["text"]}">MANAN PATEL</text></g>')

    # -- accent rule
    a, an = grow("width", 176, 0.9, 1.25)
    b.append(f'<rect x="{x0}" y="196" height="4" rx="2" {a} fill="url(#accentbar)">{an}</rect>')

    # -- role line: static anchor, rotating specialisation.
    # Mono here on purpose: the rotating half is a separate <text>, so the
    # anchor's width has to be knowable without measuring a fallback font.
    rfs = 19
    anchor, rsep = "AI Engineer", " / "
    b.append(f'{gin(1.15)}<text class="m" x="{x0}" y="252" font-size="{rfs}" '
             f'font-weight="600" fill="{pal["text"]}">{anchor}</text>'
             f'<text class="m" x="{x0 + tw(anchor, rfs):.1f}" y="252" font-size="{rfs}" '
             f'font-weight="600" fill="{pal["dim"]}">{esc(rsep)}</text></g>')

    roles = ["Agentic LLM Systems", "Multi-Agent Orchestration",
             "RAG & Retrieval", "LLM Evaluation"]
    rx, slot = x0 + tw(anchor + rsep, rfs), 3.4
    cycle = len(roles) * slot
    for i, r in enumerate(roles):
        if STATIC and i:
            continue
        if STATIC:
            b.append(f'<text class="m" x="{rx:.1f}" y="252" font-size="{rfs}" font-weight="600" '
                     f'fill="{pal["accent"]}">{esc(r)}</text>')
            continue
        t0 = i * slot
        kt = [0, t0, t0 + 0.35, t0 + slot - 0.35, t0 + slot, cycle]
        kt = ";".join(f"{min(1.0, max(0.0, v / cycle)):.4f}" for v in kt)
        # first role stays visible by default: it is what shows before the
        # cycle starts, and what a non-animating renderer falls back to
        b.append(f'<text class="m" x="{rx:.1f}" y="252" font-size="{rfs}" font-weight="600" '
                 f'fill="{pal["accent"]}" opacity="{1 if i == 0 else 0}">'
                 f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kt}" '
                 f'dur="{cycle}s" begin="1.5s" repeatCount="indefinite"/>{esc(r)}</text>')

    # -- blurb
    for i, ln in enumerate([
        "I build agentic LLM systems — multi-agent setups, RAG, and the",
        "evals that catch them being confidently wrong. Right now I'm",
        "pointing that at markets, because it's a domain that argues back.",
    ]):
        b.append(f'{gin(1.35 + i * 0.09, 6)}<text class="m" x="{x0}" y="{294 + i * 24}" '
                 f'font-size="13.5" fill="{pal["muted"]}">{esc(ln)}</text></g>')

    # ---- right panel: scanner / market view
    px0, py0, pw, ph = 744, 58, 400, 300
    b.append(fade(0.5))
    b.append(f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" rx="14" '
             f'fill="{pal["surface"]}" stroke="{pal["border"]}" stroke-width="1.5"/>')
    b.append(f'<text class="m" x="{px0 + 20}" y="{py0 + 28}" font-size="11" '
             f'letter-spacing="1.8" fill="{pal["dim"]}">CURRENT BUILD</text>')
    b.append(f'<circle cx="{px0 + pw - 62}" cy="{py0 + 24}" r="3.5" fill="{pal["accent"]}">'
             f'{pulse_op()}</circle>')
    b.append(f'<text class="m" x="{px0 + pw - 52}" y="{py0 + 28}" font-size="11" '
             f'letter-spacing="1.5" fill="{pal["muted"]}">LIVE</text>')
    b.append(f'<line x1="{px0}" y1="{py0 + 44}" x2="{px0 + pw}" y2="{py0 + 44}" '
             f'stroke="{pal["border"]}" stroke-width="1"/>')

    # deterministic pseudo-market so the chart is stable across rebuilds
    rnd = random.Random(7)
    n = 16
    cx0, cbase, step = px0 + 26, py0 + 246, (pw - 52) / n
    price, series = 50.0, []
    for i in range(n):
        o = price
        c = max(12, o + (1.9 if i % 5 != 3 else -2.4) + rnd.uniform(-3.4, 3.6))
        series.append((o, c, max(o, c) + rnd.uniform(0.6, 3.0),
                       min(o, c) - rnd.uniform(0.6, 3.0)))
        price = c
    flat = [v for s in series for v in s]
    lo_, span = min(flat), (max(flat) - min(flat)) or 1
    sc = lambda v: (v - lo_) / span * 156 + 10

    for i, (o, c, hi, lo) in enumerate(series):
        cx = cx0 + i * step + step / 2
        up = c >= o
        col = pal["accent"] if up else pal["down"]
        bw = step * 0.52
        total, k = _hold(0.75 + i * 0.045, 0.55)
        anim = "" if STATIC else (
            f'<animateTransform attributeName="transform" type="scale" '
            f'values="1 0;1 0;1 1" keyTimes="0;{k:.4f};1" dur="{total:.2f}s" '
            f'begin="0s" fill="freeze" calcMode="spline" '
            f'keySplines="0 0 1 1;0.22 1 0.36 1"/>')
        b.append(f'<g transform="translate({cx:.2f},{cbase})"><g transform="scale(1,1)">{anim}'
                 f'<line x1="0" y1="{-sc(lo):.1f}" x2="0" y2="{-sc(hi):.1f}" '
                 f'stroke="{col}" stroke-width="1.3" opacity="0.75"/>'
                 f'<rect x="{-bw / 2:.2f}" y="{-sc(max(o, c)):.1f}" width="{bw:.2f}" '
                 f'height="{max(2, sc(max(o, c)) - sc(min(o, c))):.1f}" rx="1.2" '
                 f'fill="{col}" opacity="{0.95 if up else 0.85}"/></g></g>')

    # trend polyline that draws itself
    pts = [(cx0 + i * step + step / 2, cbase - sc(s[1])) for i, s in enumerate(series)]
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    # dashoffset 0 is the drawn state, so the line is complete without SMIL
    dtotal, dk = _hold(1.0, 1.6)
    dash = "" if STATIC else f' stroke-dasharray="{L:.0f}" stroke-dashoffset="0"'
    danim = "" if STATIC else (
        f'<animate attributeName="stroke-dashoffset" values="{L:.0f};{L:.0f};0" '
        f'keyTimes="0;{dk:.4f};1" dur="{dtotal:.2f}s" begin="0s" fill="freeze" '
        f'calcMode="spline" keySplines="0 0 1 1;0.4 0 0.2 1"/>')
    b.append(f'<path d="{d}" fill="none" stroke="{pal["accent2"]}" stroke-width="2" '
             f'stroke-linecap="round" stroke-linejoin="round" opacity="0.9"{dash}>{danim}</path>')

    hx, hy = pts[-1]
    htotal, hk = _hold(2.5, 0.4)
    hanim = "" if STATIC else (
        f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{hk:.4f};1" '
        f'dur="{htotal:.2f}s" begin="0s" fill="freeze"/>')
    b.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="4" fill="{pal["accent2"]}" '
             f'opacity="1">{hanim}</circle>')
    if not STATIC:
        b.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="4" fill="none" '
                 f'stroke="{pal["accent2"]}" stroke-width="1.5" opacity="0">'
                 f'<animate attributeName="r" values="4;13" dur="2s" begin="2.5s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="0.7;0" dur="2s" begin="2.5s" '
                 f'repeatCount="indefinite"/></circle>')

    b.append(f'<text class="m" x="{px0 + 26}" y="{py0 + 280}" font-size="11" '
             f'fill="{pal["dim"]}">swing scanner → agent review → risk gate</text>')
    b.append('</g>')

    # ---- status bar
    sy = 400
    b.append(f'<line x1="0" y1="{sy - 22}" x2="{W}" y2="{sy - 22}" '
             f'stroke="{pal["border"]}" stroke-width="1"/>')
    segs = [("M.S. Computer Science · Temple University", pal["muted"]),
            ("Philadelphia, PA", pal["muted"]),
            ("4 publications & abstracts", pal["muted"]),
            ("open to AI engineering roles", pal["accent"])]
    sx = x0
    b.append(fade(1.8))
    for i, (t, col) in enumerate(segs):
        if i:
            b.append(f'<path d="M {sx:.1f} {sy - 5} l 5 5 l -5 5" fill="none" '
                     f'stroke="{pal["dim"]}" stroke-width="1.5" stroke-linecap="round" '
                     f'stroke-linejoin="round" opacity="0.7"/>')
            sx += 18
        if i == len(segs) - 1:
            b.append(f'<circle cx="{sx + 4:.1f}" cy="{sy}" r="3.5" fill="{pal["accent"]}">'
                     f'{pulse_op(1.8, "0.3")}</circle>')
            sx += 15
        b.append(f'<text class="m" x="{sx:.1f}" y="{sy + 4}" font-size="12.5" fill="{col}">{esc(t)}</text>')
        sx += tw(t, 12.5) + 18
    b.append('</g>')

    return svg(W, H, "".join(b), pal, extra)


# ------------------------------------------------------------------ stack
# (label, simple-icons slug) or (label, ("glyph", name, palette-key))

STACK = [
    ("agents", "LLM & AGENTIC", "accent", [
        ("LangChain", "langchain"), ("LangGraph", "langgraph"),
        ("LangSmith", ("glyph", "eval", "accent2")),
        ("Anthropic", "anthropic"), ("OpenAI", ("glyph", "spark", "accent")),
        ("Pydantic", "pydantic"), ("Ollama", "ollama"),
    ], [
        "multi-agent orchestration", "corrective RAG", "MCP servers",
        "human-in-the-loop", "LLM-as-judge", "structured outputs",
        "prompt engineering", "local inference",
    ]),
    ("layers", "MACHINE LEARNING", "accent2", [
        ("PyTorch", "pytorch"), ("Transformers", "huggingface"),
        ("scikit-learn", "scikitlearn"), ("XGBoost", ("glyph", "trees", "accent3")),
        ("NumPy", "numpy"), ("SciPy", "scipy"), ("MLflow", "mlflow"),
    ], [
        "embeddings", "fine-tuning", "feature engineering",
        "hyperparameter search", "cross-validation", "ablation studies",
    ]),
    ("rack", "DATA & INFRA", "accent3", [
        ("Python", "python"), ("SQL", ("glyph", "db", "accent2")),
        ("pandas", "pandas"), ("FastAPI", "fastapi"), ("Docker", "docker"),
        ("Kubernetes", "kubernetes"), ("AWS", ("glyph", "cloud", "accent3")),
        ("CUDA", "nvidia"), ("Qdrant", "qdrant"), ("Git", "git"),
    ], [
        "vector databases", "reproducible pipelines", "seeded deterministic runs",
        "cost & latency instrumentation",
    ]),
    ("candles", "MARKETS", "accent", [], [
        "equities & options", "technical analysis", "position sizing",
        "reward-to-risk floors", "stop placement", "trade journaling",
    ]),
    ("pulse", "CLINICAL AI", "accent2", [], [
        "clinical NLP", "ICD-10 / CDT coding", "linked EHR–EDR records",
        "feature reduction", "clinician-in-the-loop validation",
    ]),
]


def _wrap(items, width, measure):
    """Greedy line-wrap into rows that fit `width`."""
    rows, cur, curw = [], [], 0.0
    for it in items:
        w = measure(it)
        if cur and curw + w > width:
            rows.append(cur)
            cur, curw = [], 0.0
        cur.append((it, w))
        curw += w + 9
    if cur:
        rows.append(cur)
    return rows


def build_stack(pal):
    W, PAD, GX, CX = 1200, 46, 46, 270
    CONTENT = W - CX - PAD

    blocks = []
    for gname, title, ckey, tools, concepts in STACK:
        rows = _wrap(tools, CONTENT, lambda t: 36 + tw(t[0], 13) + 18)
        crows = _wrap(concepts, CONTENT, lambda c: tw(c, 12.5) + 26)
        blocks.append((gname, title, ckey, rows, crows))

    H = 110
    for _, _, _, rows, crows in blocks:
        H += len(rows) * 45 + (6 if rows and crows else 0) + len(crows) * 34 + 34
    H = int(H + 6)

    body = [frame(W, H, pal), header(pal, W, "cat ~/stack.toml", "Technical Stack")]

    yy, delay, first = 124, 0.15, True
    for gname, title, ckey, rows, crows in blocks:
        if not first:
            body.append(f'<line x1="{PAD}" y1="{yy - 18}" x2="{W - PAD}" y2="{yy - 18}" '
                        f'stroke="{pal["border"]}" stroke-width="1" opacity="0.7"/>')
        first = False

        col = pal[ckey]
        n = sum(len(r) for r in rows) + sum(len(r) for r in crows)
        body.append(gin(delay, 6))
        body.append(glyph(gname, GX, yy + 2, 19, col))
        body.append(f'<text class="m" x="{GX + 30}" y="{yy + 17}" font-size="13" '
                    f'font-weight="700" letter-spacing="1.6" fill="{pal["text"]}">{esc(title)}</text>')
        body.append(f'<text class="m" x="{GX + 30}" y="{yy + 38}" font-size="11" '
                    f'letter-spacing="1.2" fill="{pal["dim"]}">{n:02d} ENTRIES</text>')
        body.append('</g>')
        delay += 0.08

        ry = yy
        for row in rows:
            rx = CX
            for (label, ref), w in row:
                body.append(gin(delay, 7, 0.6))
                body.append(f'<rect x="{rx:.1f}" y="{ry}" width="{w:.1f}" height="34" rx="9" '
                            f'fill="{pal["surface"]}" stroke="{pal["border"]}" stroke-width="1"/>')
                if isinstance(ref, tuple):
                    body.append(glyph(ref[1], rx + 12, ry + 9, 16, pal[ref[2]]))
                else:
                    body.append(icon(ref, rx + 12, ry + 9, 16, brand(ref, pal)))
                body.append(f'<text class="m" x="{rx + 36:.1f}" y="{ry + 22}" font-size="13" '
                            f'fill="{pal["text"]}">{esc(label)}</text></g>')
                rx += w + 9
                delay += 0.035
            ry += 45

        if rows and crows:
            ry += 6
        for row in crows:
            rx = CX
            for c, w in row:
                body.append(gin(delay, 5, 0.55))
                body.append(f'<rect x="{rx:.1f}" y="{ry}" width="{w:.1f}" height="26" rx="13" '
                            f'fill="none" stroke="{pal["border"]}" stroke-width="1"/>')
                body.append(f'<text class="m" x="{rx + 13:.1f}" y="{ry + 17}" font-size="12.5" '
                            f'fill="{pal["muted"]}">{esc(c)}</text></g>')
                rx += w + 8
                delay += 0.025
            ry += 34

        yy = ry + 34

    return svg(W, H, "".join(body), pal)


# --------------------------------------------------------------- pipeline

def build_pipeline(pal):
    W, H = 1200, 440
    NW, NH, MID = 168, 62, 240
    b = [frame(W, H, pal),
         header(pal, W, "render architecture --graph", "The trading desk, roughly")]

    def node(x, y, title, sub, col, dashed=False, w=NW, h=NH, d=0.0):
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        return (f'{gin(d, 8, 0.6)}'
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" '
                f'fill="{pal["surface"]}" stroke="{col}" stroke-width="1.5"{dash}/>'
                f'<rect x="{x}" y="{y}" width="3.5" height="{h}" rx="1.75" fill="{col}"/>'
                f'<text class="m" x="{x + w / 2}" y="{y + h / 2 - 3}" font-size="12.5" '
                f'font-weight="700" letter-spacing="1.1" text-anchor="middle" '
                f'fill="{pal["text"]}">{esc(title)}</text>'
                f'<text class="m" x="{x + w / 2}" y="{y + h / 2 + 15}" font-size="11" '
                f'text-anchor="middle" fill="{pal["dim"]}">{esc(sub)}</text></g>')

    def wire(d, col, delay):
        s = (f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.6" opacity="0.55"/>')
        if not STATIC:
            s += (f'<circle r="3.2" fill="{col}"><animateMotion dur="2.6s" begin="{delay}s" '
                  f'repeatCount="indefinite" path="{d}" calcMode="spline" '
                  f'keyPoints="0;1" keyTimes="0;1" keySplines="0.45 0 0.55 1"/>'
                  f'<animate attributeName="opacity" values="0;1;1;0" dur="2.6s" '
                  f'begin="{delay}s" repeatCount="indefinite"/></circle>')
        return s

    c1, c2, c3, c4, c5 = 46, 268, 500, 722, 944

    b.append(node(c1, MID - NH / 2, "SCANNER", "S&P 500 · rules only", pal["accent2"], d=0.15))

    ys = [MID - 86, MID, MID + 86]
    for i, (lab, sub) in enumerate([("TECHNICAL", "price action & volume"),
                                    ("NEWS", "catalyst scan"),
                                    ("EVENTS", "earnings · calendar")]):
        b.append(node(c2, ys[i] - 30, lab, sub, pal["accent"], dashed=True, h=60,
                      d=0.35 + i * 0.08))
        b.append(wire(f"M {c1 + NW} {MID} C {c1 + NW + 40} {MID}, {c2 - 40} {ys[i]}, {c2} {ys[i]}",
                      pal["accent2"], 0.2 + i * 0.35))

    b.append(node(c3, MID - NH / 2, "TRADER", "synthesis agent", pal["accent"], dashed=True, d=0.7))
    for i in range(3):
        b.append(wire(f"M {c2 + NW} {ys[i]} C {c2 + NW + 40} {ys[i]}, {c3 - 40} {MID}, {c3} {MID}",
                      pal["accent"], 1.0 + i * 0.3))

    b.append(node(c4, MID - NH / 2, "RISK GATE", "pure code · no bypass", pal["accent3"], d=0.95))
    b.append(wire(f"M {c3 + NW} {MID} L {c4} {MID}", pal["accent"], 1.7))

    b.append(node(c5, MID - NH / 2 - 44, "HUMAN", "LangGraph interrupt", pal["text"], d=1.15))
    b.append(node(c5, MID - NH / 2 + 44, "JOURNAL", "structured trade log", pal["muted"], d=1.25))
    for dy, dl in ((-44, 2.1), (44, 2.35)):
        b.append(wire(f"M {c4 + NW} {MID} C {c4 + NW + 36} {MID}, {c5 - 36} {MID + dy}, "
                      f"{c5} {MID + dy}", pal["accent3"], dl))

    # the escape hatch that matters most
    b.append(wire(f"M {c4 + 77} {MID + NH / 2} L {c4 + 77} {MID + 92}", pal["down"], 2.0))
    b.append(f'{gin(1.5, 6, 0.6)}'
             f'<rect x="{c4 + 18}" y="{MID + 92}" width="118" height="28" rx="14" fill="none" '
             f'stroke="{pal["down"]}" stroke-width="1.2" stroke-dasharray="4 4"/>'
             f'<text class="m" x="{c4 + 77}" y="{MID + 110}" font-size="11" text-anchor="middle" '
             f'fill="{pal["down"]}">NO-TRADE</text></g>')

    ly, lx = H - 34, 46
    b.append(fade(1.6))
    for lab, col, dash in [("deterministic code", pal["accent2"], False),
                           ("LLM agent", pal["accent"], True),
                           ("hard constraint", pal["accent3"], False),
                           ("human sign-off", pal["text"], False)]:
        da = ' stroke-dasharray="3 3"' if dash else ""
        b.append(f'<rect x="{lx:.0f}" y="{ly - 8}" width="20" height="10" rx="5" fill="none" '
                 f'stroke="{col}" stroke-width="1.5"{da}/>'
                 f'<text class="m" x="{lx + 28:.0f}" y="{ly + 1}" font-size="11.5" '
                 f'fill="{pal["muted"]}">{esc(lab)}</text>')
        lx += 28 + tw(lab, 11.5) + 30
    b.append('</g>')

    return svg(W, H, "".join(b), pal)


# --------------------------------------------------------------- timeline
# The career as a level-select map: a road winding through four stage
# badges, cleared stages behind, the current one lit up ahead.

STAGES = [
    ("2023", "Technical Analyst", "Arihant Investments",
     ["screened equities for breakout", "setups, wrote daily trade reports"],
     "accent2", "candles", 196),
    ("2024 – 25", "ML Research Assistant", "Temple University",
     ["clinical AI on linked EHR data,", "NIH-funded (U01, NIDCR)"],
     "accent2", "pulse", 150),
    ("2025", "Research Lead", "Civic Interactions Lab",
     ["led an undergrad capstone team", "as their lead and stakeholder"],
     "accent3", "agents", 192),
    ("2025 →", "Independent AI Engineer", "self-directed",
     ["agentic systems, RAG, and the", "evals that keep them honest"],
     "accent", "spark", 146),
]


def _catmull(pts):
    """Smooth cubic path through pts. Returns (path data, bezier segments)."""
    segs, d = [], f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[i - 1] if i else pts[0]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append((p1, c1, c2, p2))
        d += (f" C {c1[0]:.1f} {c1[1]:.1f}, {c2[0]:.1f} {c2[1]:.1f}, "
              f"{p2[0]:.1f} {p2[1]:.1f}")
    return d, segs


def _seg_len(seg, n=36):
    (p0, c1, c2, p1), tot, prev = seg, 0.0, None
    for i in range(n + 1):
        t = i / n
        m = 1 - t
        x = m ** 3 * p0[0] + 3 * m * m * t * c1[0] + 3 * m * t * t * c2[0] + t ** 3 * p1[0]
        y = m ** 3 * p0[1] + 3 * m * m * t * c1[1] + 3 * m * t * t * c2[1] + t ** 3 * p1[1]
        if prev:
            tot += math.dist(prev, (x, y))
        prev = (x, y)
    return tot


def _hexagon(cx, cy, r):
    p = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
         for a in range(30, 390, 60)]
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in p) + " Z"


def build_timeline(pal):
    W, PAD, H = 1200, 46, 462
    colw = (W - PAD * 2) / len(STAGES)
    CARD_Y, CARD_H = 252, 120
    R = 23

    b = [frame(W, H, pal),
         header(pal, W, "load savefile.json", "The run so far")]

    xs = [PAD + colw * i + colw / 2 for i in range(len(STAGES))]
    ys = [s[6] for s in STAGES]
    road_pts = ([(PAD + 18, ys[0] + 20)] + list(zip(xs, ys))
                + [(W - PAD - 18, ys[-1] - 20)])
    d, segs = _catmull(road_pts)
    lens = [_seg_len(s) for s in segs]
    L = sum(lens)
    # the player has cleared everything up to the last badge
    reached = sum(lens[:len(STAGES)]) / L

    # -- the road: thick base that draws itself, then marching centre dashes
    rd = "" if STATIC else f' stroke-dasharray="{L:.0f}" stroke-dashoffset="0"'
    ra = "" if STATIC else (
        f'<animate attributeName="stroke-dashoffset" values="{L:.0f};{L:.0f};0" '
        f'keyTimes="0;0.12;1" dur="2.20s" begin="0s" fill="freeze" '
        f'calcMode="spline" keySplines="0 0 1 1;0.35 0 0.15 1"/>')
    b.append(f'<path d="{d}" fill="none" stroke="{pal["border"]}" stroke-width="11" '
             f'stroke-linecap="round" stroke-linejoin="round"{rd}>{ra}</path>')
    march = "" if STATIC else (
        '<animate attributeName="stroke-dashoffset" values="0;-18" dur="1.1s" '
        'repeatCount="indefinite"/>')
    b.append(f'<path d="{d}" fill="none" stroke="{pal["accent"]}" stroke-width="2" '
             f'stroke-linecap="round" opacity="0.45" stroke-dasharray="4 14" '
             f'stroke-dashoffset="0">{march}</path>')

    # -- travelling spark: purely decorative, so it stays hidden without SMIL
    if not STATIC:
        b.append(f'<circle r="5" fill="{pal["accent"]}" opacity="0">'
                 f'<animateMotion dur="3.4s" begin="1.6s" repeatCount="indefinite" '
                 f'path="{d}" keyPoints="0;{reached:.4f}" keyTimes="0;1" '
                 f'calcMode="spline" keySplines="0.4 0 0.2 1"/>'
                 f'<animate attributeName="opacity" values="0;0.9;0.9;0" dur="3.4s" '
                 f'begin="1.6s" repeatCount="indefinite"/></circle>')

    # -- stage badges
    for i, (year, role, org, det, ckey, gl, ny) in enumerate(STAGES):
        cx, col = xs[i], pal[ckey]
        current = i == len(STAGES) - 1
        t0 = 0.9 + i * 0.22

        b.append(f'<line x1="{cx:.1f}" y1="{ny + R}" x2="{cx:.1f}" y2="{CARD_Y}" '
                 f'stroke="{col}" stroke-width="1.2" stroke-dasharray="3 4" opacity="0.45"/>')

        if current and not STATIC:
            for j, dl in enumerate((0.0, 1.0)):
                b.append(f'<circle cx="{cx:.1f}" cy="{ny}" r="{R}" fill="none" '
                         f'stroke="{col}" stroke-width="1.6" opacity="0">'
                         f'<animate attributeName="r" values="{R};{R + 20}" dur="2s" '
                         f'begin="{2.2 + dl}s" repeatCount="indefinite"/>'
                         f'<animate attributeName="opacity" values="0.75;0" dur="2s" '
                         f'begin="{2.2 + dl}s" repeatCount="indefinite"/></circle>')

        b.append(gin(t0, 0, 0.5))
        sc = "" if STATIC else (
            f'<animateTransform attributeName="transform" type="scale" '
            f'values="0.4;0.4;1" keyTimes="0;{t0 / (t0 + 0.5):.4f};1" '
            f'dur="{t0 + 0.5:.2f}s" begin="0s" fill="freeze" calcMode="spline" '
            f'keySplines="0 0 1 1;0.34 1.4 0.5 1"/>')
        b.append(f'<g transform="translate({cx:.1f},{ny})"><g transform="scale(1)">{sc}'
                 f'<path d="{_hexagon(0, 0, R)}" '
                 f'fill="{col if current else pal["surface"]}" stroke="{col}" '
                 f'stroke-width="2"/>'
                 f'<text class="m" x="0" y="4.5" font-size="12.5" font-weight="700" '
                 f'text-anchor="middle" fill="{pal["bg"] if current else col}">'
                 f'{i + 1:02d}</text></g></g>')

        if current:
            b.append(f'<text class="m" x="{cx:.1f}" y="{ny - R - 13}" font-size="10" '
                     f'font-weight="700" letter-spacing="2" text-anchor="middle" '
                     f'fill="{col}">YOU ARE HERE</text>')
        else:
            b.append(f'<path d="M {cx - 5.5:.1f} {ny - R - 17} l 4 4.5 l 7.5 -8" '
                     f'fill="none" stroke="{col}" stroke-width="2" opacity="0.75" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
        b.append('</g>')

        # -- stage card
        cardx, cardw = PAD + colw * i + 9, colw - 18
        b.append(gin(1.25 + i * 0.14, 10, 0.6))
        b.append(f'<rect x="{cardx:.1f}" y="{CARD_Y}" width="{cardw:.1f}" '
                 f'height="{CARD_H}" rx="12" fill="{pal["surface"]}" stroke="{col}" '
                 f'stroke-width="{1.6 if current else 1}" opacity="{1 if current else 0.92}"/>')
        b.append(glyph(gl, cardx + cardw - 34, CARD_Y + 16, 20, col))
        yw = tw(year, 10.5) + 16
        b.append(f'<rect x="{cardx + 16:.1f}" y="{CARD_Y + 15}" width="{yw:.1f}" '
                 f'height="20" rx="6" fill="{col}" opacity="0.16"/>')
        b.append(f'<text class="m" x="{cardx + 24:.1f}" y="{CARD_Y + 29}" font-size="10.5" '
                 f'font-weight="700" letter-spacing="0.4" fill="{col}">{esc(year)}</text>')
        b.append(f'<text class="m" x="{cardx + 16:.1f}" y="{CARD_Y + 58}" font-size="13" '
                 f'font-weight="700" fill="{pal["text"]}">{esc(role)}</text>')
        b.append(f'<text class="m" x="{cardx + 16:.1f}" y="{CARD_Y + 77}" font-size="11" '
                 f'fill="{col}">{esc(org)}</text>')
        for k, ln in enumerate(det):
            b.append(f'<text class="m" x="{cardx + 16:.1f}" y="{CARD_Y + 97 + k * 15}" '
                     f'font-size="10.5" fill="{pal["dim"]}">{esc(ln)}</text>')
        b.append('</g>')

    # -- unlocked strip
    uy = CARD_Y + CARD_H + 16
    b.append(f'<line x1="{PAD}" y1="{uy}" x2="{W - PAD}" y2="{uy}" '
             f'stroke="{pal["border"]}" stroke-width="1" opacity="0.7"/>')
    b.append(fade(2.0))
    b.append(f'<text class="m" x="{PAD}" y="{uy + 34}" font-size="10.5" '
             f'font-weight="700" letter-spacing="2" fill="{pal["dim"]}">UNLOCKED</text>')
    bx = PAD + 104
    for label in ["M.S. Computer Science · Temple University · 2024–25",
                  "B.C.A. · Charotar University · 2020–23"]:
        bw = tw(label, 11.5) + 44
        b.append(f'<rect x="{bx:.1f}" y="{uy + 16}" width="{bw:.1f}" height="26" rx="13" '
                 f'fill="none" stroke="{pal["border"]}" stroke-width="1"/>')
        b.append(glyph("spark", bx + 13, uy + 23, 12, pal["accent3"]))
        b.append(f'<text class="m" x="{bx + 33:.1f}" y="{uy + 33}" font-size="11.5" '
                 f'fill="{pal["muted"]}">{esc(label)}</text>')
        bx += bw + 12
    b.append('</g>')

    return svg(W, H, "".join(b), pal)


# ------------------------------------------------------------------ chips
# Standalone link buttons. An <img> can't carry a hyperlink, so each chip is
# its own file and the README wraps it in an <a>.

LINKS = [
    ("link-email", "EMAIL", ("glyph", "mail"), "accent"),
    ("link-linkedin", "LINKEDIN", ("glyph", "linkedin"), "accent2"),
    ("link-github", "REPOSITORIES", ("icon", "github"), "text"),
]


def build_chip(label, ref, ckey, pal):
    fs, H = 13, 44
    ls = 0.8
    lw = tw(label, fs) + ls * (len(label) - 1)
    W = int(18 + 16 + 10 + lw + 18)
    col = pal[ckey]

    b = [f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="11" '
         f'fill="{pal["surface"]}" stroke="{pal["border"]}" stroke-width="1.5"/>']
    if ref[0] == "glyph":
        b.append(glyph(ref[1], 18, (H - 16) / 2, 16, col))
    else:
        b.append(icon(ref[1], 18, (H - 16) / 2, 16, brand(ref[1], pal)))
    b.append(f'<text class="m" x="{18 + 16 + 10}" y="{H / 2 + 4.5}" font-size="{fs}" '
             f'font-weight="600" letter-spacing="{ls}" fill="{pal["text"]}">{esc(label)}</text>')
    return svg(W, H, "".join(b), pal)


# -------------------------------------------------------------------- main

def main():
    dest = os.path.join(OUT, "preview") if STATIC else OUT
    os.makedirs(dest, exist_ok=True)
    for name, fn in (("hero", build_hero), ("stack", build_stack),
                     ("pipeline", build_pipeline), ("timeline", build_timeline)):
        for pal in (DARK, LIGHT):
            path = os.path.join(dest, f"{name}-{pal['name']}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(fn(pal))
            print(f"  {name}-{pal['name']}.svg  {os.path.getsize(path) / 1024:6.1f} KB")

    for slug, label, ref, ckey in LINKS:
        for pal in (DARK, LIGHT):
            path = os.path.join(dest, f"{slug}-{pal['name']}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_chip(label, ref, ckey, pal))
            print(f"  {slug}-{pal['name']}.svg  {os.path.getsize(path) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
