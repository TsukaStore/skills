# Design guide for Minecraft builds

Practical knowledge for turning a request into a good-looking `.litematic`. Read this before designing your first build; skim the relevant section on later ones.

## Orientation and coordinates

- **+y is up. The build's front should face +z (south). +x is east (screen-right when looking at the front).**
- The iso preview shows the +y (top), +z (front) and +x (east) faces — so with this convention, what you see in `*_iso.png` is the build's "hero angle".
- In the ortho sheet: front view has x increasing to the right and y up; the top view follows map convention (+z downward).

## Scale and proportions

- Features need blocks to be readable: a window wants ≥2×2, a face wants ≥8×8, a door is 1×2 (or 2×3 for a double door look).
- Small builds read as "models", large ones as "structures". A cozy house starts around 9×7 walls; a lighthouse reads well from 20+ tall.
- Walls 1 block thick are normal. For statues larger than ~16³, make the shell hollow — the interior is invisible and the user saves thousands of blocks.
- Real-world proportions don't survive contact with voxels. Compress vertically (ceilings 3–4 blocks), exaggerate the features the request is *about* (the stripes of a lighthouse, the ears of a cat statue).

## Palette

- Pick 3–7 colors: a main material, a secondary, an accent, plus roof/foundation. More colors → noise.
- `references/palette.md` lists all 258 measured block colors grouped by family; `palette_swatch.png` is the same data as a labeled image.
- Color vibrancy ladder: **concrete > wool > terracotta**. Concrete for saturated accents, wool for soft mid-tones, terracotta for muted/natural tones. They mix well within one build.
- For natural texture, vary a surface slightly (e.g. stone bricks + cracked stone bricks + andesite), but keep variation within one color family.

## Structure and depth (avoiding the "cardboard" look)

- Roofs should overhang the walls by 1 block. Stairs make convincing sloped roofs.
- Recess windows and doors 1 block into the wall; frame them with a contrasting material.
- Give buildings a foundation layer (cobble/stone) that sticks out 1 block.
- Chimneys, fences, trapdoor shutters and buttons add life for ~zero blocks.

## Recipe: head statue from a Minecraft skin

An 8×8×8 hollow head is the classic. Skin PNG layout (64×64, MC 1.8+): each 8×8 face is at a fixed offset —

| face | base (x, y) | overlay (x, y) |
|---|---|---|
| top | (8, 0) | (40, 0) |
| bottom | (16, 0) | (48, 0) |
| right | (0, 8) | (32, 8) |
| front | (8, 8) | (40, 8) |
| left | (16, 8) | (48, 8) |
| back | (24, 8) | (56, 8) |

- Alpha-composite the overlay ("hat") layer over the base layer before matching colors.
- Map each face's pixels to the cube's shell; where faces share an edge, later writes win. A pleasing priority order is: bottom < top < back < left < right < front.
- Front pixels map to z = max, x = u, y = 7 − v (image row 0 is the top of the head).
- Match colors per-pixel with CIELAB nearest-block, exactly like `voxel_art.py` does — copy its `srgb_to_lab` / palette-loading code into your generator.
- Skin URLs: `https://api.mojang.com/users/profiles/minecraft/<name>` → profile id → `https://sessionserver.mojang.com/session/minecraft/profile/<id>` → base64 `properties[0].value` → `textures.SKIN.url`. Send a `User-Agent` header; cache the PNG locally so rebuilds work offline.

## Common pitfalls (check these in the compare step)

- **Front facing the wrong way** — the #1 iteration trigger. The front door/face must be on the +z side.
- **Off-by-one sizes** — an "11 wide" house is x ∈ 0..10. `inspect_litematic.py` shows declared vs occupied bounds; an unintended air margin shrinks the occupied size.
- **Mirrored art** — in `voxel_art.py`-style vertical art, image row 0 is the *top* (max y); getting this backwards flips the build upside down.
- **Invalid block states** — stairs with a misspelled `facing=` serialize fine but break in game. Prefer plain blocks unless the shape needs the state.
- **Glass choices** — `glass` blocks for windows read cleaner than panes at small scales; panes read better at large scales.
- **Forgetting the floor** — a hollow house with no floor looks broken from the top view.
