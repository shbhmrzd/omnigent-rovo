# omnigent-rovo

Community harness plugin that brings [Atlassian Rovo Dev](https://support.atlassian.com/rovo/docs/use-rovo-dev-cli/) to [Omnigent](https://github.com/omnigent-ai/omnigent) as a first-class harness.

Rovo Dev is an AI-powered development agent that runs in your terminal via the [Atlassian CLI (`acli`)](https://support.atlassian.com/rovo/docs/install-and-run-rovo-dev-cli-on-your-device/). It can generate, review, and refactor code, analyze codebases, write documentation, debug issues, create tests, and integrates with Jira and Confluence — all from the command line.

This plugin drives Rovo Dev via its **ACP (Agent Client Protocol)** server mode (`acli rovodev acp`) over stdio — no tmux terminal needed.

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

## Verifying the installation

After installing both packages, confirm the plugin is detected:

```bash
python -c "
from omnigent.harness_plugins import plugin_state, harness_aliases, harness_labels
state = plugin_state()
print('Contributions:', [c.name for c in state.contributions])
print('rovo alias:', harness_aliases().get('rovo'))
print('Label:', harness_labels().get('rovo-cli'))
"
```

Expected output:

```
Contributions: ['omnigent', 'omnigent-rovo']
rovo alias: rovo-cli
Label: Rovo Dev
```

If `omnigent-rovo` does not appear in the list, make sure both packages are installed in the same Python environment.

## Prerequisites

1. **Rovo Dev subscription** — Rovo Dev CLI requires a paid [Rovo Dev Standard](https://www.atlassian.com/software/rovo-dev) subscription (not available during trial)
2. **Atlassian CLI (`acli`)** — install or update to the latest version following the [official setup guide](https://support.atlassian.com/rovo/docs/install-and-run-rovo-dev-cli-on-your-device/) for your OS (macOS, Linux, or Windows)
3. **Authenticate** — run `acli rovodev auth login` and complete the browser flow (or use a [scoped API token](https://support.atlassian.com/rovo/docs/install-and-run-rovo-dev-cli-on-your-device/))
4. **Verify** — run `acli rovodev auth status` to confirm you're logged in

> 📖 For full usage documentation, see [Use Rovo Dev CLI](https://support.atlassian.com/rovo/docs/use-rovo-dev-cli/) and [Rovo Dev CLI commands](https://support.atlassian.com/rovo/docs/rovo-dev-cli-commands/).

## Configuration

The harness reads configuration from environment variables (set automatically by the Omnigent runner, or manually for standalone use):

| Variable | Description | Default |
|---|---|---|
| `HARNESS_ROVO_MODEL` | Model display name, e.g. `"Claude Sonnet 4.6"` | Rovo's default |
| `HARNESS_ROVO_CWD` | Working directory for the Rovo Dev subprocess | Current directory |
| `HARNESS_ROVO_ACLI_PATH` | Absolute path to the `acli` binary | `acli` from `PATH` |
| `HARNESS_ROVO_CONFIG_FILE` | Rovo Dev `--config-file` path | `~/.rovodev/config.yml` |
| `HARNESS_ROVO_SITE_URL` | Rovo Dev `--site-url` value | None |

> See [Manage Rovo Dev CLI settings](https://support.atlassian.com/rovo/docs/manage-rovo-dev-cli-settings/) for details on the configuration file format.

## How it works

This plugin registers itself via Python's [entry points](https://packaging.python.org/en/latest/specifications/entry-points/) mechanism:

```toml
# pyproject.toml
[project.entry-points."omnigent.community.harness"]
rovo = "omnigent.community.harness.rovo.plugin:get_contribution"
```

At startup, Omnigent's plugin registry discovers all packages in the `omnigent.community.harness` entry point group and merges their contributions into the harness registry. This means:

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

# Run the test suite
uv run pytest

# Run with verbose output
uv run pytest -v
```

### Test structure

| Path | Covers |
|---|---|
| `tests/conftest.py` | Lightweight stubs for `omnigent` core types so tests run without the full core installed |
| `tests/test_plugin.py` | Plugin registration (`get_contribution`) |
| `tests/test_acp_client.py` | ACP client — command building, JSON-RPC dispatch, permission auto-allow |
| `tests/test_rovo_executor.py` | Executor — message parsing, update translation, session lifecycle, `run_turn` |
| `tests/test_rovo_harness.py` | Harness entry point — env var config, `create_app()` |

## License

MIT
