# app/services/call_stats.py
"""Numbers about calls. One place, used by the dashboard, the AI Manager and AI Insights."""

from datetime import timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.call import Call, CallStatus, RejectedRequest, utcnow
from .call_views import is_stuck


def compute_stats(db: Session, days: int = 14) -> dict:
    days = min(max(1, days), 90)
    calls = db.query(Call).all()
    by_status = {s: 0 for s in CallStatus.ALL}
    bands = {b: 0 for b in range(6)}
    audit_scores: list[float] = []
    stuck = 0
    per_agent: dict[str, dict] = {}
    per_day: dict[str, int] = {}
    today = utcnow().date()
    for i in range(days - 1, -1, -1):
        per_day[(today - timedelta(days=i)).isoformat()] = 0

    for c in calls:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        if is_stuck(c):
            stuck += 1
        band = c.lead_score.band if c.lead_score else None
        if band is not None:
            bands[band] = bands.get(band, 0) + 1
        score = c.call_audit.score_percent if c.call_audit else None
        if score is not None:
            audit_scores.append(score)
        created = c.created_at if c.created_at.tzinfo else c.created_at.replace(tzinfo=timezone.utc)
        key = created.date().isoformat()
        if key in per_day:
            per_day[key] += 1
        a = per_agent.setdefault(
            c.agent_id,
            {"agent_id": c.agent_id, "agent_name": c.agent_name, "calls": 0, "done": 0, "bands": [], "scores": []},
        )
        a["calls"] += 1
        a["done"] += 1 if c.status == CallStatus.DONE else 0
        if band is not None:
            a["bands"].append(band)
        if score is not None:
            a["scores"].append(score)

    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    total = len(calls)
    done = by_status[CallStatus.DONE]
    agents = sorted(
        (
            {
                "agent_id": a["agent_id"],
                "agent_name": a["agent_name"],
                "calls": a["calls"],
                "done": a["done"],
                "avg_band": avg(a["bands"]),
                "avg_audit_percent": avg(a["scores"]),
            }
            for a in per_agent.values()
        ),
        key=lambda a: -a["calls"],
    )
    return {
        "total": total,
        "processed": done,
        "in_progress": by_status[CallStatus.RECEIVED] + by_status[CallStatus.SENT_TO_AUTO],
        "failed": by_status[CallStatus.FAILED],
        "rejected": db.query(func.count(RejectedRequest.id)).scalar() or 0,
        "stuck": stuck,
        "success_rate": round(done * 100 / total, 1) if total else None,
        "avg_audit_percent": avg(audit_scores),
        "avg_band": avg([b for b, n in bands.items() for _ in range(n)]),
        "by_status": by_status,
        "bands": [{"band": b, "count": n} for b, n in sorted(bands.items())],
        "per_day": [{"date": d, "count": n} for d, n in per_day.items()],
        "agents": agents,
    }
