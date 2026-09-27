# Changelog

## 0.2.0 — 2026-09-27

### Rovo ACP launcher migration

Omnigent now starts Rovo with `rovo acp` by default. This replaces
`acli rovodev acp`; `rovo legacy` is a separate terminal interface and is not
used by this plugin. The `rovo` / `rovo-cli` harness names remain the same.

**Upgrade:** install a Rovo CLI build with ACP support, run `rovo auth login`,
and upgrade the plugin:

```bash
pip install --upgrade omnigent-rovo
```

Rovo uses its own credentials and defaults to `~/.rovo/config.yml`. To retain
an older acli installation, set:

```bash
export HARNESS_ROVO_ACLI_PATH=acli
```

Use `HARNESS_ROVO_PATH` for a custom Rovo binary. Do not set both launcher paths.

### Reliability and resource cleanup

- Fix checkout imports and wheel packaging that could shadow or overwrite
  Omnigent's core packages.
- Clean up failed/cancelled startup and pending RPC requests, notify Rovo when
  prompts time out, and fail promptly when the transport closes.
- Preserve string JSON-RPC request IDs and support messages up to 8 MiB instead
  of failing at asyncio's default 64 KiB line limit.
- Reuse the ACP process across turns and remove the extra per-turn completion
  task.
- Bound startup to 120 seconds; configure slower integrations with
  `HARNESS_ROVO_STARTUP_TIMEOUT`.
- Default `ROVO_UPGRADE_MODE` to `off` for headless sessions so automatic CLI
  upgrades do not block startup. Upgrade Rovo separately.

### Validation and release checks

- Replace core stubs with actual Omnigent types and its FastAPI adapter.
- Add regression and real subprocess tests, plus opt-in live coding,
  session-memory, and HTTP streaming evaluations.
- Validate source archive contents and installed wheels; exclude unrelated
  checkout files from source distributions.
- Gate PyPI publication on CI, including Python 3.12/3.13 and minimum/current
  Omnigent compatibility.

Local validation passed 109 deterministic tests with Omnigent 0.4.0, 0.9.0,
and 0.15.0. Live coding/session-memory and HTTP evaluations passed on 0.15.0;
the full terminal startup also returned the expected response.
