"""Transport evals use real pipes and the actual Omnigent event classes."""

import sys
from pathlib import Path

from omnigent.inner.executor import ExecutorError, TextChunk, TurnComplete

from omnigent.community.harness.rovo.inner.rovo_executor import RovoExecutor


async def test_real_subprocess_streaming_and_warm_session_reuse(tmp_path):
    executor = RovoExecutor(cwd=str(tmp_path), turn_timeout=5)
    executor._command = lambda: [
        sys.executable,
        str(Path(__file__).parent / "fixtures" / "acp_server.py"),
    ]
    try:
        for turn, text in enumerate(["hello", "large"], 1):
            events = [
                event
                async for event in executor.run_turn(
                    [{"role": "user", "content": text, "session_id": "conversation"}],
                    [],
                    "",
                )
            ]
            assert not [e for e in events if isinstance(e, ExecutorError)], events
            expected = f"{turn}:" + ("x" * 100_000 if text == "large" else text)
            assert "".join(e.text for e in events if isinstance(e, TextChunk)) == expected
            assert isinstance(events[-1], TurnComplete)
            assert events[-1].response == expected
            assert len(executor._sessions) == 1
    finally:
        proc = (
            executor._sessions["conversation"].client._proc
            if executor._sessions["conversation"].client
            else None
        )
        await executor.close()
        if proc is not None:
            assert proc.returncode is not None
