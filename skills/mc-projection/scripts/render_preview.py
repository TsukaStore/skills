#!/usr/bin/env python3
"""Render preview images of a .litematic file for visual self-checking.

Outputs (written next to the input file, or to --out dir):
  <name>_iso.png    isometric render (camera sees +x, +y, +z faces)
  <name>_ortho.png  orthographic sheet: front (+z), side (+x), top (looking down)
  <name>_compare.png  only with --compare: reference image pasted beside the iso render

Block colors come from block_colors.json (measured averages, full-cube blocks).
Non-full blocks (stairs, slabs, glass panes, doors...) are approximated from
their base block; unknown ids get a neutral gray and are reported on stdout.

Usage:
  python render_preview.py build.litematic [--out DIR] [--compare REF.png] [--scale N]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw
from litemapy import Schematic

COLORS_PATH = Path(__file__).parent / "block_colors.json"
BG = (24, 24, 28)
GRID = (60, 60, 68)
TEXT = (220, 220, 220)
UNKNOWN = defaultdict(int)

# --- color resolution -------------------------------------------------------

SPECIAL = {
    "glass": (210, 235, 245), "tinted_glass": (60, 55, 65),
    "torch": (255, 200, 90), "soul_torch": (120, 220, 230),
    "lantern": (255, 190, 90), "soul_lantern": (120, 220, 230),
    "glow_lichen": (140, 190, 150), "ladder": (160, 130, 80),
    "water": (60, 100, 220), "lava": (240, 110, 30),
    "fire": (240, 150, 40), "soul_fire": (80, 200, 210),
    "end_rod": (230, 225, 200),
    "chain": (70, 75, 85), "iron_chain": (70, 75, 85),
    "iron_bars": (150, 155, 160),
    "lightning_rod": (200, 130, 70), "candle": (230, 220, 190),
    "flower_pot": (150, 90, 60), "rail": (140, 120, 90),
    "powered_rail": (170, 130, 60), "detector_rail": (150, 110, 80),
    "activator_rail": (150, 110, 80),
    "redstone_wire": (180, 40, 30), "lever": (120, 100, 70),
    "tripwire_hook": (140, 130, 110), "vine": (70, 110, 50),
    "lily_pad": (60, 110, 50), "sugar_cane": (150, 200, 130),
    "wheat": (200, 180, 70), "carrots": (70, 130, 50),
    "potatoes": (80, 140, 55), "beetroots": (90, 60, 60),
    "cocoa": (150, 100, 50), "sweet_berry_bush": (60, 100, 50),
    # redstone / machinery (so farms & contraptions are readable in preview)
    "redstone_torch": (220, 60, 40), "redstone_wall_torch": (220, 60, 40),
    "redstone_block": (170, 30, 30), "redstone_lamp": (140, 110, 70),
    "repeater": (150, 100, 90), "comparator": (160, 140, 110),
    "observer": (90, 90, 95), "piston": (140, 130, 100),
    "sticky_piston": (110, 150, 80), "piston_head": (160, 150, 120),
    "hopper": (80, 80, 85), "dropper": (100, 100, 105),
    "dispenser": (100, 100, 105), "chest": (160, 110, 40),
    "trapped_chest": (160, 100, 40), "barrel": (130, 95, 55),
    "furnace": (110, 110, 115), "smoker": (90, 85, 80),
    "blast_furnace": (90, 90, 95), "crafting_table": (150, 110, 60),
    "note_block": (120, 80, 50), "jukebox": (110, 70, 45),
    "daylight_detector": (140, 120, 90), "target": (200, 180, 170),
    "tnt": (180, 60, 50), "slime_block": (110, 190, 90),
    "honey_block": (220, 160, 40), "scaffolding": (200, 180, 100),
    "composter": (100, 80, 45), "cauldron": (70, 70, 75),
    "grindstone": (130, 130, 135), "stonecutter": (120, 120, 125),
    "loom": (140, 120, 100), "cartography_table": (120, 100, 70),
    "fletching_table": (160, 140, 100), "smithing_table": (70, 70, 75),
    "enchanting_table": (90, 40, 100), "anvil": (100, 100, 105),
    "bubble_column": (50, 120, 200), "soul_sand": (80, 60, 50),
    "soul_soil": (70, 55, 45), "magma_block": (160, 60, 30),
    "obsidian": (30, 20, 45), "crying_obsidian": (50, 20, 70),
    "podzol": (90, 60, 30), "mycelium": (110, 90, 100),
    "warped_nylium": (30, 120, 120), "crimson_nylium": (140, 40, 40),
    "oak_sign": (160, 130, 70), "oak_wall_sign": (160, 130, 70),
    "iron_door": (170, 170, 175), "iron_trapdoor": (170, 170, 175),
}

COLOR_WORDS = ("white", "light_gray", "gray", "black", "brown", "red", "orange",
               "yellow", "lime", "green", "cyan", "light_blue", "blue", "purple",
               "magenta", "pink")


def load_colors() -> dict:
    raw = json.loads(COLORS_PATH.read_text())["blocks"]
    return {k.split(":", 1)[-1]: (v["r"], v["g"], v["b"]) for k, v in raw.items()}


def color_of(block_id: str, colors: dict):
    """Approximate a render color for any block id (namespace optional)."""
    name = block_id.split(":", 1)[-1].split("[")[0]
    if name in colors:
        return colors[name]
    if name in SPECIAL:
        return SPECIAL[name]
    # stained glass / panes -> corresponding wool color, lightened
    if "stained_glass" in name:
        for w in COLOR_WORDS:
            if name.startswith(w):
                base = colors.get(f"{w}_wool")
                if base:
                    return tuple(min(255, int(c * 1.25 + 30)) for c in base)
    if name.endswith("_pane"):
        return SPECIAL["glass"]
    # derivative shapes -> base block
    for suffix in ("_stairs", "_slab", "_fence_gate", "_fence", "_wall",
                   "_trapdoor", "_pressure_plate", "_button", "_sign",
                   "_hanging_sign", "_door", "_banner", "_bed"):
        if name.endswith(suffix):
            base = name[: -len(suffix)]
            for cand in (base, base + "_planks", base + "s",
                         base.replace("oak", "oak_planks")):
                if cand in colors:
                    return colors[cand]
            if suffix == "_bed" and base + "_wool" in colors:
                return colors[base + "_wool"]
            if suffix == "_door":
                return colors.get("oak_planks", (160, 130, 80))
    if name.endswith("_carpet"):
        base = name[: -len("_carpet")]
        if base + "_wool" in colors:
            return colors[base + "_wool"]
    if name.endswith("_leaves"):
        return (70, 110, 50)
    if name.endswith("_sapling") or name.endswith("_flower") or name in (
            "grass", "fern", "dandelion", "poppy", "short_grass", "tall_grass"):
        return (90, 140, 60)
    UNKNOWN[name] += 1
    return (140, 140, 145)


# --- loading ----------------------------------------------------------------

def load_voxels(path: Path, colors: dict):
    """All non-air blocks across all regions -> {(x,y,z): rgb}, offset to 0."""
    schem = Schematic.load(str(path))
    voxels = {}
    for reg in schem.regions.values():
        for pos in reg.allblockpos():
            bs = reg[pos[0], pos[1], pos[2]]
            if bs.id != "minecraft:air":
                voxels[pos] = color_of(bs.id, colors)
    if not voxels:
        sys.exit("error: schematic contains no non-air blocks")
    minx = min(p[0] for p in voxels)
    miny = min(p[1] for p in voxels)
    minz = min(p[2] for p in voxels)
    voxels = {(x - minx, y - miny, z - minz): c for (x, y, z), c in voxels.items()}
    dims = (max(p[0] for p in voxels) + 1,
            max(p[1] for p in voxels) + 1,
            max(p[2] for p in voxels) + 1)
    return schem, voxels, dims


# --- isometric --------------------------------------------------------------

def render_iso(voxels, dims, out_path: Path, scale: int | None):
    W, H, L = dims
    A = scale or max(3, min(24, 1400 // max(1, W + L)))
    B, C = A // 2, A
    pad = 12

    def proj(x, y, z):
        return ((x - z) * A + L * A + pad, (x + z) * B - y * C + H * C + pad)

    img = Image.new("RGB", ((W + L) * A + 2 * pad, (W + L) * B + H * C + 2 * pad), BG)
    draw = ImageDraw.Draw(img)
    outline = A >= 8

    def shade(c, f):
        return tuple(int(v * f) for v in c)

    def quad(pts, color):
        ol = shade(color, 0.55) if outline else None
        draw.polygon(pts, fill=color, outline=ol)

    for x, y, z in sorted(voxels, key=lambda p: p[0] + p[1] + p[2]):
        c = voxels[(x, y, z)]
        if (x, y + 1, z) not in voxels:  # top face
            quad([proj(x, y + 1, z), proj(x + 1, y + 1, z),
                  proj(x + 1, y + 1, z + 1), proj(x, y + 1, z + 1)], shade(c, 1.0))
        if (x + 1, y, z) not in voxels:  # +x (east) face
            quad([proj(x + 1, y, z), proj(x + 1, y, z + 1),
                  proj(x + 1, y + 1, z + 1), proj(x + 1, y + 1, z)], shade(c, 0.66))
        if (x, y, z + 1) not in voxels:  # +z (south/front) face
            quad([proj(x, y, z + 1), proj(x + 1, y, z + 1),
                  proj(x + 1, y + 1, z + 1), proj(x, y + 1, z + 1)], shade(c, 0.82))

    img = fit(img)
    img.save(out_path)
    return img


def fit(img: Image.Image, lo=640, hi=2600) -> Image.Image:
    w, h = img.size
    if w < lo:
        k = max(2, round(lo / w))
        img = img.resize((w * k, h * k), Image.NEAREST)
    elif w > hi:
        img = img.resize((hi, int(h * hi / w)), Image.LANCZOS)
    return img


# --- orthographic -----------------------------------------------------------

def render_ortho(voxels, dims, out_path: Path):
    W, H, L = dims
    s = max(3, min(20, 420 // max(1, max(W, H, L))))
    label_h, pad, gap = 16, 10, 24

    front = {}  # (x, y) -> color, nearest = max z
    side = {}   # (z, y) -> color, nearest = max x
    top = {}    # (x, z) -> color, nearest = max y
    for (x, y, z), c in voxels.items():
        if (x, y) not in front or z > front[(x, y)][1]:
            front[(x, y)] = (c, z)
        if (z, y) not in side or x > side[(z, y)][1]:
            side[(z, y)] = (c, x)
        if (x, z) not in top or y > top[(x, z)][1]:
            top[(x, z)] = (c, y)

    def panel(w, h):
        return Image.new("RGB", (w * s, h * s), BG)

    def draw_grid(img, w, h):
        d = ImageDraw.Draw(img)
        for i in range(w + 1):
            d.line([(i * s, 0), (i * s, h * s)], fill=GRID)
        for j in range(h + 1):
            d.line([(0, j * s), (w * s, j * s)], fill=GRID)
        if s >= 10:  # coordinate numbers every 8 cells
            for i in range(0, w, 8):
                d.text((i * s + 2, h * s - 9), str(i), fill=(150, 150, 160))
            for j in range(0, h, 8):
                d.text((2, j * s + 1), str(h - 1 - j), fill=(150, 150, 160))

    p_front = panel(W, H)
    for (x, y), (c, _) in front.items():
        ImageDraw.Draw(p_front).rectangle(
            [x * s, (H - 1 - y) * s, (x + 1) * s - 1, (H - y) * s - 1], fill=c)
    p_side = panel(L, H)  # looking from +x: screen-right is -z
    for (z, y), (c, _) in side.items():
        ImageDraw.Draw(p_side).rectangle(
            [(L - 1 - z) * s, (H - 1 - y) * s, (L - z) * s - 1, (H - y) * s - 1], fill=c)
    p_top = panel(W, L)   # map convention: +z points down-screen
    for (x, z), (c, _) in top.items():
        ImageDraw.Draw(p_top).rectangle(
            [x * s, z * s, (x + 1) * s - 1, (z + 1) * s - 1], fill=c)
    for img, w, h in ((p_front, W, H), (p_side, L, H), (p_top, W, L)):
        draw_grid(img, w, h)

    sheet_w = p_front.width + p_side.width + p_top.width + 2 * gap + 2 * pad
    sheet_h = max(p_front.height, p_side.height, p_top.height) + label_h + 2 * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (16, 16, 20))
    d = ImageDraw.Draw(sheet)
    x = pad
    for title, img, note in (
            (f"front (+z)  {W}x{H}", p_front, "x right, y up"),
            (f"side (+x)  {L}x{H}", p_side, "z left, y up"),
            (f"top (down)  {W}x{L}", p_top, "x right, z down")):
        d.text((x + 2, pad), title, fill=TEXT)
        d.text((x + 2, sheet_h - pad - 9), note, fill=(140, 140, 150))
        sheet.paste(img, (x, pad + label_h))
        x += img.width + gap
    sheet = fit(sheet)
    sheet.save(out_path)
    return sheet


# --- main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Render .litematic preview images")
    ap.add_argument("litematic", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="output directory")
    ap.add_argument("--compare", type=Path, default=None,
                    help="reference image to paste beside the iso render")
    ap.add_argument("--scale", type=int, default=None,
                    help="iso pixels per block edge (default: auto)")
    args = ap.parse_args()

    colors = load_colors()
    schem, voxels, dims = load_voxels(args.litematic, colors)
    out_dir = args.out or args.litematic.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.litematic.stem

    iso = render_iso(voxels, dims, out_dir / f"{stem}_iso.png", args.scale)
    render_ortho(voxels, dims, out_dir / f"{stem}_ortho.png")

    if args.compare:
        ref = Image.open(args.compare).convert("RGB")
        h = iso.height
        ref = ref.resize((max(1, int(ref.width * h / ref.height)), h), Image.LANCZOS)
        sheet = Image.new("RGB", (ref.width + iso.width + 30, h + 20), (16, 16, 20))
        sheet.paste(ref, (10, 10))
        sheet.paste(iso, (ref.width + 20, 10))
        sheet.save(out_dir / f"{stem}_compare.png")
        print(f"saved {out_dir / (stem + '_compare.png')}")

    meta = [f"regions={len(schem.regions)}", f"size={dims[0]}x{dims[1]}x{dims[2]}",
            f"blocks={len(voxels)}"]
    print(f"{args.litematic.name}: {'  '.join(meta)}")
    print(f"saved {out_dir / (stem + '_iso.png')}")
    print(f"saved {out_dir / (stem + '_ortho.png')}")
    if UNKNOWN:
        print("note: colors approximated as gray for: " + ", ".join(sorted(UNKNOWN)))


if __name__ == "__main__":
    main()
