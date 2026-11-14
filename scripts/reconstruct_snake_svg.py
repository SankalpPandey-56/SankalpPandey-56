#!/usr/bin/env python3
"""scripts/reconstruct_snake_svg.py
Transforms Platane/snk SVGs into a round-trip ping-pong animation:
1. First half (0% -> 50%): The snake crawls forward eating every contribution box.
2. Second half (50% -> 100%): The snake retraces its path in reverse, remaking
   and depositing every green box back onto the grid until it is fully restored!
"""
import glob
import os
import re

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_blocks(body):
    res = []
    for m in re.finditer(r'([^{]+)\{([^}]+)\}', body):
        prop = m.group(2)
        for p in m.group(1).split(','):
            p = p.strip()
            if p.endswith('%'):
                try:
                    res.append((float(p[:-1]), prop))
                except ValueError:
                    pass
    res.sort(key=lambda x: x[0])
    return res

def process_snake_svg(svg_content):
    # 1. Double the CSS animation duration so movement speed stays identical
    def double_dur(m):
        dur = int(m.group(1))
        return f"{dur * 2}ms"

    svg = re.sub(r'(\d+)ms', double_dur, svg_content)

    # 2. Transform dot keyframes (@keyframes c\w+)
    # Pattern: @keyframes c0{12.72%{fill:var(--c1)}12.74%,100%{fill:var(--ce)}}
    def repl_c(m):
        cname = m.group(1)
        p1 = float(m.group(2))
        color = m.group(3)
        p2 = float(m.group(4))

        np1 = p1 / 2.0
        np2 = p2 / 2.0
        np3 = 100.0 - np2
        np4 = 100.0 - np1

        return (
            f"@keyframes {cname}{{"
            f"{np1:.2f}%{{fill:{color}}}"
            f"{np2:.2f}%,{np3:.2f}%{{fill:var(--ce)}}"
            f"{np4:.2f}%,100%{{fill:{color}}}}}"
        )

    svg = re.sub(
        r'@keyframes\s+(c\w+)\{([\d\.]+)%\{fill:(var\(--c\d\))\}([\d\.]+)%,100%\{fill:var\(--ce\)\}\}',
        repl_c,
        svg
    )

    # 3. Transform snake (s*) and progress bar (u*) keyframes
    def transform_generic_kf(m):
        kfname = m.group(1)
        body = m.group(2)
        blocks = parse_blocks(body)
        if not blocks:
            return m.group(0)

        # Mirror trajectory: forward (0 -> 50%) and reverse (50 -> 100%)
        new_blocks = []
        for p, prop in blocks:
            new_blocks.append((p * 0.5, prop))
        for p, prop in reversed(blocks):
            new_blocks.append((100.0 - p * 0.5, prop))

        new_blocks.sort(key=lambda x: x[0])
        body_str = "".join(f"{p:.2f}%{{{prop}}}" for p, prop in new_blocks)
        return f"@keyframes {kfname}{{{body_str}}}"

    svg = re.sub(
        r'@keyframes\s+([su]\w+)\{([^{}]+(?:\{[^{}]+\}[^{}]*)*)\}',
        transform_generic_kf,
        svg
    )
    return svg

def main():
    target_patterns = [
        os.path.join(REPO_DIR, "github-contribution-grid-snake*.svg")
    ]
    files = []
    for pat in target_patterns:
        files.extend(glob.glob(pat))

    if not files:
        print("No snake SVG files found to process.")
        return

    for path in files:
        print(f"Processing: {os.path.basename(path)}...")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        updated = process_snake_svg(content)

        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"Successfully converted {os.path.basename(path)} to forward-and-reconstruct animation!")

if __name__ == "__main__":
    main()

