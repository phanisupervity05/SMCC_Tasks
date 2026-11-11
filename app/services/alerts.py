# app/services/alerts.py
"""
Watches for calls that need a person and raises an alert.

An alert is always written to the log at ERROR level (search for "ALERT"). If ALERT_WEBHOOK_URL is
set (a Slack-compatible incoming webhook), the same message is also posted there.

ALERT_CHECK_SECONDS   how often to check (default 300, 0 turns the monitor off)
ALERT_FAILED_WINDOW_MINUTES   how far back "recently failed" looks (default 60)
"""

import asyncio
import logging
import os
from datetime import timedelta

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.call import Call, CallStatus, utcnow
from .call_views import stuck_after_minutes

log = logging.getLogger(__name__)

_last_signature: tuple | None = None


def ops_summary(db: Session) -> dict:
    """What an operator needs to know at a glance."""
    now = utcnow()
    window = int(os.getenv("ALERT_FAILED_WINDOW_MINUTES", "60"))
    cutoff = now - timedelta(minutes=stuck_after_minutes())
    stuck = (
        db.query(func.count(Call.id))
        .filter(Call.status == CallStatus.SENT_TO_AUTO, Call.sent_to_auto_at.isnot(None), Call.sent_to_auto_at < cutoff)
        .scalar()
        or 0
    )
    oldest = (
        db.query(func.min(Call.sent_to_auto_at))
        .filter(Call.status == CallStatus.SENT_TO_AUTO, Call.sent_to_auto_at.isnot(None))
        .scalar()
    )
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=now.tzinfo)
    recent_failed = (
        db.query(func.count(Call.id))
        .filter(Call.status == CallStatus.FAILED, Call.updated_at >= now - timedelta(minutes=window))
        .scalar()
        or 0
    )
    return {
        "auto_mode": os.getenv("AUTO_MODE", "") or "not set",
        "stuck": stuck,
        "oldest_in_auto_minutes": round((now - oldest).total_seconds() / 60) if oldest else None,
        "failed_recently": recent_failed,
        "failed_window_minutes": window,
    }


def alert_messages(summary: dict) -> list[str]:
    msgs = []
    if summary["stuck"]:
        msgs.append(
            f"ALERT {summary['stuck']} call(s) stuck in Sent to Auto for over {stuck_after_minutes()} minutes. "
            "Check the Orchestrator."
        )
    if summary["failed_recently"]:
        msgs.append(
            f"ALERT {summary['failed_recently']} call(s) failed in the last {summary['failed_window_minutes']} minutes."
        )
    return msgs


async def _post_webhook(url: str, text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"text": text})
    except Exception as e:  # an alert must never crash the app
        log.error("Could not post the alert to the webhook: %s", type(e).__name__)


async def check_once() -> list[str]:
    """One check. Logs and posts only when the situation changed since the last check."""
    global _last_signature
    db = SessionLocal()
    try:
        summary = ops_summary(db)
    finally:
        db.close()
    msgs = alert_messages(summary)
    signature = (summary["stuck"], summary["failed_recently"])
    if msgs and signature != _last_signature:
        url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
        for m in msgs:
            log.error(m, extra={"fields": {"alert": True, **summary}})
            if url:
                await _post_webhook(url, m)
    _last_signature = signature if msgs else None
    return msgs


async def monitor_loop() -> None:
    interval = int(os.getenv("ALERT_CHECK_SECONDS", "300"))
    if interval <= 0:
        log.info("Alert monitor is off (ALERT_CHECK_SECONDS=0).")
        return
    log.info("Alert monitor running every %s seconds.", interval)
    while True:
        try:
            await check_once()
        except Exception:
            log.exception("Alert check failed")
        await asyncio.sleep(interval)
