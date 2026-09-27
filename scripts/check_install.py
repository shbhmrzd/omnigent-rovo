"""Verify a built wheel is installed without replacing Omnigent's own packages."""

from importlib.metadata import distribution

from fastapi.testclient import TestClient
from omnigent.harness_plugins import harness_aliases, plugin_state

from omnigent.community.harness.rovo.inner.rovo_harness import create_app

installed = distribution("omnigent-rovo")
files = {str(path) for path in installed.files or []}
assert "omnigent/community/harness/rovo/plugin.py" in files, "Install a wheel, not editable"
assert not files.intersection(
    {
        "omnigent/__init__.py",
        "omnigent/community/__init__.py",
        "omnigent/community/harness/__init__.py",
    }
), "Plugin must not overwrite core package initializers"
assert "omnigent-rovo" in [item.name for item in plugin_state().contributions]
assert harness_aliases()["rovo"] == "rovo-cli"
with TestClient(create_app()) as client:
    assert client.get("/health").status_code == 200
print("Wheel installation, plugin discovery, and HTTP health: OK")
