"""HTTP API server for the Nano AI agent."""

import uuid
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.config import LLM_MODEL, LLM_CTX, LLM_URL
from app.tools import register_all
from app.tools.browser import close_browser
from app.agent.memory import load_system_prompt
from app.agent.agent import run_turn
from app.logger.logger import log_user
from app.logger import logger as log_module


# --- Session management ---

class Session:
    def __init__(self):
        self.history = [{"role": "system", "content": load_system_prompt()}]
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        self.lock = asyncio.Lock()

_sessions: dict[str, Session] = {}
TTL_SECONDS = 3600


def _evict_expired():
    now = datetime.utcnow()
    expired = [sid for sid, s in _sessions.items() if (now - s.last_active).total_seconds() > TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _get_session(session_id: str | None) -> tuple[str, Session]:
    _evict_expired()
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        session.last_active = datetime.utcnow()
        return session_id, session
    new_id = session_id or str(uuid.uuid4())
    session = Session()
    _sessions[new_id] = session
    return new_id, session


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    register_all()

    # Wait for Ollama
    ollama_base = LLM_URL.replace("/api/chat", "")
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            try:
                resp = await client.get(ollama_base)
                if resp.status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            await asyncio.sleep(1)

    yield

    close_browser()
    log_module.close()


app = FastAPI(title="nano-ai", version="1.0.0", lifespan=lifespan)


# --- Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = Field(None, description="Session ID (auto-generated if omitted)")


class ChatResponse(BaseModel):
    response: str
    session_id: str


# --- Endpoints ---

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message to the agent and get a response."""
    session_id, session = _get_session(req.session_id)

    async with session.lock:
        log_user(req.message)

        # Run sync agent in threadpool to not block event loop
        loop = asyncio.get_event_loop()
        session.history = await loop.run_in_executor(
            None, run_turn, req.message, session.history
        )

    # Extract the last assistant message
    for msg in reversed(session.history):
        if msg.get("role") == "assistant" and msg.get("content"):
            return ChatResponse(response=msg["content"], session_id=session_id)

    return ChatResponse(response="(no response)", session_id=session_id)


@app.post("/reset")
async def reset(session_id: str | None = None):
    """Reset a conversation session."""
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    return {"status": "reset", "session_id": session_id}


@app.get("/health")
async def health():
    """Check agent and Ollama status."""
    ollama_status = "unknown"
    ollama_base = LLM_URL.replace("/api/chat", "")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(ollama_base, timeout=5)
            ollama_status = "healthy" if resp.status_code == 200 else f"HTTP {resp.status_code}"
    except Exception as e:
        ollama_status = f"unhealthy: {e}"

    return {
        "status": "ok" if ollama_status == "healthy" else "degraded",
        "model": LLM_MODEL,
        "ctx": LLM_CTX,
        "ollama": ollama_status,
        "sessions": len(_sessions),
    }
