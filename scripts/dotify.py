#!/usr/bin/env python3
"""
Turn a photo into a dot-matrix / halftone SVG portrait.

Each cell of a grid becomes a circle whose RADIUS tracks the cell's darkness and
whose FILL is the cell's average colour. Output is a transparent-background SVG,
so one file works on both GitHub light and dark themes.

Usage:
    python scripts/dotify.py assets/source.jpg -o assets/portrait \\
        --cols 92 --detail 0.30 --min-r 2.2 --equalize --color

Options:
    --cols N        grid columns (more = finer). Default 96.
    --detail F      0..1, how much a bright cell still draws a dot. Default 0.5.
    --equalize      stretch contrast before sampling (helps flat lighting).
    --color         colour dots. Omit for monochrome neon.
    --mono-color    hex used when --color is not set. Default #52FF78.
    --crop L,T,R,B  pixel crop applied before anything else.
"""
import argparse
import io
import os

from PIL import Image, ImageOps


def build(args):
    im = Image.open(args.source).convert("RGB")

    if args.crop:
        box = tuple(int(v) for v in args.crop.split(","))
        im = im.crop(box)

    if args.equalize:
        im = ImageOps.autocontrast(im, cutoff=1)

    # Sample down to the dot grid. Cells are square, so derive rows from aspect.
    cols = args.cols
    rows = max(1, round(cols * im.height / im.width))
    small = im.resize((cols, rows), Image.LANCZOS)
    gray = small.convert("L")

    px = small.load()
    gx = gray.load()

    step = 10.0          # SVG units per cell
    r_max = step / 2.0   # a full-strength dot exactly fills its cell
    w = cols * step
    h = rows * step

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" '
        f'width="{w:g}" height="{h:g}" role="img" '
        f'aria-label="{args.alt}">',
        f"<title>{args.alt}</title>",
    ]

    for y in range(rows):
        for x in range(cols):
            # Darkness: 0 = white, 1 = black.
            dark = 1.0 - (gx[x, y] / 255.0)

            # Lift the floor so light areas still register faintly.
            weight = dark ** (1.0 - args.detail * 0.9)
            r = r_max * weight
            if r < args.min_r:                # drop the flat background away
                continue

            if args.color:
                cr, cg, cb = px[x, y]
                fill = f"#{cr:02x}{cg:02x}{cb:02x}"
            else:
                fill = args.mono_color

            cx = x * step + r_max
            cy = y * step + r_max
            parts.append(
                f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:.1f}" fill="{fill}"/>'
            )

    parts.append("</svg>")
    svg = "".join(parts)

    out = args.out
    if not out.endswith(".svg"):
        out += ".svg"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)

    print(f"{out}  {rows}x{cols} grid  {len(parts) - 3} dots  "
          f"{os.path.getsize(out) / 1024:.0f} KB")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source")
    p.add_argument("-o", "--out", default="assets/portrait")
    p.add_argument("--cols", type=int, default=96)
    p.add_argument("--detail", type=float, default=0.5)
    p.add_argument("--min-r", type=float, default=0.35,
                   help="smallest dot to draw; raise it to erase a pale background")
    p.add_argument("--equalize", action="store_true")
    p.add_argument("--color", action="store_true")
    p.add_argument("--mono-color", default="#52FF78")
    p.add_argument("--crop", default=None)
    p.add_argument("--alt", default="Portrait rendered as a dot matrix")
    build(p.parse_args())


if __name__ == "__main__":
    main()
