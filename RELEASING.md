# Releasing omnigent-rovo

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
#   dist/omnigent_rovo-0.1.0-py3-none-any.whl
#   dist/omnigent_rovo-0.1.0.tar.gz

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
