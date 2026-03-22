"""Centralized configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM
LLM_URL: str = os.getenv("API_URL", "http://localhost:11434/api/chat")
LLM_TOKEN: str = os.getenv("API_TOKEN", "")
LLM_MODEL: str = os.getenv("API_MODEL", "huihui_ai/qwen3.5-abliterated:4b")
LLM_CTX: int = int(os.getenv("API_CTX", "65536"))

# Paths
WORKSPACE_DIR: str = os.path.join(os.path.dirname(__file__), "workspace")
LOGS_DIR: str = os.path.join(os.path.dirname(__file__), "logs")
PROMPT_PATH: str = os.path.join(os.path.dirname(__file__), "prompts", "system.md")

# Agent
MAX_TOOL_ROUNDS: int = 10
MAX_SILENT_RETRIES: int = 2
CTX_TRIM_RATIO: float = 0.75
MAX_LOOP_DETECT: int = 2  # same tool+args N times = loop
