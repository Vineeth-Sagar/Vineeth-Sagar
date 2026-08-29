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


def despeckle(bg, cols, rows, min_neighbours):
    """Drop live cells that have almost no live neighbours.

    The flood fill leaves a scatter of single dots where the wall shaded off or
    the subject's edge went soft. They read as dirt around the silhouette, so
    anything too isolated to be part of the figure gets folded back into the
    background.
    """
    if min_neighbours <= 0:
        return bg
    doomed = []
    for y in range(rows):
        for x in range(cols):
            if bg[y][x]:
                continue
            n = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < cols and 0 <= ny < rows and not bg[ny][nx]:
                        n += 1
            if n < min_neighbours:
                doomed.append((x, y))
    for x, y in doomed:
        bg[y][x] = True
    return bg


def subject_levels(gray, bg, cols, rows, lo_pct, hi_pct, gamma):
    """Build a tone curve from the SUBJECT's pixels only.

    --equalize stretches the whole frame, but most of the frame is blank wall,
    so the figure only ever gets a slice of the available range and lands dark
    against a #0D1117 page. Measuring the subject alone spends the full range
    on the person, and gamma lifts the midtones so the face reads at 300px.
    """
    gx = gray.load()
    vals = sorted(gx[x, y] for y in range(rows) for x in range(cols)
                  if bg is None or not bg[y][x])
    if not vals:
        return list(range(256))
    lo = vals[int(len(vals) * lo_pct)]
    hi = vals[min(len(vals) - 1, int(len(vals) * hi_pct))]
    if hi <= lo:
        lo, hi = 0, 255
    lut = []
    for v in range(256):
        t = (v - lo) / (hi - lo)
        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        lut.append(int(round((t ** gamma) * 255)))
    return lut

def reveal_defs(args, w, h):
    """Mask for the hero: an optional bottom fade, plus the CRT scan cover.

    Both live in one mask so they compose: the fade decides how much of each
    row can ever show, the cover decides how much has been scanned yet.
    """
    css = ""
    if args.animate:
        css = (
            # Base state = revealed. The keyframes drive it, they do not gate it.
            ".cover{transform:translateY(%(h)dpx)}"
            ".cover{animation:scan %(loop)dms linear infinite}"
            "@keyframes scan{"
            "0%%{transform:translateY(0);animation-timing-function:steps(%(n)d,end)}"
            "%(rev).3f%%{transform:translateY(%(h)dpx)}"
            "100%%{transform:translateY(%(h)dpx)}}"
        ) % {"h": h, "loop": args.loop, "n": args.slices,
             "rev": args.reveal * 100.0}

    grad = ""
    base_fill = "#fff"
    if args.fade > 0:
        start = 1.0 - args.fade
        grad = (
            '<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="{start:.3f}" stop-color="#fff"/>'
            '<stop offset="1" stop-color="#000"/>'
            "</linearGradient>"
        )
        base_fill = "url(#fade)"

    cover = ""
    if args.animate:
        cover = (f'<rect class="cover" x="0" y="0" width="{w:g}" '
                 f'height="{h:g}" fill="#000"/>')

    return (
        "<defs>"
        + grad
        + f'<mask id="reveal" maskUnits="userSpaceOnUse" '
          f'x="0" y="0" width="{w:g}" height="{h:g}">'
          f'<rect x="0" y="0" width="{w:g}" height="{h:g}" fill="{base_fill}"/>'
        + cover
        + "</mask></defs>"
        + (f"<style>{css}</style>" if css else "")
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
    if bg is not None:
        bg = despeckle(bg, cols, rows, args.despeckle)

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
            bg = despeckle(bg, cols, rows, args.despeckle)

    lut = (subject_levels(gray, bg, cols, rows, args.black, args.white,
                          args.gamma) if args.levels else None)

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

            lum = lut[gx[x, y]] if lut else gx[x, y]
            dark = 1.0 - (lum / 255.0)
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
                raw = px[x, y]
                if lut:
                    raw = (lut[raw[0]], lut[raw[1]], lut[raw[2]])
                cr, cg, cb = (min(255, (v // q) * q + q // 2) for v in raw)
                fill = f"#{cr:02x}{cg:02x}{cb:02x}"
            else:
                fill = args.mono_color

            cx = x * step + r_max
            cy = y * step + r_max
            groups.setdefault(fill, []).append(
                f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:.1f}"/>'
            )
            dots += 1

    masked = args.animate or args.fade > 0
    if masked:
        parts.append(reveal_defs(args, w, h))
        parts.append('<g mask="url(#reveal)">')

    for fill, circles in groups.items():
        parts.append(f'<g fill="{fill}">')
        parts.extend(circles)
        parts.append("</g>")

    if masked:
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
    p.add_argument("--fade", type=float, default=0.0,
                   help="fraction of the height that dissolves at the bottom, "
                        "so the torso ends instead of being chopped off")
    p.add_argument("--despeckle", type=int, default=0,
                   help="drop live cells with fewer than N live neighbours; "
                        "3 clears the scatter the flood fill leaves behind")
    p.add_argument("--levels", action="store_true",
                   help="build the tone curve from the subject only, not the "
                        "whole frame - the figure reads much brighter")
    p.add_argument("--black", type=float, default=0.02, help="black clip percentile")
    p.add_argument("--white", type=float, default=0.99, help="white clip percentile")
    p.add_argument("--gamma", type=float, default=1.0,
                   help="<1 lifts midtones; try 0.85 for a dark page")
    p.add_argument("--alt", default="Portrait rendered as a dot matrix")
    build(p.parse_args())


if __name__ == "__main__":
    main()
