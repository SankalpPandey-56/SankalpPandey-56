#!/usr/bin/env python3
"""prep_photo.py — turn a photo into a high-contrast grayscale source image.

Three steps (from the original blog post):
  1. Remove the background with rembg so the subject is isolated.
  2. Boost local contrast with OpenCV CLAHE so a flat face gains real
     highlights and shadows.
  3. Composite onto pure white so the background maps to the blank end of
     the ASCII density ramp (white -> spaces).

Heavy image libraries (opencv, numpy, rembg) are ONLY needed when you
change your photo. The daily GitHub Actions workflow never runs this.

Usage:  python scripts/prep_photo.py path/to/photo.jpg
Output: source-prepped.pgm   (what make_ascii_svg.py reads)
"""
import sys
from pathlib import Path

import cv2
import numpy as np

try:
    from rembg import remove
except ImportError:  # rembg is optional: works fine without background removal
    remove = None

OUT = Path("source-prepped.pgm")


def main(src: Path) -> None:
    img = cv2.imread(str(src))
    if img is None:
        sys.exit(f"Could not read image: {src}")

    if remove is not None:
        # rembg wants RGB, returns BGRA
        cut = remove(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        bgr = cv2.cvtColor(cut, cv2.COLOR_RGBA2BGRA)
        # Composite over white so removed background becomes spaces.
        alpha = bgr[:, :, 3:4].astype(np.float32) / 255.0
        white = np.full_like(bgr[:, :, :3], 255, dtype=np.float32)
        img = (bgr[:, :, :3].astype(np.float32) * alpha
               + white * (1.0 - alpha)).astype(np.uint8)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # CLAHE: contrast-limited adaptive histogram equalization.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Gentle gamma keeps mid-tones separated without clipping highlights.
    gray = np.clip(np.power(gray / 255.0, 0.9) * 255.0, 0, 255).astype(np.uint8)

    cv2.imwrite(str(OUT), gray)  # OpenCV writes binary PGM for a .pgm name
    print(f"Wrote {OUT} ({gray.shape[1]}x{gray.shape[0]})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/prep_photo.py path/to/photo.jpg")
    main(Path(sys.argv[1]))
