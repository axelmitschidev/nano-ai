"""LLM port — abstract interface for language model communication.

Dependency Inversion: the agent depends on this protocol, not on a concrete client.
"""

from typing import Protocol, AsyncIterator


class LLMPort(Protocol):
    """Contract for any LLM backend (Ollama, OpenAI, etc.)."""

    async def chat(
        self,
        messages: list[dict],
        *,
        stream: bool = True,
        think: bool = False,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """Send messages and yield streamed response chunks."""
        ...

    async def close(self) -> None:
        """Release underlying resources."""
        ...
