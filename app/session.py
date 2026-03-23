"""Session management — entities and store for conversation state.

Single Responsibility: owns session lifecycle (create, retrieve, expire, cleanup).
"""

import uuid
import asyncio
import logging
from datetime import datetime, timezone

from app.agent.prompt import load_system_prompt

TTL_SECONDS = 3600
MAX_SESSIONS = 100

log = logging.getLogger(__name__)


class Session:
    """A single conversation session with its message history."""

    __slots__ = ("history", "created_at", "last_active", "lock")

    def __init__(self) -> None:
        self.history: list[dict] = [{"role": "system", "content": load_system_prompt()}]
        self.created_at = datetime.now(timezone.utc)
        self.last_active = datetime.now(timezone.utc)
        self.lock = asyncio.Lock()

    def touch(self) -> None:
        self.last_active = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        elapsed = (datetime.now(timezone.utc) - self.last_active).total_seconds()
        return elapsed > TTL_SECONDS


class SessionStore:
    """In-memory session store with TTL-based eviction."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._cleanup_task: asyncio.Task | None = None

    def get_or_create(self, session_id: str | None) -> tuple[str, Session]:
        """Retrieve an existing session or create a new one."""
        self._evict_expired()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            session.touch()
            return session_id, session

        new_id = session_id or str(uuid.uuid4())
        session = Session()
        self._sessions[new_id] = session

        # Evict oldest if over capacity (skip locked sessions)
        if len(self._sessions) > MAX_SESSIONS:
            candidates = [
                (sid, s) for sid, s in self._sessions.items()
                if not s.lock.locked() and sid != new_id
            ]
            if candidates:
                oldest_id = min(candidates, key=lambda x: x[1].last_active)[0]
                del self._sessions[oldest_id]
                log.warning("Session %s evicted (capacity)", oldest_id[:8])

        return new_id, session

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> Session | None:
        """Retrieve an existing session without creating one."""
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            return None
        return session

    @property
    def count(self) -> int:
        return len(self._sessions)

    def _evict_expired(self) -> None:
        expired = [
            sid for sid, s in self._sessions.items()
            if s.is_expired() and not s.lock.locked()
        ]
        for sid in expired:
            del self._sessions[sid]

    async def start_periodic_cleanup(self) -> None:
        """Launch a background task that cleans expired sessions every 5 minutes."""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_periodic_cleanup(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def _periodic_cleanup(self) -> None:
        while True:
            await asyncio.sleep(300)
            try:
                self._evict_expired()
            except Exception:
                log.exception("Session cleanup error")
