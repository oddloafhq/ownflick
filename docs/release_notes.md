# Release notes

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
