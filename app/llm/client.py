"""LLM API client — talks to Ollama's /api/chat endpoint."""

from typing import Generator
import httpx
import json
from app.config import LLM_URL, LLM_TOKEN, LLM_MODEL, LLM_CTX

TIMEOUT = httpx.Timeout(connect=10, read=300, write=10, pool=10)


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if LLM_TOKEN:
        headers["Authorization"] = f"Bearer {LLM_TOKEN}"
    return headers


def _build_payload(
    messages: list,
    stream: bool,
    think: bool | str,
    tools: list | None = None,
) -> dict:
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": stream,
        "think": think,
        "options": {
            "num_ctx": LLM_CTX,
            "temperature": 0.1,
            "repeat_penalty": 1.05,
            "repeat_last_n": 256,
        },
    }
    if tools:
        payload["tools"] = tools
    return payload


def chat(
    messages: list,
    stream: bool = True,
    think: bool | str = "low",
    tools: list | None = None,
) -> Generator[dict, None, None]:
    """Send messages to the LLM and yield streamed chunks."""
    try:
        payload = _build_payload(messages, stream, think, tools)

        if not stream:
            res = httpx.post(url=LLM_URL, headers=_headers(), timeout=TIMEOUT, json=payload)
            yield res.json()
            return

        with httpx.stream("POST", url=LLM_URL, headers=_headers(), timeout=TIMEOUT, json=payload) as res:
            for line in res.iter_lines():
                if line:
                    yield json.loads(line)

    except httpx.HTTPError as e:
        yield {"error": str(e)}
