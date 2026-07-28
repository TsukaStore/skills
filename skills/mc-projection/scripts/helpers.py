"""Shared helpers for generating and editing .litematic files.

Coordinate model (litemapy):
  Block positions from reg[x,y,z] / allblockpos() are **region-local**.
  Size may be negative in dumped files; minx()/maxx() describe the local span.
  When we rebuild a region we always emit **positive sizes** with content in
  0..w-1 so entity positions stay aligned with blocks.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from litemapy import BlockState, Region, Schematic
from litemapy.minecraft import Entity, TileEntity
from nbtlib import Int, IntArray

AIR_IDS = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})
NS = "minecraft:"


# --- ids / block states -----------------------------------------------------

def ns(block_id: str) -> str:
    block_id = block_id.strip()
    return block_id if ":" in block_id else NS + block_id


def short_id(block_id: str) -> str:
    return block_id.split(":", 1)[-1].split("[", 1)[0]


def parse_block(spec: str) -> BlockState:
    """Parse 'oak_fence', 'minecraft:stone', or 'oak_stairs[facing=east,half=bottom]'."""
    spec = spec.strip()
    props: dict[str, str] = {}
    m = re.fullmatch(r"([^\[\]]+)(?:\[(.*)\])?", spec)
    if not m:
        raise ValueError(f"invalid block spec: {spec!r}")
    bid, prop_str = m.group(1), m.group(2)
    if prop_str:
        for part in prop_str.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"bad property in {spec!r}: {part!r}")
            k, v = part.split("=", 1)
            props[k.strip()] = v.strip().strip("'\"")
    return BlockState(ns(bid), **props)


def is_air(bs: BlockState) -> bool:
    return bs.id in AIR_IDS


# --- bounds -----------------------------------------------------------------

def region_local_bounds(reg: Region) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Inclusive local min/max of the declared volume."""
    return (reg.minx(), reg.miny(), reg.minz()), (reg.maxx(), reg.maxy(), reg.maxz())


def occupied_voxels(reg: Region) -> dict[tuple[int, int, int], BlockState]:
    out = {}
    for pos in reg.allblockpos():
        bs = reg[pos[0], pos[1], pos[2]]
        if not is_air(bs):
            out[pos] = bs
    return out


def occupied_bounds(
    voxels: dict[tuple[int, int, int], BlockState] | Iterable[tuple[int, int, int]],
) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    if isinstance(voxels, dict):
        keys = list(voxels.keys())
    else:
        keys = list(voxels)
    if not keys:
        return None
    xs = [p[0] for p in keys]
    ys = [p[1] for p in keys]
    zs = [p[2] for p in keys]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def schematic_occupied_bounds(
    schem: Schematic,
) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    mins = maxs = None
    for reg in schem.regions.values():
        b = occupied_bounds(occupied_voxels(reg))
        if b is None:
            continue
        lo, hi = b
        if mins is None:
            mins, maxs = list(lo), list(hi)
        else:
            for i in range(3):
                mins[i] = min(mins[i], lo[i])
                maxs[i] = max(maxs[i], hi[i])
    if mins is None:
        return None
    return tuple(mins), tuple(maxs)  # type: ignore[return-value]


def contains_local(reg: Region, x: int, y: int, z: int) -> bool:
    return (
        reg.minx() <= x <= reg.maxx()
        and reg.miny() <= y <= reg.maxy()
        and reg.minz() <= z <= reg.maxz()
    )


# --- entities / tile entities -----------------------------------------------

def shift_entity(ent: Entity, dx: float, dy: float, dz: float) -> None:
    x, y, z = ent.position
    ent.position = (x + dx, y + dy, z + dz)
    data = ent.data
    for key, d in (("TileX", dx), ("TileY", dy), ("TileZ", dz)):
        if key in data:
            data[key] = Int(int(data[key]) + int(d))
    if "block_pos" in data:
        bp = data["block_pos"]
        data["block_pos"] = IntArray([
            Int(int(bp[0]) + int(dx)),
            Int(int(bp[1]) + int(dy)),
            Int(int(bp[2]) + int(dz)),
        ])


def shift_tile_entity(te: TileEntity, dx: int, dy: int, dz: int) -> None:
    x, y, z = te.position
    te.position = (x + dx, y + dy, z + dz)


def clone_entity(ent: Entity) -> Entity:
    return Entity.from_nbt(ent.to_nbt())


def clone_tile_entity(te: TileEntity) -> TileEntity:
    return TileEntity.from_nbt(te.to_nbt())


def store_to_local(reg: Region, x: int, y: int, z: int) -> tuple[int, int, int]:
    """Convert storage/array indices → region-local coords.

    litemapy leaves TileEntity x/y/z as raw NBT values. With **negative** size
    those are 0-based storage indices, while block access uses local coords
    (often negative). Entities use local coords already.
    """
    if reg.width < 0:
        x = x + reg.width + 1
    if reg.height < 0:
        y = y + reg.height + 1
    if reg.length < 0:
        z = z + reg.length + 1
    return x, y, z


def tile_entity_local_pos(reg: Region, te: TileEntity) -> tuple[int, int, int]:
    return store_to_local(reg, *te.position)


# --- region rebuild (always positive size, 0-based local) -------------------

def rebuild_region(
    reg: Region,
    cover_min: tuple[int, int, int],
    cover_max: tuple[int, int, int],
) -> tuple[Region, tuple[int, int, int]]:
    """Rebuild into Region(0,0,0,+w,+h,+l) covering cover_min..cover_max (old local).

    Returns (new_region, offset) where offset is the vector added to old local
    coords to get new local coords: new = old + offset, with offset = -cover_min.
    Entities/TEs are copied and shifted by the same offset.
    Output region always has positive size so TE coords == local == storage.
    """
    ox, oy, oz = cover_min
    w = cover_max[0] - cover_min[0] + 1
    h = cover_max[1] - cover_min[1] + 1
    l = cover_max[2] - cover_min[2] + 1
    if w <= 0 or h <= 0 or l <= 0:
        raise ValueError(f"invalid cover volume {cover_min}..{cover_max}")

    new = Region(0, 0, 0, w, h, l)
    offset = (-ox, -oy, -oz)

    for (x, y, z), bs in occupied_voxels(reg).items():
        if not (cover_min[0] <= x <= cover_max[0]
                and cover_min[1] <= y <= cover_max[1]
                and cover_min[2] <= z <= cover_max[2]):
            continue
        new[x + offset[0], y + offset[1], z + offset[2]] = bs

    for ent in reg.entities:
        e2 = clone_entity(ent)
        shift_entity(e2, *offset)
        new.entities.append(e2)

    for te in reg.tile_entities:
        lx, ly, lz = tile_entity_local_pos(reg, te)
        if not (cover_min[0] <= lx <= cover_max[0]
                and cover_min[1] <= ly <= cover_max[1]
                and cover_min[2] <= lz <= cover_max[2]):
            continue
        t2 = clone_tile_entity(te)
        # set absolute local position in the new positive-size region
        t2.position = (lx + offset[0], ly + offset[1], lz + offset[2])
        new.tile_entities.append(t2)

    return new, offset


def ensure_cover(
    reg: Region,
    need_min: tuple[int, int, int],
    need_max: tuple[int, int, int],
) -> tuple[Region, tuple[int, int, int]]:
    """Ensure declared volume covers need_*; rebuild (0-based) if not.

    Returns (region, offset_from_original_local). offset is (0,0,0) if unchanged.
    """
    dmin, dmax = region_local_bounds(reg)
    fits = all(need_min[i] >= dmin[i] and need_max[i] <= dmax[i] for i in range(3))
    # Also rebuild if sizes are negative — positive 0-based is safer for further writes
    positive = reg.width > 0 and reg.height > 0 and reg.length > 0
    origin_zero = dmin == (0, 0, 0)
    if fits and positive and origin_zero:
        return reg, (0, 0, 0)

    cover_min = tuple(min(dmin[i], need_min[i]) for i in range(3))
    cover_max = tuple(max(dmax[i], need_max[i]) for i in range(3))
    # If region has empty air margins outside occupied, still cover declared so we
    # don't surprise-crop; cover_min/max already use declared bounds.
    return rebuild_region(reg, cover_min, cover_max)  # type: ignore[arg-type]


def replace_blocks_by_id(
    reg: Region,
    from_id: str,
    to: BlockState | str,
    *,
    keep_properties: bool = False,
) -> int:
    """Replace every block whose id matches from_id. Returns count of cells."""
    from_id = ns(from_id)
    to_bs = parse_block(to) if isinstance(to, str) else to

    count = sum(
        1 for pos in reg.allblockpos()
        if reg[pos[0], pos[1], pos[2]].id == from_id
    )

    def mapper(bs: BlockState) -> BlockState:
        if bs.id != from_id:
            return bs
        if keep_properties:
            props = bs.properties()
            if not isinstance(props, dict):
                try:
                    props = dict(props)
                except Exception:
                    props = {}
            return BlockState(to_bs.id, **{k: str(v) for k, v in props.items()})
        return to_bs

    reg.filter(mapper)
    return count


def put_region(schem: Schematic, name: str, reg: Region) -> None:
    if name in schem.regions:
        del schem.regions[name]
    schem.regions[name] = reg


def each_region(schem: Schematic):
    yield from list(schem.regions.items())


def load_schematic(path: str) -> Schematic:
    return Schematic.load(path)


# --- geometry primitives ----------------------------------------------------

def fence_state(
    north: bool = False,
    south: bool = False,
    east: bool = False,
    west: bool = False,
    block: str = "oak_fence",
    waterlogged: bool = False,
) -> BlockState:
    return BlockState(
        ns(block),
        waterlogged="true" if waterlogged else "false",
        north="true" if north else "false",
        south="true" if south else "false",
        east="true" if east else "false",
        west="true" if west else "false",
    )


def set_if_air(reg: Region, x: int, y: int, z: int, bs: BlockState) -> bool:
    if is_air(reg[x, y, z]):
        reg[x, y, z] = bs
        return True
    return False


def fill_box(
    reg: Region,
    x0: int, y0: int, z0: int,
    x1: int, y1: int, z1: int,
    bs: BlockState,
    *,
    hollow: bool = False,
    only_air: bool = False,
) -> int:
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    n = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                if hollow and not (x in (x0, x1) or y in (y0, y1) or z in (z0, z1)):
                    continue
                if only_air and not is_air(reg[x, y, z]):
                    continue
                reg[x, y, z] = bs
                n += 1
    return n


def draw_walls(
    reg: Region,
    x0: int, z0: int, x1: int, z1: int,
    y0: int, y1: int,
    bs: BlockState,
    *,
    only_air: bool = True,
) -> int:
    x0, x1 = min(x0, x1), max(x0, x1)
    z0, z1 = min(z0, z1), max(z0, z1)
    y0, y1 = min(y0, y1), max(y0, y1)
    n = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            for z in (z0, z1):
                if only_air:
                    n += int(set_if_air(reg, x, y, z, bs))
                else:
                    reg[x, y, z] = bs
                    n += 1
        for z in range(z0 + 1, z1):
            for x in (x0, x1):
                if only_air:
                    n += int(set_if_air(reg, x, y, z, bs))
                else:
                    reg[x, y, z] = bs
                    n += 1
    return n


def perimeter_positions(
    x0: int, z0: int, x1: int, z1: int, y: int,
) -> list[tuple[int, int, int]]:
    x0, x1 = min(x0, x1), max(x0, x1)
    z0, z1 = min(z0, z1), max(z0, z1)
    pos: set[tuple[int, int, int]] = set()
    for x in range(x0, x1 + 1):
        pos.add((x, y, z0))
        pos.add((x, y, z1))
    for z in range(z0 + 1, z1):
        pos.add((x0, y, z))
        pos.add((x1, y, z))
    return sorted(pos)


def draw_fence_ring(
    reg: Region,
    x0: int, z0: int, x1: int, z1: int,
    y: int,
    *,
    block: str = "oak_fence",
    only_air: bool = True,
    gate: str | None = None,
    gate_block: str = "oak_fence_gate",
) -> int:
    positions = perimeter_positions(x0, z0, x1, z1, y)
    pos_set = set(positions)

    gate_pos = None
    if gate:
        gx0, gz0 = min(x0, x1), min(z0, z1)
        gx1, gz1 = max(x0, x1), max(z0, z1)
        mx, mz = (gx0 + gx1) // 2, (gz0 + gz1) // 2
        g = gate.lower()
        gate_pos = {
            "north": (mx, y, gz0),
            "south": (mx, y, gz1),
            "west": (gx0, y, mz),
            "east": (gx1, y, mz),
        }.get(g)
        if gate_pos is None:
            raise ValueError(f"gate must be north|south|east|west, got {gate!r}")

    n = 0
    for x, yy, z in positions:
        if only_air and not is_air(reg[x, yy, z]):
            continue
        if gate_pos and (x, yy, z) == gate_pos:
            facing = {"north": "south", "south": "north", "west": "east", "east": "west"}[gate.lower()]
            reg[x, yy, z] = BlockState(
                ns(gate_block),
                facing=facing, open="false", powered="false", in_wall="false",
            )
            n += 1
            continue
        reg[x, yy, z] = fence_state(
            north=(x, yy, z - 1) in pos_set,
            south=(x, yy, z + 1) in pos_set,
            west=(x - 1, yy, z) in pos_set,
            east=(x + 1, yy, z) in pos_set,
            block=block,
        )
        n += 1
    return n


def draw_floor(
    reg: Region,
    x0: int, z0: int, x1: int, z1: int,
    y: int,
    bs: BlockState,
    *,
    only_air: bool = True,
) -> int:
    x0, x1 = min(x0, x1), max(x0, x1)
    z0, z1 = min(z0, z1), max(z0, z1)
    n = 0
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if only_air:
                n += int(set_if_air(reg, x, y, z, bs))
            else:
                reg[x, y, z] = bs
                n += 1
    return n


def draw_simple_roof(
    reg: Region,
    x0: int, z0: int, x1: int, z1: int,
    y_base: int,
    *,
    stairs: str = "oak_stairs",
    ridge: str = "oak_planks",
    axis: str = "x",
) -> int:
    """Gabled roof. axis='x' → ridge along X (slopes face ±z)."""
    x0, x1 = min(x0, x1), max(x0, x1)
    z0, z1 = min(z0, z1), max(z0, z1)
    n = 0
    if axis == "x":
        half = (z1 - z0) // 2
        for i in range(half + 1):
            y = y_base + i
            za, zb = z0 + i, z1 - i
            for x in range(x0, x1 + 1):
                if za == zb:
                    reg[x, y, za] = BlockState(ns(ridge))
                    n += 1
                else:
                    reg[x, y, za] = BlockState(
                        ns(stairs), facing="south", half="bottom",
                        shape="straight", waterlogged="false",
                    )
                    reg[x, y, zb] = BlockState(
                        ns(stairs), facing="north", half="bottom",
                        shape="straight", waterlogged="false",
                    )
                    n += 2
    else:
        half = (x1 - x0) // 2
        for i in range(half + 1):
            y = y_base + i
            xa, xb = x0 + i, x1 - i
            for z in range(z0, z1 + 1):
                if xa == xb:
                    reg[xa, y, z] = BlockState(ns(ridge))
                    n += 1
                else:
                    reg[xa, y, z] = BlockState(
                        ns(stairs), facing="east", half="bottom",
                        shape="straight", waterlogged="false",
                    )
                    reg[xb, y, z] = BlockState(
                        ns(stairs), facing="west", half="bottom",
                        shape="straight", waterlogged="false",
                    )
                    n += 2
    return n
