#!/usr/bin/env python3
"""Generate the Chicken Command Center's side column and its helper sensors.

Writes:
  dashboard/coop_side_section.yaml   animated coop scene, chicken comfort,
                                     controls and coop graphs
  templates/coop.yaml                helper sensors (coop temperature and
                                     humidity, chicken comfort, the scene's
                                     sky and window glow), included by
                                     packages/wall_tablet.yaml

The scene is layered images that Home Assistant swaps by state:
  sky       sensor.coop_sky     weather-station sky, day or night
  hens      sun.sun             in the run by day, in the windows at night
  glow      sensor.coop_glow    the Coop Light's colour and brightness
  weather   sensor.coop_sky     falling rain or snow in front
Animations are CSS inside the SVG pictures: a few small transforms, light
enough for the coop tablet.

Run:  python3 tools/coop.py
"""

import base64
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weather  # noqa: E402  (shared weather art: sun, clouds, moon, stars)

ROOT = Path(__file__).resolve().parent.parent

W, H = 400, 252          # scene canvas
DY = 18                  # the coop and run sit this far below the art origin
HORIZON = 176

# Coop colours: soft green with darker green trim.
WALL, WALL_SIDE, TRIM, ROOF = "#a9c99b", "#93b585", "#4f7a4a", "#3f6b3f"
WOOD, WOOD_DARK, POST = "#a68660", "#6e573f", "#b08a5c"

# ---------------------------------------------------------------------------
# The flock
# ---------------------------------------------------------------------------

# body, hackle (neck/head), tail, wing, pattern, pattern colour, extras
FLOCK = [
    ("Philomena", dict(body="#8e3b28", hackle="#7d3a2a", tail="#3b3f4f", wing="#7c3324",
                       pattern="lace", pattern_color="#6f7f99", comb="rose")),
    ("Blue", dict(body="#6f7f99", hackle="#4d5970", tail="#4d5970", wing="#66758f")),
    ("Mochi", dict(body="#c97a3d", hackle="#b8692f", tail="#2a1d14", wing="#b96d34",
                   pattern="calico")),
    ("Andromeda", dict(body="#8c97b2", hackle="#8c97b2", tail="#5f6a85", wing="#7f8aa6",
                       hackle_pattern="barred")),
    ("Sunny", dict(body="#a0522d", hackle="#b8642f", tail="#2a2420", wing="#934a28",
                   pattern="spangle")),
    ("Figgy", dict(body="#5a3a26", hackle="#4e3222", tail="#3e281b", wing="#51341f")),
    ("Cordelia", dict(body="#1f2426", hackle="#1f2426", tail="#162b26", wing="#262c2e",
                      muffs=True)),
    ("Boudica", dict(body="#efefef", hackle="#e2e2e2", tail="#1b1b1b", wing="#e8e8e8",
                     pattern="lace", pattern_color="#1b1b1b", comb="rose")),
    ("Theodora", dict(body="#6b7690", hackle="#737d94", tail="#4f5872", wing="#646f89",
                      feathered=True)),
]


def patterns(pid, p):
    """<pattern> defs for a hen's plumage, ids prefixed with pid."""
    out = ""
    if p.get("pattern") == "lace":
        out += (f'<pattern id="{pid}lace" width="4" height="3" patternUnits="userSpaceOnUse">'
                f'<path d="M0 3 A2 2 0 0 1 4 3" fill="none" stroke="{p["pattern_color"]}" '
                f'stroke-width="0.8"/></pattern>')
    if p.get("pattern") == "spangle":
        out += (f'<pattern id="{pid}spot" width="5" height="4.5" patternUnits="userSpaceOnUse">'
                '<circle cx="1.4" cy="1.4" r="0.8" fill="#fff"/>'
                '<circle cx="3.9" cy="3.6" r="0.7" fill="#141414"/></pattern>')
    if p.get("pattern") == "calico":
        out += (f'<pattern id="{pid}calico" width="8" height="7" patternUnits="userSpaceOnUse">'
                '<circle cx="2" cy="2" r="1.6" fill="#f6efe4"/>'
                '<circle cx="6" cy="5" r="1.3" fill="#2a1d14"/>'
                '<circle cx="6.2" cy="1.3" r="0.9" fill="#f6efe4"/></pattern>')
    if p.get("hackle_pattern") == "barred":
        out += (f'<pattern id="{pid}bar" width="3" height="2.4" patternUnits="userSpaceOnUse">'
                '<rect width="3" height="0.9" fill="#d8deeb"/></pattern>')
    return out


def overlay(pid, p):
    key = {"lace": "lace", "spangle": "spot", "calico": "calico"}.get(p.get("pattern"))
    return f"url(#{pid}{key})" if key else None


def hen(pid, p, mood="calm", puffed=1.0):
    """One hen facing left, feet at (0, 0), about 40 wide and 36 tall.

    mood: calm | happy | cold | panting
    """
    body_rx, body_ry = 13 * puffed, 10 * puffed
    over = overlay(pid, p)
    parts = [f'<defs>{patterns(pid, p)}</defs>']
    # Legs (feathered for Marans).
    parts.append('<path d="M-1 -5 L-2 0 M4 -5 L5 0 M-2 0 L-5 0.6 M5 0 L2 0.6" stroke="#e8a33a" '
                 'stroke-width="1.6" stroke-linecap="round" fill="none"/>')
    if p.get("feathered"):
        parts.append(f'<ellipse cx="-2" cy="-1.5" rx="2.2" ry="1.6" fill="{p["body"]}"/>'
                     f'<ellipse cx="5" cy="-1.5" rx="2.2" ry="1.6" fill="{p["body"]}"/>')
    # Tail, body, wing.
    parts.append(f'<path d="M9 -20 C16 -36 27 -32 23 -15 C20 -11 14 -11 10 -13 Z" fill="{p["tail"]}"/>')
    parts.append(f'<ellipse cx="2" cy="-14" rx="{body_rx:.1f}" ry="{body_ry:.1f}" fill="{p["body"]}"/>')
    if over:
        parts.append(f'<ellipse cx="2" cy="-14" rx="{body_rx:.1f}" ry="{body_ry:.1f}" fill="{over}"/>')
    wing_t = 'transform="rotate(-38 0 -16)"' if mood == "panting" else 'transform="rotate(-8 5 -14)"'
    parts.append(f'<ellipse cx="5" cy="-14" rx="{7.5 * puffed:.1f}" ry="{5 * puffed:.1f}" '
                 f'fill="{p["wing"]}" {wing_t}/>')
    if over:
        parts.append(f'<ellipse cx="5" cy="-14" rx="{7.5 * puffed:.1f}" ry="{5 * puffed:.1f}" '
                     f'fill="{over}" {wing_t}/>')
    # Neck and head.
    parts.append(f'<ellipse cx="-8" cy="-22" rx="6.5" ry="8.5" fill="{p["hackle"]}"/>')
    if p.get("hackle_pattern") == "barred":
        parts.append(f'<ellipse cx="-8" cy="-22" rx="6.5" ry="8.5" fill="url(#{pid}bar)"/>')
    parts.append(f'<circle cx="-10" cy="-28" r="5.6" fill="{p["hackle"]}"/>')
    if p.get("muffs"):
        parts.append(f'<ellipse cx="-12" cy="-24.5" rx="3.6" ry="2.8" fill="{p["hackle"]}"/>')
    # Comb and wattle.
    if p.get("comb") == "rose":
        parts.append('<ellipse cx="-11" cy="-33.2" rx="4" ry="1.8" fill="#d8392f"/>')
    else:
        parts.append('<path d="M-15 -32 q1 -4.5 2.8 -1 q1 -4.5 2.8 -1 q1 -4.5 2.8 -0.6 Z" fill="#d8392f"/>')
    if not p.get("muffs"):
        parts.append('<ellipse cx="-14" cy="-23.2" rx="1.6" ry="2.6" fill="#d8392f"/>')
    # Beak: open (panting) or closed.
    if mood == "panting":
        parts.append('<path d="M-15.3 -29 L-20.5 -28.6 L-15.3 -27.4 Z M-15.3 -26.6 L-19.6 -24.6 '
                     'L-15.3 -25.3 Z" fill="#f2b33d"/>')
    else:
        parts.append('<path d="M-15.3 -28.6 L-20.2 -27 L-15.3 -25.6 Z" fill="#f2b33d"/>')
    # Eye.
    eye_light = p["hackle"] in ("#1f2426",)
    if mood == "happy":
        parts.append(f'<path d="M-13 -29 Q-11.5 -31 -10 -29" stroke="{"#ddd" if eye_light else "#1b1b1b"}" '
                     'stroke-width="1" fill="none" stroke-linecap="round"/>')
    else:
        parts.append(f'<circle cx="-11.6" cy="-29" r="1.15" fill="{"#f2d58a" if eye_light else "#1b1b1b"}"/>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# Scene layers
# ---------------------------------------------------------------------------

def svg(inner, w=W, h=H, style=""):
    css = f"<style>{style}</style>" if style else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            f'{css}{inner}</svg>')


def data_uri(s):
    return "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()


ANIM = """
.cloud{animation:drift 70s linear infinite alternate}
@keyframes drift{from{transform:translateX(-18px)}to{transform:translateX(18px)}}
.twinkle{animation:tw 3.2s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:.25}50%{opacity:1}}
"""

SKY_COLORS = {
    "Sunny": ("#6eaaf0", "#cfe6ff"), "Partly cloudy": ("#7aa9e0", "#d6e6f8"),
    "Cloudy": ("#8e9db3", "#d3dbe6"), "Rain": ("#66748a", "#a9b5c6"), "Snow": ("#b2bfd2", "#e6edf6"),
    "Night": ("#0d1530", "#2b3866"), "Night rain": ("#111a2c", "#2b3448"),
    "Night snow": ("#18223e", "#3a4a6c"),
}


def ground(kind):
    night = kind.startswith("Night")
    snowy = "snow" in kind.lower()
    top, bottom = ({(False, False): ("#86b061", "#5a8a42"), (True, False): ("#2f4a30", "#1d3020"),
                    (False, True): ("#f4f7fb", "#dce4ee"), (True, True): ("#9aa7bb", "#7c899e")}
                   [(night, snowy)])
    tufts = "" if snowy else "".join(
        f'<path d="M{x} {y} l-2 -5 M{x} {y} l0 -6 M{x} {y} l2 -5" stroke="{bottom}" '
        f'stroke-width="1.2" stroke-linecap="round"/>'
        for x, y in [(40, 226), (96, 232), (150, 222), (214, 230), (268, 236), (330, 228), (380, 234)])
    return (f'<defs><linearGradient id="gr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
            f'stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient></defs>'
            f'<path d="M0 {HORIZON} Q200 {HORIZON - 8} {W} {HORIZON} V{H} H0 Z" fill="url(#gr)"/>{tufts}')


def sky(kind):
    top, bottom = SKY_COLORS[kind]
    night = kind.startswith("Night")
    art = ""
    if kind == "Sunny":
        art = weather.sun(64, 46, 17)
    elif kind == "Partly cloudy":
        art = weather.sun(76, 42, 15) + f'<g class="cloud">{weather.cloud(24, 82, 0.62)}</g>'
    elif kind in ("Cloudy", "Snow"):
        art = (f'<g class="cloud">{weather.cloud(150, 60, 0.6, "#eef1f5", "#b7c0ce")}</g>'
               f'<g class="cloud">{weather.cloud(20, 76, 0.75)}</g>')
    elif kind == "Rain":
        art = (f'<g class="cloud">{weather.cloud(150, 58, 0.6, "#b9c2d0", "#7d8aa3", "#5f6b82")}</g>'
               f'<g class="cloud">{weather.cloud(16, 74, 0.78, "#c9d1de", "#7d8aa3", "#5f6b82")}</g>')
    elif kind == "Night":
        star = "M0 -5 L1.2 -1.2 L5 0 L1.2 1.2 L0 5 L-1.2 1.2 L-5 0 L-1.2 -1.2 Z"
        art = weather.moon(60, 44, 18) + "".join(
            f'<path class="twinkle" style="animation-delay:{d}s" transform="translate({x} {y}) '
            f'scale({k})" d="{star}" fill="#fff4cc"/>'
            for x, y, k, d in [(120, 24, 0.9, 0), (176, 52, 0.6, 1.1), (232, 20, 0.75, 0.5),
                               (300, 44, 0.55, 1.8), (360, 18, 0.8, 0.9), (210, 80, 0.45, 2.4)])
    else:  # night rain / snow
        art = (f'<g class="cloud">{weather.cloud(150, 58, 0.6, "#4a556b", "#2c3447", "#1f2636")}</g>'
               f'<g class="cloud">{weather.cloud(16, 74, 0.78, "#556179", "#333c52", "#1f2636")}</g>')
    return svg(f'<defs><linearGradient id="sk" x1="0" y1="0" x2="0" y2="1">'
               f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
               f'</linearGradient></defs><rect width="{W}" height="{H}" fill="url(#sk)"/>'
               + art + ground(kind), style=ANIM)


def coop_and_run():
    """Static: the run (posts, rails, wire mesh, lean-to) and the coop."""
    mesh = "".join(f'<line x1="{x}" y1="104" x2="{x}" y2="194"/>' for x in range(26, 248, 7))
    mesh += "".join(f'<line x1="20" y1="{y}" x2="248" y2="{y}"/>' for y in range(110, 194, 7))
    posts = "".join(f'<rect x="{x - 2.5}" y="100" width="5" height="96" rx="1" fill="{POST}"/>'
                    for x in (20, 78, 136, 194, 248))
    rails = "".join(f'<rect x="18" y="{y}" width="232" height="4" rx="1" fill="{POST}"/>'
                    for y in (102, 148))
    slats = "".join(f'<rect x="196" y="{y}" width="52" height="5" fill="#7c9a5a" opacity="0.95"/>'
                    for y in range(122, 190, 11))
    lean_to = ('<path d="M188 98 L258 88 L258 94 L188 104 Z" fill="#8f979c"/>'
               '<path d="M190 104 L256 94 L256 112 Q224 122 190 116 Z" fill="#2b3036" opacity="0.85"/>')
    coop = (
        # side face, front face, roof
        f'<path d="M365 82 L390 92 L390 190 L365 196 Z" fill="{WALL_SIDE}"/>'
        f'<rect x="255" y="82" width="110" height="114" fill="{WALL}"/>'
        + "".join(f'<line x1="{x}" y1="84" x2="{x}" y2="194" stroke="{TRIM}" stroke-opacity="0.18"/>'
                  for x in range(266, 365, 11))
        + f'<rect x="255" y="82" width="5" height="114" fill="{TRIM}"/>'
        f'<rect x="360" y="82" width="5" height="114" fill="{TRIM}"/>'
        f'<path d="M386 90 L390 92 L390 190 L386 191 Z" fill="{TRIM}"/>'
        f'<path d="M246 86 L370 74 L398 88 L398 95 L370 81 L246 93 Z" fill="{ROOF}"/>'
        # side door
        f'<path d="M370 104 L384 109 L384 186 L370 190 Z" fill="none" stroke="{TRIM}" stroke-width="2"/>'
        # windows (glass; the glow layer lights them)
        + "".join(f'<rect x="{x}" y="100" width="26" height="20" rx="2" fill="#24302d" '
                  f'stroke="{TRIM}" stroke-width="3"/>' for x in (272, 306))
        # nest box
        + f'<rect x="286" y="140" width="60" height="22" fill="{WOOD}"/>'
        f'<rect x="284" y="136" width="64" height="6" rx="1" fill="{WOOD_DARK}"/>'
        + "".join(f'<line x1="286" y1="{y}" x2="346" y2="{y}" stroke="{WOOD_DARK}" stroke-opacity="0.5"/>'
                  for y in (148, 155))
        # flood lights on the roof edge, base blocks
        + '<rect x="300" y="74" width="16" height="5" rx="1" fill="#d7dbe0"/>'
        '<circle cx="298" cy="76" r="3.4" fill="#eef1f4"/><circle cx="318" cy="76" r="3.4" fill="#eef1f4"/>'
        + "".join(f'<rect x="{x}" y="196" width="14" height="5" fill="#9aa0a6"/>' for x in (262, 300, 340, 372))
    )
    inner = (f'<g transform="translate(0 {DY})">'
             f'<g stroke="#e6ece0" stroke-opacity="0.22" stroke-width="0.8">{mesh}</g>'
             f'{slats}{rails}{posts}{lean_to}{coop}</g>')
    return svg(inner)


# Inside the run: a back row of five and a front row of four, staggered.
# Feet y is in scene units (the run's bottom rail is at 208).
HEN_POS = [(38, 188), (84, 188), (130, 188), (176, 188), (222, 188),
           (61, 203), (107, 203), (153, 203), (199, 203)]
HEN_SCALE = 0.72


def run_front():
    """The run's posts and bottom rail, drawn over the hens so they're inside."""
    posts = "".join(f'<rect x="{x - 2.5}" y="{150 + DY}" width="5" height="{46}" rx="1" fill="{POST}"/>'
                    for x in (20, 78, 136, 194, 248))
    return svg(f'{posts}<rect x="18" y="{190 + DY}" width="232" height="5" rx="1" fill="{POST}"/>')

HEN_ANIM = """
.h{transform-box:fill-box;transform-origin:50% 100%}
.peck{animation:peck 5.5s ease-in-out infinite}
@keyframes peck{0%,58%,100%{transform:rotate(0)}64%{transform:rotate(-24deg)}70%{transform:rotate(0)}
76%{transform:rotate(-22deg)}82%{transform:rotate(0)}}
.bob{animation:bob 2.6s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-1.5px)}}
.stroll{animation:stroll 14s ease-in-out infinite alternate}
@keyframes stroll{from{transform:translateX(-3px)}to{transform:translateX(3px)}}
.name{font:600 9px Roboto,sans-serif;fill:#fff;paint-order:stroke;stroke:#22301f;
stroke-width:2.4px;stroke-linejoin:round;text-anchor:middle}
.z{font:700 11px Roboto,sans-serif;fill:#e9edff;animation:zz 4.5s ease-in infinite;opacity:0}
@keyframes zz{0%{transform:translate(0,0);opacity:0}20%{opacity:.9}100%{transform:translate(14px,-34px);opacity:0}}
"""


def hens_day():
    out = []
    rng = random.Random(7)
    # Back row first so the front row overlaps it.
    for i, ((name, p), (x, y)) in enumerate(zip(FLOCK, HEN_POS)):
        s = HEN_SCALE * (1.0 if y > 195 else 0.94)
        flip = i % 3 == 1
        anim = ["peck", "bob", "peck"][i % 3]
        delay = round(rng.uniform(0, 4), 1)
        g = f'<g transform="scale({-s if flip else s:.2f} {s:.2f})">{hen(f"h{i}", p)}</g>'
        out.append(f'<g transform="translate({x} {y})">'
                   f'<g class="stroll" style="animation-delay:{-delay * 3}s">'
                   f'<g class="h {anim}" style="animation-delay:{delay}s">{g}</g></g></g>')
    return svg("".join(out), style=HEN_ANIM)


def hens_night():
    """Silhouettes perched in the windows, and sleepy z's."""
    sil = ""
    for wx in (272, 306):
        for dx in (7, 19):
            sil += (f'<g transform="translate({wx + dx} {120 + DY}) scale(0.32)">'
                    '<ellipse cx="2" cy="-12" rx="13" ry="10" fill="#0d1210" fill-opacity="0.75"/>'
                    '<circle cx="-9" cy="-24" r="6" fill="#0d1210" fill-opacity="0.75"/></g>')
    zs = "".join(f'<text class="z" x="{x}" y="{96 + DY}" style="animation-delay:{d}s">z</text>'
                 for x, d in [(330, 0), (336, 1.5), (342, 3)])
    return svg(sil + zs, style=HEN_ANIM)


GLOW_COLORS = {"warm": "#ffb45a", "white": "#fff1d6", "red": "#ff5a4d", "orange": "#ff8c3a",
               "yellow": "#ffd84a", "green": "#6fe08a", "cyan": "#5fe3e8", "blue": "#5f8cff",
               "purple": "#a56bff", "pink": "#ff6fc2"}
GLOW_LEVELS = {1: 0.38, 2: 0.65, 3: 0.95}


def glow(color, level):
    o = GLOW_LEVELS[level]
    windows = "".join(
        f'<rect x="{x + 1.5}" y="{101.5 + DY}" width="23" height="17" rx="1.5" fill="{color}" '
        f'fill-opacity="{0.55 + 0.45 * o:.2f}"/>'
        f'<rect x="{x + 3}" y="{103 + DY}" width="20" height="5" rx="1" fill="#fff" fill-opacity="{0.35 * o:.2f}"/>'
        for x in (272, 306))
    return svg(f'<defs><radialGradient id="g"><stop offset="0" stop-color="{color}" stop-opacity="{0.55 * o:.2f}"/>'
               f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>'
               f'<radialGradient id="spill"><stop offset="0" stop-color="{color}" stop-opacity="{0.35 * o:.2f}"/>'
               f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient></defs>'
               f'<ellipse cx="305" cy="{110 + DY}" rx="70" ry="44" fill="url(#g)"/>'
               f'<ellipse cx="310" cy="{205 + DY}" rx="80" ry="12" fill="url(#spill)"/>' + windows)


PRECIP_ANIM = """
.fall{animation:fall 0.9s linear infinite}
@keyframes fall{from{transform:translateY(-40px)}to{transform:translateY(0)}}
.snow{animation:snow 7s linear infinite}
@keyframes snow{from{transform:translateY(-60px)}to{transform:translateY(0)}}
.sway{animation:sway 3s ease-in-out infinite alternate}
@keyframes sway{from{transform:translateX(-4px)}to{transform:translateX(4px)}}
"""


def precipitation(kind):
    rng = random.Random(3)
    if "Rain" in kind or kind == "Night rain":
        lines = "".join(
            f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x - 3:.0f}" y2="{y + 9:.0f}"/>'
            for x in range(6, W, 13) for y in [rng.uniform(0, 40) + k * 40 for k in range(7)])
        return svg(f'<g class="fall" stroke="#9cc4ff" stroke-opacity="0.75" stroke-width="1.4" '
                   f'stroke-linecap="round">{lines}</g>', style=PRECIP_ANIM)
    if "now" in kind:
        dots = "".join(f'<circle cx="{x + rng.uniform(-4, 4):.0f}" cy="{y:.0f}" r="{rng.uniform(1.2, 2.4):.1f}"/>'
                       for x in range(8, W, 18) for y in [rng.uniform(0, 60) + k * 60 for k in range(5)])
        return svg(f'<g class="sway"><g class="snow" fill="#fff" fill-opacity="0.9">{dots}</g></g>',
                   style=PRECIP_ANIM)
    return svg("")


# ---------------------------------------------------------------------------
# Chicken comfort card
# ---------------------------------------------------------------------------

CW, CH = 400, 160
MASCOT = dict(body="#e2a957", hackle="#d99a45", tail="#b97a2c", wing="#d29b4c")
LEVELS = ["Very cold", "Chilly", "Comfy", "Warm", "Hot", "Heat danger"]

MASCOT_ANIM = """
.m{transform-box:fill-box;transform-origin:50% 100%}
.bob{animation:bob 3s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
.shiver{animation:shiver .16s linear infinite alternate}
@keyframes shiver{from{transform:translateX(-1.2px)}to{transform:translateX(1.2px)}}
.pant{animation:pant .5s ease-in-out infinite alternate}
@keyframes pant{from{transform:scale(1)}to{transform:scale(1.03,0.98)}}
.drop{animation:drop 2.4s ease-in infinite}
@keyframes drop{0%{transform:translateY(0);opacity:0}15%{opacity:1}100%{transform:translateY(18px);opacity:0}}
.flake{animation:flake 4s linear infinite}
@keyframes flake{from{transform:translateY(-10px);opacity:0}20%{opacity:1}to{transform:translateY(60px);opacity:0}}
.pulse{animation:pulse 1.6s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.25}50%{opacity:.7}}
.heart{animation:heart 3.5s ease-out infinite}
@keyframes heart{0%{transform:translateY(0);opacity:0}20%{opacity:1}100%{transform:translateY(-22px);opacity:0}}
"""


def mascot(level):
    s = 2.3
    cx, cy = 72, 136                 # feet
    mood = {"Very cold": "cold", "Chilly": "cold", "Comfy": "happy", "Warm": "calm",
            "Hot": "panting", "Heat danger": "panting"}[level]
    puffed = {"Very cold": 1.22, "Chilly": 1.12}.get(level, 1.0)
    body = hen("m", MASCOT, mood=mood, puffed=puffed)
    extras_back, extras_front = "", ""
    if level in ("Very cold", "Chilly"):
        # a striped scarf around the neck
        extras_front += ('<g transform="translate(-8 -19)"><path d="M-8 0 Q0 4 8 0 L8 4 Q0 8 -8 4 Z" fill="#e2534a"/>'
                         '<path d="M3 3 L6 13 L1 13 Z" fill="#e2534a"/>'
                         '<path d="M-5 1 L-5 5 M0 2 L0 6 M5 1 L5 5" stroke="#fff" stroke-width="1.2"/></g>')
    if level == "Very cold":
        extras_front += ('<path d="M-15 -36 Q-10 -46 -4 -36 Z" fill="#5f8cff"/>'
                         '<circle cx="-9.5" cy="-45" r="2.4" fill="#fff"/>')
    if level in ("Hot", "Heat danger", "Warm"):
        drops = [(-3, -33)] if level == "Warm" else [(-3, -33), (-17, -20)]
        for i, (dx, dy) in enumerate(drops):
            extras_front += (f'<path class="drop" style="animation-delay:{i * 1.1}s" '
                             f'transform="translate({dx} {dy})" d="M0 -3 C1.5 -1 2.4 0.3 2.4 1.4 '
                             f'A2.4 2.4 0 0 1 -2.4 1.4 C-2.4 0.3 -1.5 -1 0 -3 Z" fill="#7cc4ff"/>')
    if level in ("Hot", "Heat danger"):
        extras_front += '<ellipse cx="-12.5" cy="-25" rx="2.2" ry="1.4" fill="#ff7b6b" opacity="0.7"/>'
    anim = {"Very cold": "shiver", "Chilly": "shiver", "Hot": "pant", "Heat danger": "pant"}.get(level, "bob")
    if level == "Chilly":
        anim = "bob"
    scene = ""
    if level == "Heat danger":
        scene += (f'<circle class="pulse" cx="{cx}" cy="{cy - 42}" r="58" fill="#ff5a4d"/>')
    if level == "Very cold":
        rng = random.Random(5)
        scene += "".join(f'<circle class="flake" style="animation-delay:{rng.uniform(0, 4):.1f}s" '
                         f'cx="{rng.uniform(14, 130):.0f}" cy="{rng.uniform(10, 40):.0f}" r="2" fill="#dbe9ff"/>'
                         for _ in range(10))
    if level == "Comfy":
        heart = "M0 2 C-4 -2 -4 -6 0 -4 C4 -6 4 -2 0 2 Z"
        scene += "".join(f'<path class="heart" style="animation-delay:{d}s" transform="translate({x} {y})" '
                         f'd="{heart}" fill="#ff7aa8"/>' for x, y, d in [(40, 60, 0), (104, 52, 1.7)])
    shadow = f'<ellipse cx="{cx}" cy="{cy + 2}" rx="34" ry="5" fill="#000" fill-opacity="0.22"/>'
    hen_g = (f'<g transform="translate({cx} {cy})"><g class="m {anim}"><g transform="scale({s})">'
             f'{extras_back}{body}{extras_front}</g></g></g>')
    return svg(scene + shadow + hen_g, CW, CH, style=MASCOT_ANIM)


METER = (150, 126, 236, 8)        # x, y, width, height


def comfort_base():
    x, y, w, h = METER
    return svg(f'<defs><linearGradient id="m" x1="0" x2="1">'
               '<stop offset="0" stop-color="#9cc8ff"/><stop offset="0.10" stop-color="#6aa9ff"/>'
               '<stop offset="0.32" stop-color="#6fdc8c"/><stop offset="0.75" stop-color="#6fdc8c"/>'
               '<stop offset="0.85" stop-color="#ffb347"/><stop offset="1" stop-color="#ff6b5e"/>'
               f'</linearGradient></defs>'
               f'<text x="{x}" y="24" font-family="Roboto, sans-serif" font-size="11" font-weight="600" '
               f'letter-spacing="0.08em" fill="{weather.LABEL}">CHICKEN COMFORT</text>'
               f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="url(#m)"/>'
               f'<g font-family="Roboto, sans-serif" font-size="10" fill="{weather.LABEL}">'
               f'<text x="{x}" y="{y + h + 14}">0°F</text>'
               f'<text x="{x + w * 0.32:.0f}" y="{y + h + 14}" text-anchor="middle">32°</text>'
               f'<text x="{x + w * 0.75:.0f}" y="{y + h + 14}" text-anchor="middle">75°</text>'
               f'<text x="{x + w}" y="{y + h + 14}" text-anchor="end">100°F</text></g>', CW, CH)


def meter_marker(step):
    x, y, w, h = METER
    mx = x + w * step / 20
    return svg(f'<circle cx="{mx:.1f}" cy="{y + h / 2}" r="7" fill="#fff" stroke="#1b2235" '
               f'stroke-opacity="0.35" stroke-width="2"/>', CW, CH)


def comfort_card():
    secondary = {"color": "var(--secondary-text-color)", "white-space": "nowrap",
                 "transform": "translate(0, -50%)"}
    full = {"left": "50%", "top": "50%", "width": "100%"}
    at = lambda x, y: {"left": f"{x / CW * 100:.1f}%", "top": f"{y / CH * 100:.1f}%"}
    return {
        "type": "picture-elements",
        "image": data_uri(comfort_base()),
        "elements": [
            {"type": "image", "entity": "sensor.chicken_comfort", "image": data_uri(mascot("Comfy")),
             "state_image": {lv: data_uri(mascot(lv)) for lv in LEVELS},
             "tap_action": {"action": "more-info"}, "style": full},
            {"type": "image", "entity": "sensor.chicken_comfort_meter", "image": data_uri(svg("", CW, CH)),
             "state_image": {str(i): data_uri(meter_marker(i)) for i in range(21)},
             "tap_action": {"action": "none"}, "style": full},
            {"type": "state-label", "entity": "sensor.chicken_comfort",
             "style": {**at(150, 52), **secondary, "color": "var(--primary-text-color)",
                       "font-size": "26px", "font-weight": "700"}},
            {"type": "state-label", "entity": "sensor.chicken_comfort", "attribute": "note",
             "style": {**at(150, 82), **secondary, "color": "var(--primary-text-color)",
                       "font-size": "13px"}},
            {"type": "state-label", "entity": "sensor.chicken_comfort", "attribute": "detail",
             "style": {**at(150, 104), **secondary, "font-size": "12px"}},
        ],
    }


def scene_card():
    full = {"left": "50%", "top": "50%", "width": "100%"}
    skies = {k: data_uri(sky(k)) for k in SKY_COLORS}
    precip = {k: data_uri(precipitation(k)) for k in SKY_COLORS}
    glows = {"off": data_uri(svg(""))}
    glows.update({f"{c}-{lv}": data_uri(glow(col, lv)) for c, col in GLOW_COLORS.items() for lv in GLOW_LEVELS})
    return {
        "type": "picture-elements",
        "image": data_uri(svg("")),
        "elements": [
            {"type": "image", "entity": "sensor.coop_sky", "image": skies["Partly cloudy"],
             "state_image": skies, "tap_action": {"action": "none"}, "style": full},
            {"type": "image", "image": data_uri(coop_and_run()), "tap_action": {"action": "none"},
             "style": full},
            {"type": "image", "entity": "sensor.coop_glow", "image": glows["off"], "state_image": glows,
             "tap_action": {"action": "none"}, "style": full},
            {"type": "image", "entity": "sun.sun", "image": data_uri(hens_day()),
             "state_image": {"above_horizon": data_uri(hens_day()),
                             "below_horizon": data_uri(hens_night())},
             "tap_action": {"action": "none"}, "style": full},
            {"type": "image", "image": data_uri(run_front()), "tap_action": {"action": "none"},
             "style": full},
            {"type": "image", "entity": "sensor.coop_sky", "image": data_uri(svg("")),
             "state_image": precip, "tap_action": {"action": "none"}, "style": full},
        ],
    }


def coop_graphs():
    base = {"type": "custom:mini-graph-card", "hours_to_show": 24, "points_per_hour": 2,
            "hour24": False, "height": 64, "line_width": 3, "smoothing": True, "animate": False,
            "font_size": 70, "font_size_header": 12,
            "show": {"icon": True, "name": True, "state": True, "legend": False, "labels": False,
                     "points": False, "fill": "fade"}}
    return [
        {**base, "name": "In the coop", "icon": "mdi:thermometer",
         # The coop line shades with temperature; outside is a faint reference.
         "entities": [{"entity": "sensor.coop_temperature"},
                      {"entity": "sensor.station_temperature", "color": "#a5adc6",
                       "show_fill": False, "show_state": False}],
         "color_thresholds": [{"value": 20, "color": "#b7d7ff"}, {"value": 35, "color": "#6aa9ff"},
                              {"value": 55, "color": "#6fdc8c"}, {"value": 75, "color": "#ffb347"},
                              {"value": 90, "color": "#ff6b5e"}],
         "color_thresholds_transition": "smooth"},
        {**base, "name": "Coop humidity", "icon": "mdi:water-percent",
         "entities": [{"entity": "sensor.coop_humidity", "color": "#46d0c0"}],
         "lower_bound": 0, "upper_bound": 100},
    ]


def controls():
    """Lights, switches, the door and locks in the Chicken Coop area."""
    toggle = {"type": "tile", "tap_action": {"action": "toggle"}, "hold_action": {"action": "more-info"}}
    return {
        "type": "custom:auto-entities", "show_empty": False,
        "card": {"type": "grid", "columns": 2, "square": False}, "card_param": "cards",
        "filter": {
            "include": [
                {"area": "chicken_coop", "domain": "cover",
                 "options": {"type": "tile", "features": [{"type": "cover-open-close"}]}},
                {"area": "chicken_coop", "domain": "lock",
                 "options": {"type": "tile", "features": [{"type": "lock-commands"}]}},
                {"area": "chicken_coop", "domain": "light", "options": toggle},
                {"area": "chicken_coop", "domain": "switch", "options": toggle},
            ],
            "exclude": [{"entity_id": "*chicken_cam_*"}, {"entity_id": "*chicken_run_*"},
                        {"integration": "unifi"}],
        },
        "sort": {"method": "name"},
    }


def section():
    return {
        "type": "grid",
        "cards": [
            {**scene_card(), "grid_options": {"columns": "full"}},
            {**comfort_card(), "grid_options": {"columns": "full"}},
            {**controls(), "grid_options": {"columns": "full"}},
            {"type": "grid", "columns": 2, "square": False, "grid_options": {"columns": "full"},
             "cards": coop_graphs()},
        ],
    }


# ---------------------------------------------------------------------------
# Helper sensors
# ---------------------------------------------------------------------------

def area_reading(device_class):
    """Jinja: numeric states of Chicken Coop sensors of a device class
    (cameras excluded)."""
    return ("area_entities('chicken_coop') | select('match', 'sensor\\\\.') "
            "| reject('search', 'chicken_(cam|run)') "
            f"| select('is_state_attr', 'device_class', '{device_class}') "
            "| map('states') | select('is_number') | list")


# Shared by the comfort sensors: picks the reading (outside by day, inside
# the coop at night) and works out how it feels to a hen.
COMFORT_COMMON = (
    "{%- set day = is_state('sun.sun', 'above_horizon') %}"
    "{%- set inside = not day and states('sensor.coop_temperature') | is_number %}"
    "{%- if inside %}"
    "{%- set t = states('sensor.coop_temperature') | float %}"
    "{%- set rh = states('sensor.coop_humidity') | float(50) %}"
    "{%- set where = 'In the coop' %}"
    # Heat index (NWS Rothfusz) when it's hot; otherwise the air temperature.
    "{%- if t >= 80 %}{%- set e = -42.379 + 2.04901523*t + 10.14333127*rh - 0.22475541*t*rh"
    " - 0.00683783*t*t - 0.05481717*rh*rh + 0.00122874*t*t*rh + 0.00085282*t*rh*rh"
    " - 0.00000199*t*t*rh*rh %}{%- else %}{%- set e = t %}{%- endif %}"
    "{%- else %}"
    "{%- set t = states('sensor.station_temperature') | float(0) %}"
    "{%- set rh = states('sensor.station_humidity') | float(50) %}"
    "{%- set where = 'Outside' %}"
    # The station's feels-like already includes wind chill and heat index.
    "{%- set e = states('sensor.station_feels_like') | float(t) %}"
    "{%- endif %}"
    "{%- set level = 'Very cold' if e < 10 else 'Chilly' if e < 32 else 'Comfy' if e <= 75"
    " else 'Warm' if e <= 85 else 'Hot' if e <= 95 else 'Heat danger' %}"
)

NOTES = {
    "Very cold": "Check the water isn't frozen",
    "Chilly": "Fluffed up and fine",
    "Warm": "Shade and fresh water",
    "Hot": "Cool water, shade, airflow",
    "Heat danger": "Heat stress: cool them down now",
}


def templates():
    availability = ("{{ states('sensor.station_temperature') | is_number "
                    "or states('sensor.coop_temperature') | is_number }}")
    note = (f"{{%- set notes = {NOTES} %}}"
            "{%- if rh >= 80 and t < 40 %}Damp: check ventilation"
            "{%- elif level == 'Comfy' %}{{ 'Happy hens' if day else 'Snug in the coop' }}"
            "{%- else %}{{ notes[level] }}{%- endif %}")
    return {"sensor": [
        {"name": "Coop Temperature", "unique_id": "coop_temperature", "icon": "mdi:thermometer",
         "unit_of_measurement": "°F", "device_class": "temperature", "state_class": "measurement",
         "availability": f"{{{{ ({area_reading('temperature')}) | count > 0 }}}}",
         "state": f"{{{{ ({area_reading('temperature')}) | first }}}}"},
        {"name": "Coop Humidity", "unique_id": "coop_humidity", "icon": "mdi:water-percent",
         "unit_of_measurement": "%", "device_class": "humidity", "state_class": "measurement",
         "availability": f"{{{{ ({area_reading('humidity')}) | count > 0 }}}}",
         "state": f"{{{{ ({area_reading('humidity')}) | first }}}}"},
        {"name": "Chicken Comfort", "unique_id": "chicken_comfort", "icon": "mdi:egg",
         "availability": availability,
         "state": COMFORT_COMMON + "{{ level }}",
         "attributes": {
             "note": COMFORT_COMMON + note,
             "detail": COMFORT_COMMON + ("{{ where }} · {{ 'feels ' if not inside }}{{ e | round(0) | int }}°F"
                                         " · {{ rh | round(0) | int }}%"),
             "source": COMFORT_COMMON + "{{ where }}",
             "effective_temperature": COMFORT_COMMON + "{{ e | round(1) }}",
         }},
        {"name": "Chicken Comfort Meter", "unique_id": "chicken_comfort_meter", "icon": "mdi:gauge",
         "availability": availability,
         "state": COMFORT_COMMON + "{{ [[(e / 5) | round(0) | int, 0] | max, 20] | min }}"},
        {"name": "Coop Glow", "unique_id": "coop_glow", "icon": "mdi:lightbulb",
         "state": (
             "{%- set ls = area_entities('chicken_coop') | select('match', 'light\\\\.') | list %}"
             "{%- set l = ls | first if ls else none %}"
             "{%- if not l or not is_state(l, 'on') %}off{%- else %}"
             "{%- set b = state_attr(l, 'brightness') | int(255) %}"
             "{%- set lv = 1 if b < 90 else 2 if b < 170 else 3 %}"
             "{%- set hs = state_attr(l, 'hs_color') %}"
             "{%- if hs and hs[1] > 25 %}{%- set h = hs[0] %}"
             "{%- set hue = 'red' if h < 15 or h >= 345 else 'orange' if h < 40 else 'yellow' if h < 70"
             " else 'green' if h < 160 else 'cyan' if h < 200 else 'blue' if h < 255"
             " else 'purple' if h < 290 else 'pink' %}"
             "{%- else %}{%- set hue = 'warm' if state_attr(l, 'color_temp_kelvin') | int(2700) < 3800"
             " else 'white' %}{%- endif %}"
             "{{ hue }}-{{ lv }}{%- endif %}")},
        {"name": "Coop Sky", "unique_id": "coop_sky", "icon": "mdi:weather-partly-cloudy",
         "state": (
             "{%- set sky = states('sensor.station_sky') %}"
             "{%- if is_state('sun.sun', 'below_horizon') %}"
             "{{ 'Night rain' if sky == 'Rain' else 'Night snow' if sky == 'Snow' else 'Night' }}"
             "{%- else %}"
             "{{ sky if sky in ['Sunny', 'Partly cloudy', 'Cloudy', 'Rain', 'Snow'] else 'Partly cloudy' }}"
             "{%- endif %}")},
    ]}


def write(path, header, data):
    text = yaml.dump(data, Dumper=yaml.SafeDumper, sort_keys=False, width=10_000, allow_unicode=True)
    (ROOT / path).write_text(header + text)


def main():
    header = ("# GENERATED by tools/coop.py: edit it and re-run, don't edit this\n"
              "# file by hand.\n")
    write("dashboard/coop_side_section.yaml", header, section())
    write("templates/coop.yaml", header, templates())
    print("wrote dashboard/coop_side_section.yaml and templates/coop.yaml")


if __name__ == "__main__":
    main()
