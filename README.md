# omnigent-rovo

Community harness plugin that brings [Atlassian Rovo Dev](https://developer.atlassian.com/cloud/rovo/) to [Omnigent](https://github.com/omnigent-ai/omnigent) as a first-class harness.

Rovo Dev is driven via its **ACP (Agent Client Protocol)** server mode (`acli rovodev acp`) over stdio — no tmux terminal needed.

## Quick start

```bash
# Install both packages
uv pip install omnigent omnigent-rovo

# Or with pip
pip install omnigent omnigent-rovo
```

Once installed, Omnigent automatically discovers the plugin and makes `rovo` available as a harness:

```yaml
# agent.yaml
harness: rovo
```

## Prerequisites

1. **Atlassian CLI (`acli`)** — install from https://developer.atlassian.com/cloud/acli/
2. **Authenticate** — run `acli rovodev auth login` and complete the browser flow
3. **Verify** — run `acli rovodev auth status` to confirm you're logged in

## Configuration

The harness reads configuration from environment variables (set automatically by the Omnigent runner, or manually for standalone use):

| Variable | Description | Default |
|---|---|---|
| `HARNESS_ROVO_MODEL` | Model display name, e.g. `"Claude Sonnet 4.6"` | Rovo's default |
| `HARNESS_ROVO_CWD` | Working directory for the Rovo Dev subprocess | Current directory |
| `HARNESS_ROVO_ACLI_PATH` | Absolute path to the `acli` binary | `acli` from `PATH` |
| `HARNESS_ROVO_CONFIG_FILE` | Rovo Dev `--config-file` path | `~/.rovodev/config.yml` |
| `HARNESS_ROVO_SITE_URL` | Rovo Dev `--site-url` value | None |

## How it works

This plugin registers itself via Python's [entry points](https://packaging.python.org/en/latest/specifications/entry-points/) mechanism:

```toml
# pyproject.toml
[project.entry-points."omnigent.community.harnesses"]
rovo = "omnigent.community.harnesses.rovo.plugin:get_contribution"
```

At startup, Omnigent's plugin registry discovers all packages in the `omnigent.community.harnesses` entry point group and merges their contributions into the harness registry. This means:

- `rovo` and `rovo-cli` become valid harness names
- The Rovo executor and ACP client are loaded on demand
- Model overrides via `/model` work seamlessly

## Development

```bash
# Clone the repo
git clone https://github.com/shbhmrzd/omnigent-rovo.git
cd omnigent-rovo

# Create a virtual environment
uv venv
source .venv/bin/activate

# Install in editable mode (with omnigent as a dependency)
uv pip install -e .

# Run tests (if any)
uv run pytest
```

## Publishing to PyPI

### First-time setup

1. **Create a PyPI account** at https://pypi.org/account/register/
2. **Create an API token** at https://pypi.org/manage/account/token/
   - Scope: "Entire account" (for the first upload), or project-specific after the first release
3. **Configure your token** — create/edit `~/.pypirc`:
   ```ini
   [pypi]
   username = __token__
   password = pypi-YOUR_TOKEN_HERE
   ```

### Building and publishing

```bash
# Install build tools
uv pip install build twine

# Build the package
python -m build

# This creates:
#   dist/omnigent_rovo-0.1.0-py3-none-any.whl
#   dist/omnigent_rovo-0.1.0.tar.gz

# Upload to Test PyPI first (recommended for first release)
twine upload --repository testpypi dist/*

# Verify the test release works
uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ omnigent-rovo

# Upload to production PyPI
twine upload dist/*
```

### Using a Trusted Publisher (recommended for GitHub repos)

Instead of API tokens, you can set up [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) with GitHub Actions:

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - **PyPI project name**: `omnigent-rovo`
   - **Owner**: `shbhmrzd`
   - **Repository**: `omnigent-rovo`
   - **Workflow name**: `publish.yml`
   - **Environment**: `pypi`

3. Create `.github/workflows/publish.yml` in your repo:
   ```yaml
   name: Publish to PyPI

   on:
     release:
       types: [published]

   jobs:
     publish:
       runs-on: ubuntu-latest
       environment: pypi
       permissions:
         id-token: write
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: "3.12"
         - run: pip install build
         - run: python -m build
         - uses: pypa/gh-action-pypi-publish@release/v1
   ```

4. Create a GitHub release → the workflow auto-publishes to PyPI.

### Version bumps

Update the version in `pyproject.toml`:
```toml
[project]
version = "0.2.0"
```

Then build and publish as above.

## License

MIT
