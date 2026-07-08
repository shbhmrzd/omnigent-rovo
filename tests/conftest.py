"""Conftest: install lightweight stubs for ``omnigent`` core modules.

The ``omnigent`` core library is a separate package and may not be installed in
the dev environment for this plugin.  We inject minimal stand-ins so that
``omnigent.community.harness.rovo.*`` can be imported without the full core.
"""

from __future__ import annotations

import os
import sys
import types
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_module(fqn: str, attrs: dict[str, Any] | None = None) -> types.ModuleType:
    """Register *fqn* in ``sys.modules`` (and all parent packages) if absent.

    When creating intermediate parent packages that correspond to real on-disk
    directories (e.g. ``omnigent``), we set their ``__path__`` to the real
    filesystem path so the normal import machinery can still discover
    ``omnigent.community.harness.*`` from the workspace tree.
    """
    parts = fqn.split(".")
    for i in range(1, len(parts) + 1):
        partial = ".".join(parts[:i])
        if partial not in sys.modules:
            mod = types.ModuleType(partial)
            # Check if there's a real directory on disk for this module
            disk_path = os.path.join(_PROJECT_ROOT, *parts[:i])
            if os.path.isdir(disk_path):
                mod.__path__ = [disk_path]  # type: ignore[attr-defined]
                init_file = os.path.join(disk_path, "__init__.py")
                if os.path.isfile(init_file):
                    mod.__file__ = init_file  # type: ignore[attr-defined]
            else:
                mod.__path__ = []  # type: ignore[attr-defined]
            sys.modules[partial] = mod
    mod = sys.modules[fqn]
    for k, v in (attrs or {}).items():
        setattr(mod, k, v)
    return mod


# ---------------------------------------------------------------------------
# Stub types that mirror the real omnigent core just enough for imports.
# ---------------------------------------------------------------------------

# -- omnigent.inner.executor ------------------------------------------------

Message = dict[str, Any]
ToolSpec = dict[str, Any]
EnqueuedContent = dict[str, Any]


@dataclass
class ExecutorConfig:
    model: str | None = None


class ExecutorEvent:
    """Base class for all executor events."""


@dataclass
class TextChunk(ExecutorEvent):
    text: str = ""


@dataclass
class ReasoningChunk(ExecutorEvent):
    delta: str = ""
    event_type: str = ""


@dataclass
class ToolCallRequest(ExecutorEvent):
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolCallStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ToolCallComplete(ExecutorEvent):
    name: str = ""
    status: ToolCallStatus = ToolCallStatus.SUCCESS
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnComplete(ExecutorEvent):
    response: str | None = None
    usage: Any = None


@dataclass
class ExecutorError(ExecutorEvent):
    message: str = ""
    retryable: bool = True


class Executor:
    """Minimal stub of the abstract base executor."""

    def supports_streaming(self) -> bool:
        return False

    def supports_tool_calling(self) -> bool:
        return False

    def handles_tools_internally(self) -> bool:
        return False

    def supports_live_message_queue(self) -> bool:
        return False

    async def interrupt_session(self, session_key: str) -> bool:
        return False

    async def enqueue_session_message(self, session_key: str, content: Any) -> bool:
        return False

    async def close_session(self, session_key: str) -> None:
        pass

    async def close(self) -> None:
        pass

    async def run_turn(self, messages, tools, system_prompt, config=None):
        raise NotImplementedError
        yield  # make it an async generator  # noqa: RET503


# -- omnigent.harness_install_spec ------------------------------------------

@dataclass
class HarnessInstallSpec:
    display: str = ""
    binary: str | None = None
    package: str | None = None
    install_hint: str = ""
    login_args: tuple[str, ...] = ()
    logout_args: tuple[str, ...] = ()
    status_args: tuple[str, ...] = ()
    auth_hint: str = ""


# -- omnigent.harness_plugins -----------------------------------------------

@dataclass
class HarnessContribution:
    name: str = ""
    valid_harnesses: frozenset[str] = field(default_factory=frozenset)
    harness_modules: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    native_harnesses: frozenset[str] = field(default_factory=frozenset)
    native_agents: tuple = ()
    install_specs: dict[str, HarnessInstallSpec] = field(default_factory=dict)
    harness_install_keys: dict[str, str] = field(default_factory=dict)
    model_env_keys: dict[str, str] = field(default_factory=dict)
    spawn_env_builders: dict = field(default_factory=dict)
    missing_install_package: dict[str, str] = field(default_factory=dict)
    harness_labels: dict[str, str] = field(default_factory=dict)


# -- omnigent.runtime.harnesses._executor_adapter --------------------------

class ExecutorAdapter:
    """Minimal stub — only needs to accept ``executor_factory``."""

    def __init__(self, *, executor_factory):
        self._factory = executor_factory

    def build(self):
        from unittest.mock import MagicMock
        return MagicMock(name="FastAPI-stub")


# ---------------------------------------------------------------------------
# Register all stubs in sys.modules BEFORE any test imports the plugin code.
# ---------------------------------------------------------------------------

_ensure_module("omnigent.inner.executor", {
    "EnqueuedContent": EnqueuedContent,
    "Executor": Executor,
    "ExecutorConfig": ExecutorConfig,
    "ExecutorError": ExecutorError,
    "ExecutorEvent": ExecutorEvent,
    "Message": Message,
    "ReasoningChunk": ReasoningChunk,
    "TextChunk": TextChunk,
    "ToolCallComplete": ToolCallComplete,
    "ToolCallRequest": ToolCallRequest,
    "ToolCallStatus": ToolCallStatus,
    "ToolSpec": ToolSpec,
    "TurnComplete": TurnComplete,
})

_ensure_module("omnigent.harness_install_spec", {
    "HarnessInstallSpec": HarnessInstallSpec,
})

_ensure_module("omnigent.harness_plugins", {
    "HarnessContribution": HarnessContribution,
})

_ensure_module("omnigent.runtime.harnesses._executor_adapter", {
    "ExecutorAdapter": ExecutorAdapter,
})

# Also ensure intermediate namespace packages exist.
_ensure_module("omnigent.runtime")
_ensure_module("omnigent.runtime.harnesses")
