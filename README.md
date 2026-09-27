# omnigent-rovo

Community harness plugin that brings [Atlassian Rovo Dev](https://support.atlassian.com/rovo/docs/use-rovo-dev-cli/) to [Omnigent](https://github.com/omnigent-ai/omnigent) as a first-class harness.

The plugin drives Rovo through its **ACP (Agent Client Protocol)** server over
stdio using `rovo acp`. The terminal command `rovo legacy` is a separate
plain-text interface; it is not the ACP transport and is not used by this plugin.

Older installations can explicitly select `acli rovodev acp` by setting
`HARNESS_ROVO_ACLI_PATH=acli`.

See [release notes and migration details](CHANGELOG.md) for version 0.2.0.

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

1. Install a Rovo CLI build that supports `rovo acp` and ensure `rovo` is on `PATH`.
2. Run `rovo auth login` using an account with Rovo access.
3. Verify `rovo auth status` and `rovo acp --help`.

For an older `acli` installation, set `HARNESS_ROVO_ACLI_PATH=acli` and use
`acli rovodev auth login` / `acli rovodev auth status` instead. Omnigent's setup
metadata describes the default `rovo` launcher; configure and authenticate the
older launcher manually.

### Migrating from 0.1.0

The default launch command changes from `acli rovodev acp` to `rovo acp`.
Rovo uses its own authentication and default configuration (`~/.rovo/config.yml`).
Existing users who need the old launch command must set `HARNESS_ROVO_ACLI_PATH`.
Do not set both launcher paths.

Headless sessions default `ROVO_UPGRADE_MODE` to `off` so an automatic CLI update
cannot stall the ACP handshake. Upgrade Rovo explicitly outside Omnigent.
ACP startup defaults to a 120-second deadline; prompt turns default to 600 seconds.

## Configuration

The harness reads configuration from environment variables (set automatically by the Omnigent runner, or manually for standalone use):

| Variable | Description | Default |
|---|---|---|
| `HARNESS_ROVO_MODEL` | Model display name, e.g. `"Claude Sonnet 4.6"` | Rovo's default |
| `HARNESS_ROVO_CWD` | Working directory for the Rovo Dev subprocess | Current directory |
| `HARNESS_ROVO_PATH` | Path to the `rovo` binary | `rovo` from `PATH` |
| `HARNESS_ROVO_ACLI_PATH` | Opt into `acli rovodev acp`; mutually exclusive with `HARNESS_ROVO_PATH` | Unset |
| `HARNESS_ROVO_CONFIG_FILE` | Rovo Dev `--config-file` path | `~/.rovo/config.yml` (or `~/.rovodev/config.yml` with acli) |
| `HARNESS_ROVO_STARTUP_TIMEOUT` | ACP startup deadline in seconds (increase for slow MCP integrations) | `120` |
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
uv pip install -e ".[dev]"

# Run the test suite
python -m pytest

# Run with verbose output
python -m pytest -v
```

### Test structure

| Path | Covers |
|---|---|
| `tests/test_plugin.py` | Plugin registration (`get_contribution`) |
| `tests/test_acp_client.py` | ACP client — command building, JSON-RPC dispatch, permission auto-allow |
| `tests/test_rovo_executor.py` | Executor — message parsing, update translation, session lifecycle, `run_turn` |
| `tests/test_rovo_harness.py` | Harness entry point — env var config, `create_app()` |

The suite imports the real Omnigent core and builds the real FastAPI application.
It includes subprocess transport tests for streaming, session reuse, and messages
over 64 KiB, plus failure, timeout, cancellation, and installation regressions.

Run the live release evaluations after authenticating Rovo:

```bash
ROVO_UPGRADE_MODE=off RUN_ROVO_LIVE_EVALS=1 python -m pytest tests/test_live_rovo.py -v
```

These opt-in tests consume model usage. They use temporary workspaces to verify
an actual file edit with independent Python assertions, multi-turn memory, and
the real Omnigent harness runner's HTTP streaming response. They do not judge
success from the model's own claim that it completed the task. The HTTP evaluation
uses Omnigent's session-events API (tested with 0.9.0 and 0.15.0).

## License

MIT
