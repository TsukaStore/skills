# litemapy quick reference (0.11.x)

```python
from litemapy import Region, BlockState, Schematic
```

## Creating a schematic

```python
reg = Region(x, y, z, width, height, length)   # min corner + sizes; length = Z size!
reg[x, y, z] = BlockState("minecraft:stone")   # or reg.setblock(x, y, z, bs)
schem = reg.as_schematic(name="my_build", author="...", description="...")
schem.save("my_build.litematic")
```

- `Region(x, y, z, w, h, l)` — the first three are the minimum corner, **not** the center. The third size argument is called `length` and is the **Z** size.
- Air is the default everywhere — never place air, just skip those positions.
- Writing the same position twice: the later write wins.

## Block states with properties

```python
BlockState("minecraft:oak_stairs", facing="east", half="bottom", shape="straight")
BlockState("minecraft:oak_slab", type="top")
BlockState("minecraft:glass_pane", north="true", south="true")
BlockState("minecraft:oak_door", facing="south", half="lower", hinge="left")
```

All property values are strings. **litemapy does not validate property names or values** — a typo silently serializes, and Litematica may render the block as missing/default. Double-check against the [Minecraft wiki block-state lists](https://minecraft.wiki) when using non-trivial states. When in doubt, prefer plain full blocks; they're always valid.

## Loading and verifying

```python
schem = Schematic.load("file.litematic")
schem.width, schem.height, schem.length      # declared dims (max over regions)
schem.regions                                # dict: name -> Region
reg = list(schem.regions.values())[0]
reg.count_blocks()                           # non-air block count
reg.allblockpos()                            # iterator of (x, y, z) positions
reg.minx(), reg.maxx(), ...                  # occupied bounds per region
bs = reg[x, y, z]                            # BlockState; bs.id, bs.properties
schem.name, schem.author, schem.description  # metadata
```

## Gotchas

- **Region coordinates are region-absolute.** If a schematic was saved with its min corner at (100, 64, -40), positions from `allblockpos()` live around those coordinates. Offset by the min before assuming 0-based indexing (the bundled `render_preview.py` does this for you).
- `schem.width/height/length` reflect the declared region size; the *occupied* bounds can be smaller if there are air margins. `inspect_litematic.py` prints both.
- Non-full blocks (slabs, stairs, panes, doors) are perfectly valid in a `.litematic` — they just aren't in `block_colors.json`, so the preview renderer approximates their color from their base block and notes unknown ids on stdout.
- Multiple regions per schematic are supported by the format, but one region per file keeps everything simpler (and is what Litematica creates by default).
- `as_schematic(..., mc_version=...)` defaults to 2975; the default is fine for current Litematica.
