# litemapy quick reference (0.11.x)

```python
from litemapy import Region, BlockState, Schematic
# skill helpers (add scripts/ to sys.path or run from that dir)
from helpers import parse_block, draw_floor, draw_walls, draw_fence_ring, replace_blocks_by_id
```

## Creating a schematic

```python
reg = Region(x, y, z, width, height, length)   # min corner + sizes; length = Z size!
reg[x, y, z] = BlockState("minecraft:stone")   # or reg.setblock(x, y, z, bs)
schem = reg.as_schematic(name="my_build", author="...", description="...")
schem.save("my_build.litematic")
```

- `Region(x, y, z, w, h, l)` — first three are the **minimum corner**, not the center. Third size is **Z**.
- Air is default — never place air; skip those cells.
- Later writes to the same cell win.

## Block states

```python
BlockState("minecraft:oak_stairs", facing="east", half="bottom", shape="straight")
parse_block("oak_stairs[facing=east,half=bottom,shape=straight]")  # helpers
```

All property values are **strings**. litemapy does **not** validate names/values — typos serialize and break in-game. Prefer plain full blocks when unsure.

## Loading / editing

```python
schem = Schematic.load("file.litematic")
reg = list(schem.regions.values())[0]
reg.count_blocks()
list(reg.allblockpos())
reg.minx(), reg.maxx(), reg.miny(), reg.maxy(), reg.minz(), reg.maxz()  # declared volume
bs = reg[x, y, z]          # BlockState; bs.id
reg.replace(old_bs, new_bs)  # exact palette match, O(1)
reg.filter(lambda bs: new_bs if bs.id == "minecraft:stone" else bs)  # by id
reg.entities               # list[Entity]; mutable (.append)
reg.tile_entities          # list[TileEntity]; mutable
```

Prefer skill CLI for common edits:

```bash
python edit_litematic.py replace file.litematic FROM TO
python edit_litematic.py perimeter file.litematic --margin 1 --y 6
```

## Entities & tile entities

- `Entity.position = (x,y,z)` updates NBT `Pos` (region-**local** coords, same as blocks).
- Item frames also store `TileX/Y/Z` and often `block_pos` — use `helpers.shift_entity`.
- `TileEntity.position` reads raw NBT `x/y/z`. With **negative** region size those values are **storage indices** (0-based), not local coords. Use `helpers.tile_entity_local_pos(reg, te)` / `store_to_local` before comparing to blocks.
- After `rebuild_region` the region is always positive-size 0-based, so TE coords == local == storage.
- **Surgical block edits** (`replace` only) leave entities/TEs untouched.
- **perimeter / fill / shift / crop / normalize** rebuild when needed and re-home entities + TEs — use the CLI.

## Expanding a region

Declared volume may not cover a new perimeter. `helpers.ensure_volume(reg, need_min, need_max)` clones into a larger `Region` and copies blocks + entities + TEs when needed. `edit_litematic.py perimeter|fill` call this for you.

## Foreign-file coordinates

Region origins are often **not** `(0,0,0)`. Sizes can be **negative** in metadata; `minx()`/`maxx()` still give inclusive bounds. Always:

1. `inspect_litematic.py` for occupied vs declared bounds
2. Or `edit_litematic.py normalize --crop` before assuming origin-based math

`render_preview.py` offsets occupied voxels to 0 for display only — it does not rewrite the file.

## Gotchas

- `schem.width/height/length` = declared region size; occupied can be smaller.
- Multi-region files work; one region per file is simpler.
- `as_schematic(..., mc_version=…)` default 2975 is fine for current Litematica; loading preserves the file’s `mc_version`.
- Replacing a `Region` inside `schem.regions`: `del schem.regions[name]` then `schem.regions[name] = new_reg` (see `helpers.put_region`).
