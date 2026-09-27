"""Deterministic ACP peer for exercising real subprocess pipes in tests."""

import json
import sys

turn = 0


def send(payload):
    print(json.dumps({"jsonrpc": "2.0", **payload}), flush=True)


for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        result = {"protocolVersion": 1}
    elif method == "session/new":
        result = {"sessionId": "fixture-session"}
    elif method == "session/prompt":
        turn += 1
        text = message["params"]["prompt"][0]["text"]
        if text == "large":
            text = "x" * 100_000
        send(
            {
                "method": "session/update",
                "params": {
                    "sessionId": "fixture-session",
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": f"{turn}:{text}"},
                    },
                },
            }
        )
        result = {"stopReason": "end_turn"}
    else:
        continue
    send({"id": message["id"], "result": result})
