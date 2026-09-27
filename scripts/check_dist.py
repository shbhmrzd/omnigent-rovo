"""Check built archives contain only intentional public package files."""

import sys
import tarfile
from pathlib import Path
from zipfile import ZipFile

root = Path(sys.argv[1])
allowed = {
    ".gitignore",
    "omnigent",
    "tests",
    "scripts",
    "README.md",
    "CHANGELOG.md",
    "RELEASING.md",
    "LICENSE",
    "pyproject.toml",
    "PKG-INFO",
}
archives = list(root.glob("*.tar.gz"))
wheels = list(root.glob("*.whl"))
assert archives and wheels, "Build both a source archive and wheel first"
for archive in archives:
    with tarfile.open(archive) as handle:
        for member in handle.getmembers():
            parts = Path(member.name).parts
            assert len(parts) > 1 and parts[1] in allowed, member.name
for wheel in wheels:
    with ZipFile(wheel) as handle:
        for name in handle.namelist():
            assert name.startswith("omnigent/community/harness/rovo/") or ".dist-info/" in name, (
                name
            )
print("Source archive and wheel contents: OK")
