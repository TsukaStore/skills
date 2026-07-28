# Design guide for Minecraft builds

Practical knowledge for turning a request into a good-looking `.litematic`. Read before the first build; skim later.

## Orientation and coordinates

- **+y is up. Front faces +z (south). +x is east** (screen-right when looking at the front).
- Iso preview shows +y / +z / +x — the “hero angle”.
- Ortho: front = x right, y up; top = map style (+z down-screen).
- Existing dumps may sit at arbitrary origins — inspect or `normalize` before editing by hand.

## Scale and proportions

- Readable features need blocks: window ≥2×2, face ≥8×8, door 1×2 (or 2×3 double look).
- Cozy house ~9×7 walls; lighthouse reads from 20+ tall.
- Walls 1 block thick. Statues ≳16³ → hollow shell.
- Compress real-world proportions (ceilings 3–4); exaggerate the request’s focus features.

## Palette

- 3–7 colors: main, secondary, accent, roof/foundation.
- `palette.md` / `palette_swatch.png`: 258 measured colors.
- Vibrancy: **concrete > wool > terracotta**. Mix within one family for texture.
- Material swaps on existing files: `edit_litematic.py replace` (keep stairs/facing with `--keep-properties` when both sides share properties).

## Structure and depth

- Roof overhang 1 block; stairs for slopes (`helpers.draw_simple_roof`).
- Recess windows/doors 1 block; contrast frames.
- Foundation layer sticking out 1 block.
- Fences, trapdoor shutters, buttons add life cheaply (`draw_fence_ring`, `perimeter` CLI).

## Recipe: head statue from a Minecraft skin

8×8×8 hollow head. Skin PNG (64×64, 1.8+): each 8×8 face —

| face | base (x, y) | overlay (x, y) |
|---|---|---|
| top | (8, 0) | (40, 0) |
| bottom | (16, 0) | (48, 0) |
| right | (0, 8) | (32, 8) |
| front | (8, 8) | (40, 8) |
| left | (16, 8) | (48, 8) |
| back | (24, 8) | (56, 8) |

- Alpha-composite hat overlay over base before color match.
- Map faces to the cube shell; edge priority: bottom < top < back < left < right < front.
- Front → z = max, x = u, y = 7 − v (row 0 = top of head).
- CIELAB nearest-block like `voxel_art.py` (`srgb_to_lab` / palette load).
- Skin URL: Mojang profile → session → base64 textures → `SKIN.url`. Send `User-Agent`; cache PNG.

## Editing existing machines / farms

- Prefer **CLI replace/perimeter/fill** over rebuilding.
- After edits, `inspect` entity + tile_entity counts; item frames with custom names are easy to miss visually.
- Preview colors include hoppers, chests, pistons, observers, etc. — still approximate; ortho + layer ASCII for wiring.

## Common pitfalls

- **Front facing wrong way** — #1 iteration trigger; door/face on +z.
- **Off-by-one sizes** — “11 wide” ⇒ x ∈ 0..10. Check occupied bounds.
- **Mirrored pixel art** — image row 0 is top (max y).
- **Invalid block states** — silent in file, broken in game.
- **Glass** — full `glass` / stained glass for small windows; panes at large scale.
- **No floor** — hollow house broken in top view.
- **Hand-edit without expand** — perimeter outside declared region needs `ensure_volume` (CLI handles it).
- **Losing TE/entities** — never rebuild a region by only copying blocks if chests/item frames matter.
