# EmbeddingGemma 2 on a NAS without AVX

This alternative uses llama.cpp built for SSE 4.2, with AVX, AVX2, AVX512,
FMA, F16C and BMI2 disabled. Runtime dependencies stay inside Docker.
The CPU-only service does not mount the media library and listens on the
host loopback interface. No Spooly settings or existing vectors are changed.

## Verified on 2026-10-13

Host: Intel Celeron N5105, Linux x86_64, approximately 8 GB RAM, no AVX.
The SSE-only server started successfully, loaded both model files, and
returned valid, distinct 768-dimensional image vectors. A red-square text
query scored higher against the red image than the blue image.

With two CPU threads and a two-CPU quota:

| Request | Measured time |
| --- | --- |
| First synthetic 128px image | 23.36 s |
| Second synthetic 128px image | 23.34 s |
| Short English text | 0.18 s |
| 512px synthetic JPEG through Spooly's existing client | 36.19 s |

Docker reported approximately 1.11 GiB running memory after the requests.
The cgroup peak, which also includes charged file cache and diagnostic
processes, was approximately 1.41 GiB. The model process peak RSS was about
1.15 GiB. These are small synthetic smoke tests, not a guarantee for larger
inputs.

### Real-media pilot on the same host

An isolated Spooly database indexed all 28 JPGs available in a three-source
media library (25 photos/posters and three album covers). The source files were
read only, the model was reached through `127.0.0.1`, and no cloud embedding
request was made. The library also contained hundreds of videos, which this
image-only index does not cover.

| Observation | Result |
| --- | --- |
| Image indexing | 28/28 succeeded; no missing or stale vectors afterward |
| Total time | 728.5 s (12.1 min) |
| Per image | 26.0 s mean; 25.4 s median; 20.6–36.2 s range |
| Running container memory | About 0.8–0.9 GiB during the batch |
| Same-post image pairs | 9/10 reciprocal searches ranked the paired image first; 10/10 ranked it in the top three |
| Chinese album-cover query | All three album covers occupied the top three results |

The isolated web app loaded its main pages, reported a complete index, and
returned image-search and similar-image results through the normal API. The
test database occupied approximately 256 KiB after the app indexed media
metadata; this is not a per-image storage estimate.

The production CLI dry-run then reported 28 current images and zero selected
for reindexing. Group analysis found six groups covering 20 images at the
current 0.84 default threshold. Only three of five filename-linked image pairs
landed in the same group at that threshold; all five did at 0.88. Those pairs
are a weak label, so this is a reason to review group quality with a larger
collection, not enough evidence to change the global threshold. After stopping
the model, saved similar-image results still loaded while new text searches
returned the expected service-unavailable response.

At this observed mean speed, a linear projection is about 36 hours for 5,000
images and 1.5 hours for 200 monthly additions. These are capacity estimates,
not guarantees: image complexity, other NAS workloads, hardware and model
settings can change throughput. The five same-post pairs provide only a small,
weak relevance check; broader semantic-search and grouping quality still need
evaluation on a larger, labeled photo collection.

The service was stopped after validation to release memory. The built image
and verified GGUF model volume remain available. From this directory, start it with:

```sh
docker compose start
```

Spooly's compatible client also worked without authentication. No real media
index was rebuilt or switched.

## Build, download and start

Run from this directory:

```sh
docker compose build
docker compose run --rm --user 0:0 \
  --volume embedding_llama-models:/models:rw \
  --volume "$PWD/download.py:/download.py:ro" \
  --entrypoint python embedding /download.py
docker compose up -d --no-build
python3 smoke.py
docker compose stats --no-stream
```

The download-volume name assumes the Compose project is named `embedding`,
as when invoked from this directory. If using a custom project name, use
`<project>_llama-models` instead. The download command alone mounts the model
volume writable; the service mounts it read-only.

The source is pinned to `4413a192410fad1f054e9216114087a3e01527a0`. The official
GGUF Q8 model and multimodal encoder are pinned to
`bfcd298762cc34d0357ece5ebdd31791a3a374d8` and SHA-256 checked by `download.py`.
The two model files total approximately 865 MB. No GPU access is required.
This recipe targets Linux x86_64 CPUs with SSE 4.2; ARM requires a separate
build configuration.

If your Docker build cannot reach package sources, pass your existing build
proxy settings using Docker's predefined proxy build arguments. Do not add
proxy credentials to the Dockerfile or commit them to the repository.

## Connect Spooly

Add the service to `~/.config/spooly/config.yaml` and restart Spooly:

```yaml
experiments:
  similarity:
    enabled: true
embedding:
  base_url: http://127.0.0.1:9379/v1
  model_name: embeddinggemma-2
```

Spooly always requests 768 dimensions, the model's native output verified by
this recipe. The image request uses the OpenRouter-shaped input:

```json
{
  "model": "embeddinggemma-2",
  "input": [{"content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}]}],
  "dimensions": 768,
  "encoding_format": "float"
}
```

The loopback service has no authentication and ignores any key Spooly finds in
its environment. Do not expose this service publicly.

### If Spooly also runs in Docker

Create a private Docker network once, then attach both Compose services with
the included overrides. From the Spooly repository root:

```sh
docker network create spooly-ai
docker compose -f compose.yaml -f deployment/embedding/spooly.network.yaml up -d
```

From `deployment/embedding`, after building and downloading the model:

```sh
docker compose -f compose.yaml -f compose.network.yaml up -d --no-build
```

If Spooly was started with `docker run` instead of Compose, attach its existing
container with `docker network connect spooly-ai spooly`; reconnect it after
recreating the Spooly container.

Use `base_url: http://embedding:9379/v1` in that case. Keep using the same
Compose overrides when recreating either service. The model service remains
bound to the host's loopback port; the shared Docker network lets Spooly reach
it by service name.

Prepare media from **Settings → Similar Images**, or from the Spooly container:

```sh
docker exec spooly spooly vectorize /media --dry-run --limit 100
docker exec -it spooly spooly vectorize /media --limit 100
```

On a host installation, run the same commands as `spooly vectorize ~/Videos …`.

Switching from Gemini changes the vector space. Files are prepared again for
the new model, and search and related photos include them as they are reached.

Spooly packages from PyPI or GHCR do not contain this build recipe. Download
the matching GitHub release's source archive, or view the
[repository deployment directory](https://github.com/oddloafhq/spooly/tree/main/deployment/embedding),
on the Docker host before running the commands above.

## Release memory

```sh
docker compose stop
docker compose start
```

Stopping releases process memory; model files remain downloaded. To remove
the service without losing model files, use `down`. To permanently delete
its model volume, use `down --volumes`.

The service has a 2 GiB memory ceiling, two CPUs, one request slot and a
2,048-token context. These are deployment settings, not a promise that every
input fits. Spooly sends one 512px JPEG per photo and uses each video's
library thumbnail, so a long video is represented by a single frame. The real-media
pilot above is encouraging, but does not establish retrieval quality for a
larger or more varied collection.

## Previous LiteRT attempt

The official LiteRT 0.18.0 Linux amd64 wheel aborted before model import
because it requires AVX, which the N5105 lacks. This was a binary limitation,
not a failure of the model or Docker isolation. Its image-input wrapper also
differs from OpenRouter. The validated deployment above uses llama.cpp instead.
