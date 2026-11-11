# app/services/call_stats.py
"""
Numbers about calls. One place, used by the dashboard, the AI Manager and AI Insights.

Everything is aggregated in the database, so the cost does not grow with the number of calls.
An optional created_at date range (inclusive, UTC) narrows every number.
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Integer, case, func
from sqlalchemy.orm import Session

from ..models.call import Call, CallAudit, CallStatus, LeadScore, RejectedRequest, utcnow
from .call_views import stuck_after_minutes

MAX_RANGE_DAYS = 92


def date_bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    """Inclusive dates to a [start, end) datetime pair in UTC."""
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc) if date_to else None
    return start, end


def apply_date_range(q, date_from: date | None, date_to: date | None):
    start, end = date_bounds(date_from, date_to)
    if start is not None:
        q = q.filter(Call.created_at >= start)
    if end is not None:
        q = q.filter(Call.created_at < end)
    return q


def _avg(x, places: int = 1):
    return round(float(x), places) if x is not None else None


def compute_stats(
    db: Session,
    days: int = 14,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    # Days shown in the per-day chart: the chosen range, otherwise the last `days`.
    today = utcnow().date()
    if date_from or date_to:
        last = date_to or today
        first = date_from or (last - timedelta(days=days - 1))
        first = max(first, last - timedelta(days=MAX_RANGE_DAYS - 1))
    else:
        last = today
        first = today - timedelta(days=min(max(1, days), MAX_RANGE_DAYS) - 1)

    def scoped(*entities):
        return apply_date_range(db.query(*entities).select_from(Call), date_from, date_to)

    # Status counts
    by_status = {s: 0 for s in CallStatus.ALL}
    for status, n in scoped(Call.status, func.count(Call.id)).group_by(Call.status).all():
        by_status[status] = n
    total = sum(by_status.values())
    done = by_status[CallStatus.DONE]

    # Lead band mix
    bands = {b: 0 for b in range(6)}
    for band, n in (
        scoped(LeadScore.band, func.count(LeadScore.id))
        .join(LeadScore, LeadScore.task_id == Call.task_id)
        .group_by(LeadScore.band)
        .all()
    ):
        bands[band] = n

    # Overall audit average
    avg_audit = (
        scoped(func.avg(CallAudit.score_percent))
        .join(CallAudit, CallAudit.task_id == Call.task_id)
        .scalar()
    )

    # Stuck: in "sent to Auto" for longer than the limit
    cutoff = utcnow() - timedelta(minutes=stuck_after_minutes())
    stuck = (
        scoped(func.count(Call.id))
        .filter(Call.status == CallStatus.SENT_TO_AUTO, Call.sent_to_auto_at.isnot(None), Call.sent_to_auto_at < cutoff)
        .scalar()
        or 0
    )

    missing_lead = (
        scoped(func.count(Call.id))
        .filter((Call.lead_id.is_(None)) | (func.trim(Call.lead_id) == ""))
        .scalar()
        or 0
    )

    # Calls per day
    per_day = {(first + timedelta(days=i)).isoformat(): 0 for i in range((last - first).days + 1)}
    for day, n in scoped(func.date(Call.created_at), func.count(Call.id)).group_by(func.date(Call.created_at)).all():
        if str(day) in per_day:
            per_day[str(day)] = n

    # Per sales agent, one query
    agent_rows = (
        scoped(
            Call.agent_id,
            func.max(Call.agent_name),
            func.count(Call.id),
            func.sum(case((Call.status == CallStatus.DONE, 1), else_=0).cast(Integer)),
            func.avg(LeadScore.band),
            func.avg(CallAudit.score_percent),
        )
        .outerjoin(LeadScore, LeadScore.task_id == Call.task_id)
        .outerjoin(CallAudit, CallAudit.task_id == Call.task_id)
        .group_by(Call.agent_id)
        .order_by(func.count(Call.id).desc(), Call.agent_id)
        .all()
    )
    agents = [
        {
            "agent_id": agent_id,
            "agent_name": name,
            "calls": n,
            "done": int(d or 0),
            "avg_band": _avg(band),
            "avg_audit_percent": _avg(audit),
        }
        for agent_id, name, n, d, band, audit in agent_rows
    ]

    scored = sum(bands.values())
    return {
        "total": total,
        "processed": done,
        "in_progress": by_status[CallStatus.RECEIVED] + by_status[CallStatus.SENT_TO_AUTO],
        "failed": by_status[CallStatus.FAILED],
        "rejected": db.query(func.count(RejectedRequest.id)).scalar() or 0,
        "stuck": stuck,
        "missing_lead_id": missing_lead,
        "success_rate": round(done * 100 / total, 1) if total else None,
        "avg_audit_percent": _avg(avg_audit),
        "avg_band": round(sum(b * n for b, n in bands.items()) / scored, 1) if scored else None,
        "by_status": by_status,
        "bands": [{"band": b, "count": n} for b, n in sorted(bands.items())],
        "per_day": [{"date": d, "count": n} for d, n in per_day.items()],
        "agents": agents,
        "range": {"from": first.isoformat(), "to": last.isoformat()},
    }
