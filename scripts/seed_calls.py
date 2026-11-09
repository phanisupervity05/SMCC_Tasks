#!/usr/bin/env python3
"""
Seed the call tables with 10 FAKE calls that cover every status:

    done (4)  sent to Auto (3: in progress, waiting, and one STUCK >15 min)
    received (1)  failed (2: hand-off failed, invalid band)

Plus two rejected requests for the rejected-requests screen.

All names, links and quotes are made up. recordings.example.com does not exist.
No real recordings or transcripts belong in this repo.

Safe to run more than once: calls that already exist (same TaskId) are skipped.

Usage (from the project root, DATABASE_URL set, tables already migrated):
    python scripts/seed_calls.py
    python scripts/seed_calls.py --create-tables   # local SQLite convenience only
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.call import (  # noqa: E402
    Call,
    CallAudit,
    CallStatus,
    LeadScore,
    RejectedRequest,
)
from app.services.call_rules import compute_score_percent, generate_task_id, parse_call_date  # noqa: E402

NOW = datetime.now(timezone.utc)


def ago(**kw) -> datetime:
    return NOW - timedelta(**kw)


def checks(*scores):
    names = [
        ("Greeting and introduction", "Hi, this is the sales rep from Sample Co."),
        ("Needs discovery", "What is slowing your team down today?"),
        ("Product explanation", "It automates the review step."),
        ("Objection handling", "I understand the concern about timing."),
        ("Next step agreed", "I will send the proposal tomorrow."),
    ]
    return [{"name": n, "score": s, "evidence": [q]} for (n, q), s in zip(names, scores)]


def audit(*scores, summary):
    c = checks(*scores)
    return {"checks": c, "score_percent": compute_score_percent([x["score"] for x in c]), "summary": summary}


# (agent, customer, date, minutes_ago_created, status, sent_minutes_ago, failure_reason, lead, audit)
SAMPLES = [
    dict(n=1, agent=("A-100", "Priya Sample"), customer="Northwind Sample Ltd", date="2026-11-03",
         created=ago(days=3), status=CallStatus.DONE, sent=ago(days=3),
         lead=dict(band=4, label="Strong fit", reason="Budget confirmed and a decision date this quarter.",
                   evidence=["We have budget set aside for this quarter.", "Please send the proposal by Friday."]),
         audit=audit(5, 4, 3, 4, 5, summary="Clear opening and good discovery. Product explanation could be more specific.")),
    dict(n=2, agent=("A-100", "Priya Sample"), customer="Contoso Sample Inc", date="2026-11-04",
         created=ago(days=2, hours=4), status=CallStatus.DONE, sent=ago(days=2, hours=4),
         lead=dict(band=0, label="No fit", reason="Customer said there is no project and asked not to be contacted again.",
                   evidence=["We are not planning anything like this.", "Please take us off your list."]),
         audit=audit(4, 2, 3, 2, 3, summary="Polite call, but discovery was cut short and the next step was not agreed.")),
    dict(n=3, agent=("A-200", "Marcus Example"), customer="Fabrikam Sample", date="2026-11-05",
         created=ago(days=1, hours=6), status=CallStatus.DONE, sent=ago(days=1, hours=6),
         lead=dict(band=5, label="Ready to buy", reason="Asked for a contract and named the signer.",
                   evidence=["Send over the contract, our director signs on Monday."]),
         audit=audit(5, 5, 4, 5, 5, summary="Excellent call. Every step covered with specific examples.")),
    dict(n=4, agent=("A-200", "Marcus Example"), customer="Adventure Sample Works", date="2026-11-05",
         created=ago(days=1, hours=2), status=CallStatus.DONE, sent=ago(days=1, hours=2),
         lead=dict(band=2, label="Early interest", reason="Interested, but no budget owner on the call.",
                   evidence=["I would need to check with finance first."]),
         audit=audit(3, 3, 4, 3, 2, summary="Solid structure. Objection handling and closing need work.")),
    dict(n=5, agent=("A-300", "Dana Placeholder"), customer="Tailspin Sample Co", date="2026-11-06",
         created=ago(minutes=6), status=CallStatus.SENT_TO_AUTO, sent=ago(minutes=5),
         lead=dict(band=3, label="Warm", reason="Asked for pricing and a demo next week.",
                   evidence=["Can you show us a demo next week?"]), audit=None),   # in progress: lead score arrived
    dict(n=6, agent=("A-300", "Dana Placeholder"), customer=None, date=None,
         created=ago(minutes=2), status=CallStatus.SENT_TO_AUTO, sent=ago(minutes=1),
         lead=None, audit=None),                                                    # in progress: nothing yet
    dict(n=7, agent=("A-100", "Priya Sample"), customer="Wingtip Sample Group", date="2026-11-06",
         created=ago(minutes=50), status=CallStatus.SENT_TO_AUTO, sent=ago(minutes=42),
         lead=dict(band=3, label="Warm", reason="Wants a follow-up after their board meeting.",
                   evidence=["Let us talk again after the board meets."]), audit=None),  # STUCK
    dict(n=8, agent=("A-200", "Marcus Example"), customer="Litware Sample", date="2026-11-07",
         created=ago(seconds=20), status=CallStatus.RECEIVED, sent=None, lead=None, audit=None),
    dict(n=9, agent=("A-300", "Dana Placeholder"), customer="Proseware Sample", date="2026-11-05",
         created=ago(hours=5), status=CallStatus.FAILED, sent=None,
         failure="Hand-off to Auto failed: Recording link could not be fetched (HTTP 404 from the recording host).",
         lead=None, audit=None),
    dict(n=10, agent=("A-200", "Marcus Example"), customer="Coho Sample Vineyard", date="2026-11-06",
         created=ago(hours=3), status=CallStatus.FAILED, sent=ago(hours=3),
         failure="Lead Score result rejected: band: must be a whole number from 0 to 5 (got 7)",
         lead=None,
         audit=audit(4, 4, 4, 3, 4, summary="Good call overall. Strong discovery.")),
]


def seed():
    db = SessionLocal()
    added = skipped = 0
    try:
        for s in SAMPLES:
            url = f"https://recordings.example.com/sample-{s['n']:03d}.mp3"
            call_date = parse_call_date(s["date"]) if s["date"] else None
            task_id = generate_task_id(url, call_date)
            if db.query(Call).filter(Call.task_id == task_id).first():
                skipped += 1
                continue
            call = Call(
                task_id=task_id,
                lead_id=f"LEAD-{1000 + s['n']}",
                agent_id=s["agent"][0],
                agent_name=s["agent"][1],
                customer_name=s["customer"],
                call_date=call_date,
                recording_url=url,
                status=s["status"],
                failure_reason=s.get("failure"),
                sent_to_auto_at=s["sent"],
                created_at=s["created"],
                updated_at=s["sent"] or s["created"],
            )
            db.add(call)
            db.flush()
            if s["lead"]:
                db.add(LeadScore(task_id=task_id, created_at=s["sent"] or s["created"], **s["lead"]))
            if s["audit"]:
                db.add(CallAudit(task_id=task_id, created_at=s["sent"] or s["created"], **s["audit"]))
            added += 1

        if db.query(RejectedRequest).count() == 0:
            db.add_all(
                [
                    RejectedRequest(
                        endpoint="/api/calls",
                        reason="Incomplete or invalid payload: recording_url: is required",
                        payload={"agent_id": "A-100", "agent_name": "Priya Sample"},
                        created_at=ago(hours=8),
                    ),
                    RejectedRequest(
                        endpoint="/api/webhooks/output",
                        reason="Unknown task_id 'call_000000000000000000000000'.",
                        payload={"agent": "lead_score", "task_id": "call_000000000000000000000000",
                                 "result": {"band": 3, "reason": "Sample"}},
                        created_at=ago(hours=2),
                    ),
                ]
            )
        db.commit()
        print(f"Seed complete: {added} calls added, {skipped} already present.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if "--create-tables" in sys.argv:
        import app.models  # noqa: F401

        Base.metadata.create_all(engine)
    seed()
