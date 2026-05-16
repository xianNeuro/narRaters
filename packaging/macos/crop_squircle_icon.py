#!/usr/bin/env python3
"""
Crop away near-black margins around the app artwork, then pad to a square canvas
(transparent) so the squircle fills icon slots without a visible black frame.

Usage: python3 crop_squircle_icon.py <input.png> <output.png>
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: crop_squircle_icon.py <input.png> <output.png>", file=sys.stderr)
        return 2
    inp, outp = Path(sys.argv[1]), Path(sys.argv[2])
    if not inp.is_file():
        print(f"not found: {inp}", file=sys.stderr)
        return 1

    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print(
            "Pillow and numpy are required to crop the icon. Install with:\n"
            "  pip install Pillow numpy",
            file=sys.stderr,
        )
        return 1

    im = Image.open(inp).convert("RGBA")
    arr = np.array(im)
    rgb = arr[..., :3].astype(np.int16)
    alpha = arr[..., 3]
    lum = rgb.sum(axis=2)
    h, w = lum.shape
    # Letterboxing is often opaque black. A plain luminance mask would either keep the
    # whole frame (if we OR in alpha) or drop intentional black art (if we only use lum).
    # Flood-fill from the image border through "outside" pixels: transparent or near-black.
    bg_lum_max = 48
    transparent_a = 14

    def walkable(i: int, j: int) -> bool:
        return (alpha[i, j] < transparent_a) or (lum[i, j] <= bg_lum_max)

    from collections import deque

    outside = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for i in range(h):
        for j in (0, w - 1):
            if not outside[i, j] and walkable(i, j):
                outside[i, j] = True
                q.append((i, j))
    for j in range(w):
        for i in (0, h - 1):
            if not outside[i, j] and walkable(i, j):
                outside[i, j] = True
                q.append((i, j))
    while q:
        i, j = q.popleft()
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < h and 0 <= nj < w and not outside[ni, nj] and walkable(ni, nj):
                outside[ni, nj] = True
                q.append((ni, nj))

    mask = ~outside
    if not mask.any():
        im.save(outp, format="PNG")
        return 0

    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    cropped = im.crop((x0, y0, x1, y1))

    # Square canvas: transparent padding, squircle centered (Dock / favicons expect square)
    w, h = cropped.size
    side = max(w, h) + 8
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - w) // 2
    oy = (side - h) // 2
    out.paste(cropped, (ox, oy), cropped)
    outp.parent.mkdir(parents=True, exist_ok=True)
    out.save(outp, format="PNG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
