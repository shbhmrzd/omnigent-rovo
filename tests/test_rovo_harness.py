"""Tests for ``omnigent.community.harness.rovo.inner.rovo_harness``."""

from __future__ import annotations

import os
from unittest.mock import patch

from omnigent.community.harness.rovo.inner.rovo_harness import (
    _build_rovo_executor,
    create_app,
)
from omnigent.community.harness.rovo.inner.rovo_executor import RovoExecutor


class TestBuildRovoExecutor:
    def test_defaults_with_no_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ex = _build_rovo_executor()
        assert isinstance(ex, RovoExecutor)
        assert ex._cwd is None
        assert ex._model_override is None
        assert ex._acli_path is None
        assert ex._config_file is None
        assert ex._site_url is None

    def test_reads_env_vars(self) -> None:
        env = {
            "HARNESS_ROVO_MODEL": "Claude 4",
            "HARNESS_ROVO_CWD": "/workspace",
            "HARNESS_ROVO_ACLI_PATH": "/bin/acli",
            "HARNESS_ROVO_CONFIG_FILE": "/etc/rovo.yml",
            "HARNESS_ROVO_SITE_URL": "https://mysite.atlassian.net",
        }
        with patch.dict(os.environ, env, clear=True):
            ex = _build_rovo_executor()
        assert ex._model_override == "Claude 4"
        assert ex._cwd == "/workspace"
        assert ex._acli_path == "/bin/acli"
        assert ex._config_file == "/etc/rovo.yml"
        assert ex._site_url == "https://mysite.atlassian.net"

    def test_empty_string_env_vars_treated_as_none(self) -> None:
        env = {
            "HARNESS_ROVO_MODEL": "",
            "HARNESS_ROVO_CWD": "",
        }
        with patch.dict(os.environ, env, clear=True):
            ex = _build_rovo_executor()
        assert ex._model_override is None
        assert ex._cwd is None


class TestCreateApp:
    def test_returns_app(self) -> None:
        app = create_app()
        # The stub ExecutorAdapter.build() returns a MagicMock, so just
        # verify create_app() runs without error and returns something.
        assert app is not None
