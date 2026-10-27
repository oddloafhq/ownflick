<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/oddloafhq/ownflick/main/brand/ownflick-lockup-dark.svg">
    <img src="https://raw.githubusercontent.com/oddloafhq/ownflick/main/brand/ownflick-lockup.svg" alt="OwnFlick" width="300">
  </picture>
</h1>

<p align="center">
  <strong>Your own TikTok for the videos and photos you already have.</strong><br>
  Self-hosted. No cloud account. Your library stays with you.
</p>

<p align="center">
  <a href="https://pypi.org/project/ownflick/"><img src="https://img.shields.io/pypi/v/ownflick" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/ownflick" alt="License"></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/ownflick/">PyPI</a> · <a href="docs/docker.md">Docker</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/oddloafhq/ownflick/main/docs/screenshots/hero.jpg" alt="OwnFlick Library grid on desktop with the Flow swipe feed on a phone">
</p>

**OwnFlick was formerly called Spooly.** Existing installations, data, and
`spooly` commands remain supported.

OwnFlick turns a folder of media into a private feed. Run one command on your
computer or NAS, open it on your phone, and swipe through your own videos and
photos full screen — or browse them as a Pinterest-style grid and a year/month
timeline. Browsing and playback stay on your server; optional AI features send
selected images to the provider you configure.

Local browsing and playback work without internet access. URL downloads and
remote AI features require a connection.

[Watch the 24-second demo (recorded as Spooly)](https://github.com/oddloafhq/ownflick/releases/download/v0.8.46/spooly-demo.mp4)
· [Screenshots and media kit](docs/promo/README.md)

## Quick start

Requires Python 3.10+.

```bash
pip install ownflick
ownflick ~/Videos
```

Open `http://<your-computer>:8000` on any phone, tablet, or browser on the same
network. The first start prints an access password in the terminal.

### Docker

```bash
mkdir ownflick-data
docker run -d --name ownflick --restart unless-stopped --init \
  --user "$(id -u):$(id -g)" -p 8000:8000 \
  -v ~/Videos:/media -v "$PWD/ownflick-data:/data" \
  ghcr.io/oddloafhq/ownflick:latest
docker logs ownflick    # access password
```

The image includes `ffmpeg`, `yt-dlp` and `gallery-dl` for amd64 and arm64.
See [Docker](docs/docker.md) for Compose, NAS permissions and updates.

### Android

An Android phone can run OwnFlick in Termux. See
[Android with Termux](docs/android-termux.md).

## What it does

- **Flow** — a full-screen vertical feed that mixes videos and images. Swipe to
  the next item, double-tap to favorite, hold a video to play it at 2×, and drag
  sideways to seek.
- **Library** — a year/month timeline for multi-year archives and an Explore grid
  with random images, latest videos, and large files.
- **Home** — pick up where you left off, see what happened *On This Day*, and
  open your collections.
- **Favorites and collections** — save anything from any view; long videos resume
  where you stopped, across devices.
- **Downloads** — paste a link and OwnFlick fetches it into your library with
  `yt-dlp` or `gallery-dl`.
- **Radio** — an ambient audio player for the music in the same folders.
- **Many folders, one library** — merge several media directories; deletions go
  to a trash you can undo.

<p align="center">
  <img src="https://raw.githubusercontent.com/oddloafhq/ownflick/main/docs/screenshots/flow-mobile.jpg" alt="Flow: a full-screen waterfall video with like, save and info actions" width="260">
  <img src="https://raw.githubusercontent.com/oddloafhq/ownflick/main/docs/screenshots/home-mobile.jpg" alt="Home: a collage of recent photos with entry points to Flow and Radio" width="260">
  <img src="https://raw.githubusercontent.com/oddloafhq/ownflick/main/docs/screenshots/library-mobile.jpg" alt="Library: a two-column grid of landscape and city photos" width="260">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/oddloafhq/ownflick/main/docs/screenshots/home-desktop.jpg" alt="Home on desktop with the On This Day row" width="820">
</p>

<p align="center"><sub>Screenshots use CC0 and public-domain photos and clips from Wikimedia Commons.</sub></p>

## Flow controls

| Gesture | Video | Image |
| --- | --- | --- |
| Swipe up / down, wheel, ↑ ↓ | Next / previous | Next / previous |
| Tap | Play / pause | Show / hide the interface |
| Double-tap | Favorite | Favorite |
| Press and hold | 2× while held | Show / hide the interface |
| Drag sideways | Seek | Next image in a gallery |
| ← → | Back / forward 5 s | Gallery image, otherwise next / previous |

Files the browser cannot play (for example some HEVC or AV1 videos) are skipped
with a short note instead of stopping the feed.

## Configuration

Settings come from command-line options, then environment variables
(`MEDIA_ROOT`, `SPOOLY_HOST`, `SPOOLY_PORT`), then `config.yaml` in the
`SPOOLY_INSTANCE` data directory when set, then `~/.config/spooly/config.yaml`:

```yaml
media_sources:
  - id: default
    name: Main Library
    path: ~/Videos/OwnFlick
  - id: photos
    name: Photos
    path: ~/Pictures
download_source: default   # where URL downloads are saved
name: Studio Mac           # shown in the browser tab
port: 8000
```

A single `media_root: ~/Videos` still works. Sources are merged into one library;
media URIs look like `@source_id/path`, and old bare-path links and favorites keep
working through the default source.

```bash
ownflick /path/to/media                        # start with one folder
ownflick --port 9000                           # custom port
ownflick --media-source photos=~/Pictures/AI   # add a source (repeatable)
ownflick --help
```

### Access password

Sign-in is on by default. Every page, API and media file requires it.

```bash
ownflick auth status          # status and storage path
ownflick auth set-password    # new password; signs out existing sessions
SPOOLY_AUTH_PASSWORD='a-long-private-password' ownflick auth set-password
```

The password is stored as a scrypt hash in `~/.spooly/auth.json`. Keep OwnFlick
on a trusted network.

### HTTPS

OwnFlick serves plain HTTP. For HTTPS, put it behind a reverse proxy that keeps
the original Host header and media Range requests, and mark the session cookie
secure:

```bash
FLASK_AUTH_COOKIE_SECURE=true ownflick ~/Videos --host 127.0.0.1 --port 8000
```

### URL downloads

The `/download` page queues background downloads. Install the tools it uses:

```bash
brew install yt-dlp gallery-dl ffmpeg        # macOS
sudo apt install yt-dlp gallery-dl ffmpeg    # Ubuntu / Debian
```

- `yt-dlp` (required) handles video sites; OwnFlick asks it for H.264/AAC so
  downloads play in every browser. `gallery-dl` handles image posts and albums.
  `ffmpeg` merges formats and makes video thumbnails.
- For sign-in-only content, put cookie files saved from your browser in `~/.spooly/cookies`
  with the domain in the name (`x.com.txt`, `youtube.com.cookies`), or upload
  them on the download page.

Stopping the server (Ctrl + C or SIGTERM) cancels unfinished downloads and keeps
finished files; interrupted jobs are not resumed.

<details>
<summary><strong>More commands</strong></summary>

**Thumbnails**

```bash
ownflick thumbs /path/to/media              # generate video thumbnails
ownflick thumbs /path --overwrite           # regenerate
```

**Duplicates**

```bash
ownflick dedupe /path/to/media              # dry run
ownflick dedupe /path --type video          # videos only
ownflick dedupe /path --keep newest --execute
```

Options: `--type video|image|all`, `--algorithm sha256|md5`,
`--keep oldest|newest|shortest_path`, `--dry-run` (default), `--execute`,
`--auto-confirm`.

</details>

<details>
<summary><strong>AI titles, media search and related media (optional)</strong></summary>

Image titles and tags use a vision model; related media and description search
use an embedding model. Both are off unless configured:

```yaml
vision:
  enabled: true
  base_url: https://openrouter.ai/api/v1
  model_name: google/gemini-2.5-flash
  tags_limit: 5

experiments:
  similarity:
    enabled: true

embedding:
  base_url: https://openrouter.ai/api/v1
  model_name: google/gemini-embedding-2
  # api_key: ...             # optional; otherwise read from the environment
```

Vision keys come from `SPOOLY_VISION_API_KEY`, then the shared key variables.
The embedding key comes from `embedding.api_key`, then `SPOOLY_EMBEDDING_API_KEY`,
`SPOOLY_AI_API_KEY`, `OPENAI_API_KEY` or `OPENROUTER_API_KEY`. The connection is
read only from `config.yaml`; restart OwnFlick after changing it. Settings shows
it read-only and never displays the key. OwnFlick always requests 768-dimension
vectors and sends photos as 512px JPEGs without location or other metadata.

Open **Settings → Similar Images** and choose **Prepare**. The job runs in the
background, can be paused, and handles photos first, then videos when `ffmpeg`
and `ffprobe` are installed. Videos use three frames at 20%, 50% and 80% of
their duration; videos shorter than one second use one frame, and frames that
cannot be read are skipped. Each frame is sent separately, so preparing a video
usually makes three model requests.
Sampled images are temporary and do not change the library cover. Three
consecutive service failures stop the job; an unreadable file is skipped and
retried next time. Progress lives in the serving process, so after a restart
start preparation again; prepared files are skipped. Vectors are stored in
`~/.spooly/spooly.sqlite3` (or `/data` in Docker), and viewing saved results
never calls a model. Pausing finishes the current request; a partially prepared
video is retried from the beginning. Previously prepared single-thumbnail
videos are updated on the next preparation, while photo vectors are reused.

After preparation, OwnFlick selects up to 24 varied photo groups locally from the
5,000 most recent prepared photos, compared in windows of 64. Library → Explore
shows a few groups, Flow may reuse an existing gallery slot for one, and photo
details list related photos from all prepared photos. Video details show
related videos, ranked by average best frame matches in both directions so
one shared shot does not determine the whole ranking. Older thumbnail vectors
remain usable until preparation replaces them. **Search by description**
in Library → Explore sends one text request per search (Chinese works too) and
ranks up to 48 photos and videos by similarity, which is not a confidence score;
a video matches by its closest frame. Queries are not saved.

The same preparation is available from the terminal:

```bash
ownflick vectorize ~/Videos --dry-run            # counts only; nothing is sent
ownflick vectorize ~/Videos --limit 200          # try a small batch first
ownflick vectorize ~/Videos --yes
```

Changing `model_name` starts a new vector space: files are prepared again for
the new model, and search and related photos include them as they are reached.
Files changed on disk are prepared again on the next run.

At the 2026-10-13 OpenRouter price, about 5,000 Gemini image vectors cost $0.58,
excluding retries and fees. To run a model on your own NAS instead, see the
[isolated Docker deployment guide](deployment/embedding/README.md); OwnFlick does
not install or start the model service.

`experiments.similarity.enabled: false` turns the feature off without deleting
data; restart after changing it. When omitted, a legacy `embedding.enabled: true`
enables it. An invalid embedding URL stops startup with a configuration error.

</details>

<details>
<summary><strong>Embedding in another WSGI server</strong></summary>

The CLI owns the download manager. When hosting `create_app()` yourself, call
`app.extensions['download_manager'].start()` inside the serving worker and
`.close()` in its shutdown hook — not in Flask's per-request teardown.

</details>

## Documentation

- [Docs index](docs/README.md)
- [Docker](docs/docker.md)
- [Android with Termux](docs/android-termux.md)
- [Flow interaction](docs/flow-interaction-unification.md)
- [Media index and local recommendation](docs/media-index-and-recommendation.md)
- [Release notes](docs/release_notes.md)

## Contributing

Bug reports, ideas and pull requests are welcome on
[GitHub](https://github.com/oddloafhq/ownflick/). To refresh the screenshots, serve a
demo folder without sign-in and run the capture script (it uses your installed
Chrome, or the executable set by `CHROME_PATH`):

```bash
npm install
SPOOLY_INSTANCE=/tmp/spooly-demo FLASK_AUTH_ENABLED=false ownflick demo-media --host 127.0.0.1 --port 8793
node scripts/screenshots.mjs
```

Made by [Oddloaf](https://oddloaf.dev). Contact [hello@oddloaf.dev](mailto:hello@oddloaf.dev),
or [open an issue](https://github.com/oddloafhq/ownflick/issues).

## License

[MIT](LICENSE)
