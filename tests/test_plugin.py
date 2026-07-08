"""Tests for ``omnigent.community.harnesses.rovo.plugin.get_contribution``."""

from __future__ import annotations

from omnigent.community.harness.rovo.plugin import get_contribution


class TestGetContribution:
    """Verify the plugin entry-point returns a well-formed HarnessContribution."""

    def test_returns_harness_contribution(self) -> None:
        contrib = get_contribution()
        assert contrib.name == "omnigent-rovo"

    def test_valid_harnesses(self) -> None:
        contrib = get_contribution()
        assert "rovo-cli" in contrib.valid_harnesses

    def test_alias_rovo_resolves_to_rovo_cli(self) -> None:
        contrib = get_contribution()
        assert contrib.aliases == {"rovo": "rovo-cli"}

    def test_harness_module_path(self) -> None:
        contrib = get_contribution()
        assert contrib.harness_modules["rovo-cli"] == (
            "omnigent.community.harness.rovo.inner.rovo_harness"
        )

    def test_install_spec_present(self) -> None:
        contrib = get_contribution()
        spec = contrib.install_specs["rovo"]
        assert spec.binary == "acli"
        assert "acli" in spec.install_hint
        assert spec.login_args == ("rovodev", "auth", "login")
        assert spec.logout_args == ("rovodev", "auth", "logout")
        assert spec.status_args == ("rovodev", "auth", "status")

    def test_model_env_key(self) -> None:
        contrib = get_contribution()
        assert contrib.model_env_keys["rovo-cli"] == "HARNESS_ROVO_MODEL"

    def test_harness_install_keys(self) -> None:
        contrib = get_contribution()
        assert contrib.harness_install_keys == {"rovo-cli": "rovo"}

    def test_harness_labels(self) -> None:
        contrib = get_contribution()
        assert contrib.harness_labels == {"rovo-cli": "Rovo Dev"}

    def test_native_harnesses_empty(self) -> None:
        """Rovo is not a tmux-native harness."""
        contrib = get_contribution()
        assert contrib.native_harnesses == frozenset()

    def test_missing_install_package(self) -> None:
        contrib = get_contribution()
        assert contrib.missing_install_package == {"rovo-cli": "omnigent-rovo"}
