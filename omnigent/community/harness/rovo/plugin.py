"""Rovo Dev community harness plugin for Omnigent.

This module exports :func:`get_contribution` — the entry point Omnigent's
plugin registry calls to discover the ``rovo-cli`` harness.

Entry point registration (in ``pyproject.toml``)::

    [project.entry-points."omnigent.community.harness"]
    rovo = "omnigent.community.harness.rovo.plugin:get_contribution"
"""

from __future__ import annotations

from omnigent.harness_install_spec import HarnessInstallSpec
from omnigent.harness_plugins import HarnessContribution


def get_contribution() -> HarnessContribution:
    """Return the Rovo Dev harness contribution.

    Called once at startup by Omnigent's plugin discovery. The returned
    :class:`HarnessContribution` tells the registry:

    - ``rovo-cli`` is a valid harness backed by the module at
      ``omnigent.community.harness.rovo.inner.rovo_harness``
    - ``rovo`` is a user-facing alias for ``rovo-cli``
    - ``HARNESS_ROVO_MODEL`` is the env var for model overrides
    - Install/auth metadata so ``omnigent setup`` can guide users
    """
    return HarnessContribution(
        name="omnigent-rovo",
        valid_harnesses=frozenset({"rovo-cli"}),
        harness_modules={
            "rovo-cli": "omnigent.community.harness.rovo.inner.rovo_harness",
        },
        aliases={"rovo": "rovo-cli"},
        native_harnesses=frozenset(),  # rovo is not a tmux-native harness
        native_agents=(),
        install_specs={
            "rovo": HarnessInstallSpec(
                display="Rovo (ACP)",
                binary="rovo",
                package=None,  # rovo is installed outside pip
                install_hint=(
                    "Install the Rovo CLI with ACP support, "
                    "then run: rovo auth login. "
                    "For older installations, set HARNESS_ROVO_ACLI_PATH to acli."
                ),
                login_args=("auth", "login"),
                logout_args=("auth", "logout"),
                status_args=("auth", "status"),
                auth_hint="Run `rovo auth login` to authenticate.",
            ),
        },
        harness_install_keys={"rovo-cli": "rovo"},
        model_env_keys={"rovo-cli": "HARNESS_ROVO_MODEL"},
        spawn_env_builders={},  # rovo reads HARNESS_ROVO_* directly from env
        missing_install_package={"rovo-cli": "omnigent-rovo"},
        harness_labels={"rovo-cli": "Rovo Dev"},
    )
