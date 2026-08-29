#!/usr/bin/env python3
"""
Turn a photo into a dot-matrix / halftone SVG portrait.

Each cell of a grid becomes a circle whose RADIUS tracks the cell's darkness and
whose FILL is the cell's average colour. Output is a transparent-background SVG,
so one file works on both GitHub light and dark themes.

With --animate the portrait is revealed top to bottom in slices, like a CRT
painting a frame, on a seamless loop.

Two things keep the result clean:

  * --cutout   flood-fills the flat studio background in from the border and
               drops those cells entirely, so you get a crisp silhouette instead
               of a full rectangle of wall dots.
  * --floor    guarantees every cell INSIDE the subject draws a dot of at least
               this radius, so pale areas (a light shirt, a highlight on a cheek)
               never punch blank holes through the figure.

Usage:
    python scripts/dotify.py assets/source.jpg -o assets/portrait \\
        --cols 130 --detail 0.45 --floor 0.36 --tol 50 \
        --cutout --trim --equalize --color
"""
import argparse
import io
import os
from collections import deque

from PIL import Image, ImageOps


def background_mask(small, tol):
    """BFS in from the border, marking cells close in colour to the border median."""
    cols, rows = small.size
    px = small.load()

    edge = []
    for x in range(cols):
        edge += [px[x, 0], px[x, rows - 1]]
    for y in range(rows):
        edge += [px[0, y], px[cols - 1, y]]
    seed = tuple(sorted(c[i] for c in edge)[len(edge) // 2] for i in range(3))

    def near(c):
        return (c[0] - seed[0]) ** 2 + (c[1] - seed[1]) ** 2 + (c[2] - seed[2]) ** 2 <= tol * tol

    bg = [[False] * cols for _ in range(rows)]
    q = deque()
    for x in range(cols):
        for y in (0, rows - 1):
            if near(px[x, y]) and not bg[y][x]:
                bg[y][x] = True
                q.append((x, y))
    for y in range(rows):
        for x in (0, cols - 1):
            if near(px[x, y]) and not bg[y][x]:
                bg[y][x] = True
                q.append((x, y))

    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows and not bg[ny][nx] and near(px[nx, ny]):
                bg[ny][nx] = True
                q.append((nx, ny))
    return bg


def animation_css(args, w, h):
    """A CRT-style top-to-bottom slice reveal.

    The figure sits behind a mask holding one black "cover" rectangle. The cover
    starts flush with the top (hiding everything) and steps downward, so the
    portrait is unmasked slice by slice, the way a CRT paints a frame.

    Two deliberate choices:

    * The cover moves by `transform`, never by geometry, so nothing about the
      dots or the mask has to be recomputed per frame.
    * Its BASE style is fully scrolled away - i.e. fully revealed. If a renderer
      ever ignores the animation, the portrait shows complete rather than
      vanishing behind a cover stuck at the top.
    """
    loop = args.loop
    rev = args.reveal * 100.0          # % of the loop spent scanning

    css = (
        # Base state = revealed. The keyframes drive it, they do not gate it.
        ".cover{transform:translateY(%(h)dpx)}"
        ".cover{animation:scan %(loop)dms linear infinite}"
        "@keyframes scan{"
        "0%%{transform:translateY(0);animation-timing-function:steps(%(n)d,end)}"
        "%(rev).3f%%{transform:translateY(%(h)dpx)}"
        "100%%{transform:translateY(%(h)dpx)}}"
    ) % {"h": h, "loop": loop, "n": args.slices, "rev": rev}

    return (
        "<defs>"
        f'<mask id="reveal" maskUnits="userSpaceOnUse" '
        f'x="0" y="0" width="{w:g}" height="{h:g}">'
        f'<rect x="0" y="0" width="{w:g}" height="{h:g}" fill="#fff"/>'
        f'<rect class="cover" x="0" y="0" width="{w:g}" height="{h:g}" fill="#000"/>'
        "</mask>"
        "</defs>"
        f"<style>{css}</style>"
    )


def build(args):
    im = Image.open(args.source).convert("RGB")

    if args.crop:
        im = im.crop(tuple(int(v) for v in args.crop.split(",")))

    if args.equalize:
        im = ImageOps.autocontrast(im, cutoff=1)

    cols = args.cols
    rows = max(1, round(cols * im.height / im.width))
    small = im.resize((cols, rows), Image.LANCZOS)
    gray = small.convert("L")

    px = small.load()
    gx = gray.load()

    bg = background_mask(small, args.tol) if args.cutout else None

    if bg is not None and args.trim:
        # Re-frame tightly around the subject, then rebuild the grid, so the
        # figure fills the SVG instead of floating in a field of empty wall.
        live = [(x, y) for y in range(rows) for x in range(cols) if not bg[y][x]]
        if live:
            xs = [p[0] for p in live]
            ys = [p[1] for p in live]
            pad = args.pad
            box = (
                max(0, int((min(xs) / cols - pad) * im.width)),
                max(0, int((min(ys) / rows - pad) * im.height)),
                min(im.width, int(((max(xs) + 1) / cols + pad) * im.width)),
                min(im.height, int(((max(ys) + 1) / rows + pad) * im.height)),
            )
            im = im.crop(box)
            rows = max(1, round(cols * im.height / im.width))
            small = im.resize((cols, rows), Image.LANCZOS)
            gray = small.convert("L")
            px = small.load()
            gx = gray.load()
            bg = background_mask(small, args.tol)

    step = 10.0
    r_max = step / 2.0
    r_floor = r_max * args.floor
    w, h = cols * step, rows * step

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" '
        f'width="{w:g}" height="{h:g}" role="img" aria-label="{args.alt}">',
        f"<title>{args.alt}</title>",
    ]

    # Collect per colour, then emit one <g fill> per colour. Grouping plus a
    # light colour quantisation roughly halves the file versus a fill= on every
    # circle, with no visible difference at display size. The scan reveal is a
    # single animated mask, so it needs no per-dot grouping of its own.
    q = max(1, args.quant)
    groups = {}
    dots = 0
    for y in range(rows):
        for x in range(cols):
            if bg is not None and bg[y][x]:
                continue                      # flat background - draw nothing

            dark = 1.0 - (gx[x, y] / 255.0)
            weight = dark ** (1.0 - args.detail * 0.9)

            if bg is not None:
                # Inside the subject: scale between the floor and a full cell, so
                # even a near-white shirt still renders a solid dot.
                r = r_floor + (r_max - r_floor) * weight
            else:
                r = r_max * weight
                if r < args.min_r:
                    continue

            if args.color:
                cr, cg, cb = (min(255, (v // q) * q + q // 2) for v in px[x, y])
                fill = f"#{cr:02x}{cg:02x}{cb:02x}"
            else:
                fill = args.mono_color

            cx = x * step + r_max
            cy = y * step + r_max
            groups.setdefault(fill, []).append(
                f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:.1f}"/>'
            )
            dots += 1

    if args.animate:
        parts.append(animation_css(args, w, h))
        parts.append('<g mask="url(#reveal)">')

    for fill, circles in groups.items():
        parts.append(f'<g fill="{fill}">')
        parts.extend(circles)
        parts.append("</g>")

    if args.animate:
        parts.append("</g>")

    parts.append("</svg>")

    out = args.out if args.out.endswith(".svg") else args.out + ".svg"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))

    print(f"{out}  {rows}x{cols} grid  {dots} dots  {len(groups)} colours  "
          f"{os.path.getsize(out) / 1024:.0f} KB"
          + (f"  scan {args.slices} slices / {args.loop}ms" if args.animate else ""))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source")
    p.add_argument("-o", "--out", default="assets/portrait")
    p.add_argument("--cols", type=int, default=110,
                   help="grid columns; higher is finer but the SVG grows fast")
    p.add_argument("--detail", type=float, default=0.45,
                   help="0..1, how strongly bright cells still draw")
    p.add_argument("--floor", type=float, default=0.36,
                   help="min dot radius inside the subject, as a fraction of a cell; "
                        "raise it if pale areas look patchy")
    p.add_argument("--cutout", action="store_true",
                   help="flood-fill the flat background away from the border")
    p.add_argument("--tol", type=float, default=38.0,
                   help="colour tolerance for --cutout; raise it if wall remains")
    p.add_argument("--quant", type=int, default=12,
                   help="colour quantisation step; higher = smaller file, flatter colour")
    p.add_argument("--trim", action="store_true",
                   help="re-frame tightly around the subject (needs --cutout)")
    p.add_argument("--pad", type=float, default=0.02,
                   help="margin kept around the subject when --trim is used")
    p.add_argument("--min-r", type=float, default=0.35,
                   help="smallest dot when --cutout is NOT used")
    p.add_argument("--equalize", action="store_true")
    p.add_argument("--color", action="store_true")
    p.add_argument("--mono-color", default="#52FF78")
    p.add_argument("--crop", default=None, help="L,T,R,B pixel crop")
    p.add_argument("--animate", action="store_true",
                   help="CRT-style top-to-bottom slice reveal, looping")
    p.add_argument("--loop", type=int, default=9250,
                   help="master loop length in ms; a divisor of the typing "
                        "banner's loop keeps the two in step")
    p.add_argument("--slices", type=int, default=48,
                   help="horizontal slices the reveal steps through")
    p.add_argument("--reveal", type=float, default=0.28,
                   help="fraction of the loop spent scanning; the rest holds")
    p.add_argument("--alt", default="Portrait rendered as a dot matrix")
    build(p.parse_args())


if __name__ == "__main__":
    main()
