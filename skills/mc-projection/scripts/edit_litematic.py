#!/usr/bin/env python3
"""Edit existing .litematic files without rewriting a generator.

Subcommands:
  replace     swap one block id for another
  perimeter   fence/wall ring around occupied footprint
  fill        fill an inclusive box with a block
  shift       translate all blocks + entities + tile entities
  crop        shrink to occupied (+ margin), 0-based positive region
  normalize   move occupied min corner to (margin,margin,margin)

All commands preserve entities and tile entities (positions updated when geometry moves).

Usage:
  python edit_litematic.py replace build.litematic white_stained_glass pink_stained_glass
  python edit_litematic.py perimeter build.litematic --block oak_fence --y 6 --margin 1
  python edit_litematic.py fill build.litematic --from 0,0,0 --to 5,2,5 --block stone --hollow
  python edit_litematic.py shift build.litematic --by 10,0,-3 -o out.litematic
  python edit_litematic.py crop build.litematic --margin 1
  python edit_litematic.py normalize build.litematic --margin 0 --crop
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from litemapy import Region

from helpers import (
    clone_entity,
    clone_tile_entity,
    draw_fence_ring,
    each_region,
    ensure_cover,
    fill_box,
    load_schematic,
    occupied_bounds,
    occupied_voxels,
    parse_block,
    put_region,
    rebuild_region,
    region_local_bounds,
    replace_blocks_by_id,
    shift_entity,
    tile_entity_local_pos,
)


def _parse_xyz(s: str) -> tuple[int, int, int]:
    parts = s.replace(" ", "").split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"expected x,y,z got {s!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _out_path(args) -> Path:
    return Path(args.output) if args.output else Path(args.litematic)


def _add_io(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="output path (default: overwrite input)")


def _apply_offset(x: int, y: int, z: int, off: tuple[int, int, int]) -> tuple[int, int, int]:
    return x + off[0], y + off[1], z + off[2]


def cmd_replace(args) -> None:
    schem = load_schematic(str(args.litematic))
    total = 0
    for name, reg in each_region(schem):
        n = replace_blocks_by_id(
            reg, args.from_block, args.to_block, keep_properties=args.keep_properties,
        )
        print(f"region {name!r}: replaced {n}")
        total += n
    out = _out_path(args)
    schem.save(str(out))
    print(f"saved {out}  (total {total})")


def cmd_perimeter(args) -> None:
    schem = load_schematic(str(args.litematic))
    margin = args.margin
    total = 0
    for name, reg in each_region(schem):
        vox = occupied_voxels(reg)
        b = occupied_bounds(vox)
        if b is None:
            print(f"region {name!r}: empty, skip")
            continue
        (minx, miny, minz), (maxx, maxy, maxz) = b
        x0, x1 = minx - margin, maxx + margin
        z0, z1 = minz - margin, maxz + margin

        if args.y is not None:
            fy = args.y
        else:
            yc = Counter(p[1] for p in vox)
            top = [y for y, _ in yc.most_common(5)]
            fy = min(top) if top else miny

        need_min = (x0, min(miny, fy), z0)
        need_max = (x1, max(maxy, fy), z1)
        # cover at least declared volume too so we don't crop air padding unexpectedly
        dmin, dmax = region_local_bounds(reg)
        need_min = tuple(min(need_min[i], dmin[i]) for i in range(3))
        need_max = tuple(max(need_max[i], dmax[i]) for i in range(3))

        new_reg, off = ensure_cover(reg, need_min, need_max)  # type: ignore[arg-type]
        fx0, fy2, fz0 = _apply_offset(x0, fy, z0, off)
        fx1, _, fz1 = _apply_offset(x1, fy, z1, off)
        n = draw_fence_ring(
            new_reg, fx0, fz0, fx1, fz1, fy2,
            block=args.block,
            only_air=not args.overwrite,
            gate=args.gate,
            gate_block=args.gate_block,
        )
        put_region(schem, name, new_reg)
        print(f"region {name!r}: placed {n} at y={fy2}  "
              f"ring x[{fx0}..{fx1}] z[{fz0}..{fz1}]  offset={off}")
        total += n
    out = _out_path(args)
    schem.save(str(out))
    print(f"saved {out}  (total {total})")


def cmd_fill(args) -> None:
    schem = load_schematic(str(args.litematic))
    x0, y0, z0 = args.from_pos
    x1, y1, z1 = args.to_pos
    bs = parse_block(args.block)
    total = 0
    for name, reg in each_region(schem):
        need_min = (min(x0, x1), min(y0, y1), min(z0, z1))
        need_max = (max(x0, x1), max(y0, y1), max(z0, z1))
        dmin, dmax = region_local_bounds(reg)
        need_min = tuple(min(need_min[i], dmin[i]) for i in range(3))
        need_max = tuple(max(need_max[i], dmax[i]) for i in range(3))
        new_reg, off = ensure_cover(reg, need_min, need_max)  # type: ignore[arg-type]
        a = _apply_offset(x0, y0, z0, off)
        b = _apply_offset(x1, y1, z1, off)
        n = fill_box(new_reg, *a, *b, bs, hollow=args.hollow, only_air=args.only_air)
        put_region(schem, name, new_reg)
        print(f"region {name!r}: wrote {n}  offset={off}")
        total += n
    out = _out_path(args)
    schem.save(str(out))
    print(f"saved {out}  (total {total})")


def cmd_shift(args) -> None:
    dx, dy, dz = args.by
    schem = load_schematic(str(args.litematic))
    for name, reg in each_region(schem):
        vox = occupied_voxels(reg)
        # shift in local space then rebuild 0-based covering the shifted content
        shifted = {(x + dx, y + dy, z + dz): bs for (x, y, z), bs in vox.items()}
        b = occupied_bounds(shifted)
        if b is None and not reg.entities and not reg.tile_entities:
            print(f"region {name!r}: empty")
            continue
        if b is None:
            xs, ys, zs = [], [], []
            for ent in reg.entities:
                x, y, z = ent.position
                xs.append(int(x) + dx); ys.append(int(y) + dy); zs.append(int(z) + dz)
            for te in reg.tile_entities:
                x, y, z = tile_entity_local_pos(reg, te)
                xs.append(x + dx); ys.append(y + dy); zs.append(z + dz)
            b = ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))

        (minx, miny, minz), (maxx, maxy, maxz) = b
        # include shifted entity positions in cover
        for ent in reg.entities:
            x, y, z = ent.position
            minx = min(minx, int(x + dx)); maxx = max(maxx, int(x + dx))
            miny = min(miny, int(y + dy)); maxy = max(maxy, int(y + dy))
            minz = min(minz, int(z + dz)); maxz = max(maxz, int(z + dz))
        for te in reg.tile_entities:
            x, y, z = tile_entity_local_pos(reg, te)
            minx = min(minx, x + dx); maxx = max(maxx, x + dx)
            miny = min(miny, y + dy); maxy = max(maxy, y + dy)
            minz = min(minz, z + dz); maxz = max(maxz, z + dz)

        w = maxx - minx + 1
        h = maxy - miny + 1
        l = maxz - minz + 1
        new = Region(0, 0, 0, w, h, l)
        for (x, y, z), bs in shifted.items():
            new[x - minx, y - miny, z - minz] = bs
        for ent in reg.entities:
            e2 = clone_entity(ent)
            shift_entity(e2, dx - minx, dy - miny, dz - minz)
            new.entities.append(e2)
        for te in reg.tile_entities:
            lx, ly, lz = tile_entity_local_pos(reg, te)
            t2 = clone_tile_entity(te)
            t2.position = (lx + dx - minx, ly + dy - miny, lz + dz - minz)
            new.tile_entities.append(t2)
        put_region(schem, name, new)
        print(f"region {name!r}: shifted by ({dx},{dy},{dz}) then origin→0  "
              f"blocks={len(shifted)} entities={len(new.entities)} te={len(new.tile_entities)}")
    out = _out_path(args)
    schem.save(str(out))
    print(f"saved {out}")


def cmd_crop(args) -> None:
    schem = load_schematic(str(args.litematic))
    margin = args.margin
    for name, reg in each_region(schem):
        vox = occupied_voxels(reg)
        b = occupied_bounds(vox)
        if b is None:
            print(f"region {name!r}: empty, skip")
            continue
        (minx, miny, minz), (maxx, maxy, maxz) = b
        for ent in reg.entities:
            x, y, z = ent.position
            minx = min(minx, int(x)); maxx = max(maxx, int(x))
            miny = min(miny, int(y)); maxy = max(maxy, int(y))
            minz = min(minz, int(z)); maxz = max(maxz, int(z))
        for te in reg.tile_entities:
            x, y, z = tile_entity_local_pos(reg, te)
            minx, maxx = min(minx, x), max(maxx, x)
            miny, maxy = min(miny, y), max(maxy, y)
            minz, maxz = min(minz, z), max(maxz, z)
        cover_min = (minx - margin, miny - margin, minz - margin)
        cover_max = (maxx + margin, maxy + margin, maxz + margin)
        new, off = rebuild_region(reg, cover_min, cover_max)
        put_region(schem, name, new)
        print(f"region {name!r}: cropped {new.width}x{new.height}x{new.length}  offset={off}")
    out = _out_path(args)
    schem.save(str(out))
    print(f"saved {out}")


def cmd_normalize(args) -> None:
    """Pad around occupied content; after rebuild occupied min sits at (margin,*)."""
    schem = load_schematic(str(args.litematic))
    margin = args.margin
    for name, reg in each_region(schem):
        vox = occupied_voxels(reg)
        b = occupied_bounds(vox)
        if b is None:
            print(f"region {name!r}: empty, skip")
            continue
        (minx, miny, minz), (maxx, maxy, maxz) = b
        for ent in reg.entities:
            x, y, z = ent.position
            minx = min(minx, int(x)); maxx = max(maxx, int(x))
            miny = min(miny, int(y)); maxy = max(maxy, int(y))
            minz = min(minz, int(z)); maxz = max(maxz, int(z))
        for te in reg.tile_entities:
            x, y, z = tile_entity_local_pos(reg, te)
            minx, maxx = min(minx, x), max(maxx, x)
            miny, maxy = min(miny, y), max(maxy, y)
            minz, maxz = min(minz, z), max(maxz, z)

        cover_min = (minx - margin, miny - margin, minz - margin)
        cover_max = (maxx + margin, maxy + margin, maxz + margin)
        new, off = rebuild_region(reg, cover_min, cover_max)
        put_region(schem, name, new)
        print(f"region {name!r}: normalized → {new.width}x{new.height}x{new.length}  "
              f"offset={off}  entities={len(new.entities)} te={len(new.tile_entities)}")
    out = _out_path(args)
    schem.save(str(out))
    print(f"saved {out}")


def main():
    ap = argparse.ArgumentParser(description="Edit .litematic files")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("replace", help="replace block id A with B")
    p.add_argument("litematic", type=Path)
    p.add_argument("from_block")
    p.add_argument("to_block")
    p.add_argument("--keep-properties", action="store_true")
    _add_io(p)
    p.set_defaults(func=cmd_replace)

    p = sub.add_parser("perimeter", help="fence ring around occupied footprint")
    p.add_argument("litematic", type=Path)
    p.add_argument("--block", default="oak_fence")
    p.add_argument("--y", type=int, default=None)
    p.add_argument("--margin", type=int, default=1)
    p.add_argument("--gate", choices=["north", "south", "east", "west"], default=None)
    p.add_argument("--gate-block", default="oak_fence_gate")
    p.add_argument("--overwrite", action="store_true")
    _add_io(p)
    p.set_defaults(func=cmd_perimeter)

    p = sub.add_parser("fill", help="fill a box")
    p.add_argument("litematic", type=Path)
    p.add_argument("--from", dest="from_pos", type=_parse_xyz, required=True)
    p.add_argument("--to", dest="to_pos", type=_parse_xyz, required=True)
    p.add_argument("--block", required=True)
    p.add_argument("--hollow", action="store_true")
    p.add_argument("--only-air", action="store_true")
    _add_io(p)
    p.set_defaults(func=cmd_fill)

    p = sub.add_parser("shift", help="translate content (result is 0-based)")
    p.add_argument("litematic", type=Path)
    p.add_argument("--by", type=_parse_xyz, required=True)
    _add_io(p)
    p.set_defaults(func=cmd_shift)

    p = sub.add_parser("crop", help="shrink to occupied + margin (0-based)")
    p.add_argument("litematic", type=Path)
    p.add_argument("--margin", type=int, default=0)
    _add_io(p)
    p.set_defaults(func=cmd_crop)

    p = sub.add_parser("normalize", help="re-origin so occupied min is at margin")
    p.add_argument("litematic", type=Path)
    p.add_argument("--margin", type=int, default=0,
                   help="air padding on each side; occupied min becomes this value")
    p.add_argument("--crop", action="store_true",
                   help="accepted for compatibility; normalize always crops to content+margin")
    _add_io(p)
    p.set_defaults(func=cmd_normalize)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
