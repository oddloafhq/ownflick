# Release notes

## v0.8.50 (2026-10-27) — refreshed guides and media

- The EmbeddingGemma Docker guide linked from Similar Images now uses OwnFlick
  commands while documenting the compatible `spooly` config and container names.
- The CasaOS candidate uses the OwnFlick name, current image, and repository
  links. Its app ID and service name stay stable for earlier manual installs.
- New OwnFlick share image, demo video, and poster show the current browser UI.
  Previous Spooly media files remain available for existing links.

## v0.8.49 (2026-10-27) — OwnFlick

- Spooly is now OwnFlick. The original graphic mark remains; the wordmark,
  browser interface, and public project links use the new name.
- `pip install ownflick` installs the application and adds the `ownflick`
  command. The `spooly` package and command continue to receive updates.
- The same multi-architecture image is published at both
  `ghcr.io/oddloafhq/ownflick` and `ghcr.io/oddloafhq/spooly`.
- Existing `~/.spooly` and `/data` directories, `SPOOLY_*` variables, and
  Compose service names remain valid. No data migration is needed.

## v0.8.48 (2026-10-14) — related videos

- Video details show related videos using saved vectors; browsing results does not call the model.
- Preparation samples three frames per video (one for videos shorter than a second; unreadable frames are skipped), keeping individual vectors for video similarity and description search, where a video matches by its best frame. Existing thumbnail-only video vectors are updated by the next preparation; photo vectors and library covers are kept.
- Photo and video details share the same related-media component and API. Video grouping and Flow behavior are unchanged.

## v0.8.47 (2026-10-14) — optional media discovery

- Prepare photos and videos from Settings → Similar Images, with progress and pause. Videos use their library thumbnail and need `ffmpeg`.
- Up to 24 varied photo groups are chosen locally after preparation; Library → Explore previews them and Flow can reuse an existing gallery slot.
- Search prepared photos and videos by description in Library → Explore.
- The embedding connection is read only from `config.yaml` (`base_url`, `model_name`, optional `api_key`). Dimensions, image size, quality and timeout are fixed; the saved `embedding_config.json`, its Web form and the `analyze-similar` command were removed.
- Vectors are kept per file and model. Existing 768-dimension image vectors are migrated without re-encoding; saved groups are rebuilt by the next preparation.
- Optional Docker guide for EmbeddingGemma 2 on Linux x86_64 CPUs without AVX. The model service is separate from Spooly and is not started automatically.
- The legacy media-folder `favorite.json` is no longer imported on every startup.

## v0.8.46 (2026-10-12) — Docker and distribution

- Docker image for `linux/amd64` and `linux/arm64` on GHCR, with `ffmpeg`, `yt-dlp`, `gallery-dl` and Deno, plus an example `compose.yaml`.
- `config.yaml` in the `SPOOLY_INSTANCE` data directory is read first.
- Guide for running Spooly on Android with Termux.
- Product demo and share images made from the local demo library.
- `pytest` is no longer installed with the package.

## v0.8.45 (2026-10-12) — Initial Spooly release

- A private, self-hosted media library with a mixed video and photo Flow, timeline and Explore views, favorites, collections, and playback resume.
- Home includes recent media, On This Day, and rediscovery of older media.
- Web Radio plays local music with optional ambient rooms and a sleep timer.
- URL downloads, multiple media folders, thumbnails, and recoverable deletion.
- Password-protected browser access, CSRF protection, and media Range requests. HTTPS is supplied by an external reverse proxy.
- Optional AI titles and local similarity results, disabled until configured.
- Independent Spooly branding and project links, maintained by [Oddloaf](https://oddloaf.dev).

This repository contains the server and browser interface. Native applications and device-pairing APIs are outside this release.
