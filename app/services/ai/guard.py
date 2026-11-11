"""
Safety limits for the AI Manager chat.

AI_CHAT_PER_MINUTE   messages one user may send per minute (default 20)
AI_CHAT_PER_DAY      messages one user may send per day (default 300)
AI_CHAT_MAX_CHARS    longest message accepted (default 2000)
AI_CHAT_HISTORY_MAX  earlier messages sent back to the model (default 12)
AI_CHAT_TIMEOUT_SECONDS  longest wait for the model (default 30)

Limits are counted per server process. With several workers the effective limit is higher by the
number of workers; use a shared store (for example Redis) if you need an exact limit.
"""

import os
import time
from collections import defaultdict, deque
from typing import List, Optional

from fastapi import HTTPException

from app.schemas.ai import ChatMessage


def _int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


class ChatRateLimiter:
    def __init__(self):
        self._minute: dict[str, deque] = defaultdict(deque)
        self._day: dict[str, deque] = defaultdict(deque)

    def reset(self) -> None:
        self._minute.clear()
        self._day.clear()

    def check(self, user_id: str, now: Optional[float] = None) -> None:
        """Record one message for this user, or raise 429 with Retry-After."""
        now = time.time() if now is None else now
        per_minute = _int("AI_CHAT_PER_MINUTE", 20)
        per_day = _int("AI_CHAT_PER_DAY", 300)
        minute, day = self._minute[user_id], self._day[user_id]
        while minute and now - minute[0] >= 60:
            minute.popleft()
        while day and now - day[0] >= 86400:
            day.popleft()
        if len(minute) >= per_minute:
            retry = max(1, int(60 - (now - minute[0])))
            raise HTTPException(
                status_code=429,
                detail=f"You are sending messages too quickly. Please wait {retry} seconds.",
                headers={"Retry-After": str(retry)},
            )
        if len(day) >= per_day:
            retry = max(1, int(86400 - (now - day[0])))
            raise HTTPException(
                status_code=429,
                detail="You have reached the daily limit for AI Manager messages. Please try again tomorrow.",
                headers={"Retry-After": str(retry)},
            )
        minute.append(now)
        day.append(now)


rate_limiter = ChatRateLimiter()


def check_message(message: str) -> None:
    limit = _int("AI_CHAT_MAX_CHARS", 2000)
    if len(message) > limit:
        raise HTTPException(status_code=422, detail=f"Message is too long (limit {limit} characters).")


def trim_history(history: Optional[List[ChatMessage]]) -> List[ChatMessage]:
    """Keep only the latest messages, each cut to a safe length."""
    keep = _int("AI_CHAT_HISTORY_MAX", 12)
    limit = _int("AI_CHAT_MAX_CHARS", 2000)
    out = []
    for m in (history or [])[-keep:]:
        out.append(ChatMessage(role=m.role, content=m.content[:limit]))
    return out
