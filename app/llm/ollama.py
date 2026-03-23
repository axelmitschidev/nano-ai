"""Ollama LLM client — async implementation of LLMPort.

Single Responsibility: manages HTTP communication with Ollama's /api/chat endpoint.
Uses a persistent AsyncClient with connection pooling for optimal performance.
"""

import json
import logging
import httpx
from typing import AsyncIterator
from app.config import LLM_URL, LLM_TOKEN, LLM_MODEL, LLM_CTX
from app.llm.profiles import detect_profile

log = logging.getLogger(__name__)

_NUM_PREDICT_TOOLS = 512
_NUM_PREDICT_CHAT = 1024

_TEMP: dict[str, float] = {"tool": 0.1, "code": 0.05, "chat": 0.3, "retry": 0.25}


class OllamaClient:
    """Async Ollama client with persistent connection pooling."""

    def __init__(self) -> None:
        self._profile = detect_profile(LLM_MODEL)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=300, write=10, pool=30),
            limits=httpx.Limits(
                max_connections=2,
                max_keepalive_connections=2,
                keepalive_expiry=300.0,
            ),
            headers=self._build_headers(),
        )

    @staticmethod
    def _build_headers() -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if LLM_TOKEN:
            headers["Authorization"] = f"Bearer {LLM_TOKEN}"
        return headers

    def _build_payload(
        self,
        messages: list[dict],
        *,
        stream: bool,
        think: bool,
        tools: list[dict] | None = None,
        ctx_used: int = 0,
        phase: str = "tool",
    ) -> dict:
        has_tools = bool(tools)
        remaining = max(256, LLM_CTX - ctx_used)
        cap = _NUM_PREDICT_TOOLS if has_tools else _NUM_PREDICT_CHAT
        num_predict = min(cap, int(remaining * 0.3))
        return {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": stream,
            "think": think,
            "keep_alive": -1,
            "options": {
                "num_ctx": LLM_CTX,
                "temperature": _TEMP.get(phase, self._profile["temp_default"]),
                "top_p": 0.7,
                "top_k": 15,
                "num_predict": num_predict,
                "repeat_penalty": 1.05,
                "repeat_last_n": 256,
                "stop": self._profile["stop"],
            },
            **({"tools": tools} if tools else {}),
        }

    async def chat(
        self,
        messages: list[dict],
        *,
        stream: bool = True,
        think: bool = False,
        tools: list[dict] | None = None,
        ctx_used: int = 0,
        phase: str = "tool",
    ) -> AsyncIterator[dict]:
        payload = self._build_payload(
            messages, stream=stream, think=think, tools=tools,
            ctx_used=ctx_used, phase=phase,
        )

        try:
            if not stream:
                resp = await self._client.post(LLM_URL, json=payload)
                if resp.status_code != 200:
                    body = resp.text[:200]
                    yield {"error": f"LLM HTTP {resp.status_code}: {body}"}
                    return
                try:
                    data = resp.json()
                except (json.JSONDecodeError, ValueError):
                    yield {"error": f"Invalid JSON from LLM (HTTP {resp.status_code})"}
                    return
                if "error" in data:
                    yield {"error": data["error"]}
                    return
                yield data
                return

            async with self._client.stream("POST", LLM_URL, json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")[:200]
                    yield {"error": f"LLM HTTP {resp.status_code}: {body}"}
                    return
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            log.warning("Unparseable LLM chunk: %s", line[:100])
                            continue

        except httpx.HTTPError as e:
            yield {"error": f"HTTP error: {e}"}
        except Exception as e:
            yield {"error": f"LLM client error: {e}"}

    async def close(self) -> None:
        await self._client.aclose()
