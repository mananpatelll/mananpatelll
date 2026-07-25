#!/usr/bin/env python3
"""
Generates every SVG used by the profile README.

Each asset is emitted twice - once for GitHub's dark theme, once for light -
and the README picks between them with <picture media="(prefers-color-scheme)">.
Everything is self-hosted: no badge services, no external fonts, no runtime
requests, no JavaScript.

    py assets/src/build.py               # normal, animated build
    STATIC=1 py assets/src/build.py      # freeze at final frame (for review)

Motion is split deliberately between two mechanisms:

  * SMIL (<animate>, <animateMotion>, <animateTransform>) drives anything
    where the exact geometry matters - path draws, orbital motion, typing,
    staggered entrances. It is the most predictable thing inside GitHub's
    <img> sandbox.
  * CSS @keyframes drive the cheap ambient loops - starfield twinkle, aurora
    breathing. Hundreds of stars as SMIL would triple the file size, and if
    a renderer ever ignored the CSS the stars simply hold still.

STATIC mode exists because headless screenshots don't advance animation
clocks, so it's the only way to eyeball what a reader ends up looking at.
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

# The hero renders on the same deep-space canvas in both themes. It reads as a
# viewport rather than a page background, so it doesn't need to invert - and it
# means the one graphic everybody sees first is never the washed-out variant.
COSMOS = dict(
    name="cosmos",
    void="#04050D", deep="#090C24",
    surface="#10142E", surface2="#171D42", border="#262E63",
    text="#EEF2FF", muted="#A7B2DC", dim="#6C77AB",
    a1="#22D3EE", a2="#A78BFA", a3="#F472B6", a4="#FBBF24",
    ok="#34D399", no="#FB7185",
)

DARK = dict(
    name="dark",
    bg="#070912", surface="#0E1226", surface2="#151A38",
    border="#232A54", grid="#141936",
    text="#E9EEFF", muted="#A2ADD6", dim="#6A75A6",
    a1="#22D3EE", a2="#A78BFA", a3="#F472B6", a4="#FBBF24",
    ok="#34D399", no="#FB7185",
    aurora="0.21", chip="#0E1226", edge="#262E63",
)

LIGHT = dict(
    name="light",
    bg="#FDFDFF", surface="#F2F3FE", surface2="#E9EBFB",
    border="#DBDEF4", grid="#EDEFFC",
    text="#0A0C1C", muted="#4B5480", dim="#7B85B0",
    a1="#0E7490", a2="#6D28D9", a3="#BE185D", a4="#B45309",
    ok="#047857", no="#E11D48",
    aurora="0.16", chip="#FFFFFF", edge="#C9CEEA",
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
    if pal["name"] != "light":
        if l < 0.06:
            return _mix(hexv, "#FFFFFF", 0.82)
        if l < 0.18:
            return _mix(hexv, "#FFFFFF", 0.46)
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
#      ignores animation - a static rasteriser, an exported still, a reader
#      that strips motion - gets the fully composed card rather than a blank.
#   2. Stagger delays are therefore encoded as a held first segment in
#      keyTimes rather than as begin="Ns", because a real begin offset would
#      show the base (finished) value first and then snap back to hide it.
#
# Every helper collapses to a plain finished state when STATIC is set.

EASE = "0.22 1 0.36 1"          # the settle used by every entrance
BACK = "0.34 1.56 0.64 1"       # slight overshoot, for things that "pop"


def _hold(begin, dur):
    """(total duration, keyTime at which the real motion starts)."""
    total = begin + dur
    return total, (begin / total if total else 0.0)


def gin(begin, dy=8, dur=0.7, dx=0):
    """Open a <g> that fades and drifts into place."""
    if STATIC:
        return "<g>"
    total, k = _hold(begin, dur)
    return (f'<g>'
            f'<animate attributeName="opacity" values="0;0;1" '
            f'keyTimes="0;{k:.4f};1" dur="{total:.2f}s" begin="0s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="{dx} {dy};{dx} {dy};0 0" keyTimes="0;{k:.4f};1" '
            f'dur="{total:.2f}s" begin="0s" fill="freeze" calcMode="spline" '
            f'keySplines="0 0 1 1;{EASE}"/>')


def fade(begin, dur=0.8):
    """Open a <g> that only fades in - safe around masks and filters, which
    don't follow a translating parent."""
    if STATIC:
        return "<g>"
    total, k = _hold(begin, dur)
    return (f'<g><animate attributeName="opacity" values="0;0;1" '
            f'keyTimes="0;{k:.4f};1" dur="{total:.2f}s" begin="0s" fill="freeze"/>')


def pop(begin, dur=0.62, from_=0.35):
    """Open a <g> that scales up from `from_` about its own origin. Callers
    place it inside a translate so the origin is already where it should be."""
    if STATIC:
        return "<g>"
    total, k = _hold(begin, dur)
    return (f'<g><animate attributeName="opacity" values="0;0;1" '
            f'keyTimes="0;{k:.4f};1" dur="{total:.2f}s" begin="0s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="scale" '
            f'values="{from_};{from_};1" keyTimes="0;{k:.4f};1" '
            f'dur="{total:.2f}s" begin="0s" fill="freeze" calcMode="spline" '
            f'keySplines="0 0 1 1;{BACK}"/>')


def grow(attr, final, dur, begin, start=0):
    """(attribute, child-animation) pair easing `attr` from start to final."""
    if STATIC:
        return f'{attr}="{final}"', ""
    total, k = _hold(begin, dur)
    return (f'{attr}="{final}"',
            f'<animate attributeName="{attr}" values="{start};{start};{final}" '
            f'keyTimes="0;{k:.4f};1" dur="{total:.2f}s" begin="0s" fill="freeze" '
            f'calcMode="spline" keySplines="0 0 1 1;{EASE}"/>')


def draw(d, begin, dur, length, splines="0.4 0 0.2 1"):
    """Stroke-dash pair that draws a path on. Base state is fully drawn."""
    if STATIC:
        return "", ""
    total, k = _hold(begin, dur)
    return (f' stroke-dasharray="{length:.0f}" stroke-dashoffset="0"',
            f'<animate attributeName="stroke-dashoffset" '
            f'values="{length:.0f};{length:.0f};0" keyTimes="0;{k:.4f};1" '
            f'dur="{total:.2f}s" begin="0s" fill="freeze" calcMode="spline" '
            f'keySplines="0 0 1 1;{splines}"/>')


def steps(begin, dur, frames):
    """Discrete step-through of `frames`, held on frames[0] for `begin`."""
    total, k = _hold(begin, dur)
    kt = [0.0, k] + [k + (1 - k) * i / (len(frames) - 1) for i in range(1, len(frames))]
    vals = [frames[0]] + list(frames)
    return (f'<animate attributeName="{{attr}}" values="{";".join(vals)}" '
            f'keyTimes="{";".join(f"{v:.4f}" for v in kt)}" dur="{total:.2f}s" '
            f'begin="0s" fill="freeze" calcMode="discrete"/>')


def blink(begin, dur=1.05):
    if STATIC:
        return ""
    return (f'<animate attributeName="opacity" values="1;1;0;0;1" dur="{dur}s" '
            f'begin="{begin}s" repeatCount="indefinite"/>')


def pulse_op(dur=2.2, lo="0.25"):
    if STATIC:
        return ""
    return (f'<animate attributeName="opacity" values="1;{lo};1" dur="{dur}s" '
            f'repeatCount="indefinite"/>')


def spin(cx, cy, dur, ccw=False):
    """Continuous rotation about an explicit centre. SMIL rather than CSS so
    the origin never depends on how a renderer resolves transform-box."""
    if STATIC:
        return ""
    a, b = (360, 0) if ccw else (0, 360)
    return (f'<animateTransform attributeName="transform" type="rotate" '
            f'values="{a} {cx} {cy};{b} {cx} {cy}" dur="{dur}s" '
            f'repeatCount="indefinite"/>')


def orbit(d, dur, begin=0.0, ccw=False):
    """Travel a closed path forever."""
    if STATIC:
        return ""
    kp = "1;0" if ccw else "0;1"
    return (f'<animateMotion dur="{dur}s" begin="{begin}s" repeatCount="indefinite" '
            f'path="{d}" keyPoints="{kp}" keyTimes="0;1" calcMode="linear"/>')


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
    # a ringed planet, for the projects card
    "planet": ('<circle cx="11" cy="12" r="7.2" fill="none" stroke="{c}" stroke-width="2"/>'
               '<ellipse cx="11" cy="12" rx="12.6" ry="4.2" fill="none" stroke="{c}" '
               'stroke-width="1.8" transform="rotate(-22 11 12)" opacity="0.85"/>'),
    # a shield with a slash, for the risk gate
    "gate": ('<path d="M12 1.8l8.4 3.2v6.1c0 5.1-3.5 9.4-8.4 11-4.9-1.6-8.4-5.9-8.4-11V5z" '
             'fill="none" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>'
             '<path d="M8.4 12.2h7.2" stroke="{c}" stroke-width="2.2" stroke-linecap="round"/>'),
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


# ------------------------------------------------------------------- chrome

BASE_CSS = f""".m{{font-family:{MONO}}}
.s{{font-family:{SANS}}}"""

AMBIENT_CSS = """@keyframes tw{0%,100%{opacity:1}50%{opacity:.14}}
@keyframes br{0%,100%{opacity:.55}50%{opacity:1}}
.tw{animation:tw 4s ease-in-out infinite}
.br{animation:br 7s ease-in-out infinite}"""


def svg(w, h, body, pal, extra_defs="", css=""):
    style = BASE_CSS if STATIC else "\n".join(x for x in (BASE_CSS, AMBIENT_CSS, css) if x)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img">'
            f'<defs><style>{style}</style>{extra_defs}</defs>{body}</svg>')


def card_defs(pal, w, h):
    """Gradients and patterns every non-hero card shares."""
    return f'''
<clipPath id="card"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="20"/></clipPath>
<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
  <circle cx="1.6" cy="1.6" r="1.05" fill="{pal['grid']}"/>
</pattern>
<linearGradient id="spectrum" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{pal['a1']}"/>
  <stop offset="0.5" stop-color="{pal['a2']}"/>
  <stop offset="1" stop-color="{pal['a3']}"/>
</linearGradient>
<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{pal['a2']}" stop-opacity="0.85"/>
  <stop offset="0.35" stop-color="{pal['border']}" stop-opacity="0.9"/>
  <stop offset="1" stop-color="{pal['border']}" stop-opacity="0"/>
</linearGradient>
<radialGradient id="au1" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="{pal['a2']}" stop-opacity="{pal['aurora']}"/>
  <stop offset="1" stop-color="{pal['a2']}" stop-opacity="0"/>
</radialGradient>
<radialGradient id="au2" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="{pal['a1']}" stop-opacity="{pal['aurora']}"/>
  <stop offset="1" stop-color="{pal['a1']}" stop-opacity="0"/>
</radialGradient>'''


def frame(w, h, pal, aurora=((250, 60, 420, 220, "au1"), (1010, 300, 460, 260, "au2"))):
    """Card background shared by every non-hero asset."""
    b = [f'<g clip-path="url(#card)">'
         f'<rect width="{w}" height="{h}" fill="{pal["bg"]}"/>']
    for cx, cy, rx, ry, gid in aurora:
        cls = "" if STATIC else ' class="br"'
        b.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
                 f'fill="url(#{gid})"{cls}/>')
    b.append(f'<rect width="{w}" height="{h}" fill="url(#dots)" opacity="0.5"/>')
    if pal["name"] == "dark":
        b.append(_stars(random.Random(hash(w * 7 + h) & 0xFFFF), w, h, 34,
                        pal, rmax=1.0, omax=0.42))
    b.append('</g>')
    # hairline border, drawn last so nothing bleeds over it
    b.append(f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="20" '
             f'fill="none" stroke="{pal["border"]}" stroke-width="1.5"/>')
    return "".join(b)


def corners(w, h, pal, m=15, L=20):
    """HUD brackets in the card's four corners."""
    c, sw = pal["a2"], 1.4
    o = 0.5
    return (f'<g stroke="{c}" stroke-width="{sw}" opacity="{o}" fill="none" '
            f'stroke-linecap="round">'
            f'<path d="M{m} {m + L}V{m}h{L}"/><path d="M{w - m - L} {m}h{L}v{L}"/>'
            f'<path d="M{m} {h - m - L}v{L}h{L}"/>'
            f'<path d="M{w - m} {h - m - L}v{L}h-{L}"/></g>')


def header(pal, w, cmd, title, pad=46, tag=None):
    """The `$ command` + title block every card opens with."""
    b = [f'{fade(0.05, 0.5)}',
         f'<text class="m" x="{pad}" y="48" font-size="12.5" fill="{pal["dim"]}">'
         f'<tspan fill="{pal["a1"]}">$</tspan> {esc(cmd)}</text>',
         f'<text class="s" x="{pad}" y="80" font-size="27" font-weight="800" '
         f'letter-spacing="-0.3" fill="{pal["text"]}">{esc(title)}</text>']
    if tag:
        tw_ = tw(tag, 10.5) + 22
        b.append(f'<rect x="{w - pad - tw_:.1f}" y="60" width="{tw_:.1f}" height="24" '
                 f'rx="12" fill="none" stroke="{pal["border"]}" stroke-width="1"/>')
        b.append(f'<text class="m" x="{w - pad - tw_ / 2:.1f}" y="76" font-size="10.5" '
                 f'letter-spacing="1.4" text-anchor="middle" fill="{pal["dim"]}">'
                 f'{esc(tag)}</text>')
    a, an = grow("width", w - pad * 2, 1.0, 0.2)
    b.append(f'<rect x="{pad}" y="97" height="1.5" {a} fill="url(#rule)">{an}</rect>')
    b.append('</g>')
    return "".join(b)


# ------------------------------------------------------------- space canvas

def _stars(rnd, w, h, n, pal, y0=0, y1=None, rmax=1.5, omax=0.95, tint=0.14):
    """A deterministic starfield. Brightness lives in fill-opacity so the CSS
    twinkle (which animates `opacity`) multiplies with it instead of erasing
    it - one element per star, ~130 bytes each."""
    y1 = h if y1 is None else y1
    cols = [pal["a1"], pal["a2"], pal["a3"]]
    out = []
    for _ in range(n):
        x = rnd.uniform(8, w - 8)
        y = rnd.uniform(y0 + 8, y1 - 8)
        r = round(rnd.uniform(0.45, rmax), 2)
        o = round(rnd.uniform(0.18, omax), 2)
        col = rnd.choice(cols) if rnd.random() < tint else "#FFFFFF"
        if STATIC:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{col}" '
                       f'fill-opacity="{o}"/>')
        else:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{col}" '
                       f'fill-opacity="{o}" class="tw" style="animation-duration:'
                       f'{rnd.uniform(2.6, 7.5):.1f}s;animation-delay:'
                       f'-{rnd.uniform(0, 7):.1f}s"/>')
    return "".join(out)


def _flare(x, y, s, col, dur=5.0, delay=0.0):
    """A bright star with a four-point diffraction cross."""
    a = "" if STATIC else (f' class="tw" style="animation-duration:{dur}s;'
                           f'animation-delay:-{delay}s"')
    return (f'<g{a}>'
            f'<circle cx="{x}" cy="{y}" r="{s * 0.30:.2f}" fill="{col}"/>'
            f'<circle cx="{x}" cy="{y}" r="{s * 1.1:.2f}" fill="{col}" opacity="0.13"/>'
            f'<path d="M{x - s * 3.2:.1f} {y}H{x + s * 3.2:.1f}M{x} {y - s * 3.2:.1f}'
            f'V{y + s * 3.2:.1f}" stroke="{col}" stroke-width="{s * 0.20:.2f}" '
            f'opacity="0.55" stroke-linecap="round"/></g>')


def _shooting(x, y, dx, dy, dur, begin, col):
    """An occasional streak. Purely decorative, so it stays hidden in STATIC."""
    if STATIC:
        return ""
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    return (f'<g opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0" '
            f'keyTimes="0;0.44;0.47;0.55;0.60;1" dur="{dur}s" begin="{begin}s" '
            f'repeatCount="indefinite"/>'
            f'<g><animateTransform attributeName="transform" type="translate" '
            f'values="{x} {y};{x} {y};{x + dx} {y + dy};{x + dx} {y + dy}" '
            f'keyTimes="0;0.44;0.60;1" dur="{dur}s" begin="{begin}s" '
            f'repeatCount="indefinite" calcMode="spline" '
            f'keySplines="0 0 1 1;0.3 0 0.7 1;0 0 1 1"/>'
            f'<path d="M0 0L{-ux * 78:.1f} {-uy * 78:.1f}" stroke="url(#trail)" '
            f'stroke-width="1.8" stroke-linecap="round"/>'
            f'<circle r="1.7" fill="{col}"/></g></g>')


# ------------------------------------------------------------------- hero

HERO_CSS = """@keyframes flick{0%,100%{opacity:.9}45%{opacity:.62}70%{opacity:.98}}
.fl{animation:flick 5.5s ease-in-out infinite}"""

ROLES = ["Agentic LLM Systems", "Multi-Agent Orchestration",
         "Retrieval & RAG", "LLM Evaluation"]

BLURB = [
    "I build agentic LLM systems — multi-agent setups, retrieval, and the",
    "evals that catch them being confidently wrong. Right now I'm pointing",
    "that at markets, because it's a domain that argues back.",
]

STATUS = [("M.S. Computer Science · Temple University", "muted"),
          ("Philadelphia, PA", "muted"),
          ("4 publications & abstracts", "muted"),
          ("open to AI engineering roles", "a1")]


def build_hero(pal):
    W, H, X0 = 1200, 544, 64
    C = COSMOS
    rnd = random.Random(11)
    # HUD geometry. HX is pulled left of centre-right so the leader-line
    # labels clear the card edge.
    HX, HY = 900, 238

    extra = f'''
<clipPath id="card"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22"/></clipPath>
<radialGradient id="sky" cx="0.34" cy="0.16" r="0.95">
  <stop offset="0" stop-color="#131A46"/>
  <stop offset="0.45" stop-color="{C['deep']}"/>
  <stop offset="1" stop-color="{C['void']}"/>
</radialGradient>
<radialGradient id="neb1" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="{C['a2']}" stop-opacity="0.42"/>
  <stop offset="0.55" stop-color="{C['a2']}" stop-opacity="0.10"/>
  <stop offset="1" stop-color="{C['a2']}" stop-opacity="0"/>
</radialGradient>
<radialGradient id="neb2" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="{C['a1']}" stop-opacity="0.34"/>
  <stop offset="0.55" stop-color="{C['a1']}" stop-opacity="0.08"/>
  <stop offset="1" stop-color="{C['a1']}" stop-opacity="0"/>
</radialGradient>
<radialGradient id="neb3" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="{C['a3']}" stop-opacity="0.30"/>
  <stop offset="0.6" stop-color="{C['a3']}" stop-opacity="0.06"/>
  <stop offset="1" stop-color="{C['a3']}" stop-opacity="0"/>
</radialGradient>
<linearGradient id="trail" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#FFFFFF" stop-opacity="0.9"/>
  <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>
</linearGradient>
<linearGradient id="name" x1="{X0}" y1="128" x2="{X0 + 520}" y2="200"
                gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#EAF6FF"/>
  <stop offset="0.34" stop-color="{C['a1']}"/>
  <stop offset="0.68" stop-color="{C['a2']}"/>
  <stop offset="1" stop-color="{C['a3']}"/>
</linearGradient>
<linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{C['a1']}"/>
  <stop offset="0.55" stop-color="{C['a2']}"/>
  <stop offset="1" stop-color="{C['a3']}"/>
</linearGradient>
<linearGradient id="gloss" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>
  <stop offset="0.5" stop-color="#FFFFFF" stop-opacity="1"/>
  <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>
</linearGradient>
<linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{C['a1']}" stop-opacity="0"/>
  <stop offset="1" stop-color="{C['a1']}" stop-opacity="0.22"/>
</linearGradient>
<linearGradient id="scrim" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{C['void']}" stop-opacity="0.55"/>
  <stop offset="0.55" stop-color="{C['void']}" stop-opacity="0.26"/>
  <stop offset="1" stop-color="{C['void']}" stop-opacity="0"/>
</linearGradient>
<radialGradient id="core" cx="0.5" cy="0.5" r="0.5">
  <stop offset="0" stop-color="#FFFFFF"/>
  <stop offset="0.30" stop-color="{C['a1']}"/>
  <stop offset="0.62" stop-color="{C['a2']}" stop-opacity="0.55"/>
  <stop offset="1" stop-color="{C['a2']}" stop-opacity="0"/>
</radialGradient>
<linearGradient id="limb" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{C['a2']}" stop-opacity="0"/>
  <stop offset="0.28" stop-color="{C['a1']}" stop-opacity="0.9"/>
  <stop offset="0.6" stop-color="{C['a2']}" stop-opacity="0.8"/>
  <stop offset="1" stop-color="{C['a3']}" stop-opacity="0"/>
</linearGradient>
<linearGradient id="atmo" x1="0" y1="1" x2="0" y2="0">
  <stop offset="0" stop-color="{C['a2']}" stop-opacity="0.22"/>
  <stop offset="1" stop-color="{C['a2']}" stop-opacity="0"/>
</linearGradient>
<mask id="gloss-m">
  <rect x="-300" y="120" width="260" height="92" fill="url(#gloss)">
    <animate attributeName="x" values="-300;-300;640;640" keyTimes="0;0.30;0.72;1"
             dur="7s" begin="2.4s" repeatCount="indefinite"/>
  </rect>
</mask>'''

    b = ['<g clip-path="url(#card)">']

    # ---- deep space
    b.append(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
    for cx, cy, rx, ry, gid, dx, dy, dur in (
            (250, 108, 430, 250, "neb1", 26, -16, 19),
            (900, 190, 400, 240, "neb2", -22, 18, 23),
            (640, 520, 420, 210, "neb3", 18, -12, 27)):
        mo = "" if STATIC else (
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 0;{dx} {dy};0 0" dur="{dur}s" repeatCount="indefinite" '
            f'calcMode="spline" keyTimes="0;0.5;1" '
            f'keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/>')
        cls = "" if STATIC else ' class="br"'
        b.append(f'<g{cls}><ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
                 f'fill="url(#{gid})">{mo}</ellipse></g>')

    # ---- stars, then a few hero flares on top
    b.append(_stars(rnd, W, H, 150, C, y1=500, rmax=1.5))
    b.append(_flare(1078, 96, 4.4, "#FFFFFF", 6.0, 0.4))
    b.append(_flare(126, 436, 3.4, C["a1"], 7.2, 2.6))
    b.append(_flare(690, 68, 3.0, C["a3"], 5.4, 1.4))
    b.append(_shooting(150, 60, 300, 128, 13, 4.0, "#FFFFFF"))
    b.append(_shooting(1150, 120, -270, 150, 17, 10.5, C["a1"]))

    # ---- scrim: the copy column sits over a starfield, and stars landing on a
    # baseline read as rendering artefacts. This buys contrast back without
    # flattening the nebula behind it.
    b.append(f'<rect width="660" height="{H}" fill="url(#scrim)"/>')

    # ---- planet limb along the bottom edge: a very shallow arc, dark body,
    # luminous rim. R is chosen so the horizon exits the card near both corners.
    PR, TOP = 4600, 508
    pcy = TOP + PR
    edge_y = pcy - math.sqrt(PR * PR - 600 * 600)
    arc = f'M0 {edge_y:.1f} A {PR} {PR} 0 0 1 {W} {edge_y:.1f}'
    b.append(f'<rect x="0" y="{TOP - 46}" width="{W}" height="{56}" fill="url(#atmo)"/>')
    b.append(f'<path d="{arc} L{W} {H + 4} L0 {H + 4} Z" fill="{C["void"]}"/>')
    b.append(f'<path d="{arc}" stroke="url(#limb)" stroke-width="1.6" fill="none"/>')

    # ============================================================ left column
    # -- typed prompt line
    prompt, sep, cmd, fs = "manan@orion", ":~$ ", "whoami --verbose", 14.5
    px = X0
    b.append(f'<text class="m" x="{px}" y="80" font-size="{fs}" fill="{C["a1"]}">{prompt}</text>')
    px += tw(prompt, fs)
    b.append(f'<text class="m" x="{px:.1f}" y="80" font-size="{fs}" fill="{C["dim"]}">{esc(sep)}</text>')
    px += tw(sep, fs)
    cw_, n = tw(cmd, fs), len(cmd)
    widths = [f"{cw_ * i / n:.1f}" for i in range(n + 1)]
    curxs = [f"{px + cw_ * i / n:.1f}" for i in range(n + 1)]
    if STATIC:
        b.append(f'<text class="m" x="{px:.1f}" y="80" font-size="{fs}" fill="{C["text"]}">{cmd}</text>')
        b.append(f'<rect x="{px + cw_:.1f}" y="66" width="8" height="17" fill="{C["a1"]}"/>')
    else:
        b.append(f'<clipPath id="typ"><rect x="{px:.1f}" y="64" width="{cw_:.1f}" height="22">'
                 + steps(0.3, 1.05, widths).format(attr="width") + '</rect></clipPath>')
        b.append(f'<g clip-path="url(#typ)"><text class="m" x="{px:.1f}" y="80" '
                 f'font-size="{fs}" fill="{C["text"]}">{cmd}</text></g>')
        b.append(f'<rect x="{px + cw_:.1f}" y="66" width="8" height="17" fill="{C["a1"]}">'
                 + steps(0.3, 1.05, curxs).format(attr="x") + blink(1.4) + '</rect>')

    # -- the name: gradient fill, bloom behind, specular sweep on top.
    # The bloom is two stroked copies rather than a Gaussian blur. A blur here
    # is the single most expensive thing in the file, and as an <img> the whole
    # card re-rasterises every animated frame - so it would be paid over and
    # over. Widening strokes hug the letterforms and cost nothing.
    NFS, NY = 71, 184
    name_text = lambda extra: (
        f'<text class="s" x="{X0}" y="{NY}" font-size="{NFS}" font-weight="800" '
        f'letter-spacing="0.5" {extra}>MANAN PATEL</text>')
    b.append(fade(1.0, 0.9))
    for sw, op in ((13, "0.07"), (7, "0.10"), (3, "0.13")):
        b.append(name_text(f'fill="none" stroke="{C["a2"]}" stroke-width="{sw}" '
                           f'stroke-linejoin="round" opacity="{op}"'))
    b.append(name_text('fill="url(#name)"'))
    if not STATIC:
        b.append(f'<g mask="url(#gloss-m)" opacity="0.85">'
                 f'{name_text("fill=\"#FFFFFF\"")}</g>')
    b.append('</g>')

    # -- spectrum rule with a runner light on the end
    a, an = grow("width", 214, 0.95, 1.5)
    b.append(f'<rect x="{X0}" y="206" height="4" rx="2" {a} fill="url(#bar)">{an}</rect>')
    if not STATIC:
        b.append(f'<circle cy="208" r="4.5" fill="#FFFFFF" opacity="0">'
                 f'<animate attributeName="cx" values="{X0};{X0};{X0 + 214}" '
                 f'keyTimes="0;0.61;1" dur="2.45s" begin="0s" fill="freeze" '
                 f'calcMode="spline" keySplines="0 0 1 1;{EASE}"/>'
                 f'<animate attributeName="opacity" values="0;0;1;1;0" '
                 f'keyTimes="0;0.61;0.68;0.95;1" dur="2.45s" begin="0s" fill="freeze"/>'
                 f'</circle>')

    # -- role line: static anchor, rotating specialisation. Mono on purpose -
    # the rotating half is a separate <text>, so the anchor's width has to be
    # knowable without measuring whatever fallback font the reader resolved.
    RFS, RY = 19, 254
    anchor, rsep = "AI Engineer", " · "
    b.append(f'{gin(1.35)}<text class="m" x="{X0}" y="{RY}" font-size="{RFS}" '
             f'font-weight="700" fill="{C["text"]}">{anchor}</text>'
             f'<text class="m" x="{X0 + tw(anchor, RFS):.1f}" y="{RY}" font-size="{RFS}" '
             f'fill="{C["dim"]}">{esc(rsep)}</text></g>')

    rx, slot = X0 + tw(anchor + rsep, RFS), 3.2
    cycle = len(ROLES) * slot
    for i, r in enumerate(ROLES):
        if STATIC and i:
            continue
        if STATIC:
            b.append(f'<text class="m" x="{rx:.1f}" y="{RY}" font-size="{RFS}" '
                     f'font-weight="700" fill="{C["a1"]}">{esc(r)}</text>')
            continue
        t0 = i * slot
        kt = ";".join(f"{min(1.0, max(0.0, v / cycle)):.4f}" for v in
                      [0, t0, t0 + 0.34, t0 + slot - 0.34, t0 + slot, cycle])
        # the first role is visible by default: it is what shows before the
        # cycle starts, and what a non-animating renderer falls back to
        b.append(f'<g opacity="{1 if i == 0 else 0}">'
                 f'<animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="{kt}" '
                 f'dur="{cycle}s" begin="1.9s" repeatCount="indefinite"/>'
                 f'<animateTransform attributeName="transform" type="translate" '
                 f'values="0 9;0 9;0 0;0 0;0 -9;0 -9" keyTimes="{kt}" dur="{cycle}s" '
                 f'begin="1.9s" repeatCount="indefinite" calcMode="spline" '
                 f'keySplines="0 0 1 1;{EASE};0 0 1 1;0.4 0 1 1;0 0 1 1"/>'
                 f'<text class="m" x="{rx:.1f}" y="{RY}" font-size="{RFS}" '
                 f'font-weight="700" fill="{C["a1"]}">{esc(r)}</text></g>')

    # -- blurb
    for i, ln in enumerate(BLURB):
        b.append(f'{gin(1.55 + i * 0.1, 7)}<text class="m" x="{X0}" y="{300 + i * 25}" '
                 f'font-size="13.5" fill="{C["muted"]}">{esc(ln)}</text></g>')

    # -- signal chips under the blurb
    cx_ = X0
    b.append(fade(2.1))
    for label, col in (("LangGraph", "a1"), ("Anthropic + OpenAI", "a2"),
                       ("Qdrant", "a3"), ("LLM-as-judge", "a4")):
        cw2 = tw(label, 11.5) + 26
        b.append(f'<rect x="{cx_:.1f}" y="{392}" width="{cw2:.1f}" height="26" rx="13" '
                 f'fill="{C["surface"]}" fill-opacity="0.75" stroke="{C[col]}" '
                 f'stroke-opacity="0.45" stroke-width="1"/>'
                 f'<circle cx="{cx_ + 13:.1f}" cy="405" r="2.6" fill="{C[col]}"/>'
                 f'<text class="m" x="{cx_ + 22:.1f}" y="409" font-size="11.5" '
                 f'fill="{C["muted"]}">{esc(label)}</text>')
        cx_ += cw2 + 9
    b.append('</g>')

    # ========================================================== orbital HUD
    b.append(fade(0.55, 1.0))

    # radar sweep, clipped to the system's outer disc
    b.append(f'<clipPath id="disc"><circle cx="{HX}" cy="{HY}" r="163"/></clipPath>')
    if not STATIC:
        b.append(f'<g clip-path="url(#disc)"><g>{spin(HX, HY, 7.5)}'
                 f'<path d="M{HX} {HY} L{HX + 170} {HY - 96} A 196 196 0 0 1 '
                 f'{HX + 170} {HY + 96} Z" fill="url(#sweep)"/></g></g>')

    # tick ring
    ticks = []
    for i in range(72):
        aa = math.radians(i * 5)
        L = 9 if i % 6 == 0 else 4.5
        r0, r1 = 163, 163 - L
        ticks.append(f'M{HX + r0 * math.cos(aa):.1f} {HY + r0 * math.sin(aa):.1f}'
                     f'L{HX + r1 * math.cos(aa):.1f} {HY + r1 * math.sin(aa):.1f}')
    b.append(f'<g><path d="{"".join(ticks)}" stroke="{C["a2"]}" stroke-width="1.1" '
             f'opacity="0.42"/>{spin(HX, HY, 90, ccw=True)}</g>')
    b.append(f'<circle cx="{HX}" cy="{HY}" r="150" fill="none" stroke="{C["border"]}" '
             f'stroke-width="1" opacity="0.75"/>')

    # crosshair
    b.append(f'<g stroke="{C["a2"]}" stroke-width="1" opacity="0.24">'
             f'<path d="M{HX - 176} {HY}h44M{HX + 132} {HY}h44"/>'
             f'<path d="M{HX} {HY - 176}v44M{HX} {HY + 132}v44"/></g>')

    # three orbits in a shared, tilted plane + one polar ring
    def ellipse_path(cx, cy, rx, ry):
        return (f'M{cx - rx} {cy} a{rx} {ry} 0 1 0 {2 * rx} 0 '
                f'a{rx} {ry} 0 1 0 {-2 * rx} 0')

    bodies = [(132, 46, "a1", 14.0, False, "AGENTS"),
              (96, 34, "a3", 9.5, True, "RETRIEVAL"),
              (60, 21, "a4", 6.2, False, "EVALS")]
    b.append(f'<g transform="rotate(-17 {HX} {HY})">')
    for rx_, ry_, ck, dur, ccw, _ in bodies:
        p = ellipse_path(HX, HY, rx_, ry_)
        b.append(f'<path d="{p}" fill="none" stroke="{C[ck]}" stroke-width="1.1" '
                 f'opacity="0.45"/>')
        # without animation the body has to be parked somewhere, so park it at
        # the path's start point - exactly where animateMotion would begin
        park = "" if not STATIC else f' transform="translate({HX - rx_},{HY})"'
        b.append(f'<g opacity="0.9"{park}><circle r="5.2" fill="{C[ck]}"/>'
                 f'<circle r="10" fill="{C[ck]}" opacity="0.18"/>'
                 f'{orbit(p, dur, ccw=ccw)}</g>')
    b.append('</g>')

    # polar ring, standing on edge
    pp = ellipse_path(HX, HY, 26, 150)
    b.append(f'<g transform="rotate(24 {HX} {HY})">'
             f'<path d="{pp}" fill="none" stroke="{C["a2"]}" stroke-width="1" '
             f'opacity="0.30"/></g>')

    # the core
    b.append(f'<circle cx="{HX}" cy="{HY}" r="42" fill="url(#core)" opacity="0.9"/>')
    b.append(f'<circle cx="{HX}" cy="{HY}" r="11" fill="#FFFFFF" opacity="0.95"/>')
    if not STATIC:
        for d in (0.0, 1.3):
            b.append(f'<circle cx="{HX}" cy="{HY}" r="11" fill="none" stroke="{C["a1"]}" '
                     f'stroke-width="1.4" opacity="0">'
                     f'<animate attributeName="r" values="11;74" dur="2.6s" begin="{2 + d}s" '
                     f'repeatCount="indefinite"/>'
                     f'<animate attributeName="opacity" values="0.7;0" dur="2.6s" '
                     f'begin="{2 + d}s" repeatCount="indefinite"/></circle>')

    # leader lines + labels, anchored outside the disc so they stay readable
    for i, (rx_, ry_, ck, _, _, lab) in enumerate(bodies):
        ly = HY - 92 + i * 34
        lx = HX + 174
        b.append(f'<path d="M{HX + 150} {ly}h16" stroke="{C[ck]}" stroke-width="1" '
                 f'opacity="0.5"/>')
        b.append(f'<circle cx="{lx - 2}" cy="{ly}" r="2.4" fill="{C[ck]}"/>')
        b.append(f'<text class="m" x="{lx + 8}" y="{ly + 4}" font-size="10.5" '
                 f'letter-spacing="1.3" fill="{C["muted"]}">{esc(lab)}</text>')

    b.append(f'<text class="m" x="{HX}" y="{HY + 192}" font-size="10.5" '
             f'letter-spacing="2.2" text-anchor="middle" fill="{C["dim"]}">'
             f'CURRENT SYSTEM · ONE STAR, THREE PROBLEMS</text>')
    b.append('</g>')

    # ============================================================ status bar
    SY = 478
    b.append(f'<line x1="0" y1="{SY - 26}" x2="{W}" y2="{SY - 26}" '
             f'stroke="{C["border"]}" stroke-width="1" opacity="0.8"/>')
    sx = X0
    b.append(fade(2.3))
    for i, (t, ck) in enumerate(STATUS):
        if i:
            b.append(f'<path d="M{sx:.1f} {SY - 5}l5 5l-5 5" fill="none" '
                     f'stroke="{C["dim"]}" stroke-width="1.5" stroke-linecap="round" '
                     f'stroke-linejoin="round" opacity="0.6"/>')
            sx += 18
        if i == len(STATUS) - 1:
            b.append(f'<circle cx="{sx + 4:.1f}" cy="{SY}" r="3.6" fill="{C["a1"]}">'
                     f'{pulse_op(1.9, "0.25")}</circle>')
            b.append(f'<circle cx="{sx + 4:.1f}" cy="{SY}" r="7" fill="{C["a1"]}" '
                     f'opacity="0.18"/>')
            sx += 16
        b.append(f'<text class="m" x="{sx:.1f}" y="{SY + 4}" font-size="12.5" '
                 f'fill="{C[ck]}">{esc(t)}</text>')
        sx += tw(t, 12.5) + 18
    b.append('</g>')

    b.append('</g>')  # /clip
    b.append(corners(W, H, C, m=17, L=22))
    b.append(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="none" '
             f'stroke="{pal["edge"]}" stroke-width="1.5"/>')

    return svg(W, H, "".join(b), C, extra, HERO_CSS)


# --------------------------------------------------------------- projects

def _candles(x, y, w, h, pal, seed=7, n=14, delay=0.6):
    """A schematic price series - shape only, no scale, no numbers."""
    rnd = random.Random(seed)
    step = w / n
    price, series = 50.0, []
    for i in range(n):
        o = price
        c = max(12, o + (2.0 if i % 5 != 3 else -2.6) + rnd.uniform(-3.4, 3.6))
        series.append((o, c, max(o, c) + rnd.uniform(0.6, 3.0),
                       min(o, c) - rnd.uniform(0.6, 3.0)))
        price = c
    flat = [v for s in series for v in s]
    lo_, span = min(flat), (max(flat) - min(flat)) or 1
    sc = lambda v: (v - lo_) / span * (h - 16) + 8

    out = []
    for i, (o, c, hi, lo) in enumerate(series):
        cx = x + i * step + step / 2
        up = c >= o
        col = pal["ok"] if up else pal["no"]
        bw = step * 0.5
        total, k = _hold(delay + i * 0.04, 0.5)
        anim = "" if STATIC else (
            f'<animateTransform attributeName="transform" type="scale" '
            f'values="1 0;1 0;1 1" keyTimes="0;{k:.4f};1" dur="{total:.2f}s" '
            f'begin="0s" fill="freeze" calcMode="spline" keySplines="0 0 1 1;{EASE}"/>')
        out.append(f'<g transform="translate({cx:.1f},{y + h})"><g transform="scale(1,1)">{anim}'
                   f'<line x1="0" y1="{-sc(lo):.1f}" x2="0" y2="{-sc(hi):.1f}" '
                   f'stroke="{col}" stroke-width="1.2" opacity="0.7"/>'
                   f'<rect x="{-bw / 2:.1f}" y="{-sc(max(o, c)):.1f}" width="{bw:.1f}" '
                   f'height="{max(2, sc(max(o, c)) - sc(min(o, c))):.1f}" rx="1.2" '
                   f'fill="{col}" opacity="{0.95 if up else 0.85}"/></g></g>')

    pts = [(x + i * step + step / 2, y + h - sc(s[1])) for i, s in enumerate(series)]
    d = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    da, dan = draw(d, delay + 0.3, 1.5, L)
    out.append(f'<path d="{d}" fill="none" stroke="{pal["a1"]}" stroke-width="1.8" '
               f'stroke-linecap="round" stroke-linejoin="round" opacity="0.9"{da}>{dan}</path>')
    hx, hy = pts[-1]
    out.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="3.4" fill="{pal["a1"]}"/>')
    if not STATIC:
        out.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="3.4" fill="none" '
                   f'stroke="{pal["a1"]}" stroke-width="1.3" opacity="0">'
                   f'<animate attributeName="r" values="3.4;12" dur="2.1s" begin="2.4s" '
                   f'repeatCount="indefinite"/>'
                   f'<animate attributeName="opacity" values="0.7;0" dur="2.1s" '
                   f'begin="2.4s" repeatCount="indefinite"/></circle>')
    return "".join(out)


PROJECT = dict(
    key="a1", glyph="candles", status="IN PROGRESS", state="a4",
    name="Multi-Agent Trading Desk",
    line=["A deterministic scanner screens the S&P 500, three specialist agents",
          "review what it finds, and a pure-code risk gate gets the last word —",
          "including the option to say no."],
    tags=["LangGraph", "human-in-the-loop", "risk gate", "trade journal"],
)


def build_projects(pal):
    """One panel, full width. With a single system to show there's no grid to
    balance, so the copy takes the left half and the chart takes the right."""
    W, H, PAD = 1200, 440, 46
    PY, PH, PW = 126, 242, 1200 - 46 * 2
    LEFT, VIZ = PAD + 26, PAD + 566

    p, col, st = PROJECT, pal[PROJECT["key"]], pal[PROJECT["state"]]
    b = [frame(W, H, pal),
         header(pal, W, "ls -l ~/projects", "What I'm actually building",
                tag="1 SYSTEM")]

    b.append(gin(0.35, 12, 0.7))
    b.append(f'<rect x="{PAD}" y="{PY}" width="{PW}" height="{PH}" rx="16" '
             f'fill="{pal["surface"]}" stroke="{pal["border"]}" stroke-width="1.5"/>')
    # a rect, not a stroked horizontal path: an objectBoundingBox gradient
    # on a zero-height bbox is degenerate and renders nothing at all
    b.append(f'<rect x="{PAD + 16}" y="{PY - 1.25}" width="{PW - 32}" '
             f'height="2.5" rx="1.25" fill="url(#spectrum)"/>')

    b.append(glyph(p["glyph"], LEFT, PY + 30, 24, col))
    b.append(f'<text class="s" x="{LEFT + 36}" y="{PY + 50}" font-size="20" '
             f'font-weight="700" fill="{pal["text"]}">{esc(p["name"])}</text>')

    # inline with the title, not flush right: flush right would sit on top of
    # the chart panel, which starts at VIZ
    sw, sx = tw(p["status"], 10) + 30, LEFT + 326
    b.append(f'<rect x="{sx:.1f}" y="{PY + 32}" width="{sw:.1f}" '
             f'height="22" rx="11" fill="{st}" fill-opacity="0.14" stroke="{st}" '
             f'stroke-opacity="0.45" stroke-width="1"/>')
    b.append(f'<circle cx="{sx + 12:.1f}" cy="{PY + 43}" r="3" fill="{st}">'
             f'{pulse_op(2.4, "0.3")}</circle>')
    b.append(f'<text class="m" x="{sx + 20:.1f}" y="{PY + 47}" font-size="10" '
             f'letter-spacing="1.2" fill="{st}">{esc(p["status"])}</text>')

    for k, ln in enumerate(p["line"]):
        b.append(f'<text class="m" x="{LEFT}" y="{PY + 90 + k * 21}" '
                 f'font-size="12" fill="{pal["muted"]}">{esc(ln)}</text>')

    tx = LEFT
    for t in p["tags"]:
        twd = tw(t, 10.5) + 20
        b.append(f'<rect x="{tx:.1f}" y="{PY + 186}" width="{twd:.1f}" height="22" '
                 f'rx="11" fill="none" stroke="{pal["border"]}" stroke-width="1"/>')
        b.append(f'<text class="m" x="{tx + 10:.1f}" y="{PY + 201}" font-size="10.5" '
                 f'fill="{pal["dim"]}">{esc(t)}</text>')
        tx += twd + 7

    vw, vh = PW - 566 - 26, 168
    b.append(f'<rect x="{VIZ}" y="{PY + 32}" width="{vw}" height="{vh}" rx="10" '
             f'fill="{pal["bg"]}" fill-opacity="0.6" stroke="{pal["border"]}" '
             f'stroke-width="1" opacity="0.8"/>')
    b.append(_candles(VIZ + 20, PY + 46, vw - 40, vh - 34, pal, delay=0.9))
    b.append('</g>')

    b.append(f'<line x1="{PAD}" y1="{PY + PH + 26}" x2="{W - PAD}" y2="{PY + PH + 26}" '
             f'stroke="{pal["border"]}" stroke-width="1" opacity="0.7"/>')
    b.append(f'{fade(1.6)}<text class="m" x="{PAD}" y="{PY + PH + 52}" font-size="11.5" '
             f'fill="{pal["dim"]}">The chart is a schematic of the system, not a '
             f'measured result — the numbers that matter live in the repo.</text></g>')

    return svg(W, H, "".join(b), pal, card_defs(pal, W, H))


# --------------------------------------------------------------- pipeline

def build_pipeline(pal):
    W, H = 1200, 470
    NW, NH, MID = 168, 62, 262
    b = [frame(W, H, pal),
         header(pal, W, "render architecture --graph", "The trading desk, roughly",
                tag="NO-TRADE IS A VALID OUTPUT")]

    def node(x, y, title, sub, col, dashed=False, w=NW, h=NH, d=0.0, solidfill=None):
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        return (f'{gin(d, 10, 0.62)}'
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="13" '
                f'fill="{solidfill or pal["surface"]}" stroke="{col}" '
                f'stroke-width="1.5"{dash}/>'
                f'<rect x="{x}" y="{y + 12}" width="3" height="{h - 24}" rx="1.5" fill="{col}"/>'
                f'<text class="m" x="{x + w / 2}" y="{y + h / 2 - 3}" font-size="12.5" '
                f'font-weight="700" letter-spacing="1.1" text-anchor="middle" '
                f'fill="{pal["text"]}">{esc(title)}</text>'
                f'<text class="m" x="{x + w / 2}" y="{y + h / 2 + 15}" font-size="10.5" '
                f'text-anchor="middle" fill="{pal["dim"]}">{esc(sub)}</text></g>')

    def wire(d, col, delay, length=None):
        s = f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.5" opacity="0.45"/>'
        if not STATIC:
            s += (f'<g><circle r="3" fill="{col}"/>'
                  f'<circle r="7" fill="{col}" opacity="0.2"/>'
                  f'<animateMotion dur="2.8s" begin="{delay}s" repeatCount="indefinite" '
                  f'path="{d}" calcMode="spline" keyPoints="0;1" keyTimes="0;1" '
                  f'keySplines="0.45 0 0.55 1"/>'
                  f'<animate attributeName="opacity" values="0;1;1;0" dur="2.8s" '
                  f'begin="{delay}s" repeatCount="indefinite"/></g>')
        return s

    c1, c2, c3, c4, c5 = 46, 268, 500, 722, 944

    b.append(node(c1, MID - NH / 2, "SCANNER", "S&P 500 · rules only", pal["a1"], d=0.3))

    ys = [MID - 90, MID, MID + 90]
    for i, (lab, sub) in enumerate([("TECHNICAL", "price action & volume"),
                                    ("NEWS", "catalyst scan"),
                                    ("EVENTS", "earnings · calendar")]):
        b.append(node(c2, ys[i] - 30, lab, sub, pal["a2"], dashed=True, h=60,
                      d=0.5 + i * 0.08))
        b.append(wire(f"M{c1 + NW} {MID}C{c1 + NW + 40} {MID},{c2 - 40} {ys[i]},{c2} {ys[i]}",
                      pal["a1"], 0.3 + i * 0.34))

    b.append(node(c3, MID - NH / 2, "TRADER", "synthesis agent", pal["a2"], dashed=True, d=0.85))
    for i in range(3):
        b.append(wire(f"M{c2 + NW} {ys[i]}C{c2 + NW + 40} {ys[i]},{c3 - 40} {MID},{c3} {MID}",
                      pal["a2"], 1.1 + i * 0.3))

    b.append(node(c4, MID - NH / 2, "RISK GATE", "pure code · no bypass", pal["a4"], d=1.1))
    b.append(wire(f"M{c3 + NW} {MID}L{c4} {MID}", pal["a2"], 1.8))
    b.append(glyph("gate", c4 + NW - 26, MID - NH / 2 + 8, 14, pal["a4"]))

    b.append(node(c5, MID - NH / 2 - 46, "HUMAN", "LangGraph interrupt", pal["a3"], d=1.3))
    b.append(node(c5, MID - NH / 2 + 46, "JOURNAL", "structured trade log", pal["muted"], d=1.4))
    for dy, dl in ((-46, 2.2), (46, 2.45)):
        b.append(wire(f"M{c4 + NW} {MID}C{c4 + NW + 36} {MID},{c5 - 36} {MID + dy},"
                      f"{c5} {MID + dy}", pal["a4"], dl))

    # the escape hatch that matters most
    b.append(wire(f"M{c4 + 77} {MID + NH / 2}L{c4 + 77} {MID + 96}", pal["no"], 2.1))
    b.append(f'{gin(1.7, 8, 0.6)}'
             f'<rect x="{c4 + 18}" y="{MID + 96}" width="118" height="28" rx="14" '
             f'fill="{pal["no"]}" fill-opacity="0.08" stroke="{pal["no"]}" '
             f'stroke-width="1.2" stroke-dasharray="4 4"/>'
             f'<text class="m" x="{c4 + 77}" y="{MID + 114}" font-size="11" '
             f'letter-spacing="1" text-anchor="middle" fill="{pal["no"]}">NO-TRADE</text></g>')

    ly, lx = H - 36, 46
    b.append(fade(1.9))
    for lab, col, dash in [("deterministic code", pal["a1"], False),
                           ("LLM agent", pal["a2"], True),
                           ("hard constraint", pal["a4"], False),
                           ("human sign-off", pal["a3"], False)]:
        da = ' stroke-dasharray="3 3"' if dash else ""
        b.append(f'<rect x="{lx:.0f}" y="{ly - 8}" width="20" height="10" rx="5" fill="none" '
                 f'stroke="{col}" stroke-width="1.5"{da}/>'
                 f'<text class="m" x="{lx + 28:.0f}" y="{ly + 1}" font-size="11.5" '
                 f'fill="{pal["muted"]}">{esc(lab)}</text>')
        lx += 28 + tw(lab, 11.5) + 30
    b.append('</g>')

    return svg(W, H, "".join(b), pal, card_defs(pal, W, H))


# --------------------------------------------------------------- timeline
# The career as a star chart: a course plotted between four waypoints, the
# legs behind you already flown, the current one still burning.

STAGES = [
    ("2023", "Technical Analyst", "Arihant Investments",
     ["screened equities for breakout", "setups, wrote daily trade reports"],
     "a1", "candles", 202),
    ("2024 – 25", "ML Research Assistant", "Temple University",
     ["clinical AI on linked EHR data,", "NIH-funded (U01, NIDCR)"],
     "a1", "pulse", 156),
    ("2025", "Research Lead", "Civic Interactions Lab",
     ["led an undergrad capstone team", "as their lead and stakeholder"],
     "a3", "agents", 198),
    ("2025 →", "Independent AI Engineer", "self-directed",
     ["agentic systems, retrieval, and", "the evals that keep them honest"],
     "a2", "spark", 150),
]


def _catmull(pts):
    """Smooth cubic path through pts. Returns (path data, bezier segments)."""
    segs, d = [], f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[i - 1] if i else pts[0]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append((p1, c1, c2, p2))
        d += (f"C{c1[0]:.1f} {c1[1]:.1f},{c2[0]:.1f} {c2[1]:.1f},"
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


def build_timeline(pal):
    W, PAD, H = 1200, 46, 476
    colw = (W - PAD * 2) / len(STAGES)
    CARD_Y, CARD_H = 262, 124
    R = 23

    b = [frame(W, H, pal, aurora=((180, 150, 380, 200, "au2"),
                                  (1040, 120, 400, 220, "au1"))),
         header(pal, W, "plot course --from 2023", "The run so far",
                tag="YOU ARE HERE ↗")]

    xs = [PAD + colw * i + colw / 2 for i in range(len(STAGES))]
    ys = [s[6] for s in STAGES]
    road = ([(PAD + 18, ys[0] + 22)] + list(zip(xs, ys)) + [(W - PAD - 18, ys[-1] - 22)])
    d, segs = _catmull(road)
    lens = [_seg_len(s) for s in segs]
    L = sum(lens)
    reached = sum(lens[:len(STAGES)]) / L

    # -- the course: a thick dim base that draws itself, then a marching lane
    da, dan = draw(d, 0.15, 2.1, L, splines="0.35 0 0.15 1")
    b.append(f'<path d="{d}" fill="none" stroke="{pal["border"]}" stroke-width="10" '
             f'stroke-linecap="round" stroke-linejoin="round"{da}>{dan}</path>')
    march = "" if STATIC else ('<animate attributeName="stroke-dashoffset" values="0;-20" '
                               'dur="1.15s" repeatCount="indefinite"/>')
    b.append(f'<path d="{d}" fill="none" stroke="url(#spectrum)" stroke-width="2.2" '
             f'stroke-linecap="round" opacity="0.6" stroke-dasharray="4 16" '
             f'stroke-dashoffset="0">{march}</path>')

    # -- the ship: decorative, so it stays hidden without animation
    if not STATIC:
        b.append(f'<g opacity="0">'
                 f'<circle r="5" fill="{pal["a2"]}"/>'
                 f'<circle r="12" fill="{pal["a2"]}" opacity="0.2"/>'
                 f'<animateMotion dur="3.6s" begin="1.8s" repeatCount="indefinite" '
                 f'path="{d}" keyPoints="0;{reached:.4f}" keyTimes="0;1" '
                 f'calcMode="spline" keySplines="0.4 0 0.2 1"/>'
                 f'<animate attributeName="opacity" values="0;0.95;0.95;0" dur="3.6s" '
                 f'begin="1.8s" repeatCount="indefinite"/></g>')

    # -- waypoints
    for i, (year, role, org, det, ck, gl, ny) in enumerate(STAGES):
        cx, col = xs[i], pal[ck]
        current = i == len(STAGES) - 1
        t0 = 1.0 + i * 0.2

        b.append(f'<line x1="{cx:.1f}" y1="{ny + R}" x2="{cx:.1f}" y2="{CARD_Y}" '
                 f'stroke="{col}" stroke-width="1.2" stroke-dasharray="3 4" opacity="0.4"/>')

        if current and not STATIC:
            for dl in (0.0, 1.1):
                b.append(f'<circle cx="{cx:.1f}" cy="{ny}" r="{R}" fill="none" '
                         f'stroke="{col}" stroke-width="1.5" opacity="0">'
                         f'<animate attributeName="r" values="{R};{R + 26}" dur="2.2s" '
                         f'begin="{2.4 + dl}s" repeatCount="indefinite"/>'
                         f'<animate attributeName="opacity" values="0.7;0" dur="2.2s" '
                         f'begin="{2.4 + dl}s" repeatCount="indefinite"/></circle>')

        b.append(f'<g transform="translate({cx:.1f},{ny})">')
        b.append(pop(t0, 0.55))
        b.append(f'<circle r="{R + 7}" fill="none" stroke="{col}" stroke-width="1" '
                 f'opacity="0.32" stroke-dasharray="2 5"/>')
        b.append(f'<circle r="{R}" fill="{col if current else pal["surface"]}" '
                 f'stroke="{col}" stroke-width="2"/>')
        b.append(f'<text class="m" y="4.5" font-size="12.5" font-weight="700" '
                 f'text-anchor="middle" fill="{pal["bg"] if current else col}">'
                 f'{i + 1:02d}</text>')
        b.append('</g></g>')

        if current:
            b.append(f'<text class="m" x="{cx:.1f}" y="{ny - R - 15}" font-size="10" '
                     f'font-weight="700" letter-spacing="2" text-anchor="middle" '
                     f'fill="{col}">CURRENT LEG</text>')
        else:
            b.append(f'<path d="M{cx - 5.5:.1f} {ny - R - 18}l4 4.5l7.5 -8" '
                     f'fill="none" stroke="{col}" stroke-width="2" opacity="0.7" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')

        # -- waypoint card
        cardx, cardw = PAD + colw * i + 9, colw - 18
        b.append(gin(1.35 + i * 0.13, 12, 0.62))
        b.append(f'<rect x="{cardx:.1f}" y="{CARD_Y}" width="{cardw:.1f}" '
                 f'height="{CARD_H}" rx="14" fill="{pal["surface"]}" stroke="{col}" '
                 f'stroke-width="{1.6 if current else 1}" '
                 f'stroke-opacity="{1 if current else 0.55}"/>')
        b.append(f'<path d="M{cardx + 14:.1f} {CARD_Y}h{cardw - 28:.1f}" stroke="{col}" '
                 f'stroke-width="2.5" opacity="{0.95 if current else 0.5}" '
                 f'stroke-linecap="round"/>')
        b.append(glyph(gl, cardx + cardw - 36, CARD_Y + 18, 20, col))
        yw = tw(year, 10.5) + 16
        b.append(f'<rect x="{cardx + 16:.1f}" y="{CARD_Y + 17}" width="{yw:.1f}" '
                 f'height="20" rx="6" fill="{col}" opacity="0.16"/>')
        b.append(f'<text class="m" x="{cardx + 24:.1f}" y="{CARD_Y + 31}" font-size="10.5" '
                 f'font-weight="700" fill="{col}">{esc(year)}</text>')
        b.append(f'<text class="m" x="{cardx + 16:.1f}" y="{CARD_Y + 60}" font-size="13" '
                 f'font-weight="700" fill="{pal["text"]}">{esc(role)}</text>')
        b.append(f'<text class="m" x="{cardx + 16:.1f}" y="{CARD_Y + 79}" font-size="11" '
                 f'fill="{col}">{esc(org)}</text>')
        for k, ln in enumerate(det):
            b.append(f'<text class="m" x="{cardx + 16:.1f}" y="{CARD_Y + 100 + k * 15}" '
                     f'font-size="10.5" fill="{pal["dim"]}">{esc(ln)}</text>')
        b.append('</g>')

    # -- credentials strip
    uy = CARD_Y + CARD_H + 18
    b.append(f'<line x1="{PAD}" y1="{uy}" x2="{W - PAD}" y2="{uy}" '
             f'stroke="{pal["border"]}" stroke-width="1" opacity="0.7"/>')
    b.append(fade(2.1))
    b.append(f'<text class="m" x="{PAD}" y="{uy + 34}" font-size="10.5" '
             f'font-weight="700" letter-spacing="2" fill="{pal["dim"]}">UNLOCKED</text>')
    bx = PAD + 104
    for label in ["M.S. Computer Science · Temple University · 2024–25",
                  "B.C.A. · Charotar University · 2020–23"]:
        bw = tw(label, 11.5) + 44
        b.append(f'<rect x="{bx:.1f}" y="{uy + 16}" width="{bw:.1f}" height="26" rx="13" '
                 f'fill="none" stroke="{pal["border"]}" stroke-width="1"/>')
        b.append(glyph("spark", bx + 13, uy + 23, 12, pal["a4"]))
        b.append(f'<text class="m" x="{bx + 33:.1f}" y="{uy + 33}" font-size="11.5" '
                 f'fill="{pal["muted"]}">{esc(label)}</text>')
        bx += bw + 12
    b.append('</g>')

    return svg(W, H, "".join(b), pal, card_defs(pal, W, H))


# ------------------------------------------------------------------ stack
# (label, simple-icons slug) or (label, ("glyph", name, palette-key))

STACK = [
    ("agents", "LLM & AGENTIC", "a2", [
        ("LangChain", "langchain"), ("LangGraph", "langgraph"),
        ("LangSmith", ("glyph", "eval", "a1")),
        ("Anthropic", "anthropic"), ("OpenAI", ("glyph", "spark", "a1")),
        ("Pydantic", "pydantic"), ("Ollama", "ollama"),
    ], [
        "multi-agent orchestration", "corrective RAG", "MCP servers",
        "human-in-the-loop", "LLM-as-judge", "structured outputs",
        "prompt engineering", "local inference",
    ]),
    ("layers", "MACHINE LEARNING", "a1", [
        ("PyTorch", "pytorch"), ("Transformers", "huggingface"),
        ("scikit-learn", "scikitlearn"), ("XGBoost", ("glyph", "trees", "a4")),
        ("NumPy", "numpy"), ("SciPy", "scipy"), ("MLflow", "mlflow"),
    ], [
        "embeddings", "fine-tuning", "feature engineering",
        "hyperparameter search", "cross-validation", "ablation studies",
    ]),
    ("rack", "DATA & INFRA", "a3", [
        ("Python", "python"), ("SQL", ("glyph", "db", "a1")),
        ("pandas", "pandas"), ("FastAPI", "fastapi"), ("Docker", "docker"),
        ("Kubernetes", "kubernetes"), ("AWS", ("glyph", "cloud", "a4")),
        ("CUDA", "nvidia"), ("Qdrant", "qdrant"), ("Git", "git"),
    ], [
        "vector databases", "reproducible pipelines", "seeded deterministic runs",
        "cost & latency instrumentation",
    ]),
    ("candles", "MARKETS", "a4", [], [
        "equities & options", "technical analysis", "position sizing",
        "reward-to-risk floors", "stop placement", "trade journaling",
    ]),
    ("pulse", "CLINICAL AI", "a1", [], [
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
    W, PAD, GX, CX = 1200, 46, 46, 274
    CONTENT = W - CX - PAD

    blocks = []
    for gname, title, ck, tools, concepts in STACK:
        rows = _wrap(tools, CONTENT, lambda t: 36 + tw(t[0], 13) + 18)
        crows = _wrap(concepts, CONTENT, lambda c: tw(c, 12.5) + 26)
        blocks.append((gname, title, ck, rows, crows))

    H = 118
    for _, _, _, rows, crows in blocks:
        H += len(rows) * 45 + (6 if rows and crows else 0) + len(crows) * 34 + 34
    H = int(H + 6)

    total = sum(sum(len(r) for r in rows) + sum(len(r) for r in crows)
                for _, _, _, rows, crows in blocks)
    body = [frame(W, H, pal, aurora=((240, 90, 420, 240, "au1"),
                                     (980, H - 140, 440, 260, "au2"))),
            header(pal, W, "cat ~/stack.toml", "Technical Stack",
                   tag=f"{total} ENTRIES")]

    yy, delay, first = 132, 0.25, True
    for gname, title, ck, rows, crows in blocks:
        if not first:
            body.append(f'<line x1="{PAD}" y1="{yy - 18}" x2="{W - PAD}" y2="{yy - 18}" '
                        f'stroke="{pal["border"]}" stroke-width="1" opacity="0.65"/>')
        first = False

        col = pal[ck]
        n = sum(len(r) for r in rows) + sum(len(r) for r in crows)
        # vertical rail tying the category to its rows
        depth = len(rows) * 45 + (6 if rows and crows else 0) + len(crows) * 34 - 14
        body.append(f'<rect x="{GX + 2}" y="{yy + 30}" width="2" height="{max(0, depth - 30)}" '
                    f'rx="1" fill="{col}" opacity="0.22"/>')
        body.append(gin(delay, 8))
        body.append(f'<rect x="{GX - 8}" y="{yy - 6}" width="34" height="34" rx="10" '
                    f'fill="{col}" fill-opacity="0.12"/>')
        body.append(glyph(gname, GX + 1, yy + 3, 18, col))
        body.append(f'<text class="m" x="{GX + 42}" y="{yy + 12}" font-size="13" '
                    f'font-weight="700" letter-spacing="1.6" fill="{pal["text"]}">'
                    f'{esc(title)}</text>')
        body.append(f'<text class="m" x="{GX + 42}" y="{yy + 32}" font-size="10.5" '
                    f'letter-spacing="1.2" fill="{pal["dim"]}">{n:02d} ENTRIES</text>')
        body.append('</g>')
        delay += 0.08

        ry = yy
        for row in rows:
            rx = CX
            for (label, ref), w in row:
                body.append(gin(delay, 8, 0.55))
                body.append(f'<rect x="{rx:.1f}" y="{ry}" width="{w:.1f}" height="34" rx="10" '
                            f'fill="{pal["chip"]}" stroke="{pal["border"]}" stroke-width="1"/>')
                if isinstance(ref, tuple):
                    body.append(glyph(ref[1], rx + 12, ry + 9, 16, pal[ref[2]]))
                else:
                    body.append(icon(ref, rx + 12, ry + 9, 16, brand(ref, pal)))
                body.append(f'<text class="m" x="{rx + 36:.1f}" y="{ry + 22}" font-size="13" '
                            f'fill="{pal["text"]}">{esc(label)}</text></g>')
                rx += w + 9
                delay += 0.032
            ry += 45

        if rows and crows:
            ry += 6
        for row in crows:
            rx = CX
            for c, w in row:
                body.append(gin(delay, 6, 0.5))
                body.append(f'<rect x="{rx:.1f}" y="{ry}" width="{w:.1f}" height="26" rx="13" '
                            f'fill="none" stroke="{pal["border"]}" stroke-width="1"/>')
                body.append(f'<text class="m" x="{rx + 13:.1f}" y="{ry + 17}" font-size="12.5" '
                            f'fill="{pal["muted"]}">{esc(c)}</text></g>')
                rx += w + 8
                delay += 0.022
            ry += 34

        yy = ry + 34

    return svg(W, H, "".join(body), pal, card_defs(pal, W, H))


# ------------------------------------------------------------------ chips
# Standalone link buttons. An <img> can't carry a hyperlink, so each chip is
# its own file and the README wraps it in an <a>.

LINKS = [
    ("link-email", "EMAIL", ("glyph", "mail"), "a1"),
    ("link-linkedin", "LINKEDIN", ("glyph", "linkedin"), "a2"),
    ("link-github", "REPOSITORIES", ("icon", "github"), "a3"),
]


def build_chip(label, ref, ck, pal):
    fs, H, ls = 13, 46, 0.9
    lw = tw(label, fs) + ls * (len(label) - 1)
    W = int(20 + 16 + 11 + lw + 20)
    col = pal[ck]

    extra = (f'<linearGradient id="cg" x1="0" y1="0" x2="1" y2="1">'
             f'<stop offset="0" stop-color="{col}" stop-opacity="0.75"/>'
             f'<stop offset="1" stop-color="{col}" stop-opacity="0.22"/>'
             f'</linearGradient>'
             f'<linearGradient id="cf" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{col}" stop-opacity="0.10"/>'
             f'<stop offset="1" stop-color="{col}" stop-opacity="0.02"/>'
             f'</linearGradient>')

    b = [f'<rect x="1.25" y="1.25" width="{W - 2.5}" height="{H - 2.5}" rx="12" '
         f'fill="{pal["surface"]}"/>',
         f'<rect x="1.25" y="1.25" width="{W - 2.5}" height="{H - 2.5}" rx="12" '
         f'fill="url(#cf)"/>',
         f'<rect x="1.25" y="1.25" width="{W - 2.5}" height="{H - 2.5}" rx="12" '
         f'fill="none" stroke="url(#cg)" stroke-width="1.5"/>']
    if ref[0] == "glyph":
        b.append(glyph(ref[1], 20, (H - 16) / 2, 16, col))
    else:
        b.append(icon(ref[1], 20, (H - 16) / 2, 16, brand(ref[1], pal)))
    b.append(f'<text class="m" x="{20 + 16 + 11}" y="{H / 2 + 4.5}" font-size="{fs}" '
             f'font-weight="700" letter-spacing="{ls}" fill="{pal["text"]}">'
             f'{esc(label)}</text>')
    if not STATIC:
        b.append(f'<rect x="1.25" y="{H - 3.5}" height="2" rx="1" fill="{col}" '
                 f'width="{W / 3:.1f}" opacity="0.9">'
                 f'<animate attributeName="x" values="1.25;{W - W / 3 - 1.25:.1f};1.25" '
                 f'dur="4.5s" repeatCount="indefinite" calcMode="spline" '
                 f'keyTimes="0;0.5;1" keySplines="0.45 0 0.55 1;0.45 0 0.55 1"/></rect>')
    return svg(W, H, "".join(b), pal, extra)


# -------------------------------------------------------------------- main

BUILDS = (("hero", build_hero), ("projects", build_projects),
          ("pipeline", build_pipeline), ("timeline", build_timeline),
          ("stack", build_stack))


def main():
    dest = os.path.join(OUT, "preview") if STATIC else OUT
    os.makedirs(dest, exist_ok=True)
    tot = 0
    for name, fn in BUILDS:
        for pal in (DARK, LIGHT):
            path = os.path.join(dest, f"{name}-{pal['name']}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(fn(pal))
            kb = os.path.getsize(path) / 1024
            tot += kb
            print(f"  {name}-{pal['name']}.svg  {kb:7.1f} KB")

    for slug, label, ref, ck in LINKS:
        for pal in (DARK, LIGHT):
            path = os.path.join(dest, f"{slug}-{pal['name']}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_chip(label, ref, ck, pal))
            kb = os.path.getsize(path) / 1024
            tot += kb
            print(f"  {slug}-{pal['name']}.svg  {kb:7.1f} KB")

    print(f"  {'total':>28}  {tot:7.1f} KB")


if __name__ == "__main__":
    main()
