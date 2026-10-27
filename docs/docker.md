# Docker

The image `ghcr.io/oddloafhq/ownflick` runs OwnFlick on Linux servers and NAS
devices (`linux/amd64` and `linux/arm64`). It includes `ffmpeg`, `yt-dlp`,
`gallery-dl` and Deno, the JavaScript runtime yt-dlp uses for YouTube.

The former image name, `ghcr.io/oddloafhq/spooly`, receives the same releases.
Existing deployments can keep that image reference and their current data mount.

On macOS and Windows, `pip install ownflick` is faster: Docker Desktop reads
mounted folders slowly, and OwnFlick scans the whole library at startup.

## Start

```bash
mkdir ownflick-data                     # create it yourself so your user owns it
docker run -d --name ownflick --restart unless-stopped --init \
  --user "$(id -u):$(id -g)" -p 8000:8000 -e TZ=Asia/Shanghai \
  -v ~/Videos:/media -v "$PWD/ownflick-data:/data" \
  ghcr.io/oddloafhq/ownflick:latest
docker logs ownflick                    # shows the initial access password
```

Or download [`compose.yaml`](../compose.yaml), edit the media path and time
zone, then run `docker compose up -d`.

Open `http://<server-address>:8000`.

## Volumes

| Path | Contents | Access |
| --- | --- | --- |
| `/media` | Your library | Read-write for URL downloads and the deletion trash (`.spooly-trash`). Read-only works if you never delete or download. |
| `/data` | Database, password, thumbnails, cookies, `config.yaml` | Read-write; back it up |

Run the container as the user that owns your media (`--user` or `user:` in
Compose). On Synology this is often `1026:100`. If Docker creates a missing
host folder, it belongs to root and OwnFlick cannot write to it.

## Password

The first start prints a generated password in `docker logs ownflick`. To choose
it instead, set `SPOOLY_AUTH_PASSWORD` before the first start; it is ignored
once `/data/auth.json` exists. Change it later with:

```bash
docker exec -it ownflick ownflick auth set-password
```

## Configuration

Place `config.yaml` in `/data`; it takes priority over other configuration
files. Several folders become one library when you mount them under separate
paths:

```yaml
# /data/config.yaml
name: Home NAS
media_sources:
  - id: default
    name: Videos
    path: /media
  - id: photos
    name: Photos
    path: /photos
```

```bash
docker run ... -v /volume1/video:/media -v /volume1/photo:/photos ...
```

Environment variables also work: `TZ`, `SPOOLY_NAME`, `SPOOLY_PORT` (also
change the published port), and `FLASK_AUTH_COOKIE_SECURE=true` behind an HTTPS
reverse proxy.

## Updating

```bash
docker pull ghcr.io/oddloafhq/ownflick:latest
docker rm -f ownflick  # then run the same docker run command again
# or: docker compose pull && docker compose up -d
```

Tags: `latest`, a release such as `0.8.46`, or a minor line such as `0.8`.

Video sites change often. If downloads fail before a new image is published,
update yt-dlp inside the running container (lost when the container is
recreated):

```bash
docker exec -u 0 ownflick pip install -U "yt-dlp[default]"
```

## Notes

- Files added to `/media` from another computer appear after a library sync in
  Settings or a container restart.
- Thumbnails, downloads and AI features work as in a regular install. AI API
  keys are passed as environment variables, for example
  `-e SPOOLY_AI_API_KEY=...`.
