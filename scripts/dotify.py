#!/usr/bin/env python3
"""
Turn a photo into a dot-matrix / halftone SVG portrait.

Each cell of a grid becomes a circle whose RADIUS tracks the cell's darkness and
whose FILL is the cell's average colour. Output is a transparent-background SVG,
so one file works on both GitHub light and dark themes.

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


def animation_css(args, w, h, pts):
    """Seamless looping motion: breathing parallax, head tilt, amber LED shimmer.

    Every period divides the master loop, so the result is seamless: tilt runs
    once per loop, breathing and shimmer twice, the amber pulse three times.
    All motion is CSS, which the browser drives at display refresh rate, and
    only the ~30 groups ever carry a transform - never the individual dots.
    """
    loop = args.loop
    # Pivot the sway around the middle of the torso rather than the image
    # centre, so the head swings while the base stays planted.
    ox = sum(p[0] for p in pts) / len(pts) if pts else w / 2
    oy = h * 0.72

    amp = {0: 0.34, 1: 0.62, 2: 1.0}          # back, mid, front
    css = [
        ".fig{transform-box:view-box;transform-origin:%.0fpx %.0fpx;"
        "animation:tilt %dms ease-in-out infinite}" % (ox, oy, loop),
        "@keyframes tilt{0%%,100%%{transform:rotate(%.2fdeg)}"
        "50%%{transform:rotate(%.2fdeg)}}" % (-args.tilt, args.tilt),
    ]
    for ly in range(3):
        a = amp[ly]
        css.append(
            ".ly%d{transform-box:view-box;transform-origin:%.0fpx %.0fpx;"
            "animation:br%d %dms ease-in-out infinite}" % (ly, ox, oy, ly, loop // 2)
        )
        css.append(
            "@keyframes br%d{0%%,100%%{transform:scale(1) translateY(0)}"
            "50%%{transform:scale(%.4f) translateY(%.2fpx)}}"
            % (ly, 1.0 + args.breathe * a, -args.rise * a)
        )
    # Shimmer: one keyframe set, each band offset by a negative delay so the
    # highlight travels across the figure instead of blinking in unison.
    css.append("@keyframes shim{0%%,100%%{opacity:%.3f}50%%{opacity:1}}" % args.dim)
    for b in range(args.bands):
        css.append(
            ".bd%d{animation:shim %dms ease-in-out infinite;animation-delay:%dms}"
            % (b, loop // 2, -(loop // 2) * b // args.bands)
        )
    # Amber glow: feFlood tinted through the dots' own alpha, screened back on
    # top. Compositing against SourceAlpha lights the dots only, never the
    # transparent background between them.
    css.append(
        "@keyframes glow{0%%,100%%{flood-opacity:%.3f}50%%{flood-opacity:%.3f}}"
        % (args.amber_min, args.amber_max)
    )
    css.append("#amberflood{animation:glow %dms ease-in-out infinite}" % (loop // 3))

    return (
        "<defs>"
        '<filter id="amber" x="-5%" y="-5%" width="110%" height="110%" '
        'color-interpolation-filters="sRGB">'
        '<feFlood id="amberflood" flood-color="' + args.amber + '" '
        'flood-opacity="' + ("%.3f" % args.amber_min) + '" result="amb"/>'
        '<feComposite in="amb" in2="SourceAlpha" operator="in" result="tint"/>'
        '<feBlend in="SourceGraphic" in2="tint" mode="screen"/>'
        "</filter>"
        "</defs>"
        "<style>" + "".join(css) + "</style>"
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

    # Collect the dots. Static mode groups by colour (smallest file). Animated
    # mode groups by (depth layer, shimmer band) instead, because those groups
    # are what the CSS animates - colour then rides along on each circle.
    q = max(1, args.quant)
    groups = {}
    dots = 0
    live_pts = []

    # Pre-pass: the diagonal sweep must span the subject, not the canvas.
    # Without this the leading bands come out empty and the shimmer starts
    # part-way through the loop.
    t_lo, t_hi = 0.0, 1.0
    if args.animate:
        ts = [(x / cols) * 0.6 + (y / rows) * 0.4
              for y in range(rows) for x in range(cols)
              if bg is None or not bg[y][x]]
        if ts:
            t_lo, t_hi = min(ts), max(ts)
    t_rng = (t_hi - t_lo) or 1.0
    for y in range(rows):
        for x in range(cols):
            if bg is not None and bg[y][x]:
                continue                      # flat background - draw nothing

            lum = gx[x, y]
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
                cr, cg, cb = (min(255, (v // q) * q + q // 2) for v in px[x, y])
                fill = f"#{cr:02x}{cg:02x}{cb:02x}"
            else:
                fill = args.mono_color

            cx = x * step + r_max
            cy = y * step + r_max

            if args.animate:
                # Depth from luminance: a front-lit portrait puts the bright
                # planes (face, shirt) nearer the camera and the dark ones
                # (hair, shadow) behind, which is enough for a 2.5D parallax.
                layer = 2 if lum >= 170 else (1 if lum >= 100 else 0)
                # Diagonal bands give the shimmer a direction to travel in.
                t = ((x / cols) * 0.6 + (y / rows) * 0.4 - t_lo) / t_rng
                band = min(args.bands - 1, max(0, int(t * args.bands)))
                groups.setdefault((layer, band), []).append(
                    f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:.1f}" fill="{fill}"/>'
                )
                live_pts.append((cx, cy))
            else:
                groups.setdefault(fill, []).append(
                    f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:.1f}"/>'
                )
            dots += 1

    if args.animate:
        parts.append(animation_css(args, w, h, live_pts))
        parts.append('<g class="fig" filter="url(#amber)">')
        for layer in range(3):
            parts.append(f'<g class="ly{layer}">')
            for band in range(args.bands):
                circles = groups.get((layer, band))
                if not circles:
                    continue
                parts.append(f'<g class="bd{band}">')
                parts.extend(circles)
                parts.append("</g>")
            parts.append("</g>")
        parts.append("</g>")
    else:
        for fill, circles in groups.items():
            parts.append(f'<g fill="{fill}">')
            parts.extend(circles)
            parts.append("</g>")

    parts.append("</svg>")

    out = args.out if args.out.endswith(".svg") else args.out + ".svg"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))

    kind = "motion groups" if args.animate else "colours"
    print(f"{out}  {rows}x{cols} grid  {dots} dots  {len(groups)} {kind}  "
          f"{os.path.getsize(out) / 1024:.0f} KB")


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
                   help="seamless looping animation: breathing parallax, gentle "
                        "tilt, pulsing amber LED shimmer")
    p.add_argument("--loop", type=int, default=12000, help="master loop length, ms")
    p.add_argument("--bands", type=int, default=10, help="shimmer bands across the figure")
    p.add_argument("--tilt", type=float, default=0.55, help="head tilt, degrees each way")
    p.add_argument("--breathe", type=float, default=0.014, help="extra scale on the front layer")
    p.add_argument("--rise", type=float, default=5.0, help="vertical lift, SVG units")
    p.add_argument("--dim", type=float, default=0.82, help="shimmer trough opacity")
    p.add_argument("--amber", default="#FFB020", help="LED glow colour")
    p.add_argument("--amber-min", type=float, default=0.05)
    p.add_argument("--amber-max", type=float, default=0.20)
    p.add_argument("--alt", default="Portrait rendered as a dot matrix")
    build(p.parse_args())


if __name__ == "__main__":
    main()
