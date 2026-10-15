"""Thin LLM provider wrapper: one function, llm_call(messages, tools) -> (assistant_msg, usage).

The loop only ever sees the provider-neutral message format below; switching
provider means rewriting this file, nothing else.

Neutral messages
    {"role": "system",    "content": str}                       # optional, first
    {"role": "user",      "content": str}
    {"role": "assistant", "content": str | None,
                          "tool_calls": [{"id": str, "name": str, "args": dict}],
                          "_raw_parts": [...]}                   # provider replay data, don't touch
    {"role": "tool",      "tool_call_id": str, "name": str, "content": str,
                          "is_error": bool}                     # is_error optional

Provider: Gemini REST API (generateContent), stdlib only. Config from .env:
LLM_PROVIDER=gemini, LLM_MODEL, LLM_API_KEY, optional LLM_RPM (client-side throttle).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUS = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """The provider failed in a way the loop can't fix by changing its messages."""


# --- config -----------------------------------------------------------------

def load_env(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines); real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _config() -> dict[str, str]:
    load_env()
    cfg = {k: os.environ.get(k, "") for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "LLM_RPM")}
    if cfg["LLM_PROVIDER"] != "gemini":
        raise LLMError(f"LLM_PROVIDER={cfg['LLM_PROVIDER']!r} not supported (only 'gemini').")
    if not cfg["LLM_MODEL"] or not cfg["LLM_API_KEY"]:
        raise LLMError("Set LLM_MODEL and LLM_API_KEY in .env.")
    return cfg


# --- neutral -> Gemini --------------------------------------------------------

def to_gemini_tools(tools: list[dict]) -> list[dict]:
    # parametersJsonSchema takes full JSON Schema (anyOf, defaults...), unlike the
    # older OpenAPI-subset "parameters" field, so Pydantic's Optional works as-is.
    return [{"functionDeclarations": [
        {"name": t["name"], "description": t["description"], "parametersJsonSchema": t["parameters"]}
        for t in tools
    ]}]


def to_gemini_contents(messages: list[dict]) -> tuple[dict | None, list[dict]]:
    """Returns (systemInstruction, contents). Consecutive tool results are merged
    into one user turn, as Gemini expects one functionResponse per functionCall."""
    system, contents = None, []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            system = {"parts": [{"text": msg["content"]}]}
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
        elif role == "assistant":
            parts = msg.get("_raw_parts") or _assistant_parts(msg)
            contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            key = "error" if msg.get("is_error") else "result"
            response = {"name": msg["name"], "response": {key: msg["content"]}}
            if msg.get("tool_call_id"):
                response["id"] = msg["tool_call_id"]
            part = {"functionResponse": response}
            if contents and contents[-1]["role"] == "user" and "functionResponse" in contents[-1]["parts"][0]:
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": "user", "parts": [part]})
        else:
            raise ValueError(f"Unknown message role {role!r}")
    return system, contents


def _assistant_parts(msg: dict) -> list[dict]:
    parts: list[dict] = [{"text": msg["content"]}] if msg.get("content") else []
    parts += [{"functionCall": {"name": c["name"], "args": c["args"]}} for c in msg.get("tool_calls", [])]
    return parts


def _tool_config(tool_choice: str) -> dict:
    """'auto' = model decides; 'any' = must call some tool; any other value = must call that tool."""
    if tool_choice == "auto":
        return {"functionCallingConfig": {"mode": "AUTO"}}
    if tool_choice == "any":
        return {"functionCallingConfig": {"mode": "ANY"}}
    return {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": [tool_choice]}}


# --- Gemini -> neutral --------------------------------------------------------

def parse_response(data: dict) -> tuple[dict, dict]:
    candidates = data.get("candidates") or []
    cand = candidates[0] if candidates else {}
    parts = (cand.get("content") or {}).get("parts") or []

    texts = [p["text"] for p in parts if "text" in p and not p.get("thought")]
    calls = []
    for i, p in enumerate(parts):
        if "functionCall" in p:
            fc = p["functionCall"]
            calls.append({"id": fc.get("id") or f"call_{i}", "name": fc["name"], "args": fc.get("args") or {}})

    # _raw_parts keeps thought signatures: Gemini 3 rejects a follow-up request
    # whose function calls lost the signature they came with.
    msg = {"role": "assistant", "content": "\n".join(texts) or None, "tool_calls": calls, "_raw_parts": parts}

    meta = data.get("usageMetadata") or {}
    usage = {
        "input_tokens": meta.get("promptTokenCount", 0),
        "output_tokens": meta.get("candidatesTokenCount", 0),
        "thinking_tokens": meta.get("thoughtsTokenCount", 0),
        "total_tokens": meta.get("totalTokenCount", 0),
        "finish_reason": cand.get("finishReason") or (data.get("promptFeedback") or {}).get("blockReason"),
    }
    return msg, usage


# --- the call -----------------------------------------------------------------

_last_call = 0.0


def _throttle(rpm: str) -> None:
    """Space calls to stay under the free-tier requests-per-minute limit."""
    global _last_call
    if rpm:
        wait = 60.0 / float(rpm) - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
    _last_call = time.monotonic()


def _post(url: str, body: dict, api_key: str, timeout_s: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read())


def llm_call(
    messages: list[dict],
    tools: list[dict],
    *,
    tool_choice: str = "auto",
    temperature: float = 0.0,
    max_retries: int = 3,
    timeout_s: float = 60.0,
) -> tuple[dict, dict]:
    """One model call. Returns (assistant_msg, usage); usage also has latency_ms and model."""
    cfg = _config()
    system, contents = to_gemini_contents(messages)
    body: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if system:
        body["systemInstruction"] = system
    if tools:
        body["tools"] = to_gemini_tools(tools)
        body["toolConfig"] = _tool_config(tool_choice)

    url = GEMINI_URL.format(model=cfg["LLM_MODEL"])
    for attempt in range(max_retries + 1):
        _throttle(cfg["LLM_RPM"])
        start = time.perf_counter()
        try:
            data = _post(url, body, cfg["LLM_API_KEY"], timeout_s)
            break
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:500]
            if err.code not in RETRY_STATUS or attempt == max_retries:
                raise LLMError(f"HTTP {err.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt == max_retries:
                raise LLMError(f"Network error: {err}") from None
        time.sleep(2 ** attempt * 5)  # 5s, 10s, 20s

    msg, usage = parse_response(data)
    usage["latency_ms"] = round((time.perf_counter() - start) * 1000)
    usage["model"] = cfg["LLM_MODEL"]
    return msg, usage
