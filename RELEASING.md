# Releasing omnigent-rovo

## Release validation gate

Before bumping the version or creating a GitHub release:

1. Install the checkout with `uv pip install -e ".[dev]"`.
2. Run `python -m pytest -q`, `ruff check .`, and `ruff format --check .`.
3. Run the opt-in live evaluations with an authenticated Rovo CLI:
   `RUN_ROVO_LIVE_EVALS=1 python -m pytest tests/test_live_rovo.py -v`.
   Use the current Omnigent version for the HTTP/session-events evaluation.
4. Build with `uv build`, run `python scripts/check_dist.py dist`, and
   install the wheel into a separate virtual
   environment containing Omnigent. From outside the checkout, run
   `python /absolute/path/to/omnigent-rovo/scripts/check_install.py`.
5. Confirm the supported minimum Omnigent version (0.4.0) and the current version
   pass the deterministic suite. CI covers both on Python 3.12 and 3.13.
6. Run `omni run --harness rovo -p "Reply with OK. Do not use tools."` and confirm
   the terminal receives the answer. ACP-only success is insufficient to certify
   the full application startup path.
7. Record tested versions, results, and migration notes. Only then bump the
   package version, rebuild, and publish that exact artifact.

The publish workflow runs CI before uploading. Live evaluations remain an
explicit pre-release step because they require credentials and model usage.
A GitHub release triggers publication; do not create one with unresolved failures.

## First-time setup

1. **Create a PyPI account** at https://pypi.org/account/register/
2. **Create an API token** at https://pypi.org/manage/account/token/
   - Scope: "Entire account" (for the first upload), or project-specific after the first release
3. **Configure your token** — create/edit `~/.pypirc`:
   ```ini
   [pypi]
   username = __token__
   password = pypi-YOUR_TOKEN_HERE
   ```

## Building and publishing

```bash
# Install build tools
uv pip install build twine

# Build the package
python -m build

# This creates:
#   dist/omnigent_rovo-0.2.0-py3-none-any.whl
#   dist/omnigent_rovo-0.2.0.tar.gz

# Upload to Test PyPI first (recommended for first release)
twine upload --repository testpypi dist/*

# Verify the test release works
uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ omnigent-rovo

# Upload to production PyPI
twine upload dist/*
```

## Using a Trusted Publisher (recommended for GitHub repos)

Instead of API tokens, you can set up [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) with GitHub Actions:

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - **PyPI project name**: `omnigent-rovo`
   - **Owner**: `shbhmrzd`
   - **Repository**: `omnigent-rovo`
   - **Workflow name**: `publish.yml`
   - **Environment**: `pypi`

3. The workflow is already set up at `.github/workflows/publish.yml`. Create a GitHub release and it auto-publishes to PyPI.

## Version bumps

Update the version in `pyproject.toml`:
```toml
[project]
version = "0.2.0"
```

Then build and publish as above.
