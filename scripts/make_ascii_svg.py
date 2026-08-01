#!/usr/bin/env python3
"""make_ascii_svg.py — portrait photo -> terminal-window ASCII SVG.

Mirrors AVIVASHISHTA29's portrait pipeline: a clean, monochrome ASCII
portrait that "types" itself in row by row inside a terminal window
(traffic dots, title bar, status bar with a steady blinking cursor).
One light-gray color, a density ramp, and high contrast keep it legible.

Pure standard library: reads the grayscale PGM written by prep_photo.py
(no PIL/numpy needed). GitHub renders SVGs via <img> and runs their SMIL
animations; the whole thing prints once and freezes.

Usage:  python scripts/make_ascii_svg.py [source-prepped.pgm]
Output: ascii.svg
"""
import html
import os
import sys
from pathlib import Path

from config import PROMPT, PROFILE_NAME

# ---- grid + chrome --------------------------------------------------------
COLS, ROWS = 100, 53
CELL_W, CELL_H = 8, 15
ART_W, ART_H = COLS * CELL_W, ROWS * CELL_H
PAD, TITLEBAR_H, STATUS_H = 20, 30, 30
CANVAS_W, CANVAS_H = ART_W + PAD * 2, TITLEBAR_H + ART_H + STATUS_H + PAD
RAMP = " .`:-=+*cs#%@"  # bright (sparse) -> dark (dense); leading space clears bg
GAMMA = 1.18            # >1 brightens mid tones -> face lands in sparser chars
WHITE_FLOOR = 0.80      # luminance above this is forced to blank (space)
BG, BG2 = "#0d1117", "#111722"
FRAME, TITLE_TEXT = "#30363d", "#7d8590"
INK = "#c9d1d9"
CURSOR = INK
ROW_DUR, STAGGER = 0.11, 0.11  # a single cursor rasters top -> bottom
DEFAULT_SRC = "source-prepped.pgm"
STATIC = bool(os.environ.get("STATIC"))  # frozen frame, for local previews


# ---- PGM reading (P5 binary / P2 ascii) -----------------------------------
def _pgm_header(buf):
    pos = 0

    def next_token():
        nonlocal pos
        while pos < len(buf) and buf[pos:pos + 1].isspace():
            pos += 1
        while pos < len(buf) and buf[pos:pos + 1] == b"#":
            while pos < len(buf) and buf[pos:pos + 1] != b"\n":
                pos += 1
            while pos < len(buf) and buf[pos:pos + 1].isspace():
                pos += 1
        start = pos
        while pos < len(buf) and not buf[pos:pos + 1].isspace():
            pos += 1
        return buf[start:pos]

    magic = next_token()
    if magic not in (b"P2", b"P5"):
        sys.exit(f"Not a PGM (expected P2 or P5, got {magic!r})")
    w, h = int(next_token()), int(next_token())
    int(next_token())  # maxval
    while pos < len(buf) and buf[pos:pos + 1].isspace():
        pos += 1
    return w, h, pos


def read_pgm(path: Path):
    buf = path.read_bytes()
    w, h, start = _pgm_header(buf)
    if buf[:2] == b"P5":
        px = buf[start:start + w * h]
        if len(px) < w * h:
            sys.exit("Truncated PGM pixel data")
        return w, h, [list(px[y * w:(y + 1) * w]) for y in range(h)]
    vals = buf[start:].split()
    if len(vals) < w * h:
        sys.exit("Truncated PGM pixel data")
    it = iter(int(v) for v in vals)
    return w, h, [[next(it) for _ in range(w)] for _ in range(h)]


def downsample(px, w, h, cols, rows):
    """Block-average the source into a COLS x ROWS grayscale grid."""
    grid = []
    for r in range(rows):
        y0, y1 = r * h // rows, (r + 1) * h // rows
        row = []
        for c in range(cols):
            x0, x1 = c * w // cols, (c + 1) * w // cols
            total, n = 0, 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    total += px[y][x]
                    n += 1
            row.append(total // max(n, 1))
        grid.append(row)
    return grid


def to_ascii(grid):
    out = []
    for row in grid:
        chars = []
        for v in row:
            lum = v / 255.0
            lum = pow(lum, GAMMA)
            if lum >= WHITE_FLOOR:
                chars.append(" ")
                continue
            idx = int((1.0 - lum) * (len(RAMP) - 1) + 0.5)
            chars.append(RAMP[max(0, min(len(RAMP) - 1, idx))])
        out.append("".join(chars))
    return out


# ---- SVG assembly ---------------------------------------------------------
def build_svg(rows) -> str:
    art_top = TITLEBAR_H + PAD * 0.35
    font_size = CELL_H * 0.86
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
        f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<defs>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
        '</linearGradient></defs>',
        f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="12" fill="url(#bg)"/>',
        f'<rect x="0.5" y="0.5" width="{CANVAS_W - 1}" height="{CANVAS_H - 1}" rx="12" '
        f'fill="none" stroke="{FRAME}" stroke-width="1"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        p.append(f'<circle cx="{PAD + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{dotcol}"/>')
    p.append(f'<text x="{CANVAS_W / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{TITLE_TEXT}" '
             f'font-size="12" text-anchor="middle">{PROMPT} ~$ ./portrait.sh</text>')

    for ry, line in enumerate(rows):
        y = art_top + ry * CELL_H + CELL_H * 0.74
        row_y = art_top + ry * CELL_H
        delay = ry * STAGGER
        text = (f'<text xml:space="preserve" x="{PAD}" y="{y:.1f}" fill="{INK}" '
                f'font-size="{font_size:.1f}" textLength="{ART_W}" '
                f'lengthAdjust="spacing">{html.escape(line)}</text>')
        if STATIC:
            p.append(text)
            continue
        p.append(
            f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_y:.1f}" height="{CELL_H}" width="0">'
            f'<animate attributeName="width" from="0" to="{ART_W}" begin="{delay:.3f}s" '
            f'dur="{ROW_DUR:.2f}s" fill="freeze"/></rect></clipPath>')
        p.append(f'<g clip-path="url(#r{ry})">{text}</g>')
        p.append(
            f'<rect y="{row_y + 1:.1f}" width="{CELL_W}" height="{CELL_H - 2}" '
            f'fill="{CURSOR}" opacity="0">'
            f'<animate attributeName="x" from="{PAD}" to="{PAD + ART_W}" begin="{delay:.3f}s" '
            f'dur="{ROW_DUR:.2f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{delay + ROW_DUR:.3f}s"/></rect>')

    # status bar with a steady blinking cursor
    status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
    status_y = status_line_y + 19
    whoami = f"{PROMPT}:~$ whoami "
    cx = PAD + len(whoami) * 7.2
    p += [
        f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>',
        f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
        f'{PROMPT}:~$ whoami <tspan fill="{INK}">{PROFILE_NAME}</tspan></text>',
        f'<rect x="{cx:.1f}" y="{status_y - 12:.1f}" width="8" height="14" fill="{INK}">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
        f'dur="1s" repeatCount="indefinite"/></rect>',
        '</svg>',
    ]
    return "".join(p)


def main(src: Path) -> None:
    if not src.exists():
        sys.exit(
            f"Missing {src}. Run prep_photo.py on a photo first:\n"
            f"  python scripts/prep_photo.py my-photo.jpg")
    w, h, px = read_pgm(src)
    rows = to_ascii(downsample(px, w, h, COLS, ROWS))
    out = Path("ascii.svg")
    out.write_text(build_svg(rows))
    print(f"Wrote {out} ({CANVAS_W}x{CANVAS_H})")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC))
