"""Behavioral regression tests for installation and ACP resource ownership."""

import asyncio
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from omnigent.community.harness.rovo.inner.rovo_acp import AcpClient, AcpProcessExited
from omnigent.community.harness.rovo.inner.rovo_executor import _RovoSession


def test_checkout_imports_real_core_and_discovers_plugin():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from omnigent.harness_plugins import plugin_state
from omnigent.community.harness.rovo.inner.rovo_harness import create_app
from fastapi.testclient import TestClient
assert 'omnigent-rovo' in [c.name for c in plugin_state().contributions]
with TestClient(create_app()) as client:
    assert client.get('/openapi.json').status_code == 200
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


async def test_failed_write_removes_pending_request():
    client = AcpClient(["missing"])
    with pytest.raises(AcpProcessExited):
        await client.request("initialize")
    assert not client._pending


async def test_cancelled_request_removes_pending_request():
    client = AcpClient(["unused"])
    client._write = AsyncMock()
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(client.request("initialize"), timeout=0.01)
    assert not client._pending


async def test_string_server_request_id_is_preserved():
    client = AcpClient(["unused"])
    client._write = AsyncMock()
    await client._dispatch(
        {
            "id": "permission-uuid",
            "method": "session/request_permission",
            "params": {"options": [{"kind": "allow_once", "optionId": "yes"}]},
        }
    )
    assert client._write.call_args.args[0]["id"] == "permission-uuid"


@pytest.mark.parametrize("stage", ["initialize", "session_new"])
@pytest.mark.parametrize("error", [RuntimeError("boot failed"), asyncio.CancelledError()])
async def test_partial_boot_closes_subprocess(stage, error):
    client = AsyncMock()
    getattr(client, stage).side_effect = error
    state = _RovoSession()
    with (
        patch("omnigent.community.harness.rovo.inner.rovo_executor.AcpClient", return_value=client),
        pytest.raises(type(error)),
    ):
        await state.ensure(command=["unused"], env=None, cwd="/tmp")
    client.close.assert_awaited_once()
    assert state.client is None


async def test_request_after_stdout_eof_fails_immediately():
    client = AcpClient([sys.executable, "-c", "pass"])
    await client.start()
    try:
        await asyncio.wait_for(client._reader_task, timeout=5)
        with pytest.raises(AcpProcessExited):
            await asyncio.wait_for(client.request("initialize"), timeout=0.1)
    finally:
        await client.close()


async def test_prompt_timeout_sends_cancel():
    client = AcpClient(["unused"])
    client._write = AsyncMock()
    client.session_cancel = AsyncMock()
    with pytest.raises(TimeoutError):
        await client.session_prompt("s1", [], on_update=AsyncMock(), timeout=0.01)
    client.session_cancel.assert_awaited_once_with("s1")
    assert not client._pending
    assert not client._update_handlers


def test_rovo_launcher_and_explicit_acli_compatibility():
    from omnigent.community.harness.rovo.inner.rovo_acp import default_acp_command

    assert default_acp_command() == ["rovo", "acp"]
    assert default_acp_command(rovo_path="/opt/rovo") == ["/opt/rovo", "acp"]
    assert default_acp_command(acli_path="/opt/acli") == ["/opt/acli", "rovodev", "acp"]
    with pytest.raises(ValueError, match="both"):
        default_acp_command(rovo_path="/opt/rovo", acli_path="/opt/acli")


def test_rovo_path_env_reaches_command(monkeypatch):
    from omnigent.community.harness.rovo.inner.rovo_harness import _build_rovo_executor

    monkeypatch.setenv("HARNESS_ROVO_PATH", "/opt/rovo")
    monkeypatch.delenv("HARNESS_ROVO_ACLI_PATH", raising=False)
    assert _build_rovo_executor()._command() == ["/opt/rovo", "acp"]


async def test_closing_turn_iterator_cancels_prompt():
    from omnigent.community.harness.rovo.inner.rovo_executor import RovoExecutor

    client = AsyncMock()
    client.session_new.return_value = {"sessionId": "s1"}
    cancelled = asyncio.Event()

    async def prompt(session_id, content, *, on_update, timeout):
        try:
            await on_update({"sessionUpdate": "agent_message_chunk", "content": {"text": "hi"}})
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client.session_prompt = prompt
    executor = RovoExecutor()
    with patch(
        "omnigent.community.harness.rovo.inner.rovo_executor.AcpClient", return_value=client
    ):
        turn = executor.run_turn([{"role": "user", "content": "hi"}], [], "")
        await anext(turn)
        await turn.aclose()
        try:
            await asyncio.wait_for(cancelled.wait(), timeout=0.2)
        finally:
            await executor.close()


async def test_boot_timeout_cleans_up():
    client = AsyncMock()
    client.initialize.side_effect = lambda: None

    async def hang():
        await asyncio.Event().wait()

    client.initialize.side_effect = hang
    state = _RovoSession()
    with (
        patch("omnigent.community.harness.rovo.inner.rovo_executor.AcpClient", return_value=client),
        pytest.raises(TimeoutError, match="startup exceeded"),
    ):
        await state.ensure(command=["unused"], env=None, cwd="/tmp", startup_timeout=0.01)
    client.close.assert_awaited_once()


async def test_headless_launch_disables_wrapper_auto_upgrade(monkeypatch):
    from omnigent.community.harness.rovo.inner.rovo_executor import RovoExecutor

    monkeypatch.delenv("ROVO_UPGRADE_MODE", raising=False)
    executor = RovoExecutor(env={"PATH": "/bin"})
    client = AsyncMock()
    client.session_new.return_value = {"sessionId": "s1"}
    client.session_prompt.return_value = "end_turn"
    with patch(
        "omnigent.community.harness.rovo.inner.rovo_executor.AcpClient",
        return_value=client,
    ) as factory:
        try:
            _ = [e async for e in executor.run_turn([{"role": "user", "content": "hi"}], [], "")]
            assert factory.call_args.kwargs["env"] == {"PATH": "/bin", "ROVO_UPGRADE_MODE": "off"}
        finally:
            await executor.close()


def test_startup_timeout_configuration(monkeypatch):
    from omnigent.community.harness.rovo.inner.rovo_harness import _build_rovo_executor

    monkeypatch.setenv("HARNESS_ROVO_STARTUP_TIMEOUT", "180")
    assert _build_rovo_executor()._startup_timeout == 180
