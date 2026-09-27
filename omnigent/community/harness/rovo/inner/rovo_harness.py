"""``harness: rovo`` wrap — community plugin edition.

Thin module exposing :func:`create_app` — the entrypoint the shared
:mod:`omnigent.runtime.harnesses._runner` invokes after the plugin registry
resolves ``"rovo-cli"`` to this module.

Internally instantiates
:class:`omnigent.runtime.harnesses._executor_adapter.ExecutorAdapter` around a
:class:`.rovo_executor.RovoExecutor` configured from env vars the parent
process sets before spawning.

Env vars read at startup:

- ``HARNESS_ROVO_MODEL``: Rovo Dev model display name, e.g.
  ``"Claude Sonnet 4.6"``. ``None`` lets Rovo pick its own default.
- ``HARNESS_ROVO_CWD``: working directory the executor launches Rovo Dev in.
  ``None`` falls back to the current working directory at turn time.
- ``HARNESS_ROVO_PATH``: path to ``rovo``; defaults to searching ``PATH``.
- ``HARNESS_ROVO_ACLI_PATH``: explicitly use the older ``acli rovodev acp``
  launcher instead. Mutually exclusive with ``HARNESS_ROVO_PATH``.
- ``HARNESS_ROVO_CONFIG_FILE``: Rovo Dev ``--config-file`` (defaults to
  ``~/.rovo/config.yml`` with rovo, ``~/.rovodev/config.yml`` with acli).
- ``HARNESS_ROVO_SITE_URL``: Rovo Dev ``--site-url``.
- ``HARNESS_ROVO_STARTUP_TIMEOUT``: seconds allowed for ACP startup (default 120).
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from omnigent.inner.executor import Executor
from omnigent.runtime.harnesses._executor_adapter import ExecutorAdapter

from .rovo_executor import RovoExecutor

_logger = logging.getLogger(__name__)

_ENV_MODEL = "HARNESS_ROVO_MODEL"
_ENV_CWD = "HARNESS_ROVO_CWD"
_ENV_ROVO_PATH = "HARNESS_ROVO_PATH"
_ENV_ACLI_PATH = "HARNESS_ROVO_ACLI_PATH"
_ENV_CONFIG_FILE = "HARNESS_ROVO_CONFIG_FILE"
_ENV_SITE_URL = "HARNESS_ROVO_SITE_URL"


def _build_rovo_executor() -> Executor:
    """Construct a :class:`RovoExecutor` from env-var config.

    Called lazily by the :class:`ExecutorAdapter` on the first turn, so the
    Rovo Dev ACP subprocess is only spawned when a real conversation starts.
    """
    return RovoExecutor(
        cwd=os.environ.get(_ENV_CWD) or None,
        model=os.environ.get(_ENV_MODEL) or None,
        rovo_path=os.environ.get(_ENV_ROVO_PATH) or None,
        acli_path=os.environ.get(_ENV_ACLI_PATH) or None,
        config_file=os.environ.get(_ENV_CONFIG_FILE) or None,
        site_url=os.environ.get(_ENV_SITE_URL) or None,
        startup_timeout=float(os.environ.get("HARNESS_ROVO_STARTUP_TIMEOUT") or "120"),
    )


def create_app() -> FastAPI:
    """Build the rovo harness's FastAPI app.

    Required entry point per the harness contract — the runner imports this
    module and invokes ``create_app()`` to get the app it serves. The wrapped
    :class:`RovoExecutor` is constructed lazily on the first turn.
    """
    adapter = ExecutorAdapter(executor_factory=_build_rovo_executor)
    return adapter.build()
