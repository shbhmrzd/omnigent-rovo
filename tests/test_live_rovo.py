"""Opt-in release eval: real Rovo, real tools, independent correctness checks.

Run with RUN_ROVO_LIVE_EVALS=1 after authenticating `rovo auth login`.
This consumes model usage and edits only pytest's temporary workspace.
"""

import asyncio
import os
import secrets
import subprocess
import sys

import pytest
from omnigent.inner.executor import ExecutorError, TextChunk, ToolCallComplete, TurnComplete

from omnigent.community.harness.rovo.inner.rovo_executor import RovoExecutor

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_ROVO_LIVE_EVALS") != "1",
    reason="requires authenticated Rovo and model usage",
)


async def test_live_coding_and_session_memory(tmp_path):
    source = tmp_path / "calculator.py"
    source.write_text("def add(a, b):\n    return a - b\n")
    check = (
        "from calculator import add; assert add(2, 3) == 5; "
        "assert add(-2, 5) == 3; assert add(0, 0) == 0"
    )
    # Verify the evaluation detects the seeded defect before asking Rovo to fix it.
    before = subprocess.run([sys.executable, "-c", check], cwd=tmp_path, capture_output=True)
    assert before.returncode != 0
    marker = "rovo-" + secrets.token_hex(6)
    executor = RovoExecutor(
        cwd=str(tmp_path),
        turn_timeout=120,
        config_file=os.environ.get("HARNESS_ROVO_CONFIG_FILE") or None,
        startup_timeout=float(os.environ.get("HARNESS_ROVO_STARTUP_TIMEOUT") or "120"),
    )
    messages = [
        {
            "role": "user",
            "session_id": "live-eval",
            "content": f"Remember this marker for our next turn: {marker}. "
            "Fix calculator.py so add returns the sum of its two arguments. "
            "Read the file and edit it using your tools. Work only in the current directory. "
            "Do not create any other files. Reply FIXED when done.",
        }
    ]
    try:
        async with asyncio.timeout(360):
            events = [e async for e in executor.run_turn(messages, [], "")]
            assert not [e for e in events if isinstance(e, ExecutorError)], events
            assert isinstance(events[-1], TurnComplete)
            assert any(isinstance(e, TextChunk) for e in events)
            assert any(isinstance(e, ToolCallComplete) for e in events)
            # Independent Python assertions determine success, never the model's self-report.
            after = subprocess.run([sys.executable, "-c", check], cwd=tmp_path, capture_output=True)
            assert after.returncode == 0, after.stderr.decode()
            state = executor._sessions["live-eval"]
            proc = state.client._proc
            session_id = state.session_id
            messages += [
                {"role": "assistant", "content": events[-1].response},
                {
                    "role": "user",
                    "content": "Return only the exact marker I asked you to remember. "
                    "Do not use tools.",
                },
            ]
            followup = [e async for e in executor.run_turn(messages, [], "")]
            assert not [e for e in followup if isinstance(e, ExecutorError)], followup
            assert isinstance(followup[-1], TurnComplete)
            assert (followup[-1].response or "").strip() == marker
            assert state.session_id == session_id
            assert state.client._proc is proc
    finally:
        await executor.close()
    assert proc.returncode is not None


async def test_live_harness_http(tmp_path):
    """Start Omnigent's actual harness runner and verify its HTTP/SSE output."""
    import json
    import tempfile

    import httpx

    with tempfile.TemporaryDirectory(prefix="rovo-http-", dir="/tmp") as runtime:
        socket_path = runtime + "/h.sock"
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "omnigent.runtime.harnesses._runner",
            "--harness",
            "rovo-cli",
            "--module",
            "omnigent.community.harness.rovo.inner.rovo_harness",
            "--socket",
            socket_path,
            "--conversation-id",
            "live-http",
            cwd=tmp_path,
            env={**os.environ, "HARNESS_ROVO_CWD": str(tmp_path)},
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            transport = httpx.AsyncHTTPTransport(uds=socket_path)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://localhost", timeout=180
            ) as client:
                async with asyncio.timeout(20):
                    while True:
                        assert proc.returncode is None, (await proc.stderr.read()).decode()
                        try:
                            health = await client.get("/health")
                            if health.status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        await asyncio.sleep(0.1)
                response = await client.post(
                    "/v1/sessions/live-http/events",
                    json={
                        "type": "message",
                        "role": "user",
                        "model": "rovo",
                        "content": "Reply with exactly ROVO_HTTP_OK. Do not use tools.",
                    },
                )
                assert response.status_code == 200, response.text
                payloads = [
                    json.loads(line[6:])
                    for line in response.text.splitlines()
                    if line.startswith("data: ") and line[6:] != "[DONE]"
                ]
                text = "".join(
                    p.get("delta", "")
                    for p in payloads
                    if p.get("type") == "response.output_text.delta"
                )
                assert text.strip() == "ROVO_HTTP_OK", response.text
                assert any(p.get("type") == "response.completed" for p in payloads)
                assert not [p for p in payloads if p.get("type") in {"error", "response.failed"}]
        finally:
            if proc.returncode is None:
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=15)
            except TimeoutError:
                proc.kill()
                await proc.wait()
