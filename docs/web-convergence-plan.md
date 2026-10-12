# Web architecture

Spooly contains a Flask server and a responsive browser interface. Native applications, device pairing, built-in TLS, PWA installation, and offline asset caching are outside the current product.

## Boundaries

- `spooly/app.py` assembles configuration, services, authentication, cache policies, and routes.
- `spooly/run.py` owns the CLI and server lifecycle. Configuration priority is CLI arguments, environment, YAML, then defaults.
- `spooly/web/` contains HTTP entry points for media, Flow, Library, collections, Radio, downloads, captions, and settings.
- `spooly/services/` owns media indexing, persistence, recommendation, thumbnails, downloads, and playback state.
- `spooly/experiments/similarity/` is optional and does not participate in regular Library browsing when disabled.
- Templates pass boot data; per-page behavior and styles live in `spooly/static/`.

## Runtime constraints

Authentication protects pages, APIs, thumbnails, and media. Public static files and favicons remain accessible before login. Mutations require CSRF validation. Private API responses must not be cached publicly; media streams retain Range support.

A complete scan may remove missing media from the index. An unavailable source must retain its previous index. Downloads complete only after their outputs have been registered. Deletion moves media to a recoverable trash before permanent removal.

Browsing, local recommendation, and playback do not require a model provider. Optional AI requests are explicit remote operations; model credentials and personal media must never enter the repository.

The CLI starts and closes the download manager. A separate WSGI host must own the same lifecycle. HTTPS belongs to an external reverse proxy; active obsolete TLS settings are rejected to prevent an accidental downgrade.

## Verification

Run `poetry run pytest` and `npm run build-css-prod`. For browser changes, use an isolated `SPOOLY_INSTANCE` and a temporary media library to check `/`, `/flow`, `/library`, `/radio`, `/download`, and login at desktop and mobile sizes.

See the [documentation index](README.md) for media and interaction contracts.
