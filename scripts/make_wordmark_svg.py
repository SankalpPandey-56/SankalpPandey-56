#!/usr/bin/env python3
"""make_wordmark_svg.py — render an EXTRUDED 3D ASCII wordmark as an SVG.

Technique by AVIVASHISHTA29 (github.com/AVIVASHISHTA29): rasterize the text
to a mask, extrude it along +z into a surface shell (front/back caps + side
walls), rotate + perspective-project each frame, Lambert-shade into a density
ramp, and z-buffer splat into a character grid. The SVG is a pre-rendered
SMIL flipbook: each frame is a hidden <g> cycled by a discrete opacity
animation, so it animates inside a GitHub <img> with no JavaScript.

Runs with ZERO dependencies: it falls back to an embedded 5x7 bitmap font and
pure-Python 3D math. If numpy + Pillow are installed it renders the word with
a bold TTF (Futura by default) instead, which looks crisper.

Modes: rock (oscillates forever — the README default), once (one full turn
then freeze), spin (continuous turntable), static (frozen frame 0).

Env overrides: WORDMARK_TEXT, WORDMARK_FONT, WORDMARK_FONT_INDEX, WORDMARK_TILT,
WORDMARK_COLS, WORDMARK_ROW_MARGIN.

Usage:  python scripts/make_wordmark_svg.py --mode rock --out wordmark.svg
"""
import argparse
import html
import math
import os
import sys
from pathlib import Path

from config import PROMPT

# ---- geometry / grid -------------------------------------------------------
COLS = int(os.environ.get("WORDMARK_COLS", 50))
ROWS = 0  # derived from the art — see fit()
ROW_MARGIN = int(os.environ.get("WORDMARK_ROW_MARGIN", 5))
CELL_W, CELL_H = 9.0, 15.5
TEXT = os.environ.get("WORDMARK_TEXT", "SKP")  # initials look best at 50 cols
MASK_H = 300        # TTF raster height in mask px (drives voxel density)
TRACKING = 0.14     # extra letter-spacing in em (keeps counters open)
LINE_GAP = 1.20
DEPTH_FRAC = 0.34   # extrusion depth as a fraction of glyph height
TILT_DEG = float(os.environ.get("WORDMARK_TILT", 4.0))
CAM_DIST, FOCAL, FIT = 6.0, 4.15, 0.92
RAMP = " .`:-=+*csS#%@"  # sparse/dim -> dense/bright; index 0 is blank
LIGHT = (-0.15, -0.45, -1.00)
LIGHT_LEN = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / LIGHT_LEN for c in LIGHT)
AMBIENT, FOG, FOG_SPAN = 0.22, 0.34, 0.55

# ---- chrome (matches the rest of the profile) ------------------------------
BG, BG2 = "#0d1117", "#111722"
FRAME = "#30363d"
INK = "#c9d1d9"
MUTED = "#7d8590"
PAD, TITLEBAR_H = 18, 28

# ---- optional TTF fonts (used when numpy + Pillow are importable) ----------
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/System/Library/Fonts/Futura.ttc",
    "/Library/Fonts/Futura.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]
FONT_INDEX = int(os.environ.get("WORDMARK_FONT_INDEX", 2))  # Futura Bold face

# ---- embedded 5x7 bitmap font (fallback) -----------------------------------
_B = "#"
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "?": ("#####", "#####", "#####", "#####", "#####", "#####", "#####"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


# ---- mask generation --------------------------------------------------------
def bitmap_mask(text, scale=6):
    """Rasterize TEXT with the embedded font, upscaled, as a 2D int mask."""
    lines_out = []
    for line in text.split("\n"):
        glyphs = [FONT.get(ch.upper(), FONT["?"]) for ch in line]
        gw, gh = 5 * scale, 7 * scale
        w = len(glyphs) * gw + (len(glyphs) - 1) * 2 * scale
        mask = [[0] * w for _ in range(gh)]
        x = 0
        for g in glyphs:
            for gy, grow in enumerate(g):
                for gx, ch in enumerate(grow):
                    if ch == "1":
                        for dy in range(scale):
                            for dx in range(scale):
                                mask[gy * scale + dy][x + gx * scale + dx] = 1
            x += gw + 2 * scale
        lines_out.append(mask)
    if len(lines_out) == 1:
        return lines_out[0]
    max_w = max(len(m[0]) for m in lines_out)
    gap = [0] * max_w
    lines_out = [m + [[0] * (max_w - len(m[0])) for _ in m] for m in lines_out]
    return [row for m in lines_out for row in m + [gap] * scale][:-scale]


def ttf_mask(text):
    """Rasterize TEXT with a bold TTF (numpy/Pillow required)."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    if font_path is None:
        sys.exit("No candidate TTF font found; install one or drop numpy/Pillow "
                 "to use the built-in bitmap font.")
    index = FONT_INDEX if font_path.endswith(".ttc") else 0
    font_size = MASK_H
    for _ in range(40):
        font = ImageFont.truetype(font_path, font_size, index=index)
        l, t, r, b = font.getbbox(text.replace("\n", ""))
        if b - t <= MASK_H:
            break
        font_size = int(font_size * 0.92)
    h = b - t
    track = int(round(TRACKING * font_size))
    lines = text.split("\n")
    line_h = int(round(h * LINE_GAP))

    def line_w(s):
        return sum(font.getlength(c) for c in s) + track * (len(s) - 1)

    total_w = int(round(max(line_w(s) for s in lines))) + 8
    total_h = line_h * (len(lines) - 1) + h + 8
    img = Image.new("L", (total_w, total_h), 0)
    d = ImageDraw.Draw(img)
    for li, s in enumerate(lines):
        pen = 4.0 + (total_w - 8 - line_w(s)) / 2.0
        base = -t + 4 + li * line_h
        for ch in s:
            d.text((pen, base), ch, font=font, fill=255)
            pen += font.getlength(ch) + track
    w, hh = img.size
    return [[1 if img.getpixel((x, y)) > 127 else 0 for x in range(w)]
            for y in range(hh)]


def build_mask(text):
    try:
        import numpy  # noqa: F401
        import PIL  # noqa: F401
        return ttf_mask(text)
    except ImportError:
        return bitmap_mask(text)


# ---- surface shell (points + normals, pure Python) -------------------------
def build_shell(mask):
    H, W = len(mask), len(mask[0])
    depth = max(4, int(round(H * DEPTH_FRAC)))
    filled = [(x, y) for y in range(H) for x in range(W) if mask[y][x]]

    pts, nrm = [], []
    # front cap sits a hair proud of z=0 so it wins z-buffer ties vs the walls
    pts += [(x, y, -0.6) for x, y in filled]
    nrm += [(0.0, 0.0, -1.0)] * len(filled)
    pts += [(x, y, float(depth)) for x, y in filled]
    nrm += [(0.0, 0.0, 1.0)] * len(filled)
    # side walls: boundary pixels extruded through the depth
    boundary = []
    for y in range(H):
        for x in range(W):
            if not mask[y][x]:
                continue
            nx = (1 if (x + 1 >= W or not mask[y][x + 1]) else 0) \
                 - (1 if (x - 1 < 0 or not mask[y][x - 1]) else 0)
            ny = (1 if (y + 1 >= H or not mask[y + 1][x]) else 0) \
                 - (1 if (y - 1 < 0 or not mask[y - 1][x]) else 0)
            if nx or ny:
                ln = math.sqrt(nx * nx + ny * ny)
                boundary.append((x, y, nx / ln, ny / ln))
    nz = max(3, depth // 2)
    for z in (i * depth / (nz - 1) for i in range(nz)):
        for x, y, nx, ny in boundary:
            pts.append((x, y, z))
            nrm.append((nx, ny, 0.0))
    # center on the origin, normalize so the wordmark is 1.0 unit wide
    cx, cy, cz = W / 2.0, H / 2.0, depth / 2.0
    pts = [(x - cx, y - cy, z - cz) for x, y, z in pts]
    return [(x / W, y / W, z / W) for x, y, z in pts], nrm


# ---- projection ------------------------------------------------------------
def _mat3(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def project(P, N, yaw):
    M = _mat3(rot_x(math.radians(TILT_DEG)), rot_y(yaw))
    xs, ys, zs, idxs = [], [], [], []
    for (px, py, pz), (nx, ny, nz) in zip(P, N):
        x = M[0][0] * px + M[0][1] * py + M[0][2] * pz
        y = M[1][0] * px + M[1][1] * py + M[1][2] * pz
        z = M[2][0] * px + M[2][1] * py + M[2][2] * pz
        rnx = M[0][0] * nx + M[0][1] * ny + M[0][2] * nz
        rny = M[1][0] * nx + M[1][1] * ny + M[1][2] * nz
        rnz = M[2][0] * nx + M[2][1] * ny + M[2][2] * nz
        if rnz >= 0.0:  # back-face cull: camera sits at -z
            continue
        zz = z + CAM_DIST
        f = FOCAL / zz
        lam = rnx * LIGHT[0] + rny * LIGHT[1] + rnz * LIGHT[2]
        inten = AMBIENT + (1 - AMBIENT) * max(0.0, min(1.0, lam))
        t = max(-1.0, min(1.0, (zz - CAM_DIST) / FOG_SPAN))
        inten *= 1.0 - FOG * (t + 1.0) / 2.0
        idx = int(round(inten * (len(RAMP) - 1)))
        idx = max(1, min(len(RAMP) - 1, idx))
        xs.append(x * f)
        ys.append(y * f)
        zs.append(zz)
        idxs.append(idx)
    return xs, ys, zs, idxs


def fit(projs):
    global ROWS
    xs = [x for p in projs for x in p[0]]
    ys = [y for p in projs for y in p[1]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 - x0 < 1e-6:
        raise SystemExit("wordmark has no width — check WORDMARK_TEXT / font")
    ar = CELL_W / CELL_H
    scale = FIT * (COLS - 1) / (x1 - x0)
    ROWS = int(math.ceil((y1 - y0) * ar * scale)) + 1 + 2 * ROW_MARGIN
    cx = (COLS - 1) / 2.0 - (x0 + x1) / 2.0 * scale
    cy = (ROWS - 1) / 2.0 - (y0 + y1) / 2.0 * scale * ar
    return scale, cx, cy


def rasterize(proj, scale, cx, cy):
    xs, ys, zs, idxs = proj
    cells = []
    for x, y, z, i in zip(xs, ys, zs, idxs):
        col = int(round(cx + x * scale))
        row = int(round(cy + y * scale * (CELL_W / CELL_H)))
        if 0 <= col < COLS and 0 <= row < ROWS:
            cells.append((row, col, z, i))
    cells.sort(key=lambda c: -c[2])  # far -> near, nearest wins
    grid = [[0] * COLS for _ in range(ROWS)]
    for row, col, _z, i in cells:
        grid[row][col] = i
    return ["".join(RAMP[i] for i in r) for r in grid]


# ---- SVG emission ----------------------------------------------------------
def emit(frames, mode, out, dur, reveal):
    art_w, art_h = COLS * CELL_W, ROWS * CELL_H
    canvas_w, canvas_h = art_w + PAD * 2, TITLEBAR_H + art_h + PAD
    art_top = TITLEBAR_H + PAD * 0.3
    fs = CELL_H * 0.92
    n = len(frames)
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" height="{canvas_h:.0f}" '
        f'viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<defs><linearGradient id="wbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
        '</linearGradient></defs>',
        f'<rect width="{canvas_w:.0f}" height="{canvas_h:.0f}" rx="12" fill="url(#wbg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w - 1:.0f}" height="{canvas_h - 1:.0f}" rx="12" '
        f'fill="none" stroke="{FRAME}" stroke-width="1"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w:.0f}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dot in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        p.append(f'<circle cx="{PAD + i * 15}" cy="{TITLEBAR_H / 2}" r="4.5" fill="{dot}"/>')
    p.append(f'<text x="{canvas_w / 2:.0f}" y="{TITLEBAR_H / 2 + 4:.0f}" fill="{MUTED}" '
             f'font-size="11.5" text-anchor="middle">{PROMPT}: ~$ ./wordmark.sh --3d</text>')

    def frame_g(rows, extra=""):
        out_rows = []
        for ry, line in enumerate(rows):
            s = line.rstrip()
            if not s.strip():
                continue
            lead = len(s) - len(s.lstrip(" "))
            body = s[lead:]
            x = PAD + lead * CELL_W
            y = art_top + ry * CELL_H + CELL_H * 0.78
            out_rows.append(
                f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-size="{fs:.1f}" '
                f'textLength="{len(body) * CELL_W:.1f}" lengthAdjust="spacing">'
                f'{html.escape(body)}</text>')
        return f'<g fill="{INK}"{extra}>' + "".join(out_rows) + "</g>"

    if mode == "static":
        p.append(frame_g(frames[0]))
        p.append("</svg>")
        out.write_text("".join(p))
        print("wrote", out)
        return

    # intro (all modes): resting pose wipes in left -> right behind a soft bar
    p.append(f'<clipPath id="wipe"><rect x="{PAD}" y="{art_top:.1f}" height="{art_h:.1f}" width="0">'
             f'<animate attributeName="width" from="0" to="{art_w:.0f}" begin="0s" '
             f'dur="{reveal:.2f}s" fill="freeze"/></rect></clipPath>')
    p.append(f'<g clip-path="url(#wipe)">{frame_g(frames[0])}'
             f'<set attributeName="opacity" to="0" begin="{reveal:.2f}s"/></g>')
    p.append(f'<rect x="{PAD}" y="{art_top + 2:.1f}" width="{CELL_W * 1.6:.1f}" '
             f'height="{art_h - 4:.1f}" fill="{INK}" opacity="0.16">'
             f'<animate attributeName="x" from="{PAD}" to="{PAD + art_w:.0f}" begin="0s" '
             f'dur="{reveal:.2f}s" fill="freeze"/>'
             f'<set attributeName="opacity" to="0" begin="{reveal:.2f}s"/></rect>')
    if mode == "once":
        step = dur / n
        for i, rows in enumerate(frames):
            begin = reveal + i * step
            sets = f'<set attributeName="opacity" to="1" begin="{begin:.3f}s"/>'
            if i != n - 1:
                sets += f'<set attributeName="opacity" to="0" begin="{begin + step:.3f}s"/>'
            p.append(frame_g(rows, ' opacity="0"').replace("</g>", sets + "</g>"))
    else:
        # cycle the flipbook forever; each frame owns one dur/n slice of the loop
        for i, rows in enumerate(frames):
            if i == 0:
                vals, kt = "1;0", f"0;{1 / n:.5f}"
            else:
                vals, kt = "0;1;0", f"0;{i / n:.5f};{(i + 1) / n:.5f}"
            anim = (f'<animate attributeName="opacity" calcMode="discrete" values="{vals}" '
                    f'keyTimes="{kt}" dur="{dur:.2f}s" begin="{reveal:.2f}s" '
                    f'repeatCount="indefinite"/>')
            p.append(frame_g(rows, ' opacity="0"').replace("</g>", anim + "</g>"))
    p.append("</svg>")
    svg = "".join(p)
    out.write_text(svg)
    print(f"wrote {out} {len(svg) / 1024:.1f} KB {n} frames {canvas_w:.0f}x{canvas_h:.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["spin", "once", "rock", "static"], default="rock")
    ap.add_argument("--out", default=None)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--dur", type=float, default=None)
    ap.add_argument("--reveal", type=float, default=1.6)
    ap.add_argument("--preview", action="store_true", help="print frames to stdout")
    a = ap.parse_args()

    mask = build_mask(TEXT)
    P, N = build_shell(mask)
    rest = math.radians(-13)  # the 3/4 pose the wordmark rests in
    if a.mode == "spin":
        nf = a.frames or 36
        yaws = [rest + 2 * math.pi * i / nf for i in range(nf)]
        dur = a.dur or 7.0
    elif a.mode == "once":
        nf = a.frames or 32
        yaws = [rest + 2 * math.pi * i / nf for i in range(nf)] + [rest]
        dur = a.dur or 3.6
    else:  # rock: ping-pong, cosine-eased
        nf = a.frames or 20
        amp = math.radians(11)
        yaws = [rest + amp * math.sin(2 * math.pi * i / nf) for i in range(nf)]
        dur = a.dur or 5.0

    projs = [project(P, N, y) for y in yaws]
    scale, cx, cy = fit(projs)
    frames = [rasterize(q, scale, cx, cy) for q in projs]
    if a.preview:
        for row in frames[0]:
            print(row.rstrip())
        return
    out = (Path(a.out) if a.out else
           Path(__file__).resolve().parent.parent / "wordmark.svg")
    emit(frames, a.mode, out, dur, a.reveal)


if __name__ == "__main__":
    main()
