"""Smoke test: one real LLM call with our tool specs. Proves key, model and schemas work.

    .venv/Scripts/python scripts/ping_llm.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.llm import llm_call  # noqa: E402
from agent.tools.registry import tool_specs  # noqa: E402

messages = [
    {"role": "system", "content": "You investigate incidents using the tools provided."},
    {"role": "user", "content": "Start by getting log statistics for the 'api' service."},
]

msg, usage = llm_call(messages, tool_specs(), tool_choice="any")
print("text:      ", msg["content"])
print("tool calls:", json.dumps(msg["tool_calls"], indent=2))
print("usage:     ", {k: v for k, v in usage.items()})
