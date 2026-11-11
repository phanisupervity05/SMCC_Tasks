# app/services/call_views.py
"""Turns call rows into API responses. The "stuck" rule lives here, not in the screens."""

import os
from datetime import datetime, timedelta, timezone

from ..models.call import Call, CallStatus, RejectedRequest, utcnow


def stuck_after_minutes() -> int:
    try:
        return max(1, int(os.getenv("STUCK_AFTER_MINUTES", "15")))
    except ValueError:
        return 15


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite drops tzinfo


def _iso(dt: datetime | None) -> str | None:
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def is_stuck(call: Call, now: datetime | None = None) -> bool:
    """In "sent to Auto" for longer than STUCK_AFTER_MINUTES."""
    if call.status != CallStatus.SENT_TO_AUTO or call.sent_to_auto_at is None:
        return False
    now = now or utcnow()
    return now - _aware(call.sent_to_auto_at) > timedelta(minutes=stuck_after_minutes())


def call_summary(call: Call) -> dict:
    return {
        "task_id": call.task_id,
        "lead_id": call.lead_id,
        "agent_id": call.agent_id,
        "agent_name": call.agent_name,
        "customer_name": call.customer_name,
        "call_date": _iso(call.call_date),
        "status": call.status,
        "failure_reason": call.failure_reason,
        "is_stuck": is_stuck(call),
        "stuck_after_minutes": stuck_after_minutes(),
        "results_received": {
            "lead_score": call.lead_score is not None,
            "call_audit": call.call_audit is not None,
        },
        "flags": [{"policy_id": f.policy_id, "policy": f.policy_name, "message": f.message} for f in (call.flags or [])],
        "lead_band": call.lead_score.band if call.lead_score else None,
        "audit_score_percent": call.call_audit.score_percent if call.call_audit else None,
        "sent_to_auto_at": _iso(call.sent_to_auto_at),
        "created_at": _iso(call.created_at),
        "updated_at": _iso(call.updated_at),
    }


def call_detail(call: Call) -> dict:
    d = call_summary(call)
    d["recording_url"] = call.recording_url
    d["transcript"] = call.transcript
    d["auto_output"] = call.auto_output
    d["lead_score"] = (
        {
            "band": call.lead_score.band,
            "label": call.lead_score.label,
            "reason": call.lead_score.reason,
            "evidence": list(call.lead_score.evidence or []),
            "created_at": _iso(call.lead_score.created_at),
        }
        if call.lead_score
        else None
    )
    d["call_audit"] = (
        {
            "checks": list(call.call_audit.checks or []),
            "score_percent": call.call_audit.score_percent,
            "summary": call.call_audit.summary,
            "created_at": _iso(call.call_audit.created_at),
        }
        if call.call_audit
        else None
    )
    return d


def rejected_view(r: RejectedRequest) -> dict:
    return {
        "id": r.id,
        "endpoint": r.endpoint,
        "reason": r.reason,
        "payload": r.payload,
        "created_at": _iso(r.created_at),
    }
