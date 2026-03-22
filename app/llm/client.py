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
            "temperature": 0.15,
            "top_p": 0.7,
            "top_k": 15,
            "num_predict": 1024,
            "repeat_penalty": 1.05,
            "repeat_last_n": 256,
            "stop": ["<|im_end|>"],
        },
    }
    if tools:
        payload["tools"] = tools
    return payload


def chat(
    messages: list,
    stream: bool = True,
    think: bool | str = False,
    tools: list | None = None,
) -> Generator[dict, None, None]:
    """Send messages to the LLM and yield streamed chunks."""
    try:
        payload = _build_payload(messages, stream, think, tools)

        if not stream:
            res = httpx.post(url=LLM_URL, headers=_headers(), timeout=TIMEOUT, json=payload)
            try:
                data = res.json()
            except (json.JSONDecodeError, ValueError):
                yield {"error": f"Invalid response from LLM (HTTP {res.status_code})"}
                return
            if "error" in data:
                yield {"error": data["error"]}
                return
            yield data
            return

        with httpx.stream("POST", url=LLM_URL, headers=_headers(), timeout=TIMEOUT, json=payload) as res:
            for line in res.iter_lines():
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    except httpx.HTTPError as e:
        yield {"error": f"HTTP error: {e}"}
    except Exception as e:
        yield {"error": f"LLM client error: {e}"}
