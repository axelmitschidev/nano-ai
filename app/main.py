"""CLI entry point for the Nano AI agent."""

import asyncio
import atexit
from app.config import LLM_MODEL, LLM_CTX
from app.llm.ollama import OllamaClient
from app.tools import register_all
from app.tools.browser import close_browser
from app.agent.prompt import load_system_prompt
from app.agent.orchestrator import run_turn
from app.agent.display import print_banner, print_end
from app.logger.logger import log_user, close as close_logger


async def _run() -> None:
    register_all()
    llm = OllamaClient()

    try:
        system_prompt = load_system_prompt()
        history: list[dict] = [{"role": "system", "content": system_prompt}]
        print_banner(LLM_MODEL, LLM_CTX)

        while True:
            try:
                user_input = await asyncio.to_thread(input, ">> ")
            except (EOFError, KeyboardInterrupt):
                print_end()
                break

            if not user_input.strip():
                continue

            log_user(user_input)
            history = await run_turn(llm, user_input, history)
    finally:
        await llm.close()


def main() -> None:
    atexit.register(close_browser)
    atexit.register(close_logger)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
