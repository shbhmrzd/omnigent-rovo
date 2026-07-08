"""RovoExecutor: run agents through Rovo Dev's ACP server (``acli rovodev acp``).

This is the per-harness "translator" in Omnigent's harness architecture. The
shared :class:`~omnigent.runtime.harnesses._executor_adapter.ExecutorAdapter`
drives any :class:`~omnigent.inner.executor.Executor`; this subclass implements
``run_turn`` by spawning a Rovo Dev ACP session (via
:class:`.rovo_acp.AcpClient`) and translating the streamed ACP
``session/update`` notifications into Omnigent
:class:`~omnigent.inner.executor.ExecutorEvent` instances.

Event mapping (confirmed against ``acli rovodev acp`` over stdio):

==============================  ===============================================
ACP ``update.sessionUpdate``    Omnigent event
==============================  ===============================================
``agent_message_chunk``         :class:`TextChunk`
``agent_thought_chunk``         :class:`ReasoningChunk`
``tool_call``                   :class:`ToolCallRequest`
``tool_call_update`` (done)     :class:`ToolCallComplete`
(prompt result) ``stopReason``  :class:`TurnComplete`
==============================  ===============================================

Rovo Dev runs its own agent loop and executes its own tools, so
:meth:`handles_tools_internally` returns ``True`` — the Session must not
re-execute tools; the tool events emitted here are informational.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator

from omnigent.inner.executor import (
    EnqueuedContent,
    Executor,
    ExecutorConfig,
    ExecutorError,
    ExecutorEvent,
    Message,
    ReasoningChunk,
    TextChunk,
    ToolCallComplete,
    ToolCallRequest,
    ToolCallStatus,
    ToolSpec,
    TurnComplete,
)

from .rovo_acp import AcpClient, AcpError, JsonObj, default_acp_command

logger = logging.getLogger(__name__)

# Rovo Dev exposes models by human-readable display name (e.g.
# "Claude Sonnet 4.6"). When no model is pinned we let Rovo pick its own
# default by not passing a model at session/new.
_DEFAULT_TURN_TIMEOUT_SECONDS = 600.0


def _session_key(messages: list[Message]) -> str:
    """Derive a stable session key from the conversation's first message.

    Mirrors the codex executor's approach: the first message carries a stable
    ``session_id`` for the conversation when the runner provides one; otherwise
    we fall back to a constant so a single-session client still reuses one ACP
    subprocess across turns.
    """
    for msg in messages:
        sid = msg.get("session_id")
        if sid:
            return str(sid)
    return "default"


def _latest_user_text(messages: list[Message]) -> str:
    """Extract the latest user message as plain text for an ACP prompt."""
    import json

    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if content is None:
                return ""
            if isinstance(content, str):
                return content
            return json.dumps(content)
    return ""


def _to_acp_prompt(text: str) -> list[JsonObj]:
    """Wrap plain text into ACP prompt content blocks."""
    return [{"type": "text", "text": text}]


def _content_text(content: object) -> str:
    """Pull the ``text`` out of an ACP content block (or stringify it)."""
    if isinstance(content, dict):
        if content.get("type") == "text":
            return str(content.get("text", ""))
        return str(content.get("text", "")) or ""
    if isinstance(content, str):
        return content
    return ""


class _RovoSession:
    """Holds the live ACP client + session id for one Omnigent conversation."""

    def __init__(self) -> None:
        self.client: AcpClient | None = None
        self.session_id: str | None = None
        self.available_models: list[str] = []
        self.current_model_id: str | None = None
        self.cwd: str | None = None
        self._lock = asyncio.Lock()

    async def ensure(
        self,
        *,
        command: list[str],
        env: dict[str, str] | None,
        cwd: str,
    ) -> None:
        """Start the ACP client and open a session if not already done."""
        async with self._lock:
            if self.client is not None and self.session_id is not None:
                return
            client = AcpClient(command=command, env=env, cwd=cwd)
            await client.start()
            await client.initialize()
            result = await client.session_new(cwd=cwd)
            session_id = result.get("sessionId")
            if not session_id:
                await client.close()
                raise AcpError("session/new did not return a sessionId")
            self.client = client
            self.session_id = str(session_id)
            self.cwd = cwd
            models_obj = result.get("models")
            if isinstance(models_obj, dict):
                available = models_obj.get("availableModels")
                if isinstance(available, list):
                    self.available_models = [
                        str(m.get("modelId") if isinstance(m, dict) else m) for m in available
                    ]
                current = models_obj.get("currentModelId")
                self.current_model_id = str(current) if current is not None else None

    async def set_model(self, model_id: str) -> None:
        """Select ``model_id`` for this session (no-op if already current)."""
        async with self._lock:
            if self.client is None or self.session_id is None:
                return
            if model_id == self.current_model_id:
                return
            await self.client.session_set_model(self.session_id, model_id)
            self.current_model_id = model_id

    async def close(self) -> None:
        async with self._lock:
            if self.client is not None:
                await self.client.close()
            self.client = None
            self.session_id = None


class RovoExecutor(Executor):
    """Drive Rovo Dev via its ACP server (``acli rovodev acp``).

    One ACP subprocess/session is kept warm per Omnigent conversation and
    reused across turns. Rovo runs its own agent loop and tools, so this
    executor reports :meth:`handles_tools_internally` ``True``.
    """

    def __init__(
        self,
        *,
        cwd: str | None = None,
        model: str | None = None,
        acli_path: str | None = None,
        config_file: str | None = None,
        site_url: str | None = None,
        env: dict[str, str] | None = None,
        turn_timeout: float = _DEFAULT_TURN_TIMEOUT_SECONDS,
    ) -> None:
        self._cwd = cwd
        self._model_override = model
        self._acli_path = acli_path
        self._config_file = config_file
        self._site_url = site_url
        self._env = env
        self._turn_timeout = turn_timeout
        self._sessions: dict[str, _RovoSession] = {}

    # -- capability flags ---------------------------------------------------

    def supports_streaming(self) -> bool:
        return True

    def supports_tool_calling(self) -> bool:
        return True

    def handles_tools_internally(self) -> bool:
        return True

    def supports_live_message_queue(self) -> bool:
        return False

    # -- lifecycle ----------------------------------------------------------

    async def interrupt_session(self, session_key: str) -> bool:
        state = self._sessions.get(session_key)
        if state is None or state.client is None or state.session_id is None:
            return False
        await state.client.session_cancel(state.session_id)
        return True

    async def enqueue_session_message(
        self,
        session_key: str,  # noqa: ARG002
        content: EnqueuedContent,  # noqa: ARG002
    ) -> bool:
        return False

    async def close_session(self, session_key: str) -> None:
        state = self._sessions.pop(session_key, None)
        if state is not None:
            await state.close()

    async def close(self) -> None:
        for state in list(self._sessions.values()):
            await state.close()
        self._sessions.clear()

    # -- core turn ----------------------------------------------------------

    def _command(self) -> list[str]:
        return default_acp_command(
            acli_path=self._acli_path,
            config_file=self._config_file,
            site_url=self._site_url,
        )

    async def run_turn(
        self,
        messages: list[Message],
        tools: list[ToolSpec],  # noqa: ARG002
        system_prompt: str,
        config: ExecutorConfig | None = None,
    ) -> AsyncIterator[ExecutorEvent]:
        cfg = config or ExecutorConfig()
        session_key = _session_key(messages)
        state = self._sessions.setdefault(session_key, _RovoSession())
        effective_cwd = self._cwd or os.getcwd()
        model = cfg.model or self._model_override

        try:
            await state.ensure(command=self._command(), env=self._env, cwd=effective_cwd)
            if model:
                await state.set_model(model)
        except Exception as exc:  # noqa: BLE001
            yield ExecutorError(
                message=_boot_error_message(exc, state),
                retryable=False,
            )
            return

        assert state.client is not None and state.session_id is not None

        prompt_text = _latest_user_text(messages)
        if system_prompt and _is_first_turn(messages):
            prompt_text = f"{system_prompt}\n\n{prompt_text}"

        queue: asyncio.Queue[ExecutorEvent | None] = asyncio.Queue()
        tool_call_names: dict[str, str] = {}

        async def on_update(update: JsonObj) -> None:
            for event in _translate_update(update, tool_call_names):
                await queue.put(event)

        prompt_task = asyncio.create_task(
            state.client.session_prompt(
                state.session_id,
                _to_acp_prompt(prompt_text),
                on_update=on_update,
                timeout=self._turn_timeout,
            )
        )

        async def _await_prompt() -> None:
            try:
                await prompt_task
            finally:
                await queue.put(None)

        finisher = asyncio.create_task(_await_prompt())

        final_text_parts: list[str] = []
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                if isinstance(event, TextChunk):
                    final_text_parts.append(event.text)
                yield event
            stop_reason = await prompt_task
            yield TurnComplete(
                response="".join(final_text_parts) or None,
                usage=None,
            )
            logger.debug("rovo: turn complete stop_reason=%s", stop_reason)
        except asyncio.CancelledError:
            await state.client.session_cancel(state.session_id)
            raise
        except Exception as exc:  # noqa: BLE001
            yield ExecutorError(message=f"Rovo executor error: {exc}")
        finally:
            if not finisher.done():
                finisher.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await finisher


def _is_first_turn(messages: list[Message]) -> bool:
    """True when this is the conversation's first user turn."""
    return sum(1 for m in messages if m.get("role") == "user") <= 1


def _boot_error_message(exc: Exception, state: _RovoSession) -> str:
    tail = ""
    if state.client is not None:
        tail = state.client.stderr_tail
    base = (
        "Failed to start Rovo Dev ACP session. Ensure `acli` is installed and "
        "you are logged in (`acli rovodev auth login`)."
    )
    detail = f"{type(exc).__name__}: {exc}"
    return f"{base}\n{detail}" + (f"\n{tail}" if tail else "")


def _translate_update(update: JsonObj, tool_call_names: dict[str, str]) -> list[ExecutorEvent]:
    """Translate one ACP ``update`` payload into zero or more ExecutorEvents."""
    kind = update.get("sessionUpdate")
    events: list[ExecutorEvent] = []

    if kind == "agent_message_chunk":
        text = _content_text(update.get("content"))
        if text:
            events.append(TextChunk(text=text))
    elif kind == "agent_thought_chunk":
        text = _content_text(update.get("content"))
        if text:
            events.append(ReasoningChunk(delta=text, event_type="reasoning_text"))
    elif kind == "tool_call":
        call_id = str(update.get("toolCallId", ""))
        name = str(update.get("title") or update.get("kind") or "tool")
        tool_call_names[call_id] = name
        events.append(
            ToolCallRequest(
                name=name,
                args=update.get("rawInput") or {},
                metadata={"call_id": call_id} if call_id else {},
            )
        )
    elif kind == "tool_call_update":
        status = str(update.get("status", ""))
        if status in {"completed", "failed"}:
            call_id = str(update.get("toolCallId", ""))
            name = tool_call_names.get(call_id, "tool")
            events.append(
                ToolCallComplete(
                    name=name,
                    status=(
                        ToolCallStatus.SUCCESS if status == "completed" else ToolCallStatus.ERROR
                    ),
                    result=update.get("rawOutput"),
                    metadata={"call_id": call_id} if call_id else {},
                )
            )
    return events
