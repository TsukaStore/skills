#!/usr/bin/env python3
"""Convert an image into a flat Minecraft pixel-art .litematic.

Each pixel maps to the nearest block color in CIELAB space. Pixels with
alpha < 128 become air, so non-rectangular art keeps its silhouette.

Usage:
  python voxel_art.py art.png --out art.litematic [options]

Options:
  --width W / --height H   target size in blocks (give one, the other follows
                           the aspect ratio; default width 32)
  --orientation vertical|floor   vertical = wall facing +z (default), floor = flat map
  --include f1,f2,...      substring filters on block names, or "all"
                           (default: _wool,_concrete,terracotta)
  --dither                 Floyd-Steinberg dithering in Lab space
  --name NAME              schematic name metadata (default: output filename)
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from litemapy import BlockState, Region

COLORS_PATH = Path(__file__).parent / "block_colors.json"
DEFAULT_INCLUDE = ["_wool", "_concrete", "terracotta"]


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """rgb float array (..., 3) in 0..255 -> CIELAB (D65)."""
    x = rgb / 255.0
    lin = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = (lin @ m.T) / np.array([0.95047, 1.0, 1.08883])
    eps, kap = 0.008856, 903.3
    f = np.where(xyz > eps, np.cbrt(xyz), (kap * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def load_palette(include: list[str]):
    raw = json.loads(COLORS_PATH.read_text())["blocks"]
    if include != ["all"]:
        raw = {k: v for k, v in raw.items()
               if any(f in k for f in include) and "glazed" not in k}
    if not raw:
        raise SystemExit(f"error: no blocks match --include {include}")
    ids = sorted(raw)
    rgbs = np.array([[raw[k]["r"], raw[k]["g"], raw[k]["b"]] for k in ids],
                    dtype=np.float32)
    return ids, srgb_to_lab(rgbs)


def nearest(pixels_lab: np.ndarray, pal_lab: np.ndarray) -> np.ndarray:
    """pixels_lab (N,3) -> indices of nearest palette colors."""
    d = ((pixels_lab[:, None, :] - pal_lab[None, :, :]) ** 2).sum(axis=2)
    return d.argmin(axis=1)


def main():
    ap = argparse.ArgumentParser(description="Image -> pixel-art .litematic")
    ap.add_argument("image", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--orientation", choices=["vertical", "floor"],
                    default="vertical")
    ap.add_argument("--include", type=str, default=",".join(DEFAULT_INCLUDE),
                    help='comma substrings on block names, or "all"')
    ap.add_argument("--dither", action="store_true")
    ap.add_argument("--name", type=str, default=None)
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGBA")
    w0, h0 = img.size
    if args.width and args.height:
        W, H = args.width, args.height
    elif args.width:
        W, H = args.width, max(1, round(h0 * args.width / w0))
    elif args.height:
        W, H = max(1, round(w0 * args.height / h0)), args.height
    else:
        W, H = 32, max(1, round(h0 * 32 / w0))
    resample = Image.NEAREST if (w0 <= 64 and W >= w0) else Image.LANCZOS
    img = img.resize((W, H), resample)

    include = args.include.split(",")
    ids, pal_lab = load_palette(include)
    pal_rgb = None  # lazily used for dithering output

    px = np.array(img, dtype=np.float32)
    rgb, alpha = px[..., :3], px[..., 3]
    solid = alpha >= 128

    if args.dither:
        lab = srgb_to_lab(rgb.reshape(-1, 3)).reshape(H, W, 3)
        choice = np.full((H, W), -1, dtype=int)
        for y in range(H):
            for x in range(W):
                if not solid[y, x]:
                    continue
                i = int(((pal_lab - lab[y, x]) ** 2).sum(axis=1).argmin())
                choice[y, x] = i
                err = lab[y, x] - pal_lab[i]
                for dx, dy, w_ in ((1, 0, 7 / 16), (-1, 1, 3 / 16),
                                   (0, 1, 5 / 16), (1, 1, 1 / 16)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < W and 0 <= ny < H:
                        lab[ny, nx] += err * w_
    else:
        flat = rgb.reshape(-1, 3)
        choice = np.full(W * H, -1, dtype=int)
        idx = np.where(solid.reshape(-1))[0]
        choice[idx] = nearest(srgb_to_lab(flat[idx]), pal_lab)
        choice = choice.reshape(H, W)

    if args.orientation == "vertical":
        reg = Region(0, 0, 0, W, H, 1)
    else:
        reg = Region(0, 0, 0, W, 1, H)
    counts = Counter()
    for v in range(H):
        for u in range(W):
            if choice[v, u] < 0:
                continue
            bid = ids[choice[v, u]]
            counts[bid] += 1
            if args.orientation == "vertical":
                reg[u, H - 1 - v, 0] = BlockState(bid)  # image top = max y
            else:
                reg[u, 0, v] = BlockState(bid)          # image top = z=0

    name = args.name or args.out.stem
    schem = reg.as_schematic(
        name=name, author="mc-projection skill",
        description=(f"Pixel art from {args.image.name}; {W}x{H} "
                     f"{args.orientation}; palette filter: {args.include}"))
    schem.save(str(args.out))

    print(f"saved {args.out} ({W}x{H} {args.orientation}, "
          f"{sum(counts.values())} blocks, {len(counts)} materials)")
    for bid, n in counts.most_common(10):
        print(f"  {bid:<32} x{n}")


if __name__ == "__main__":
    main()
