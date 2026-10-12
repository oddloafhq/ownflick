# Releasing Spooly

Repository: `oddloafhq/spooly`. Public contact: `hello@oddloaf.dev`.

## Local preparation

Run `poetry run pytest`, `npm ci`, `npm run build-css-prod`, `poetry check`, and `poetry build`. Keep Python and npm package versions aligned. Update the release notes and capture screenshots from an isolated demo instance when the UI changes.

The first full application version is 0.8.45. Keep the package version and release tag aligned for each subsequent release.

## GitHub and PyPI setup

Configure a PyPI Trusted Publisher for this project with:

- GitHub owner: `oddloafhq`
- Repository: `spooly`
- Workflow: `main.yml`
- Environment: `pypi`

The workflow runs these jobs:

- Pushes to `main` and pull requests run one Python 3.12 job that tests and builds the package.
- A published GitHub Release runs that job plus a Python 3.10 compatibility test in parallel, then publishes only if both succeed.
- Version-tag pushes do not trigger a separate run. Python 3.14 is not part of the fixed test matrix.
- Every run also builds the Docker image and smoke-tests it against a sample library. After PyPI publication, a release pushes the `linux/amd64` and `linux/arm64` image to `ghcr.io/oddloafhq/spooly` with the version, minor and `latest` tags.

Dependencies are cached per Python version and lock file. New development commits cancel outdated checks; release runs are not cancelled by newer development checks. Package artifacts are uploaded only for releases. Avoid embedding registry tokens in repository files.

## Publication

Push the reviewed commits and a matching version tag when publication is authorized. Publish the GitHub Release with the tested tag and release notes. The workflow uploads the wheel and source distribution to PyPI using the configured publisher.

After the release succeeds, verify that `pip install spooly` installs the new version and that the CLI and browser pages work from the installed package.

GHCR creates the package as private on its first push. Make it public once under the package's settings on GitHub, then confirm `docker pull ghcr.io/oddloafhq/spooly:latest` works without signing in.
