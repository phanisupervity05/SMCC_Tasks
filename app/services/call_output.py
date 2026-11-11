# app/services/call_output.py
"""
Output webhook logic: receives {agent, task_id, result} from Auto.

The real route (POST /api/webhooks/output) and the Auto stub both call
process_output(), so there is exactly one set of validation rules.

Rules:
  1. Unknown task_id: reject and log.
  2. lead_score: band must be a whole number 0..5 and a reason must exist,
     otherwise reject and mark the call failed.
  3. call_audit: each check score 1..5. score_percent is recalculated as
     sum(scores) / (5 x number of checks) x 100. A percentage that was sent is ignored.
  4. A repeated result for the same call and agent changes nothing. A different
     result for one already saved is ignored and logged.
  5. When both results are saved, the call becomes "done".

Decisions beyond the spec (easy to change here):
  - An invalid call_audit is handled like an invalid lead_score: rejected, logged,
    and the call is marked failed (otherwise it would sit in "sent to Auto" forever).
  - "failed" is final. A result arriving for an already failed call is rejected and logged.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.call import Call, CallAudit, CallStatus, LeadScore, utcnow
from .call_intake import fail_call, record_rejection
from .policy_engine import run_results_policies
from .call_rules import (
    AGENT_CALL_AUDIT,
    AGENT_LEAD_SCORE,
    AGENTS,
    VALIDATORS,
    RuleError,
)

log = logging.getLogger(__name__)

OUTPUT_ENDPOINT = "/api/webhooks/output"


class OutputRejected(Exception):
    def __init__(self, http_status: int, code: str, errors: list[dict]):
        self.http_status = http_status
        self.code = code
        self.errors = errors
        super().__init__(code)


def _stored_normalized(call: Call, agent: str) -> dict | None:
    if agent == AGENT_LEAD_SCORE and call.lead_score:
        r = call.lead_score
        return {"band": r.band, "label": r.label, "reason": r.reason, "evidence": list(r.evidence or [])}
    if agent == AGENT_CALL_AUDIT and call.call_audit:
        r = call.call_audit
        return {"checks": list(r.checks or []), "score_percent": r.score_percent, "summary": r.summary}
    return None


def _reject(db, endpoint, http_status, code, reason, payload, errors=None, *, commit=True):
    record_rejection(db, endpoint, reason, payload, commit=commit)
    raise OutputRejected(http_status, code, errors or [{"field": "payload", "message": reason}])


def process_output(db: Session, payload, *, endpoint: str = OUTPUT_ENDPOINT) -> dict:
    """Returns {"outcome": "saved"|"duplicate", ...} or raises OutputRejected."""
    if not isinstance(payload, dict):
        _reject(db, endpoint, 422, "invalid_payload", "Payload must be a JSON object.", payload)

    agent, task_id, result = payload.get("agent"), payload.get("task_id"), payload.get("result")
    missing = [
        {"field": f, "message": "is required"}
        for f, v in (("agent", agent), ("task_id", task_id), ("result", result))
        if v in (None, "")
    ]
    if missing:
        _reject(
            db, endpoint, 422, "invalid_payload",
            "Missing " + ", ".join(m["field"] for m in missing) + ".", payload, missing,
        )
    if agent not in AGENTS:
        _reject(
            db, endpoint, 422, "unknown_agent",
            f"Unknown agent '{str(agent)[:50]}'. Expected one of: {', '.join(AGENTS)}.", payload,
            [{"field": "agent", "message": f"must be one of: {', '.join(AGENTS)}"}],
        )

    # Rule 1: unknown task_id
    call = db.query(Call).filter(Call.task_id == str(task_id)).first() if isinstance(task_id, str) else None
    if call is None:
        _reject(
            db, endpoint, 404, "unknown_task_id",
            f"Unknown task_id '{str(task_id)[:80]}'.", payload,
            [{"field": "task_id", "message": "is not a known call"}],
        )

    # Rule 4: already saved for this call and agent?
    outcome = _check_already_saved(db, endpoint, call, agent, result, payload)
    if outcome:
        return outcome

    # A failed call is final.
    if call.status == CallStatus.FAILED:
        _reject(
            db, endpoint, 409, "call_failed",
            f"Call already failed ({call.failure_reason or 'no reason recorded'}); {agent} result not saved.",
            payload,
        )

    # Rules 2 and 3: validate
    try:
        clean = VALIDATORS[agent](result)
    except RuleError as e:
        label = "Lead Score" if agent == AGENT_LEAD_SCORE else "Call Audit"
        record_rejection(db, endpoint, f"{label} result rejected: {e.summary()}", payload, commit=False)
        fail_call(db, call.id, f"{label} result rejected: {e.summary()}")  # commits both
        raise OutputRejected(422, "invalid_result", e.errors)

    # Save
    row = (
        LeadScore(task_id=call.task_id, **clean)
        if agent == AGENT_LEAD_SCORE
        else CallAudit(task_id=call.task_id, **clean)
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        db.expire_all()
        call = db.query(Call).filter(Call.task_id == call.task_id).one()
        outcome = _check_already_saved(db, endpoint, call, agent, result, payload)
        if outcome:
            return outcome
        raise

    # Rule 5: both saved -> done
    db.expire_all()
    call = db.query(Call).filter(Call.task_id == call.task_id).one()
    if call.lead_score and call.call_audit and call.status != CallStatus.FAILED:
        call.status = CallStatus.DONE
        call.failure_reason = None
        db.commit()
        try:
            run_results_policies(db, call)  # flag for review; never fails the result
        except Exception:
            db.rollback()
            log.exception("Results policies failed for %s", call.task_id)
    else:
        call.updated_at = utcnow()  # a result arrived
        db.commit()

    return {"outcome": "saved", "task_id": call.task_id, "agent": agent, "status": call.status}


def _check_already_saved(db, endpoint, call, agent, result, payload) -> dict | None:
    stored = _stored_normalized(call, agent)
    if stored is None:
        return None
    try:
        incoming = VALIDATORS[agent](result)
    except RuleError:
        incoming = None
    if incoming == stored:
        return {"outcome": "duplicate", "task_id": call.task_id, "agent": agent, "status": call.status}
    # Different from what is saved: ignore and log.
    record_rejection(
        db, endpoint,
        f"Conflicting {agent} result ignored: a different result is already saved for this call.",
        payload,
    )
    raise OutputRejected(
        409, "conflicting_result",
        [{"field": "result", "message": f"a different {agent} result is already saved; the new one was ignored"}],
    )
