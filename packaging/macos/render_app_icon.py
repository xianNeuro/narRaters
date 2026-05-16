#!/usr/bin/env python3
"""
Render narRater ``static/app-icon.png``.

Concept: **story arc + recall echoes**.

Upper third: five bright "story event" nodes connected by a smooth narrative
arc (gentle rise to a late climax, then falling resolution).
Lower third: smaller dimmer "recall" nodes representing what participants
remember — some directly below story events (matched) with faint match lines,
some offset (unmatched / paraphrased).

Palette: deep indigo (top-left) → warm plum (bottom-right), no glossy
highlight. Flat / modern Big Sur+ macOS aesthetic.

Usage:
  python3 packaging/macos/render_app_icon.py
  python3 packaging/macos/render_app_icon.py --out /path/to/app-icon.png
  python3 packaging/macos/render_app_icon.py --size 512

Requires Pillow.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
except ImportError:
    print("Pillow is required: pip install Pillow", file=sys.stderr)
    raise SystemExit(1)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Squircle background
# ---------------------------------------------------------------------------

def _squircle_mask(size: int, n: float = 5.0) -> Image.Image:
    """Superellipse mask, |x/a|^n + |y/b|^n <= 1.

    n=5.0 closely approximates the macOS Big Sur+ "G2 continuous" corner —
    less geometric than a plain rounded rectangle, with no visible transition
    where the straight edge meets the curve.
    """
    mask = Image.new("L", (size, size), 0)
    px = mask.load()
    a = b = (size - 1) / 2.0
    for y in range(size):
        ny = (y - b) / b
        any_n = abs(ny) ** n
        for x in range(size):
            nx = (x - a) / a
            if abs(nx) ** n + any_n <= 1.0:
                px[x, y] = 255
    return mask


def _diagonal_gradient(size: int, c_nw: tuple[int, int, int], c_se: tuple[int, int, int]) -> Image.Image:
    """Smooth NW→SE diagonal gradient between two RGB colors."""
    grad = Image.new("RGB", (size, size))
    px = grad.load()
    inv = 1.0 / (2 * (size - 1))
    for y in range(size):
        for x in range(size):
            t = (x + y) * inv  # 0 at top-left, 1 at bottom-right
            # smoothstep so the midband doesn't feel mathematically linear
            t = t * t * (3 - 2 * t)
            r = int(c_nw[0] + (c_se[0] - c_nw[0]) * t)
            g = int(c_nw[1] + (c_se[1] - c_nw[1]) * t)
            b = int(c_nw[2] + (c_se[2] - c_nw[2]) * t)
            px[x, y] = (r, g, b)
    return grad


def _inner_vignette(size: int, strength: int = 38) -> Image.Image:
    """Subtle darkening near the squircle's edge for a touch of depth."""
    vig = Image.new("L", (size, size), 0)
    px = vig.load()
    cx = cy = (size - 1) / 2.0
    max_d = math.hypot(cx, cy)
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - cx, y - cy) / max_d
            # 0 in center, ramps up near edges
            v = max(0.0, (d - 0.55) / 0.45) ** 2
            px[x, y] = int(strength * v)
    return vig


# ---------------------------------------------------------------------------
# Icon composition
# ---------------------------------------------------------------------------

def _quadratic_bezier(
    p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], steps: int
) -> list[tuple[float, float]]:
    pts = []
    for s in range(steps + 1):
        t = s / steps
        omt = 1 - t
        x = omt * omt * p0[0] + 2 * omt * t * p1[0] + t * t * p2[0]
        y = omt * omt * p0[1] + 2 * omt * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def _smooth_polyline_through(points: list[tuple[float, float]], steps_per_segment: int = 24) -> list[tuple[float, float]]:
    """Smooth path through N points using midpoint-anchored quadratic Béziers.

    Each interior point is treated as a control point; adjacent segment midpoints
    are the on-curve anchors. Tangent continuity at every original point, no
    overshoot, no extra dependencies.
    """
    if len(points) < 3:
        return list(points)
    path: list[tuple[float, float]] = [points[0]]
    for i in range(1, len(points) - 1):
        a = points[i - 1]
        b = points[i]
        c = points[i + 1]
        m1 = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        m2 = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        # Skip the first repeat of m1 after the first iteration
        seg = _quadratic_bezier(m1, b, m2, steps_per_segment)
        path.extend(seg if i == 1 else seg[1:])
    path.append(points[-1])
    return path


def _stroked_polyline(
    layer: Image.Image,
    pts: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int,
) -> None:
    """Draw a smooth polyline. PIL's line() handles joins poorly at low alpha,
    so we draw it onto a fresh layer and composite."""
    tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.line(pts, fill=color, width=width, joint="curve")
    # Round caps: draw small filled circles at every vertex of the polyline.
    r = max(1, width // 2)
    for x, y in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    layer.alpha_composite(tmp)


def _soft_drop_shadow(layer: Image.Image, blur: int, opacity: int) -> Image.Image:
    """Return an RGBA shadow layer (black, blurred) shaped by `layer`'s alpha."""
    alpha = layer.split()[3]
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda p: min(opacity, int(p * (opacity / 255)))))
    return shadow.filter(ImageFilter.GaussianBlur(radius=blur))


def render_app_icon(size: int = 1024) -> Image.Image:
    W = H = size

    # 1) Squircle background --------------------------------------------------
    mask = _squircle_mask(W, n=5.0)
    c_nw = (54, 42, 118)   # deep indigo
    c_se = (118, 52, 112)  # plum, slightly desaturated so it doesn't fight the story arc
    grad = _diagonal_gradient(W, c_nw, c_se).convert("RGBA")

    # Subtle inner vignette so the icon doesn't look like a flat sticker.
    vig = _inner_vignette(W, strength=42)
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    dark.putalpha(vig)
    grad = Image.alpha_composite(grad, dark)

    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    base.paste(grad, (0, 0), mask)

    # 2) Story arc geometry ---------------------------------------------------
    # Five story-event nodes following a gentle narrative arc: shallow rise,
    # late climax, falling resolution. Y values are deliberately not symmetric;
    # a perfectly symmetric arc reads as a graph, not a story.
    story_norm = [
        (0.16, 0.46),  # opening
        (0.32, 0.38),  # rising
        (0.50, 0.32),  # turn / inciting
        (0.68, 0.34),  # climax (slightly past center)
        (0.84, 0.44),  # resolution
    ]

    # Recall echoes: smaller dimmer nodes below the arc, distributed widely so
    # the bottom half has visual weight comparable to the top. Some sit
    # directly under a story node (matched, drawn with a connecting line);
    # some are offset (unmatched / paraphrased / out-of-order).
    recall_norm = [
        (0.16, 0.74, True),   # matched to opening
        (0.28, 0.80, False),  # offset between events 1–2
        (0.42, 0.78, False),  # offset between events 2–3
        (0.50, 0.74, True),   # matched to the turn
        (0.62, 0.80, False),  # offset (climax remembered slightly early)
        (0.74, 0.78, False),  # offset between events 4–5
        (0.84, 0.74, True),   # matched to resolution
    ]

    def to_px(nx: float, ny: float) -> tuple[float, float]:
        return (nx * W, ny * H)

    story_pts = [to_px(x, y) for x, y in story_norm]
    recall_pts = [(to_px(x, y), matched) for x, y, matched in recall_norm]

    # 3) Foreground composition layer ----------------------------------------
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Match lines from each matched recall node up to its story node. Drawn
    # first so the nodes overlap them at both ends — the line visually
    # terminates inside the node rather than at the rim, which reads as
    # "linked" rather than "approaching".
    match_color = (255, 240, 230, 110)
    match_w = max(2, W // 280)
    story_r_for_clip = W * 0.045
    recall_r_for_clip = W * 0.022
    for (rx, ry), matched in recall_pts:
        if not matched:
            continue
        sx, sy = min(story_pts, key=lambda p: abs(p[0] - rx))
        # Trim the line so it starts/ends just inside each node — eliminates the
        # disconnected-tick look from v1.
        _stroked_polyline(
            fg,
            [(rx, ry - recall_r_for_clip * 0.2), (sx, sy + story_r_for_clip * 0.4)],
            match_color,
            match_w,
        )

    # Smooth narrative arc through the 5 story nodes.
    arc_path = _smooth_polyline_through(story_pts, steps_per_segment=32)
    arc_w = max(6, int(W * 0.012))
    # Soft outer halo on the arc — gives the line a luminous quality at any size.
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _stroked_polyline(halo, arc_path, (255, 235, 215, 60), arc_w + 6)
    halo = halo.filter(ImageFilter.GaussianBlur(radius=max(2, W // 220)))
    fg.alpha_composite(halo)
    _stroked_polyline(fg, arc_path, (255, 246, 232, 230), arc_w)

    # 4) Recall (small) nodes -------------------------------------------------
    recall_r = W * 0.020
    for (rx, ry), matched in recall_pts:
        a_fill = 215 if matched else 150
        a_ring = 110 if matched else 70
        # outer glow
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gr = recall_r + W * 0.012
        gd.ellipse((rx - gr, ry - gr, rx + gr, ry + gr), fill=(255, 245, 230, 38))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=max(2, W // 220)))
        fg.alpha_composite(glow)
        dr = ImageDraw.Draw(fg)
        dr.ellipse(
            (rx - recall_r, ry - recall_r, rx + recall_r, ry + recall_r),
            fill=(255, 246, 232, a_fill),
            outline=(255, 220, 200, a_ring),
            width=max(1, W // 512),
        )

    # 5) Story (large) nodes — drawn last so they sit on top of the arc -------
    story_r = W * 0.045
    inner_r = story_r * 0.35
    for sx, sy in story_pts:
        # outer halo
        for halo_r, halo_a in ((story_r + W * 0.030, 18), (story_r + W * 0.014, 38)):
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(g)
            gd.ellipse((sx - halo_r, sy - halo_r, sx + halo_r, sy + halo_r), fill=(255, 245, 230, halo_a))
            g = g.filter(ImageFilter.GaussianBlur(radius=max(3, W // 160)))
            fg.alpha_composite(g)
        dr = ImageDraw.Draw(fg)
        # ring + fill
        dr.ellipse(
            (sx - story_r, sy - story_r, sx + story_r, sy + story_r),
            fill=(255, 248, 238, 255),
        )
        # inner colored dot — same plum as the gradient's SE so it reads as
        # "story = same color family, distilled".
        dr.ellipse(
            (sx - inner_r, sy - inner_r, sx + inner_r, sy + inner_r),
            fill=(122, 48, 110, 255),
        )

    # 6) Compose: base + soft shadow under fg + fg, all clipped to the squircle.
    shadow = _soft_drop_shadow(fg, blur=max(3, W // 200), opacity=80)
    shadow_offset = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow_offset.paste(shadow, (0, max(2, W // 256)))
    out = Image.alpha_composite(base, shadow_offset)
    out = Image.alpha_composite(out, fg)

    # Clip everything to the squircle silhouette.
    alpha = out.split()[3]
    alpha = ImageChops.multiply(alpha, mask)
    out.putalpha(alpha)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Render narRater app-icon.png (story arc + recall echoes)")
    ap.add_argument("--size", type=int, default=1024, help="Square size in pixels (default: 1024)")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output PNG path (default: <repo>/static/app-icon.png)",
    )
    ap.add_argument(
        "--also-bundle",
        action="store_true",
        help="Also overwrite narRater.app/Contents/Resources/AppIcon.png",
    )
    args = ap.parse_args()
    outp = args.out if args.out else _repo_root() / "static" / "app-icon.png"
    outp.parent.mkdir(parents=True, exist_ok=True)
    im = render_app_icon(size=max(256, args.size))
    im.save(outp, format="PNG", optimize=True)
    print(f"Wrote {outp} ({im.size[0]}×{im.size[1]})")
    if args.also_bundle:
        bundle = _repo_root() / "narRater.app" / "Contents" / "Resources" / "AppIcon.png"
        if bundle.parent.exists():
            im.save(bundle, format="PNG", optimize=True)
            print(f"Wrote {bundle}")
        else:
            print(f"(skipped {bundle} — bundle not present)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
