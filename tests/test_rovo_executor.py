"""Tests for ``omnigent.community.harness.rovo.inner.rovo_executor``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omnigent.community.harness.rovo.inner.rovo_executor import (
    RovoExecutor,
    _boot_error_message,
    _content_text,
    _is_first_turn,
    _latest_user_text,
    _session_key,
    _to_acp_prompt,
    _translate_update,
)
from tests.conftest import (
    ExecutorError,
    ReasoningChunk,
    TextChunk,
    ToolCallComplete,
    ToolCallRequest,
    ToolCallStatus,
    TurnComplete,
)

# ---------------------------------------------------------------------------
# Pure-function helpers
# ---------------------------------------------------------------------------


class TestSessionKey:
    def test_returns_session_id_from_first_message(self) -> None:
        msgs = [{"role": "user", "content": "hi", "session_id": "abc"}]
        assert _session_key(msgs) == "abc"

    def test_falls_back_to_default(self) -> None:
        msgs = [{"role": "user", "content": "hi"}]
        assert _session_key(msgs) == "default"

    def test_empty_messages_returns_default(self) -> None:
        assert _session_key([]) == "default"

    def test_ignores_none_session_id(self) -> None:
        msgs = [{"role": "user", "content": "hi", "session_id": None}]
        assert _session_key(msgs) == "default"


class TestLatestUserText:
    def test_extracts_string_content(self) -> None:
        msgs = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "second"},
        ]
        assert _latest_user_text(msgs) == "second"

    def test_extracts_non_string_content_as_json(self) -> None:
        msgs = [{"role": "user", "content": ["a", "b"]}]
        result = _latest_user_text(msgs)
        assert '"a"' in result and '"b"' in result

    def test_returns_empty_when_no_user_messages(self) -> None:
        msgs = [{"role": "assistant", "content": "reply"}]
        assert _latest_user_text(msgs) == ""

    def test_returns_empty_when_content_is_none(self) -> None:
        msgs = [{"role": "user", "content": None}]
        assert _latest_user_text(msgs) == ""

    def test_returns_empty_for_empty_list(self) -> None:
        assert _latest_user_text([]) == ""


class TestToAcpPrompt:
    def test_wraps_text(self) -> None:
        result = _to_acp_prompt("hello")
        assert result == [{"type": "text", "text": "hello"}]

    def test_empty_text(self) -> None:
        result = _to_acp_prompt("")
        assert result == [{"type": "text", "text": ""}]


class TestContentText:
    def test_dict_with_type_text(self) -> None:
        assert _content_text({"type": "text", "text": "hi"}) == "hi"

    def test_dict_without_type_text(self) -> None:
        assert _content_text({"text": "fallback"}) == "fallback"

    def test_plain_string(self) -> None:
        assert _content_text("raw") == "raw"

    def test_other_type(self) -> None:
        assert _content_text(42) == ""

    def test_dict_no_text_key(self) -> None:
        assert _content_text({"type": "image"}) == ""


class TestIsFirstTurn:
    def test_single_user_message(self) -> None:
        assert _is_first_turn([{"role": "user", "content": "hi"}]) is True

    def test_multiple_user_messages(self) -> None:
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "bye"},
        ]
        assert _is_first_turn(msgs) is False

    def test_no_user_messages(self) -> None:
        assert _is_first_turn([{"role": "system", "content": "sys"}]) is True

    def test_empty(self) -> None:
        assert _is_first_turn([]) is True


# ---------------------------------------------------------------------------
# _translate_update
# ---------------------------------------------------------------------------


class TestTranslateUpdate:
    def test_agent_message_chunk(self) -> None:
        events = _translate_update(
            {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "hi"}},
            {},
        )
        assert len(events) == 1
        assert isinstance(events[0], TextChunk)
        assert events[0].text == "hi"

    def test_agent_message_chunk_empty_text(self) -> None:
        events = _translate_update(
            {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": ""}},
            {},
        )
        assert len(events) == 0

    def test_agent_thought_chunk(self) -> None:
        events = _translate_update(
            {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": "text", "text": "thinking..."},
            },
            {},
        )
        assert len(events) == 1
        assert isinstance(events[0], ReasoningChunk)
        assert events[0].delta == "thinking..."

    def test_tool_call(self) -> None:
        names: dict[str, str] = {}
        events = _translate_update(
            {
                "sessionUpdate": "tool_call",
                "toolCallId": "tc-1",
                "title": "read_file",
                "rawInput": {"path": "foo.py"},
            },
            names,
        )
        assert len(events) == 1
        assert isinstance(events[0], ToolCallRequest)
        assert events[0].name == "read_file"
        assert events[0].args == {"path": "foo.py"}
        assert events[0].metadata == {"call_id": "tc-1"}
        # Side effect: name recorded
        assert names["tc-1"] == "read_file"

    def test_tool_call_uses_kind_fallback(self) -> None:
        names: dict[str, str] = {}
        events = _translate_update(
            {
                "sessionUpdate": "tool_call",
                "toolCallId": "tc-2",
                "kind": "bash",
            },
            names,
        )
        assert events[0].name == "bash"

    def test_tool_call_update_completed(self) -> None:
        names = {"tc-1": "read_file"}
        events = _translate_update(
            {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "tc-1",
                "status": "completed",
                "rawOutput": "file contents here",
            },
            names,
        )
        assert len(events) == 1
        assert isinstance(events[0], ToolCallComplete)
        assert events[0].name == "read_file"
        assert events[0].status == ToolCallStatus.SUCCESS
        assert events[0].result == "file contents here"

    def test_tool_call_update_failed(self) -> None:
        names = {"tc-1": "write_file"}
        events = _translate_update(
            {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "tc-1",
                "status": "failed",
            },
            names,
        )
        assert len(events) == 1
        assert isinstance(events[0], ToolCallComplete)
        assert events[0].status == ToolCallStatus.ERROR

    def test_tool_call_update_running_ignored(self) -> None:
        events = _translate_update(
            {"sessionUpdate": "tool_call_update", "status": "running"},
            {},
        )
        assert len(events) == 0

    def test_unknown_session_update_ignored(self) -> None:
        events = _translate_update({"sessionUpdate": "unknown_type"}, {})
        assert len(events) == 0


# ---------------------------------------------------------------------------
# _boot_error_message
# ---------------------------------------------------------------------------


class TestBootErrorMessage:
    def test_without_stderr(self) -> None:
        from omnigent.community.harness.rovo.inner.rovo_executor import _RovoSession

        state = _RovoSession()
        msg = _boot_error_message(RuntimeError("nope"), state)
        assert "Failed to start Rovo Dev" in msg
        assert "RuntimeError: nope" in msg

    def test_with_stderr(self) -> None:
        from omnigent.community.harness.rovo.inner.rovo_executor import _RovoSession

        state = _RovoSession()
        mock_client = MagicMock()
        mock_client.stderr_tail = "auth expired"
        state.client = mock_client
        msg = _boot_error_message(ValueError("oops"), state)
        assert "auth expired" in msg


# ---------------------------------------------------------------------------
# RovoExecutor — capability flags and session management
# ---------------------------------------------------------------------------


class TestRovoExecutorCapabilities:
    def test_supports_streaming(self) -> None:
        ex = RovoExecutor()
        assert ex.supports_streaming() is True

    def test_supports_tool_calling(self) -> None:
        ex = RovoExecutor()
        assert ex.supports_tool_calling() is True

    def test_handles_tools_internally(self) -> None:
        ex = RovoExecutor()
        assert ex.handles_tools_internally() is True

    def test_does_not_support_live_message_queue(self) -> None:
        ex = RovoExecutor()
        assert ex.supports_live_message_queue() is False


class TestRovoExecutorCommand:
    def test_command_uses_defaults(self) -> None:
        ex = RovoExecutor()
        assert ex._command() == ["acli", "rovodev", "acp"]

    def test_command_uses_custom_acli_path(self) -> None:
        ex = RovoExecutor(acli_path="/opt/acli")
        assert ex._command()[0] == "/opt/acli"

    def test_command_includes_config_file(self) -> None:
        ex = RovoExecutor(config_file="/my/config.yml")
        cmd = ex._command()
        assert "--config-file" in cmd
        assert "/my/config.yml" in cmd

    def test_command_includes_site_url(self) -> None:
        ex = RovoExecutor(site_url="https://test.atlassian.net")
        cmd = ex._command()
        assert "--site-url" in cmd
        assert "https://test.atlassian.net" in cmd


class TestRovoExecutorSessionLifecycle:
    @pytest.mark.asyncio
    async def test_enqueue_session_message_returns_false(self) -> None:
        ex = RovoExecutor()
        result = await ex.enqueue_session_message("key", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_close_session_removes_session(self) -> None:
        ex = RovoExecutor()
        from omnigent.community.harness.rovo.inner.rovo_executor import _RovoSession

        state = _RovoSession()
        state.client = MagicMock()
        state.client.close = AsyncMock()
        ex._sessions["test-key"] = state

        await ex.close_session("test-key")
        assert "test-key" not in ex._sessions

    @pytest.mark.asyncio
    async def test_close_session_noop_for_unknown_key(self) -> None:
        ex = RovoExecutor()
        await ex.close_session("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_close_clears_all_sessions(self) -> None:
        ex = RovoExecutor()
        from omnigent.community.harness.rovo.inner.rovo_executor import _RovoSession

        for key in ("s1", "s2"):
            state = _RovoSession()
            state.client = MagicMock()
            state.client.close = AsyncMock()
            ex._sessions[key] = state

        await ex.close()
        assert len(ex._sessions) == 0

    @pytest.mark.asyncio
    async def test_interrupt_session_returns_false_when_no_session(self) -> None:
        ex = RovoExecutor()
        result = await ex.interrupt_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_interrupt_session_cancels_active_session(self) -> None:
        ex = RovoExecutor()
        from omnigent.community.harness.rovo.inner.rovo_executor import _RovoSession

        state = _RovoSession()
        state.session_id = "sid-1"
        mock_client = MagicMock()
        mock_client.session_cancel = AsyncMock()
        state.client = mock_client
        ex._sessions["key"] = state

        result = await ex.interrupt_session("key")
        assert result is True
        mock_client.session_cancel.assert_awaited_once_with("sid-1")


# ---------------------------------------------------------------------------
# RovoExecutor.run_turn — integration-style with mocked ACP
# ---------------------------------------------------------------------------


class TestRovoExecutorRunTurn:
    @pytest.mark.asyncio
    async def test_run_turn_yields_events_and_turn_complete(self) -> None:
        """Full happy-path: ACP session boots, prompt returns, events stream."""
        ex = RovoExecutor(cwd="/tmp")

        # Mock the AcpClient that _RovoSession will create
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.initialize = AsyncMock(return_value={})
        mock_client.session_new = AsyncMock(
            return_value={"sessionId": "s1", "models": {}}
        )

        # session_prompt should push updates via the on_update callback, then return
        async def fake_prompt(session_id, prompt, *, on_update, timeout):
            await on_update(
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "Hello!"},
                }
            )
            return "end_turn"

        mock_client.session_prompt = fake_prompt
        mock_client.session_cancel = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.stderr_tail = ""

        with patch(
            "omnigent.community.harness.rovo.inner.rovo_executor.AcpClient",
            return_value=mock_client,
        ):
            messages = [{"role": "user", "content": "hi", "session_id": "test"}]
            events = []
            async for event in ex.run_turn(messages, [], "system prompt"):
                events.append(event)

        # Should have a TextChunk + TurnComplete
        text_chunks = [e for e in events if isinstance(e, TextChunk)]
        turn_completes = [e for e in events if isinstance(e, TurnComplete)]
        assert len(text_chunks) >= 1
        assert text_chunks[0].text == "Hello!"
        assert len(turn_completes) == 1
        assert turn_completes[0].response == "Hello!"

        await ex.close()

    @pytest.mark.asyncio
    async def test_run_turn_boot_failure_yields_error(self) -> None:
        """When the ACP subprocess fails to start, yield ExecutorError."""
        ex = RovoExecutor(cwd="/tmp")

        mock_client = AsyncMock()
        mock_client.start = AsyncMock(side_effect=OSError("acli not found"))
        mock_client.stderr_tail = ""
        mock_client.close = AsyncMock()

        with patch(
            "omnigent.community.harness.rovo.inner.rovo_executor.AcpClient",
            return_value=mock_client,
        ):
            messages = [{"role": "user", "content": "hi"}]
            events = []
            async for event in ex.run_turn(messages, [], ""):
                events.append(event)

        errors = [e for e in events if isinstance(e, ExecutorError)]
        assert len(errors) == 1
        assert "Failed to start Rovo Dev" in errors[0].message

    @pytest.mark.asyncio
    async def test_run_turn_with_model_override(self) -> None:
        """Model override is passed through to set_model."""
        ex = RovoExecutor(cwd="/tmp", model="claude-test")

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.initialize = AsyncMock(return_value={})
        mock_client.session_new = AsyncMock(
            return_value={"sessionId": "s1", "models": {"currentModelId": "default"}}
        )
        mock_client.session_set_model = AsyncMock()

        async def fake_prompt(session_id, prompt, *, on_update, timeout):
            return "end_turn"

        mock_client.session_prompt = fake_prompt
        mock_client.session_cancel = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.stderr_tail = ""

        with patch(
            "omnigent.community.harness.rovo.inner.rovo_executor.AcpClient",
            return_value=mock_client,
        ):
            messages = [{"role": "user", "content": "hi"}]
            events = []
            async for event in ex.run_turn(messages, [], ""):
                events.append(event)

        mock_client.session_set_model.assert_awaited_once_with("s1", "claude-test")
        await ex.close()

    @pytest.mark.asyncio
    async def test_run_turn_prepends_system_prompt_on_first_turn(self) -> None:
        """System prompt should be prepended only on the first turn."""
        ex = RovoExecutor(cwd="/tmp")
        captured_prompts: list = []

        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.initialize = AsyncMock(return_value={})
        mock_client.session_new = AsyncMock(
            return_value={"sessionId": "s1", "models": {}}
        )

        async def fake_prompt(session_id, prompt, *, on_update, timeout):
            captured_prompts.append(prompt)
            return "end_turn"

        mock_client.session_prompt = fake_prompt
        mock_client.session_cancel = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.stderr_tail = ""

        with patch(
            "omnigent.community.harness.rovo.inner.rovo_executor.AcpClient",
            return_value=mock_client,
        ):
            # First turn — only one user message
            messages = [{"role": "user", "content": "hello"}]
            async for _ in ex.run_turn(messages, [], "You are helpful"):
                pass

        assert len(captured_prompts) == 1
        prompt_text = captured_prompts[0][0]["text"]
        assert prompt_text.startswith("You are helpful")
        assert "hello" in prompt_text
        await ex.close()
