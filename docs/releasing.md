# Releasing Spooly

Repository: `oddloafhq/spooly`. Public contact: `hello@oddloaf.dev`.

## Local preparation

Run `poetry run pytest`, `npm ci`, `npm run build-css-prod`, `poetry check`, and `poetry build`. Keep Python and npm package versions aligned. Update the release notes and capture screenshots from an isolated demo instance when the UI changes.

The first full application release is being prepared as 0.8.45. PyPI currently has a 0.0.1 name-reservation package; source installation is documented until the application is published.

## GitHub and PyPI setup

Configure a PyPI Trusted Publisher for this project with:

- GitHub owner: `oddloafhq`
- Repository: `spooly`
- Workflow: `main.yml`
- Environment: `pypi`

The workflow has three straightforward jobs:

- Pushes to `main` and pull requests run one Python 3.12 job that tests and builds the package.
- A published GitHub Release runs that job plus a Python 3.10 compatibility test in parallel, then publishes only if both succeed.
- Version-tag pushes do not trigger a separate run. Python 3.14 is not part of the fixed test matrix.

Dependencies are cached per Python version and lock file. New development commits cancel outdated checks; release runs are not cancelled by newer development checks. Package artifacts are uploaded only for releases. Avoid embedding registry tokens in repository files.

## Publication

Push the reviewed commits and a matching version tag when publication is authorized. Publish the GitHub Release with the tested tag and release notes. The workflow uploads the wheel and source distribution to PyPI using the configured publisher.

After the release succeeds, change the README quick start to `pip install spooly` and `spooly ~/Videos`, replacing the source-install instructions and name-reservation note.
