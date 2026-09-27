# Local validation — 2026-09-27

## Result

The plugin works locally through `rovo acp`, including Omnigent's complete terminal
startup path. `rovo legacy` is the plain-text terminal interface and is not the
transport this ACP plugin should spawn.

This record describes pre-release local validation. Version 0.2.0 is now being
prepared with migration notes in CHANGELOG.md. Publication status is tracked by
the GitHub release and its publishing workflow, not this historical test record.

## Tests performed

All local runs used macOS arm64 and Python 3.12.13.

| Check | Result |
| --- | --- |
| Original suite, before edits | 92 passed; core was replaced with stubs |
| Final suite with real Omnigent 0.9.0, editable install | 109 passed, 2 live evals skipped |
| Final built wheel with Omnigent 0.4.0 | 109 passed, 2 live evals skipped |
| Final built wheel with Omnigent 0.15.0 | 109 passed, 2 live evals skipped |
| Wheel install, plugin discovery, HTTP health on 0.4.0 and 0.15.0 | Passed |
| Real Rovo coding and multi-turn memory eval on 0.15.0 | Passed |
| Real harness runner HTTP/SSE eval on 0.15.0 | Passed |
| Full `omni run --harness rovo` with normal Rovo settings and a fresh daemon | Returned `OMNIGENT_ROVO_OK`, exit 0 |
| Ruff lint, formatting, and `git diff --check` | Passed |
| Wheel and source-distribution builds | Passed |
| Archive contents allowlist | Passed after excluding unrelated draft/screenshots |

The live coding eval first proves that a seeded arithmetic defect fails Python
assertions, asks Rovo to edit the temporary file, then independently checks the
result. A second turn must reproduce an unpredictable marker and reuse the same
ACP process/session. The HTTP eval starts the actual Omnigent harness runner and
checks its streamed answer. Both passed together in 114.56 seconds on 0.15.0 with
the normal Rovo configuration. A later diagnostic-only change improves startup
timeout messages; deterministic tests and wheel checks were repeated afterward.

CI now tests minimum/current Omnigent on Python 3.12 and 3.13 and verifies a wheel
installation outside the checkout. The remote matrix has not been executed yet;
Python 3.13 is not covered by these local results.

## Failures reproduced before fixes

- Checkout imports shadowed Omnigent core; the stub suite concealed this.
- The default launch command still selected `acli rovodev acp`.
- Failed writes and cancelled requests retained pending RPC futures.
- String JSON-RPC request IDs raised `ValueError`.
- Failed/cancelled initialization left its subprocess unclosed.
- Requests after stdout EOF could wait forever.
- Prompt timeouts did not notify the server to cancel.
- A real subprocess emitting a 100,000-character frame exceeded asyncio's 64 KiB
  default and broke the transport.
- Automatic Rovo updates could consume the startup deadline.
- The source archive included unrelated checkout screenshots and a draft document.

Regression tests were added and observed failing before the corresponding fixes.
Existing successful behavior also has explicit coverage for iterator cleanup and
warm process reuse. Tests now use the actual Omnigent core types and app adapter.

## Implemented changes

- Default to `rovo acp`; support an explicit `HARNESS_ROVO_PATH` and retain the
  older command through `HARNESS_ROVO_ACLI_PATH`.
- Stop shipping parent-package initializers that shadow/overwrite Omnigent core.
- Bound startup (120 seconds, configurable), clean up failed startup, release RPC
  futures, preserve string IDs, cancel timed-out prompts, and fail promptly after
  transport EOF.
- Accept frames up to 8 MiB. Replace the per-turn finisher task with a completion
  callback and always retrieve the prompt task's result/exception.
- Default headless Rovo wrapper upgrades to `off`; update setup/auth metadata and
  migration instructions.
- Restrict source distributions to intentional package files, tests, scripts, and
  release documentation; check archive contents in CI.
- Require CI to succeed before the existing publish workflow uploads a release.

## Environment observations and release decision

The installed Rovo wrapper auto-updated from 202609.23.1 to 202609.24.2 during the
first complete terminal test. Subsequent headless launches default updates off.
The new build and configured MCP integrations sometimes exceeded the initial
60-second startup deadline. A configurable 120-second deadline passed the normal
configuration's live evals and the final full terminal check.

A separate temporary configuration without external MCP servers was used to
isolate startup delays. It also passed the terminal test. The user's normal Rovo
configuration was not edited. Initial sandbox-only attempts also encountered a
SOCKS dependency error in the bundled Rovo executable; authenticated live tests
were run outside that sandbox.

Recommend a 0.2.0 release after review and remote CI because the default launcher
and authentication/configuration path change. Users retaining acli should set
`HARNESS_ROVO_ACLI_PATH=acli`. See RELEASING.md for the release gate. These are
integration/correctness evaluations, not broad model-quality or performance
benchmarks; no throughput or latency improvement is claimed.

## Versioned 0.2.0 artifact check

The exact 0.2.0 wheel passed installed-plugin discovery/health and the live HTTP
streaming evaluation on Omnigent 0.15.0. The first coding evaluation hit its
120-second test deadline before editing the fixture. One unchanged retry passed
in 43.34 seconds, including independent correctness assertions and session memory.
No implementation or test timeout was changed to obtain that result. Live Rovo
service latency can vary; deterministic coverage and remote CI remain separate
release gates.
