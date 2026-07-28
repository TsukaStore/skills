---
name: mc-projection
description: Design and generate Minecraft Litematica projection files (.litematic / MC投影) from text descriptions or reference images, using a generate → render → compare loop where the agent visually checks its own build against the request before delivering. Use whenever the user mentions MC投影, 投影文件, litematic, litematica, .litematic, Minecraft schematic/原理图, wants to turn an image or idea into a Minecraft build, make Minecraft pixel art or statues, or create/modify structures for Litematica — even if they just say "make me a projection" without naming the format.
---

# mc-projection

Generate `.litematic` files (Litematica 投影) from a text description or a reference image.

## The core loop: generate → render → look → compare → repeat

A `.litematic` is thousands of invisible voxels. You cannot judge whether the build looks right by reading your own generator code — misplacements only reveal themselves visually. So the central rule of this skill: **never present a `.litematic` you have not looked at.** The bundled renderer turns the file into images you can read and compare against the request; iterate until the render genuinely matches, then deliver.

A typical task takes 2–5 rounds:

1. Write or adjust a generator script (keep sizes and palette as constants at the top so each round is a small edit)
2. Run it → produces the `.litematic`
3. Run `render_preview.py` → read the PNGs
4. Compare against the requirement or reference image — specifically, item by item (see the checklist below)
5. Fix and regenerate. Only stop when the render matches.

Do not rationalize mismatches ("close enough"). If the roof is lopsided or the heart is off-center, the user will see it immediately in game — fix it now, while it's cheap.

## Setup

Requires Python 3 with `pip install litemapy pillow numpy`. Block colors come from `scripts/block_colors.json` (258 full-cube blocks, average colors measured from MC 26.2 textures); the scripts find it next to themselves, so they work from any cwd.

## Step 0 — understand the input

- **Text requirement** → design from scratch. First restate it as a concrete plan: exact dimensions W×H×L, which side is the front, the block palette, and a checklist of every requested feature (door, 2 windows, chimney...). This plan is your comparison baseline in step 3; vague plans produce vague builds.
- **Pixel art / flat image** (sprite, icon, logo, QR code) → use `scripts/voxel_art.py` to quantize pixels to blocks, then verify with `--compare`.
- **Minecraft skin** (head statue, skin wall) → see the skin-UV recipe in `references/design-guide.md`.
- **Real-world photo** → interpret, don't trace: decide the viewing angle, pick 4–8 dominant colors and map them to blocks via `references/palette.md`, then design manually. The fixed-angle iso render won't match the photo's perspective; compare structurally (silhouette, proportions, features) instead of pixel-by-pixel.

## Step 1 — generate

Write a small Python script using litemapy. Keep `references/litemapy-api.md` open for the API and its traps; keep `references/design-guide.md` in mind for proportions, orientation and palette choices (it also explains common pitfalls — read it before your first build).

Key conventions:

- **The front of the build faces +z (south); up is +y.** The preview views assume this, and Litematica users expect to rotate the projection, not rebuild it.
- Build at origin (0,0,0)+ unless there's a reason not to.
- Air is free: skip interior blocks of large statues (hollow shell) to save the user thousands of blocks.

## Step 2 — render and inspect

```bash
python scripts/render_preview.py build.litematic [--compare ref.png]
#  → build_iso.png    isometric (sees +x, +y, +z faces)
#  → build_ortho.png  front / side / top with grid + coordinates
#  → build_compare.png  reference pasted beside the render (with --compare)

python scripts/inspect_litematic.py build.litematic [--layers] [--layer Y]
#  → declared size vs occupied bounds, block count, materials table,
#    optional per-layer ASCII floor plans
```

**Read the PNGs.** Numbers alone won't catch a lopsided roof, and images alone won't catch an off-by-one in height — use both.

## Step 3 — compare honestly

Against the plan (or reference image), check at minimum:

- **Silhouette & proportions** — read W:H:L off the ortho views; eyeball whether it matches the intent
- **Orientation** — is the front really facing +z? door / face on the correct side?
- **Every feature from the checklist** — count them (2 windows? chimney present?)
- **Palette** — does the render's color read match the request? With `--compare`, does it match the source image?
- **Sanity numbers** — declared size and block count from `inspect_litematic.py` within expectations

If anything fails: edit the generator, regenerate, re-render. That's the loop — it's normal.

## Step 4 — deliver

Present together:

- the `.litematic` path
- the iso + ortho preview images
- the materials table (from `inspect_litematic.py`) so the user can gather blocks
- one-line usage note: copy the file into `.minecraft/schematics/`, then in game: Litematica menu (M) → Load Schematics

If the user asks for changes, that's just another trip through the loop — edit the script, don't hand-patch the file.

## Bundled files

| File | Purpose |
|---|---|
| `scripts/render_preview.py` | iso + ortho renders of any `.litematic`; `--compare` pastes a reference image beside the render |
| `scripts/inspect_litematic.py` | text verification: sizes, materials, per-layer floor plans |
| `scripts/voxel_art.py` | image → flat pixel-art `.litematic` (CIELAB nearest block, optional dithering) |
| `scripts/block_colors.json` | measured average colors, 258 full-cube blocks (MC 26.2) |
| `references/litemapy-api.md` | litemapy API quick reference + gotchas — read before writing a generator |
| `references/design-guide.md` | orientation, proportions, palette and structure tips; skin-head recipe; common pitfalls |
| `references/palette.md`, `references/palette_swatch.png` | labeled block-color palette for choosing colors |
