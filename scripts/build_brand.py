"""Regenerate the OwnFlick brand assets from one geometry definition.

The mark is a spool seen from the side: one line wound around a hub, with the
loose end running off along the ground. It is drawn on a 24-unit grid with a
2.5-unit round stroke. The wordmark is set in Outfit Medium (SIL OFL 1.1) and
converted to outlines so no font ships.

Requirements (not project dependencies): fonttools, brotli, pillow, and the
Outfit static WOFF2 files from ``npm pack @fontsource/outfit``.

Usage:
    npm pack @fontsource/outfit && tar xzf fontsource-outfit-*.tgz
    uv run --with fonttools --with brotli --with pillow scripts/build_brand.py --font-dir package/files
"""

from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "brand"
WEB_DIR = ROOT / "spooly" / "static" / "brand"
TEMPLATE_DIR = ROOT / "spooly" / "templates"

INK = "#141414"
INK_DARK = "#E9E7DF"
BLUE = "#3F5FC4"
BLUE_DARK = "#7F96E8"  # the dot on dark surfaces, where BLUE is too dim
PAPER = "#F4F1EA"

# The mark, in 24-unit grid coordinates.
CENTER = (11.0, 12.0)
RADIUS = 7.5
STROKE = 2.5
TAIL_END_X = 20.5
OPEN_ANGLE = 22.0  # degrees clockwise from 3 o'clock, where the winding stops
DOT_RADIUS = 2.25

GROUND_Y = CENTER[1] + RADIUS
ARC_END = (
    CENTER[0] + RADIUS * math.cos(math.radians(OPEN_ANGLE)),
    CENTER[1] + RADIUS * math.sin(math.radians(OPEN_ANGLE)),
)
# Tight bounds of the drawn mark, used to center it on square tiles.
BOUNDS = (
    CENTER[0] - RADIUS - STROKE / 2,
    CENTER[1] - RADIUS - STROKE / 2,
    TAIL_END_X + STROKE / 2,
    GROUND_Y + STROKE / 2,
)

MARK_PATH = (
    f'<path d="M{TAIL_END_X:g} {GROUND_Y:g}H{CENTER[0]:g}'
    f'A{RADIUS:g} {RADIUS:g} 0 1 1 {ARC_END[0]:.2f} {ARC_END[1]:.2f}"/>'
)
STROKE_ATTRS = f'fill="none" stroke-width="{STROKE:g}" stroke-linecap="round" stroke-linejoin="round"'
# Favicons crop to the drawn shape so the mark fills the tab icon.
FAVICON_BOX = (1.5, 1.5, 21.0)


def mark_group(stroke: str, dot: str) -> str:
    return (
        f'<g {STROKE_ATTRS} stroke="{stroke}">{MARK_PATH}</g>'
        f'<circle cx="{CENTER[0]:g}" cy="{CENTER[1]:g}" r="{DOT_RADIUS:g}" fill="{dot}"/>'
    )


def mark_svg(stroke: str, dot: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" role="img" aria-label="Spooly">\n'
        f"  {mark_group(stroke, dot)}\n"
        "</svg>\n"
    )


def inline_svg() -> str:
    # For templates: the line follows the text color, the dot can be themed.
    return (
        '<svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true" focusable="false">\n'
        f"  {mark_group('currentColor', f'var(--brand-dot, {BLUE})')}\n"
        "</svg>\n"
    )


def favicon_svg() -> str:
    # Browsers render SVG favicons against their own tab color, so follow it.
    x, y, side = FAVICON_BOX
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:g} {y:g} {side:g} {side:g}">\n'
        f"  <style>.l{{stroke:{INK}}}.d{{fill:{BLUE}}}"
        f"@media (prefers-color-scheme:dark){{.l{{stroke:{INK_DARK}}}.d{{fill:{BLUE_DARK}}}}}</style>\n"
        f'  <g class="l" {STROKE_ATTRS}>{MARK_PATH}</g>\n'
        f'  <circle class="d" cx="{CENTER[0]:g}" cy="{CENTER[1]:g}" r="{DOT_RADIUS:g}"/>\n'
        "</svg>\n"
    )


def word_paths(font_dir: Path, word: str, size: float, tracking_em: float) -> tuple[str, float, float, float]:
    """Return SVG path data and dimensions for a wordmark."""
    font = TTFont(font_dir / "outfit-latin-500-normal.woff2")
    scale = size / font["head"].unitsPerEm
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    bounds = BoundsPen(glyph_set)
    parts = []
    x = 0.0
    for char in word:
        glyph = glyph_set[cmap[ord(char)]]
        glyph.draw(bounds)
        pen = SVGPathPen(glyph_set, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        # Font units are y-up; flip onto an SVG baseline at y = 0.
        glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, 0)))
        parts.append(pen.getCommands())
        x += glyph.width * scale + tracking_em * size
    _, y_min, _, y_max = bounds.bounds
    return "".join(parts), x - tracking_em * size, y_max * scale, -y_min * scale


def lockup_svg(font_dir: Path, word: str, stroke: str, dot: str, text_color: str) -> str:
    size = 72.0
    pad = 8.0
    path, advance, ascender, descender = word_paths(font_dir, word, size, tracking_em=-0.02)
    left, top, right, bottom = BOUNDS
    # The tail sits on the text baseline and the spool rises to the height of the l.
    scale = ascender / (bottom - top)
    baseline = pad + ascender
    mark_x = pad - left * scale
    mark_y = baseline - bottom * scale
    text_x = pad + (right - left) * scale + size * 0.3
    width = text_x + advance + pad
    height = baseline + descender + pad
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'role="img" aria-label="{word}">\n'
        f'  <g transform="translate({mark_x:.2f} {mark_y:.2f}) scale({scale:.4f})">{mark_group(stroke, dot)}</g>\n'
        f'  <path transform="translate({text_x:.2f} {baseline:.2f})" fill="{text_color}" d="{path}"/>\n'
        "</svg>\n"
    )


def render_mark(size: int, background: str | None, line: str, dot: str, fit: float | None) -> Image.Image:
    """Rasterize the mark with 8x supersampling.

    ``fit`` centers the drawn shape on a tile and scales it to that fraction of
    the tile; ``None`` maps the favicon box onto the image, matching favicon.svg.
    """
    ss = 8
    canvas = size * ss
    image = Image.new("RGBA", (canvas, canvas), background or (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    left, top, right, bottom = BOUNDS
    if fit is None:
        x, y, side = FAVICON_BOX
        unit = canvas / side
        ox, oy = -x * unit, -y * unit
    else:
        unit = canvas * fit / max(right - left, bottom - top)
        ox = canvas / 2 - (left + right) / 2 * unit
        oy = canvas / 2 - (top + bottom) / 2 * unit

    def pt(x: float, y: float) -> tuple[float, float]:
        return ox + x * unit, oy + y * unit

    half = STROKE / 2 * unit
    width = round(STROKE * unit)

    def disc(x: float, y: float, radius: float, fill: str) -> None:
        cx, cy = pt(x, y)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)

    draw.line((pt(CENTER[0], GROUND_Y), pt(TAIL_END_X, GROUND_Y)), fill=line, width=width)
    cx, cy = pt(*CENTER)
    outer = RADIUS * unit + half
    draw.arc((cx - outer, cy - outer, cx + outer, cy + outer), 90, 360 + OPEN_ANGLE, fill=line, width=width)
    disc(TAIL_END_X, GROUND_Y, half, line)
    disc(*ARC_END, half, line)
    disc(*CENTER, DOT_RADIUS * unit, dot)

    return image.resize((size, size), Image.LANCZOS)


def rounded(image: Image.Image, radius: float = 0.22) -> Image.Image:
    """Round the corners of a square tile; ``radius`` is a fraction of its side."""
    ss = 8
    side = image.width * ss
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side - 1, side - 1), radius=side * radius, fill=255)
    image.putalpha(mask.resize(image.size, Image.LANCZOS))
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font-dir", type=Path, required=True, help="Directory with Outfit WOFF2 files")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "spooly-mark.svg").write_text(mark_svg(INK, BLUE))
    (OUT_DIR / "spooly-mark-dark.svg").write_text(mark_svg(INK_DARK, BLUE_DARK))
    (OUT_DIR / "spooly-mark-mono.svg").write_text(mark_svg("currentColor", "currentColor"))
    (OUT_DIR / "spooly-lockup.svg").write_text(lockup_svg(args.font_dir, "spooly", INK, BLUE, INK))
    (OUT_DIR / "spooly-lockup-dark.svg").write_text(lockup_svg(args.font_dir, "spooly", INK_DARK, BLUE_DARK, INK_DARK))
    (OUT_DIR / "ownflick-lockup.svg").write_text(lockup_svg(args.font_dir, "ownflick", INK, BLUE, INK))
    (OUT_DIR / "ownflick-lockup-dark.svg").write_text(lockup_svg(args.font_dir, "ownflick", INK_DARK, BLUE_DARK, INK_DARK))
    shutil.copy2(OUT_DIR / "spooly-lockup.svg", WEB_DIR / "spooly-lockup.svg")
    shutil.copy2(OUT_DIR / "spooly-lockup-dark.svg", WEB_DIR / "spooly-lockup-dark.svg")
    shutil.copy2(OUT_DIR / "ownflick-lockup.svg", WEB_DIR / "ownflick-lockup.svg")
    shutil.copy2(OUT_DIR / "ownflick-lockup-dark.svg", WEB_DIR / "ownflick-lockup-dark.svg")
    render_mark(512, BLUE, PAPER, PAPER, fit=0.56).save(OUT_DIR / "spooly-avatar-512.png", optimize=True)

    (TEMPLATE_DIR / "brand_mark.html").write_text(inline_svg())
    (WEB_DIR / "favicon.svg").write_text(favicon_svg())
    render_mark(180, BLUE, PAPER, PAPER, fit=0.6).save(WEB_DIR / "apple-touch-icon.png", optimize=True)
    # The .ico cannot follow the tab color, so it carries its own blue tile.
    small, medium, large = (rounded(render_mark(s, BLUE, PAPER, PAPER, fit=0.74)) for s in (16, 32, 48))
    large.save(WEB_DIR / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[small, medium])


if __name__ == "__main__":
    main()
