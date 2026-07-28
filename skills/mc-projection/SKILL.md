---
name: mc-projection
description: Design, generate, and edit Minecraft Litematica projection files (.litematic / MC投影) from text, reference images, or existing schematics — using generate/edit → render → compare. Use for MC投影, 投影文件, litematic, litematica, .litematic, schematics, pixel art, statues, or any structure the user wants as a Litematica file.
---

# mc-projection

Produce and modify `.litematic` (Litematica 投影) files.

**Deliverable = only the `.litematic` file.** Preview PNGs and inspect text are for *your* self-check; do not treat them as user-facing deliverables unless the user asks for them.

## The core loop

A `.litematic` is thousands of invisible voxels. **Never present a file you have not rendered and looked at.**

1. Generate (new script / template) **or** edit (CLI / small script)
2. Write/update the `.litematic`
3. `render_preview.py` → read the PNGs
4. `inspect_litematic.py` when sizes, materials, entities, or a floor plan matter
5. Compare against the request; fix and repeat

Typical task: 2–5 rounds. Do not rationalize mismatches.

Script paths below are relative to this skill root (`…/mc-projection/`). Resolve them from the skill install location (project: `.agents/skills/mc-projection/`).

```bash
SKILL=…/mc-projection   # this skill directory
python "$SKILL/scripts/render_preview.py" path/to/build.litematic
python "$SKILL/scripts/inspect_litematic.py" path/to/build.litematic
python "$SKILL/scripts/edit_litematic.py" <subcommand> …
```

## Setup

Python 3 + `pip install litemapy pillow numpy`. Colors: `scripts/block_colors.json` (found next to the scripts).

## Choose a path

| Input | Path |
|---|---|
| New build from text | Generator script (start from `templates/basic_build.py` + `scripts/helpers.py`) |
| Flat pixel art / logo | `scripts/voxel_art.py` |
| Minecraft skin head | Recipe in `references/design-guide.md` |
| **Edit existing** `.litematic` | `scripts/edit_litematic.py` first; only write a custom script if the CLI cannot do it |
| Real-world photo | Interpret (palette + silhouette), do not trace pixels into 3D |

---

## A — Generate from scratch

### A0. Plan before code

Restate as a concrete plan: **W×H×L**, front side (+z), palette (3–7 blocks), feature checklist (door, windows, chimney…). That plan is the compare baseline.

### A1. Write a generator

- Prefer **`templates/basic_build.py`** as a starting point; import **`helpers`** for floor/walls/roof/fence.
- Keep sizes and palette as **constants at the top**.
- API + traps: `references/litemapy-api.md`. Design rules: `references/design-guide.md`.
- Colors: `references/palette.md` / `palette_swatch.png`.

Conventions:

- **Front faces +z (south); +y up; +x east.** Previews assume this.
- Build near origin `(0,0,0)+` for new work. Foreign files may use arbitrary region origins — use inspect / `normalize` before assuming 0-based coords.
- Skip interior fills of large statues (hollow shell).

```python
from litemapy import Region, BlockState
from helpers import draw_floor, draw_walls, draw_simple_roof, draw_fence_ring, parse_block

reg = Region(0, 0, 0, width, height, length)  # length = Z size
reg[x, y, z] = parse_block("oak_planks")
schem = reg.as_schematic(name="…", author="…")
schem.save("build.litematic")
```

### A2. Pixel art

```bash
python scripts/voxel_art.py art.png --out art.litematic [--width 32] [--dither]
python scripts/render_preview.py art.litematic --compare art.png
```

---

## B — Edit an existing projection

**Do not regenerate from nothing** when the user has a file and wants a surgical change. Use the editor:

```bash
# palette swap (id → id)
python scripts/edit_litematic.py replace in.litematic white_stained_glass pink_stained_glass
python scripts/edit_litematic.py replace in.litematic oak_stairs spruce_stairs --keep-properties

# fence ring outside occupied footprint
python scripts/edit_litematic.py perimeter in.litematic --block oak_fence --y 6 --margin 1
python scripts/edit_litematic.py perimeter in.litematic --gate south   # auto y

# box fill
python scripts/edit_litematic.py fill in.litematic --from 0,0,0 --to 5,3,5 --block stone --hollow

# geometry hygiene
python scripts/edit_litematic.py shift in.litematic --by 10,0,-3 -o out.litematic
python scripts/edit_litematic.py crop in.litematic --margin 1
python scripts/edit_litematic.py normalize in.litematic --margin 0 --crop
```

Defaults **overwrite** the input unless `-o` is set. All subcommands preserve **entities** and **tile entities** (positions updated on shift/normalize).

`scripts/helpers.py` is the library behind the CLI — import it for custom edits (expand region, fence ring with connections, etc.) when one CLI call is not enough. Still: edit → render → look.

---

## C — Render, inspect, compare

```bash
python scripts/render_preview.py build.litematic [--compare ref.png] [--out DIR]
#  → build_iso.png   isometric (+x,+y,+z faces)
#  → build_ortho.png front / side / top + grid

python scripts/inspect_litematic.py build.litematic [--top 20] [--layers] [--layer Y]
#  → declared vs occupied bounds, materials, entities, tile-entity summary, ASCII layers
```

**Read the PNGs.** Numbers miss a lopsided roof; images miss an off-by-one height — use both.

Compare checklist:

- Silhouette & proportions (W:H:L from ortho)
- Orientation (front on +z?)
- Every feature on the plan checklist
- Palette / requested material change actually applied
- Entities/TE still present after edits (`inspect`)

---

## D — Deliver

Present **only**:

- Path to the `.litematic`
- One line of usage: copy into `.minecraft/schematics/`, in-game **M** → Load Schematics

Do **not** require README, material lists, or preview images as delivery unless the user asks. Keep previews as your work product (next to the file or in a temp dir).

Further changes = another loop (prefer `edit_litematic.py` for surgical edits).

---

## Bundled files

| Path | Purpose |
|---|---|
| `scripts/edit_litematic.py` | replace / perimeter / fill / shift / crop / normalize |
| `scripts/helpers.py` | block parse, bounds, floor/walls/roof/fence, entity shift, region expand |
| `scripts/render_preview.py` | iso + ortho; machinery-friendly colors |
| `scripts/inspect_litematic.py` | sizes, materials, entities/TE, ASCII layers |
| `scripts/voxel_art.py` | image → flat pixel-art schematic |
| `scripts/block_colors.json` | 258 measured full-cube colors (MC 26.2) |
| `templates/basic_build.py` | minimal house generator to copy |
| `references/litemapy-api.md` | API + edit gotchas |
| `references/design-guide.md` | orientation, proportions, palette, skin recipe, pitfalls |
| `references/palette.md`, `palette_swatch.png` | block color chooser |
