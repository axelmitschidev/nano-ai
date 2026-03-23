"""Ollama LLM client — async implementation of LLMPort.

Single Responsibility: manages HTTP communication with Ollama's /api/chat endpoint.
Uses a persistent AsyncClient with connection pooling for optimal performance.
"""

import json
import logging
import httpx
from typing import AsyncIterator
from app.config import LLM_URL, LLM_TOKEN, LLM_MODEL, LLM_CTX

log = logging.getLogger(__name__)


# Shorter num_predict for tool calls (tool JSON is ~50-100 tokens)
_NUM_PREDICT_TOOLS = 512
_NUM_PREDICT_CHAT = 1024


class OllamaClient:
    """Async Ollama client with persistent connection pooling."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=300, write=10, pool=30),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            ),
            headers=self._build_headers(),
        )

    @staticmethod
    def _build_headers() -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if LLM_TOKEN:
            headers["Authorization"] = f"Bearer {LLM_TOKEN}"
        return headers

    @staticmethod
    def _build_payload(
        messages: list[dict],
        *,
        stream: bool,
        think: bool,
        tools: list[dict] | None = None,
    ) -> dict:
        has_tools = bool(tools)
        return {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": stream,
            "think": think,
            "keep_alive": -1,
            "options": {
                "num_ctx": LLM_CTX,
                "temperature": 0.15,
                "top_p": 0.7,
                "top_k": 15,
                "num_predict": _NUM_PREDICT_TOOLS if has_tools else _NUM_PREDICT_CHAT,
                "repeat_penalty": 1.05,
                "repeat_last_n": 256,
                "stop": ["<|im_end|>"],
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
    ) -> AsyncIterator[dict]:
        """Send messages to Ollama and yield streamed chunks."""
        payload = self._build_payload(messages, stream=stream, think=think, tools=tools)

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
        """Shut down the underlying HTTP client."""
        await self._client.aclose()
