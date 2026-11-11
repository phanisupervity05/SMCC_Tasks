# app/services/retention.py
"""
Data retention: remove old calls, their results and their stored recordings.

Nothing runs on its own. Run scripts/purge_old_calls.py (a dry run unless --apply is given).

Rules:
  * Only calls that are finished ("done" or "failed") and older than the cutoff are removed.
    Calls still in progress are never touched.
  * A call goes together with its lead score and call audit.
  * An uploaded recording file is deleted only when no remaining call still uses it
    (the same recording can belong to calls with different dates).
  * Rejected requests older than the cutoff are removed too, because they keep a copy of the payload.
  * The retention period must be at least MIN_DAYS, so a typo cannot wipe recent data.
"""

import logging
import re
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.call import Call, CallAudit, CallStatus, LeadScore, RejectedRequest, utcnow

log = logging.getLogger(__name__)

MIN_DAYS = 30
BATCH = 500
AUDIO_DIR = "calls/audio"
_OWN_AUDIO = re.compile(r"/api/calls/audio/(?P<name>[0-9a-f]{32}\.[a-z0-9]+)$")


def own_audio_name(recording_url: str | None) -> str | None:
    m = _OWN_AUDIO.search((recording_url or "").split("?")[0])
    return m.group("name") if m else None


async def purge_old_calls(db: Session, days: int, *, apply: bool = False, storage=None) -> dict:
    """Returns a summary. With apply=False nothing is deleted."""
    if days < MIN_DAYS:
        raise ValueError(f"Retention must be at least {MIN_DAYS} days (got {days}).")
    cutoff = utcnow() - timedelta(days=days)
    expired = db.query(Call).filter(
        Call.created_at < cutoff, Call.status.in_([CallStatus.DONE, CallStatus.FAILED])
    )
    expired_ids = [row[0] for row in expired.with_entities(Call.id).all()]
    expired_tasks = [r[0] for r in db.query(Call.task_id).filter(Call.id.in_(expired_ids)).all()] if expired_ids else []

    # Recording files used by expired calls, minus the ones a remaining call still needs.
    candidate_audio = {n for (u,) in db.query(Call.recording_url).filter(Call.id.in_(expired_ids)).all()
                       if (n := own_audio_name(u))} if expired_ids else set()
    remaining = db.query(Call.recording_url)
    if expired_ids:
        remaining = remaining.filter(~Call.id.in_(expired_ids))
    still_used = {n for (u,) in remaining.all() if (n := own_audio_name(u))}
    audio_to_delete = sorted(candidate_audio - still_used)

    rejected = db.query(RejectedRequest).filter(RejectedRequest.created_at < cutoff)
    rejected_count = rejected.with_entities(func.count(RejectedRequest.id)).scalar() or 0

    summary = {
        "dry_run": not apply,
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "calls": len(expired_ids),
        "lead_scores": db.query(func.count(LeadScore.id)).filter(LeadScore.task_id.in_(expired_tasks)).scalar() or 0
        if expired_tasks else 0,
        "call_audits": db.query(func.count(CallAudit.id)).filter(CallAudit.task_id.in_(expired_tasks)).scalar() or 0
        if expired_tasks else 0,
        "audio_files": len(audio_to_delete),
        "rejected_requests": rejected_count,
    }
    if not apply:
        log.info("Retention dry run: %s", summary)
        return summary

    for i in range(0, len(expired_tasks), BATCH):
        chunk = expired_tasks[i:i + BATCH]
        db.query(LeadScore).filter(LeadScore.task_id.in_(chunk)).delete(synchronize_session=False)
        db.query(CallAudit).filter(CallAudit.task_id.in_(chunk)).delete(synchronize_session=False)
        db.query(Call).filter(Call.task_id.in_(chunk)).delete(synchronize_session=False)
        db.commit()
    rejected.delete(synchronize_session=False)
    db.commit()

    failed_files = 0
    if audio_to_delete:
        if storage is None:
            from ..core.storage import get_storage_instance

            storage = get_storage_instance()
        for name in audio_to_delete:
            try:
                await storage.delete(f"{AUDIO_DIR}/{name}")
            except Exception:
                failed_files += 1
                log.exception("Could not delete recording %s", name)
    summary["audio_files_failed"] = failed_files
    log.warning("Retention purge applied: %s", summary)
    return summary
