#!/usr/bin/env python3
"""Minimal generator template for a new .litematic.

Copy this file, tweak the constants at the top, run it, then:
  python ../scripts/render_preview.py out.litematic
  python ../scripts/inspect_litematic.py out.litematic

Convention: front faces +z (south), +y up, origin at min corner.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from litemapy import Region, BlockState
from helpers import draw_floor, draw_walls, draw_simple_roof, draw_fence_ring, parse_block

# --- tweak these -----------------------------------------------------------
NAME = "cottage"
AUTHOR = "mc-projection"
# write relative to the process cwd (usually the project root)
OUT = Path("projections") / f"{NAME}.litematic"

# interior footprint (wall outer face sits on these coords)
W, L, WALL_H = 9, 7, 4          # width(x), length(z), wall height
FLOOR_Y = 0
# ---------------------------------------------------------------------------

# region padding: +1 for roof overhang, +2 for fence ring margin
PAD = 2
reg = Region(0, 0, 0, W + 2 * PAD, WALL_H + 6, L + 2 * PAD)

ox, oz = PAD, PAD                 # building origin inside region
x0, z0 = ox, oz
x1, z1 = ox + W - 1, oz + L - 1

planks = parse_block("oak_planks")
log = parse_block("oak_log[axis=y]")
glass = parse_block("glass")
door_lower = parse_block("oak_door[facing=south,half=lower,hinge=left,open=false,powered=false]")
door_upper = parse_block("oak_door[facing=south,half=upper,hinge=left,open=false,powered=false]")

# floor + walls
draw_floor(reg, x0, z0, x1, z1, FLOOR_Y, planks, only_air=False)
draw_walls(reg, x0, z0, x1, z1, FLOOR_Y + 1, FLOOR_Y + WALL_H, planks, only_air=False)

# corner posts
for x, z in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)):
    for y in range(FLOOR_Y, FLOOR_Y + WALL_H + 1):
        reg[x, y, z] = log

# door on +z (front) wall, centered
dx = (x0 + x1) // 2
reg[dx, FLOOR_Y + 1, z1] = door_lower
reg[dx, FLOOR_Y + 2, z1] = door_upper

# two windows on left/right walls
reg[x0, FLOOR_Y + 2, (z0 + z1) // 2] = glass
reg[x1, FLOOR_Y + 2, (z0 + z1) // 2] = glass

# roof + fence
draw_simple_roof(reg, x0 - 1, z0 - 1, x1 + 1, z1 + 1, FLOOR_Y + WALL_H + 1,
                 stairs="oak_stairs", ridge="oak_planks", axis="x")
draw_fence_ring(reg, x0 - 2, z0 - 2, x1 + 2, z1 + 2, FLOOR_Y,
                block="oak_fence", gate="south")

OUT.parent.mkdir(parents=True, exist_ok=True)
schem = reg.as_schematic(name=NAME, author=AUTHOR, description="template cottage")
schem.save(str(OUT))
print(f"wrote {OUT}  blocks={reg.count_blocks()}")
