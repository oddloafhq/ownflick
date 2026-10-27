# Releasing OwnFlick

Repository: `oddloafhq/ownflick`. Public contact: `hello@oddloaf.dev`.

## Local preparation

Run `poetry run pytest`, `npm ci`, `npm run build-css-prod`, `poetry check`, and both Poetry builds. Keep the `spooly`, `ownflick`, and npm package versions aligned. Update the release notes and capture screenshots from an isolated demo instance when the UI changes.

The first full application version is 0.8.45. Keep the package version and release tag aligned for each subsequent release.

## GitHub and PyPI setup

Configure PyPI Trusted Publishers for both `spooly` and `ownflick` with:

- GitHub owner: `oddloafhq`
- Repository: `ownflick`
- Workflow: `main.yml`
- Environment: `pypi`

Both PyPI projects now exist. Confirm the Trusted Publisher on each project's
Publishing page before a release. Both publishers use the same repository,
workflow, and environment.

The workflow runs these jobs:

- Pushes to `main` and pull requests run one Python 3.12 job that tests and builds both distributions.
- A published GitHub Release runs that job plus a Python 3.10 compatibility test in parallel, then publishes only if both succeed.
- Version-tag pushes do not trigger a separate run. Python 3.14 is not part of the fixed test matrix.
- Every run also builds the Docker image and smoke-tests it against a sample library. A release publishes the full `spooly` distribution first, then the `ownflick` installer package. It pushes the same `linux/amd64` and `linux/arm64` image to `ghcr.io/oddloafhq/ownflick` and `ghcr.io/oddloafhq/spooly` with version, minor and `latest` tags.

Dependencies are cached per Python version and lock file. New development commits cancel outdated checks; release runs are not cancelled by newer development checks. Package artifacts are uploaded only for releases. Avoid embedding registry tokens in repository files.

## Publication

Push the reviewed commits and a matching version tag when publication is authorized. Publish the GitHub Release with the tested tag and release notes. The workflow uploads both wheels and source distributions using the configured publishers.

After the release succeeds, verify fresh installs of `pip install ownflick` and
`pip install spooly`, both CLI commands, and an upgrade with the existing data
directory. The `spooly` Python package and `SPOOLY_*` configuration remain the
compatibility contract; `ownflick` depends on `spooly` rather than installing a
second copy of the application files.

Confirm both packages grant this repository Actions write access, then verify
anonymous pulls of both `latest` tags.
