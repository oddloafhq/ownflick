# Spooly brand

Logo assets for Spooly (server, web UI, README, PyPI).

## Meaning

A spool seen from the side: one line wound around a hub, with the loose end
running off along the ground. The line is your library, the hub is where it
lives (your own machine), and the loose end is the feed you scroll.

## Construction

- Drawn on a 24 × 24 grid with a 2.5-unit stroke, round caps and joins.
- Winding: an arc of radius 7.5 around `(11, 12)`, starting at the ground
  point `(11, 19.5)` and running clockwise for 292°, so it stops at
  `(17.95, 14.81)` and leaves a gap above the tail.
- Tail: a straight line along the ground from `(11, 19.5)` to `(20.5, 19.5)`.
- Hub: a dot at `(11, 12)`, radius 2.25.
- Only the hub carries the accent color.

The geometry is defined once in `../scripts/build_brand.py`; every file here is generated
from it. `../spooly/templates/brand_mark.html` is a copy of the same path for inlining in
templates.

## Color

| Role | Light surface | Dark surface |
| --- | --- | --- |
| Line | `#141414` | `#E9E7DF` |
| Hub dot | `#3F5FC4` | `#7F96E8` |
| Wordmark | `#141414` | `#E9E7DF` |
| Icon tile | `#3F5FC4` with a `#F4F1EA` mark | same |

The blue is the only brand color. On icon tiles (avatar, touch icon, `.ico`)
it becomes the background and the whole mark, hub included, turns paper white.

## Wordmark

Lowercase `spooly` in Outfit Medium (500), tracking −0.02em, converted to
outlines so no font is needed. Outfit is licensed under the SIL Open Font
License 1.1. In the lockup the tail sits on the text baseline and the spool
rises to the height of the `l`.

## Files

| File | Use |
| --- | --- |
| `spooly-mark.svg` | Mark on light surfaces |
| `spooly-mark-dark.svg` | Mark on dark surfaces |
| `spooly-mark-mono.svg` | One-color mark using `currentColor` |
| `spooly-lockup.svg` | Mark + wordmark on light surfaces (README header) |
| `spooly-lockup-dark.svg` | Mark + wordmark on dark surfaces |
| `spooly-avatar-512.png` | Social avatar, GitHub org or repo image; safe under a circular crop |
| `../spooly/templates/brand_mark.html` | Inline SVG for templates; the line follows the text color, the dot reads `--brand-dot` |
| `../spooly/static/brand/favicon.svg` | Tab icon, follows the system light/dark setting |
| `../spooly/static/brand/favicon.ico` | Safari and `/favicon.ico` (16/32/48px), on a blue tile so it reads on any tab color |
| `../spooly/static/brand/apple-touch-icon.png` | iOS home screen (180px) |

## Usage

- Minimum size 16px.
- Keep clear space of at least 2 grid units (1/12 of the mark) on every side.
- Do not stretch, rotate, outline or add shadows, and do not move or recolor
  the hub dot outside the values above.
- In dark themes set `--brand-dot: #7F96E8` so the inline mark's dot stays
  visible.

## Regenerate

Run from the repository root:

```bash
npm pack @fontsource/outfit && tar xzf fontsource-outfit-*.tgz
uv run --with fonttools --with brotli --with pillow scripts/build_brand.py --font-dir package/files
```
