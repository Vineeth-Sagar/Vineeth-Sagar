#!/usr/bin/env python3
"""
Generate a self-hosted animated "typing" banner as a standalone SVG.

Why not readme-typing-svg.demolab.com? Two reasons:
  1. It is a third-party service - if it goes down, the hero of the README
     goes with it (the same way github-readme-stats did).
  2. Its URL never changes, so once a browser or GitHub's Camo proxy has
     cached a frame of it, you are stuck with that cache.

This writes a plain file into the repo instead, animated with CSS keyframes.
SVGs loaded through <img> run in "secure animated mode": declarative animation
(CSS and SMIL) plays, scripts do not. So this animates anywhere the service did.

The reveal is a clip rectangle that scales from 0 to full width in character
steps, matching how the hosted service does it - which means the text metrics
never matter and the banner cannot mis-clip on a machine lacking the font.

Usage:
    python scripts/typing_svg.py -o assets/typing.svg \\
        --lines "Vineeth Sagar H L" "Machine Learning Engineer" \\
        --color "#52FF78" --size 27 --width 640
"""
import argparse
import io
import os
from xml.sax.saxutils import escape

FONT_STACK = ("'Fira Code','JetBrains Mono',ui-monospace,SFMono-Regular,"
              "Menlo,Consolas,'DejaVu Sans Mono',monospace")


def build(args):
    lines = args.lines
    n = len(lines)

    cycle = args.duration + args.pause          # ms on screen per line
    total = cycle * n                           # ms for one full rotation
    span = cycle / total                        # fraction of the loop per line

    # Proportions within one line's slot, matching readme-typing-svg's feel.
    type_frac, hold_frac = 0.605, 0.849

    css = [
        f"svg{{background:transparent}}",
        f".l{{font-family:{FONT_STACK};font-size:{args.size}px;"
        f"font-weight:{args.weight};fill:{args.color};"
        f"dominant-baseline:central;text-anchor:middle}}",
        f".r{{transform-origin:0 0}}",
    ]
    body = []

    for i, text in enumerate(lines):
        start = i * span
        steps = max(1, len(text))

        p0 = start * 100
        p1 = (start + type_frac * span) * 100
        p2 = (start + hold_frac * span) * 100
        p3 = (start + span) * 100

        # Outside its slot the clip is collapsed, which hides the line entirely.
        frames = [
            f"0%,{p0:.4f}%{{transform:scaleX(0);animation-timing-function:steps({steps},end)}}",
            f"{p1:.4f}%{{transform:scaleX(1)}}",
            f"{p2:.4f}%{{transform:scaleX(1);animation-timing-function:steps({steps},end)}}",
            f"{p3:.4f}%,100%{{transform:scaleX(0)}}",
        ]
        css.append("@keyframes k%d{%s}" % (i, "".join(frames)))
        css.append(f"#r{i}{{animation:k{i} {total}ms linear infinite}}")

        body.append(
            f'<clipPath id="c{i}">'
            f'<rect id="r{i}" class="r" x="0" y="0" '
            f'width="{args.width}" height="{args.height}"/>'
            f"</clipPath>"
            f'<g clip-path="url(#c{i})">'
            f'<text class="l" x="{args.width / 2:g}" y="{args.height / 2:g}">'
            f"{escape(text)}</text></g>"
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {args.width} {args.height}" '
        f'width="{args.width}" height="{args.height}" '
        f'role="img" aria-label="{escape(" - ".join(lines))}">'
        f"<title>{escape(' - '.join(lines))}</title>"
        f"<style>{''.join(css)}</style>"
        f"{''.join(body)}</svg>"
    )

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"{args.out}  {n} lines  {total}ms loop  "
          f"{os.path.getsize(args.out) / 1024:.1f} KB")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-o", "--out", default="assets/typing.svg")
    p.add_argument("--lines", nargs="+", required=True)
    p.add_argument("--color", default="#52FF78")
    p.add_argument("--size", type=int, default=27)
    p.add_argument("--weight", type=int, default=600)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=48)
    p.add_argument("--duration", type=int, default=2800, help="ms to type a line")
    p.add_argument("--pause", type=int, default=900, help="ms held after typing")
    build(p.parse_args())


if __name__ == "__main__":
    main()
