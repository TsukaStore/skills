#!/usr/bin/env python3
"""Text-level verification for a .litematic file.

Prints dimensions, region bounds, non-air block count, materials table,
entities / tile-entities summary. Optional per-layer ASCII floor plans.

Usage:
  python inspect_litematic.py build.litematic [--top N] [--layers] [--layer Y]
"""
import argparse
from collections import Counter
from pathlib import Path

from litemapy import Schematic

SYMBOLS = "#@%*=+abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ0123456789"


def _te_local(reg, te):
    """TileEntity NBT x/y/z are storage indices when region size is negative."""
    x, y, z = te.position
    if reg.width < 0:
        x = x + reg.width + 1
    if reg.height < 0:
        y = y + reg.height + 1
    if reg.length < 0:
        z = z + reg.length + 1
    return x, y, z


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


def _entity_label(ent) -> str:
    eid = ent.id.split(":", 1)[-1] if ent.id else "?"
    extra = ""
    data = ent.data
    if "Item" in data:
        item = data["Item"]
        iid = str(item.get("id", "?"))
        name = None
        comps = item.get("components") or item.get("tag")
        if comps is not None and "minecraft:custom_name" in comps:
            name = str(comps["minecraft:custom_name"])
        extra = f" item={iid.split(':',1)[-1]}"
        if name:
            extra += f" name={name}"
    x, y, z = ent.position
    return f"{eid} @ ({x:.1f},{y:.1f},{z:.1f}){extra}"


def _te_label(te, block_at, pos=None) -> str:
    x, y, z = pos if pos is not None else te.position
    bid = block_at.get((x, y, z), "?")
    tid = None
    if "id" in te.data:
        tid = str(te.data["id"]).split(":", 1)[-1]
    label = tid or bid
    return f"{label} @ ({x},{y},{z})"


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
    for rname, reg in schem.regions.items():
        print(f"  region {rname!r}: declared "
              f"({reg.minx()},{reg.miny()},{reg.minz()}).."
              f"({reg.maxx()},{reg.maxy()},{reg.maxz()})  "
              f"{abs(reg.width)}x{abs(reg.height)}x{abs(reg.length)}")
    print(f"schematic size: {schem.width} x {schem.height} x {schem.length}  (W x H x L, declared)")
    print(f"occupied bounds: {mins} .. {maxs}  ({W} x {H} x {L})")
    print(f"non-air blocks: {len(voxels)}")

    counts = Counter(voxels.values())
    print(f"\nmaterials (top {args.top} of {len(counts)}):")
    for bid, n in counts.most_common(args.top):
        print(f"  {bid:<36} x{n}")

    # entities / tile entities
    n_ent = sum(len(r.entities) for r in schem.regions.values())
    n_te = sum(len(r.tile_entities) for r in schem.regions.values())
    print(f"\nentities: {n_ent}")
    for reg in schem.regions.values():
        for ent in reg.entities:
            print(f"  - {_entity_label(ent)}")
    print(f"tile_entities: {n_te}")
    if n_te:
        te_kinds = Counter()
        for reg in schem.regions.values():
            for te in reg.tile_entities:
                x, y, z = _te_local(reg, te)
                bid = voxels.get((x, y, z), "?")
                if "id" in te.data:
                    bid = str(te.data["id"]).split(":", 1)[-1]
                te_kinds[bid] += 1
        for k, n in te_kinds.most_common(20):
            print(f"  {k:<36} x{n}")
        if n_te <= 12:
            for reg in schem.regions.values():
                for te in reg.tile_entities:
                    print(f"  - {_te_label(te, voxels, _te_local(reg, te))}")

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
