"""HTTP API server for the Nano AI agent."""

from fastapi import FastAPI
from pydantic import BaseModel
from app.config import LLM_MODEL, LLM_CTX
from app.tools import register_all
from app.tools.browser import close_browser
from app.agent.memory import load_system_prompt
from app.agent.agent import run_turn
from app.logger.logger import log_user

app = FastAPI(title="nano-ai", version="1.0.0")

# Agent state
_state = {"history": []}


@app.on_event("startup")
def startup():
    register_all()
    system_prompt = load_system_prompt()
    _state["history"] = [{"role": "system", "content": system_prompt}]


@app.on_event("shutdown")
def shutdown():
    close_browser()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Send a message to the agent and get a response."""
    log_user(req.message)
    _state["history"] = run_turn(req.message, _state["history"])

    # Extract the last assistant message
    for msg in reversed(_state["history"]):
        if msg.get("role") == "assistant" and msg.get("content"):
            return ChatResponse(response=msg["content"])

    return ChatResponse(response="(no response)")


@app.post("/reset")
def reset():
    """Reset the conversation history."""
    system_prompt = load_system_prompt()
    _state["history"] = [{"role": "system", "content": system_prompt}]
    return {"status": "reset"}


@app.get("/health")
def health():
    return {"status": "ok", "model": LLM_MODEL, "ctx": LLM_CTX}
