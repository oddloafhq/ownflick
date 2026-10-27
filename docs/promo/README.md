# OwnFlick media kit

OwnFlick (formerly Spooly) turns local photos and videos into a private, swipeable feed. Browse a
timeline library, save favorites and collections, and rediscover media you
already own. The server and browser interface are open source and self-hosted.

- Maintainer: Oddloaf — https://oddloaf.dev
- Contact: hello@oddloaf.dev
- Source and installation: https://github.com/oddloafhq/ownflick
- License: MIT
- Python package: https://pypi.org/project/ownflick/
- Container: `ghcr.io/oddloafhq/ownflick`

## Assets

- `ownflick-demo.mp4`: 24-second silent walkthrough with the current name,
  H.264, 1280 × 720. Shows real browser interactions with the local demo
  library. English captions are included.
- `ownflick-social-preview.jpg`: current share image and CasaOS thumbnail.
- `ownflick-demo-poster.jpg`: preview frame for the current video.
- `spooly-demo.mp4`, `social-preview.jpg`, and `demo-poster.jpg`: historical
  Spooly materials retained for existing links.
- [Screenshots](../screenshots/): desktop and mobile product views.
- [Brand](../../brand/): icon and vector wordmarks.

The example photos and videos come from Wikimedia Commons under CC0 or public
domain. The original media are kept outside Git; their source list is in the
local `demo-media/CREDITS.md` and the published [media credits](media-credits.md).
No personal media are included in these assets.

## Reproduce

Run an isolated OwnFlick instance against `demo-media/` on port 8793, with
authentication disabled only for this local recording instance. Build the
production CSS before recording. Then:

```sh
node scripts/record_demo.mjs /tmp/ownflick-recording
poetry run python scripts/build_promo.py
```

The recording script uses Chrome by default; `CHROME_PATH` selects another
installed Chromium executable. The compositor needs ffmpeg and the FreeSans
system font. The demo uses keyboard navigation in Flow and scrolls the Library
and Home pages.

## Editorial introduction

OwnFlick is built for the gap between keeping a media collection and actually
enjoying it. Point it at an existing folder, then browse your photos and videos
in a private feed from a phone or desktop browser. A timeline, favorites and
collections provide more deliberate ways to browse.

It complements an existing storage or backup setup. It does not provide phone
backup, facial recognition, or a public social network. Access is protected by
a password; remote HTTPS access needs an external reverse proxy.

OwnFlick is maintained by Oddloaf. AI tools assisted development and preparation
of these materials. The demo shows the actual application with sample media.
