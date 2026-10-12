# syntax=docker/dockerfile:1

# Build the wheel from this checkout so the image ships the same package as PyPI.
FROM python:3.12-slim-trixie AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY spooly ./spooly
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /dist .

# yt-dlp needs a JavaScript runtime for YouTube; Deno is its default.
FROM denoland/deno:bin-2.9.7 AS deno

FROM python:3.12-slim-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deno /deno /usr/local/bin/deno
COPY --from=build /dist /tmp/dist
RUN pip install --no-cache-dir /tmp/dist/*.whl "yt-dlp[default]" gallery-dl \
    && rm -rf /tmp/dist

RUN useradd --uid 1000 --user-group --home-dir /data --no-create-home spooly \
    && mkdir -p /data /media \
    && chown spooly:spooly /data /media

# /data holds the database, password, thumbnails, cookies and an optional config.yaml.
ENV HOME=/data \
    SPOOLY_INSTANCE=/data \
    SPOOLY_NAME=Spooly \
    PYTHONUNBUFFERED=1

USER spooly
EXPOSE 8000

# The first start indexes the whole library before it serves pages.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/login' % (os.environ.get('SPOOLY_PORT') or 8000), timeout=4)"]

ENTRYPOINT ["spooly"]
CMD ["serve", "/media"]
