# app/services/call_intake.py
"""
Intake: the one place a call enters the system.

Used by BOTH the dashboard drop form (POST /api/calls) and the inbound webhook
(POST /api/webhooks/intake). 401 handling happens before this runs (see
app/auth), so nothing reaches here unauthenticated.

Rules:
  2. Required fields (recording_url, agent_id, agent_name). Incomplete payloads are
     rejected, written to rejected_requests, and never saved as a call.
  3. TaskId = hash(recording link + call date). If it already exists, return the
     existing call and do nothing else (one call, one run).
  4. Save as "received", pass to Auto, set "sent_to_auto". If the hand-off fails,
     set "failed" with the reason.
"""

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.call import Call, CallAudit, CallStatus, LeadScore, RejectedRequest, utcnow
from . import auto_gateway
from .auto_gateway import AutoHandoffError, HandOff
from .call_rules import RuleError, generate_task_id, safe_payload_copy, validate_intake_payload

log = logging.getLogger(__name__)

INTAKE_DROP_ENDPOINT = "/api/calls"
INTAKE_WEBHOOK_ENDPOINT = "/api/webhooks/intake"


class IntakeRejected(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))


def record_rejection(db: Session, endpoint: str, reason: str, payload, *, commit: bool = True):
    """Write a rejected request with a safe copy of its payload (no tokens)."""
    db.add(
        RejectedRequest(
            endpoint=endpoint[:255],
            reason=reason[:2000],
            payload=safe_payload_copy(payload),
        )
    )
    if commit:
        db.commit()


def _now() -> datetime:
    return utcnow()


def fail_call(db: Session, call_id: int, reason: str) -> None:
    """Mark a call failed (never overrides a finished call)."""
    db.query(Call).filter(Call.id == call_id, Call.status != CallStatus.DONE).update(
        {"status": CallStatus.FAILED, "failure_reason": reason[:2000], "updated_at": _now()}
    )
    db.commit()


def intake_call(
    db: Session,
    payload,
    *,
    endpoint: str,
    stub_scenario: str | None = None,
) -> tuple[Call, bool]:
    """
    Returns (call, created). created is False when the TaskId already existed.
    Raises IntakeRejected for an incomplete or invalid payload.
    """
    try:
        data = validate_intake_payload(payload)
    except RuleError as e:
        record_rejection(db, endpoint, f"Incomplete or invalid payload: {e.summary()}", payload)
        raise IntakeRejected(e.errors)

    task_id = generate_task_id(data["recording_url"], data["call_date"])

    existing = db.query(Call).filter(Call.task_id == task_id).first()
    if existing is not None:
        return existing, False

    call = Call(task_id=task_id, status=CallStatus.RECEIVED, **data)
    db.add(call)
    try:
        db.commit()
    except IntegrityError:
        # Two identical drops raced; the other one won. Same answer as rule 3.
        db.rollback()
        return db.query(Call).filter(Call.task_id == task_id).one(), False
    db.refresh(call)

    handoff = HandOff(
        task_id=task_id,
        recording_url=call.recording_url,
        agent_id=call.agent_id,
        agent_name=call.agent_name,
        lead_id=call.lead_id,
        customer_name=call.customer_name,
        call_date=data["call_date"],
    )
    try:
        auto_gateway.hand_off(handoff, stub_scenario)
    except AutoHandoffError as e:
        fail_call(db, call.id, f"Hand-off to Auto failed: {e}")
    except Exception as e:  # never leave a call in "received" without a reason
        log.exception("Unexpected hand-off error for %s", task_id)
        fail_call(db, call.id, f"Hand-off to Auto failed: {type(e).__name__}")
    else:
        now = _now()
        # Conditional: a very fast result may already have moved the call on.
        db.query(Call).filter(Call.id == call.id, Call.status == CallStatus.RECEIVED).update(
            {"status": CallStatus.SENT_TO_AUTO, "sent_to_auto_at": now, "updated_at": now}
        )
        db.commit()

    db.expire_all()
    return db.query(Call).filter(Call.id == call.id).one(), True


class RetryNotAllowed(Exception):
    """Only a failed call can be run again."""


def retry_call(db: Session, call: Call, stub_scenario: str | None = None) -> Call:
    """
    Run a failed call again with the same task_id. Anything left over from the failed run
    (partial results, transcript, output) is cleared so the new run starts clean.
    Raises RetryNotAllowed unless the call is "failed".
    """
    # Conditional claim: two quick clicks cannot start two runs.
    claimed = (
        db.query(Call)
        .filter(Call.id == call.id, Call.status == CallStatus.FAILED)
        .update(
            {
                "status": CallStatus.RECEIVED,
                "failure_reason": None,
                "sent_to_auto_at": None,
                "transcript": None,
                "auto_output": None,
                "updated_at": _now(),
            }
        )
    )
    if not claimed:
        db.rollback()
        raise RetryNotAllowed("Only a failed call can be run again.")
    db.query(LeadScore).filter(LeadScore.task_id == call.task_id).delete()
    db.query(CallAudit).filter(CallAudit.task_id == call.task_id).delete()
    db.commit()
    db.expire_all()
    call = db.query(Call).filter(Call.id == call.id).one()

    handoff = HandOff(
        task_id=call.task_id,
        recording_url=call.recording_url,
        agent_id=call.agent_id,
        agent_name=call.agent_name,
        lead_id=call.lead_id,
        customer_name=call.customer_name,
        call_date=call.call_date,
    )
    try:
        auto_gateway.hand_off(handoff, stub_scenario)
    except AutoHandoffError as e:
        fail_call(db, call.id, f"Hand-off to Auto failed: {e}")
    except Exception as e:
        log.exception("Unexpected hand-off error on retry for %s", call.task_id)
        fail_call(db, call.id, f"Hand-off to Auto failed: {type(e).__name__}")
    else:
        now = _now()
        db.query(Call).filter(Call.id == call.id, Call.status == CallStatus.RECEIVED).update(
            {"status": CallStatus.SENT_TO_AUTO, "sent_to_auto_at": now, "updated_at": now}
        )
        db.commit()
    db.expire_all()
    return db.query(Call).filter(Call.id == call.id).one()
