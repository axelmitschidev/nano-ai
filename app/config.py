"""Centralized configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM
LLM_URL: str = os.getenv("API_URL", "http://localhost:11434/api/chat")
LLM_TOKEN: str = os.getenv("API_TOKEN", "")
LLM_MODEL: str = os.getenv("API_MODEL", "huihui_ai/qwen3.5-abliterated:4b")
LLM_CTX: int = int(os.getenv("API_CTX", "8192"))
LLM_THINK: bool = os.getenv("API_THINK", "false").lower() in ("1", "true", "yes")

# Paths
WORKSPACE_DIR: str = os.path.join(os.path.dirname(__file__), "workspace")
LOGS_DIR: str = os.path.join(os.path.dirname(__file__), "logs")
PROMPT_PATH: str = os.path.join(os.path.dirname(__file__), "prompts", "system.md")

# Agent (configurable via env)
MAX_TOOL_ROUNDS: int = int(os.getenv("AGENT_MAX_ROUNDS", "10"))
MAX_SILENT_RETRIES: int = int(os.getenv("AGENT_MAX_RETRIES", "2"))
CTX_TRIM_RATIO: float = float(os.getenv("AGENT_CTX_TRIM", "0.75"))
MAX_LOOP_DETECT: int = int(os.getenv("AGENT_LOOP_DETECT", "2"))

# Feature flags
AGENT_PLAN: bool = os.getenv("AGENT_PLAN", "true").lower() in ("1", "true", "yes")
AGENT_MEMORY: bool = os.getenv("AGENT_MEMORY", "true").lower() in ("1", "true", "yes")
AGENT_PROFILE: str = os.getenv("AGENT_PROFILE", "default")
