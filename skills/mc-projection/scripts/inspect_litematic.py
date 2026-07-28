#!/usr/bin/env python3
"""Text-level verification for a .litematic file.

Prints dimensions, region bounds, non-air block count and a materials table.
With --layers, also prints one ASCII map per y-level (top view, +z downward)
so structural details (window holes, floor plans) can be checked numerically.

Usage:
  python inspect_litematic.py build.litematic [--top N] [--layers] [--layer Y]
"""
import argparse
from collections import Counter
from pathlib import Path

from litemapy import Schematic

SYMBOLS = "#@%*=+abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ0123456789"


def collect(schem):
    voxels = {}
    for reg in schem.regions.values():
        for pos in reg.allblockpos():
            bs = reg[pos[0], pos[1], pos[2]]
            if bs.id != "minecraft:air":
                voxels[pos] = bs.id.split(":", 1)[-1]
    if not voxels:
        return voxels, (0, 0, 0), (0, 0, 0)
    mins = tuple(min(p[i] for p in voxels) for i in range(3))
    maxs = tuple(max(p[i] for p in voxels) for i in range(3))
    return voxels, mins, maxs


def main():
    ap = argparse.ArgumentParser(description="Inspect a .litematic file")
    ap.add_argument("litematic", type=Path)
    ap.add_argument("--top", type=int, default=15, help="materials table size")
    ap.add_argument("--layers", action="store_true", help="ASCII map of every y-level")
    ap.add_argument("--layer", type=int, default=None, help="ASCII map of one y-level")
    args = ap.parse_args()

    schem = Schematic.load(str(args.litematic))
    voxels, mins, maxs = collect(schem)
    W = maxs[0] - mins[0] + 1
    H = maxs[1] - mins[1] + 1
    L = maxs[2] - mins[2] + 1

    print(f"file: {args.litematic.name}")
    for attr in ("name", "author", "description"):
        val = getattr(schem, attr, None)
        if val:
            print(f"{attr}: {val}")
    print(f"regions: {len(schem.regions)}")
    print(f"schematic size: {schem.width} x {schem.height} x {schem.length}  (W x H x L, declared)")
    print(f"occupied bounds: {mins} .. {maxs}  ({W} x {H} x {L})")
    print(f"non-air blocks: {len(voxels)}")

    counts = Counter(voxels.values())
    print(f"\nmaterials (top {args.top} of {len(counts)}):")
    for bid, n in counts.most_common(args.top):
        print(f"  {bid:<36} x{n}")

    layers = None
    if args.layer is not None:
        layers = [args.layer]
    elif args.layers:
        layers = sorted({p[1] for p in voxels})
    if layers is not None:
        if W > 120 or L > 120:
            print("\n(skipping layer maps: footprint larger than 120x120)")
            return
        legend = {bid: SYMBOLS[i] for i, (bid, _) in
                  enumerate(counts.most_common(len(SYMBOLS)))}
        print("\nlegend: " + "  ".join(f"{sym}={bid}" for bid, sym in legend.items())
              + "  .=air")
        for y in layers:
            solid = sum(1 for p in voxels if p[1] == y)
            print(f"\ny={y} ({solid} blocks)")
            for z in range(mins[2], maxs[2] + 1):
                row = []
                for x in range(mins[0], maxs[0] + 1):
                    bid = voxels.get((x, y, z))
                    row.append(legend.get(bid, "?") if bid else ".")
                print("  " + "".join(row))


if __name__ == "__main__":
    main()
