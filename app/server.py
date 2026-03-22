"""HTTP API server — thin controller layer.

Single Responsibility: HTTP routing and request/response mapping.
All domain logic is delegated to the orchestrator, session store, and LLM client.
"""

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.config import LLM_MODEL, LLM_CTX, LLM_URL
from app.llm.ollama import OllamaClient
from app.session import SessionStore
from app.tools import register_all
from app.tools.browser import close_browser
from app.agent.orchestrator import run_turn
from app.logger.logger import log_user
from app.logger import logger as log_module


# --- Application state (initialized in lifespan) ---

llm_client: OllamaClient
sessions: SessionStore


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client, sessions

    register_all()
    llm_client = OllamaClient()
    sessions = SessionStore()
    await sessions.start_periodic_cleanup()

    # Quick Ollama reachability check
    ollama_base = LLM_URL.replace("/api/chat", "")
    async with httpx.AsyncClient() as probe:
        for _ in range(5):
            try:
                resp = await probe.get(ollama_base, timeout=2)
                if resp.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(1)

    yield

    await sessions.stop_periodic_cleanup()
    await llm_client.close()
    close_browser()
    log_module.close()


app = FastAPI(title="nano-ai", version="1.0.0", lifespan=lifespan)


# --- Request / Response models ---

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
    session_id, session = sessions.get_or_create(req.session_id)

    async with session.lock:
        log_user(req.message)
        session.history = await run_turn(llm_client, req.message, session.history)

    # Extract the last assistant message
    for msg in reversed(session.history):
        if msg.get("role") == "assistant" and msg.get("content"):
            return ChatResponse(response=msg["content"], session_id=session_id)

    return ChatResponse(response="(no response)", session_id=session_id)


@app.post("/reset")
async def reset(session_id: str | None = None):
    """Reset a conversation session."""
    if session_id:
        sessions.remove(session_id)
    return {"status": "reset", "session_id": session_id}


@app.get("/health")
async def health():
    """Check agent and Ollama status."""
    ollama_status = "unknown"
    ollama_base = LLM_URL.replace("/api/chat", "")

    try:
        async with httpx.AsyncClient() as probe:
            resp = await probe.get(ollama_base, timeout=5)
            ollama_status = "healthy" if resp.status_code == 200 else f"HTTP {resp.status_code}"
    except Exception as e:
        ollama_status = f"unhealthy: {e}"

    return {
        "status": "ok" if ollama_status == "healthy" else "degraded",
        "model": LLM_MODEL,
        "ctx": LLM_CTX,
        "ollama": ollama_status,
        "sessions": sessions.count,
    }
