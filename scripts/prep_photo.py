#!/usr/bin/env python3
"""prep_photo.py — turn a photo into a high-contrast grayscale source image.

Two paths:

1. Full pipeline (needs `pip install -r scripts/requirements.txt`):
   rembg background removal -> OpenCV CLAHE local contrast -> white
   composite. Best quality; run locally when you change your photo.

2. Zero-dependency fallback (pure standard library, macOS): uses `sips`
   to decode PNG/JPEG to a BMP (or reads a BMP directly), removes a
   uniform background with a flood fill from the borders, boosts local
   contrast with a box-blur high-pass, and writes the same PGM.

Usage:  python scripts/prep_photo.py path/to/photo.png|jpg|bmp
Output: source-prepped.pgm   (what make_ascii_svg.py reads)
"""
import os
import struct
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

OUT = Path("source-prepped.pgm")


# ── full pipeline (cv2/numpy/rembg) ───────────────────────────────────────
def prep_full(img):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:
        from rembg import remove
    except ImportError:
        remove = None

    if remove is not None:
        cut = remove(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        bgr = cv2.cvtColor(cut, cv2.COLOR_RGBA2BGRA)
        alpha = bgr[:, :, 3:4].astype(np.float32) / 255.0
        white = np.full_like(bgr[:, :, :3], 255, dtype=np.float32)
        img = (bgr[:, :, :3].astype(np.float32) * alpha
               + white * (1.0 - alpha)).astype(np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = np.clip(np.power(gray / 255.0, 0.9) * 255.0, 0, 255).astype(np.uint8)
    return gray.tolist()


# ── zero-dependency fallback ───────────────────────────────────────────────
def load_bmp(path: Path):
    """Parse a 24/32-bit BMP -> (width, height, [[(r,g,b),...],...])."""
    data = path.read_bytes()
    if data[:2] != b"BM":
        sys.exit(f"{path} is not a BMP")
    pix_off = struct.unpack_from("<I", data, 10)[0]
    w = struct.unpack_from("<i", data, 18)[0]
    h = struct.unpack_from("<i", data, 22)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    top_down = h < 0
    h = abs(h)
    row_stride = ((w * bpp + 31) // 32) * 4
    rows = []
    for row in range(h):
        src_row = row if top_down else (h - 1 - row)
        off = pix_off + src_row * row_stride
        px_row = []
        for x in range(w):
            b, g, r = data[off + x * bpp // 8: off + x * bpp // 8 + 3]
            px_row.append((r, g, b))
        rows.append(px_row)
    return w, h, rows


def load_image(src: Path):
    """Decode PNG/JPEG via sips (macOS) to BMP, or read BMP directly."""
    try:
        from PIL import Image  # noqa: PLC0415
        img = Image.open(src).convert("RGB")
        w, h = img.size
        pixels = list(img.getdata())
        return w, h, [pixels[y * w:(y + 1) * w] for y in range(h)]
    except ImportError:
        pass
    if src.suffix.lower() == ".bmp":
        return load_bmp(src)
    if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".tiff"):
        if not sys.platform.startswith("darwin"):
            sys.exit("Decoding PNG/JPEG without Pillow needs macOS `sips`. "
                     "Install Pillow: pip install -r scripts/requirements.txt")
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(["sips", "-s", "format", "bmp", str(src),
                            "--out", tmp_path], check=True,
                           capture_output=True)
            return load_bmp(Path(tmp_path))
        finally:
            os.unlink(tmp_path)
    sys.exit(f"Unsupported image: {src}")


def remove_background(px, w, h, threshold=42):
    """Flood-fill from the borders, whitening pixels near the border color."""
    from statistics import median
    border = ([px[y][x] for x in range(w) for y in (0, h - 1)]
              + [px[y][x] for x in (0, w - 1) for y in range(h)])
    bg = tuple(median(c[i] for c in border) for i in range(3))
    t2 = threshold * threshold

    def dist(c):
        return sum((c[i] - bg[i]) ** 2 for i in range(3))

    mask = [[False] * w for _ in range(h)]
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if dist(px[y][x]) < t2 and not mask[y][x]:
                mask[y][x] = True
                dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if dist(px[y][x]) < t2 and not mask[y][x]:
                mask[y][x] = True
                dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not mask[ny][nx] \
                    and dist(px[ny][nx]) < t2:
                mask[ny][nx] = True
                dq.append((nx, ny))
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                px[y][x] = (255, 255, 255)


def local_contrast(g, w, h, radius=9, amount=0.7):
    """High-pass boost: pixel += amount * (pixel - local box mean)."""
    P = [[0] * (w + 1) for _ in range(h + 1)]
    for y in range(h):
        row = 0
        for x in range(w):
            row += g[y][x]
            P[y + 1][x + 1] = P[y][x + 1] + row

    def box(x0, y0, x1, y1):
        return P[y1 + 1][x1 + 1] - P[y0][x1 + 1] - P[y1 + 1][x0] + P[y0][x0]

    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            x0, x1 = max(0, x - radius), min(w - 1, x + radius)
            y0, y1 = max(0, y - radius), min(h - 1, y + radius)
            n = (x1 - x0 + 1) * (y1 - y0 + 1)
            mean = box(x0, y0, x1, y1) / n
            v = g[y][x] + amount * (g[y][x] - mean)
            out[y][x] = max(0, min(255, int(v)))
    return out


def prep_stdlib(src: Path):
    w, h, px = load_image(src)
    remove_background(px, w, h)
    gray = [[int(0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in row]
            for row in px]
    return local_contrast(gray, w, h)


# ── output ─────────────────────────────────────────────────────────────────
def write_pgm(grid):
    h = len(grid)
    w = len(grid[0])
    with open(OUT, "wb") as f:
        f.write(b"P5\n%d %d\n255\n" % (w, h))
        for row in grid:
            f.write(bytes(row))
    print(f"Wrote {OUT} ({w}x{h})")


def main(src: Path) -> None:
    if not src.exists():
        sys.exit(f"Could not read image: {src}")

    gray = None
    try:
        import cv2  # noqa: F401
        img = cv2.imread(str(src))
        if img is not None:
            gray = prep_full(img)
    except ImportError:
        gray = None
    if gray is None:
        gray = prep_stdlib(src)
    write_pgm(gray)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/prep_photo.py path/to/photo.png|jpg|bmp")
    main(Path(sys.argv[1]))
