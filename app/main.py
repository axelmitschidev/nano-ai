"""Entry point for the Nano AI agent."""

import atexit
from app.config import LLM_MODEL, LLM_CTX
from app.tools import register_all
from app.tools.browser import close_browser
from app.agent.memory import load_system_prompt
from app.agent.agent import run_turn
from app.agent.display import print_banner, print_end
from app.logger.logger import log_user


def main():
    # Register all tools
    register_all()

    # Cleanup browser on exit
    atexit.register(close_browser)

    # Load system prompt + memory
    system_prompt = load_system_prompt()
    history = [{"role": "system", "content": system_prompt}]

    print_banner(LLM_MODEL, LLM_CTX)

    while True:
        try:
            user_input = input(">> ")
        except (EOFError, KeyboardInterrupt):
            print_end()
            break

        if not user_input.strip():
            continue

        log_user(user_input)
        history = run_turn(user_input, history)


if __name__ == "__main__":
    main()
