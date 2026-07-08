"""Tests for ``omnigent.community.harnesses.rovo.inner.rovo_acp``."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omnigent.community.harness.rovo.inner.rovo_acp import (
    ACP_PROTOCOL_VERSION,
    AcpClient,
    AcpError,
    AcpProcessExited,
    _auto_allow_permission,
    _format_rpc_error,
    default_acp_command,
)


# ---------------------------------------------------------------------------
# default_acp_command
# ---------------------------------------------------------------------------

class TestDefaultAcpCommand:
    def test_bare_defaults(self) -> None:
        cmd = default_acp_command()
        assert cmd == ["acli", "rovodev", "acp"]

    def test_custom_acli_path(self) -> None:
        cmd = default_acp_command(acli_path="/usr/local/bin/acli")
        assert cmd[0] == "/usr/local/bin/acli"
        assert cmd[1:] == ["rovodev", "acp"]

    def test_config_file(self) -> None:
        cmd = default_acp_command(config_file="/etc/rovo.yml")
        assert "--config-file" in cmd
        idx = cmd.index("--config-file")
        assert cmd[idx + 1] == "/etc/rovo.yml"

    def test_site_url(self) -> None:
        cmd = default_acp_command(site_url="https://mysite.atlassian.net")
        assert "--site-url" in cmd
        idx = cmd.index("--site-url")
        assert cmd[idx + 1] == "https://mysite.atlassian.net"

    def test_all_options_together(self) -> None:
        cmd = default_acp_command(
            acli_path="/bin/acli",
            config_file="/cfg.yml",
            site_url="https://x.atlassian.net",
        )
        assert cmd[0] == "/bin/acli"
        assert "--config-file" in cmd
        assert "--site-url" in cmd


# ---------------------------------------------------------------------------
# _auto_allow_permission
# ---------------------------------------------------------------------------

class TestAutoAllowPermission:
    def test_no_options(self) -> None:
        result = _auto_allow_permission({})
        assert result == {"outcome": {"outcome": "selected"}}

    def test_empty_options_list(self) -> None:
        result = _auto_allow_permission({"options": []})
        assert result == {"outcome": {"outcome": "selected"}}

    def test_prefers_allow_once(self) -> None:
        result = _auto_allow_permission(
            {
                "options": [
                    {"optionId": "deny-1", "kind": "deny"},
                    {"optionId": "once-1", "kind": "allow_once"},
                    {"optionId": "always-1", "kind": "allow_always"},
                ]
            }
        )
        assert result["outcome"]["optionId"] == "once-1"

    def test_falls_back_to_allow_always(self) -> None:
        result = _auto_allow_permission(
            {
                "options": [
                    {"optionId": "deny-1", "kind": "deny"},
                    {"optionId": "always-1", "kind": "allow_always"},
                ]
            }
        )
        assert result["outcome"]["optionId"] == "always-1"

    def test_falls_back_to_allow_prefix(self) -> None:
        result = _auto_allow_permission(
            {
                "options": [
                    {"optionId": "deny-1", "kind": "deny"},
                    {"optionId": "allow-x", "kind": "allow_forever"},
                ]
            }
        )
        assert result["outcome"]["optionId"] == "allow-x"

    def test_falls_back_to_first_option(self) -> None:
        result = _auto_allow_permission(
            {
                "options": [
                    {"optionId": "whatever-1", "kind": "deny"},
                ]
            }
        )
        assert result["outcome"]["optionId"] == "whatever-1"

    def test_skips_options_without_option_id(self) -> None:
        result = _auto_allow_permission(
            {"options": [{"kind": "allow_once"}]}
        )
        assert result == {"outcome": {"outcome": "selected"}}


# ---------------------------------------------------------------------------
# _format_rpc_error
# ---------------------------------------------------------------------------

class TestFormatRpcError:
    def test_dict_with_code_and_message(self) -> None:
        out = _format_rpc_error({"code": -32600, "message": "Invalid Request"})
        assert "ACP error -32600" in out
        assert "Invalid Request" in out

    def test_dict_without_code(self) -> None:
        out = _format_rpc_error({"message": "bad"})
        assert out == "ACP error: bad"

    def test_dict_with_data(self) -> None:
        out = _format_rpc_error({"code": 1, "message": "err", "data": {"detail": "x"}})
        assert "detail" in out

    def test_non_dict(self) -> None:
        out = _format_rpc_error("something went wrong")
        assert out == "ACP error: something went wrong"


# ---------------------------------------------------------------------------
# AcpClient — unit tests with a mocked subprocess
# ---------------------------------------------------------------------------

def _make_mock_proc(
    stdout_lines: list[str] | None = None,
    stderr_lines: list[str] | None = None,
) -> MagicMock:
    """Build a mock ``asyncio.subprocess.Process``."""
    proc = MagicMock()
    proc.returncode = None

    # stdin
    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()

    # stdout — async readline that yields lines then b""
    lines = [line.encode() for line in (stdout_lines or [])] + [b""]
    proc.stdout = MagicMock()
    proc.stdout.readline = AsyncMock(side_effect=lines)

    # stderr
    stderr = [line.encode() for line in (stderr_lines or [])] + [b""]
    proc.stderr = MagicMock()
    proc.stderr.readline = AsyncMock(side_effect=stderr)

    proc.wait = AsyncMock(return_value=0)
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    return proc


class TestAcpClientLifecycle:

    @pytest.mark.asyncio
    async def test_start_spawns_subprocess(self) -> None:
        proc = _make_mock_proc()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            client = AcpClient(command=["acli", "rovodev", "acp"])
            await client.start()
            assert client._proc is proc
            await client.close()

    @pytest.mark.asyncio
    async def test_close_terminates_process(self) -> None:
        proc = _make_mock_proc()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            client = AcpClient(command=["acli", "rovodev", "acp"])
            await client.start()
            await client.close()
            proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_raises_when_closed(self) -> None:
        client = AcpClient(command=["echo"])
        client._closed = True
        with pytest.raises(AcpProcessExited, match="closed"):
            await client.request("test")


class TestAcpClientDispatch:

    @pytest.mark.asyncio
    async def test_dispatch_response_resolves_future(self) -> None:
        client = AcpClient(command=["echo"])
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        client._pending[1] = fut
        await client._dispatch({"id": 1, "result": {"ok": True}})
        assert fut.result() == {"ok": True}

    @pytest.mark.asyncio
    async def test_dispatch_error_sets_exception(self) -> None:
        client = AcpClient(command=["echo"])
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        client._pending[1] = fut
        await client._dispatch({"id": 1, "error": {"code": -1, "message": "fail"}})
        with pytest.raises(AcpError, match="fail"):
            fut.result()

    @pytest.mark.asyncio
    async def test_dispatch_notification_calls_handler(self) -> None:
        client = AcpClient(command=["echo"])
        received: list[dict] = []

        async def handler(update: dict) -> None:
            received.append(update)

        client._update_handlers["sess-1"] = handler
        await client._dispatch({
            "method": "session/update",
            "params": {"sessionId": "sess-1", "update": {"sessionUpdate": "agent_message_chunk"}},
        })
        assert len(received) == 1
        assert received[0]["sessionUpdate"] == "agent_message_chunk"

    @pytest.mark.asyncio
    async def test_dispatch_server_request_auto_allows_permission(self) -> None:
        client = AcpClient(command=["echo"])
        # Give it a mock proc with stdin so _write works
        proc = _make_mock_proc()
        client._proc = proc

        await client._dispatch({
            "id": 99,
            "method": "session/request_permission",
            "params": {
                "options": [
                    {"optionId": "allow-1", "kind": "allow_once"},
                ]
            },
        })
        # Verify it wrote a response
        proc.stdin.write.assert_called()
        written = proc.stdin.write.call_args[0][0].decode()
        response = json.loads(written)
        assert response["id"] == 99
        assert response["result"]["outcome"]["optionId"] == "allow-1"

    @pytest.mark.asyncio
    async def test_dispatch_server_request_uses_custom_handler(self) -> None:
        handler_called = False

        async def custom_handler(method: str, params: dict) -> dict:
            nonlocal handler_called
            handler_called = True
            return {"custom": True}

        client = AcpClient(command=["echo"], request_handler=custom_handler)
        proc = _make_mock_proc()
        client._proc = proc

        await client._dispatch({
            "id": 42,
            "method": "custom/method",
            "params": {"key": "value"},
        })
        assert handler_called
        written = proc.stdin.write.call_args[0][0].decode()
        response = json.loads(written)
        assert response["result"]["custom"] is True


class TestAcpClientStderrTail:
    @pytest.mark.asyncio
    async def test_stderr_tail_returns_joined_lines(self) -> None:
        client = AcpClient(command=["echo"])
        client._stderr_tail = ["line1", "line2"]
        assert client.stderr_tail == "line1\nline2"

    @pytest.mark.asyncio
    async def test_stderr_tail_empty(self) -> None:
        client = AcpClient(command=["echo"])
        assert client.stderr_tail == ""


class TestAcpClientNotify:
    @pytest.mark.asyncio
    async def test_notify_sends_without_id(self) -> None:
        client = AcpClient(command=["echo"])
        proc = _make_mock_proc()
        client._proc = proc

        await client.notify("session/cancel", {"sessionId": "s1"})
        written = proc.stdin.write.call_args[0][0].decode()
        msg = json.loads(written)
        assert "id" not in msg
        assert msg["method"] == "session/cancel"


class TestAcpClientHighLevel:
    @pytest.mark.asyncio
    async def test_initialize_sends_correct_params(self) -> None:
        client = AcpClient(command=["echo"])
        client._closed = False

        # Mock request to capture the call
        async def fake_request(method, params=None):
            return {"protocolVersion": ACP_PROTOCOL_VERSION}

        client.request = fake_request  # type: ignore[assignment]
        result = await client.initialize()
        assert result["protocolVersion"] == ACP_PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_session_cancel_suppresses_errors(self) -> None:
        client = AcpClient(command=["echo"])

        async def failing_notify(method, params=None):
            raise RuntimeError("boom")

        client.notify = failing_notify  # type: ignore[assignment]
        # Should not raise
        await client.session_cancel("sess-1")
