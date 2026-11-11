# app/routers/calls.py
"""
Calls API for the dashboard (user login required, see authz.map.json).

Thin on purpose: parse, call the service, return. Rules live in app/services.
"""

import csv
import hashlib
import io
import json
import logging
import mimetypes
import os
import re
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.storage import get_storage_instance
from ..models.call import Call, CallFlag, CallStatus, LeadScore, RejectedRequest, utcnow
from ..services import auto_gateway  # AUTO STUB: for test-mode config only
from ..services.call_intake import (
    INTAKE_DROP_ENDPOINT,
    IntakeRejected,
    RetryNotAllowed,
    intake_call,
    record_rejection,
    retry_call,
)
from ..services.call_rules import RuleError, validate_lead_id
from ..services.call_stats import apply_date_range, compute_stats
from ..services.call_views import call_detail, call_summary, is_stuck, rejected_view, stuck_after_minutes

log = logging.getLogger(__name__)

router = APIRouter(tags=["Calls"])


@router.get("/calls/config")
def calls_config():
    """What the drop form may offer. Test-mode values come from the backend, never the screen."""
    return {
        "stuck_after_minutes": stuck_after_minutes(),
        "statuses": list(CallStatus.ALL),
        # AUTO STUB START
        "test_mode": auto_gateway.test_mode_enabled(),
        "stub_scenarios": auto_gateway.stub_scenarios(),
        # AUTO STUB END
    }


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".aac", ".flac"}
MAX_AUDIO_BYTES = 50 * 1024 * 1024
AUDIO_DIR = "calls/audio"


def _audio_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": {"error": "validation_failed", "errors": [{"field": "audio_file", "message": message}]}},
    )


@router.post("/calls/upload-audio")
async def upload_call_audio(request: Request, file: UploadFile = File(...)):
    """
    Store a dropped audio file and return a link for it. The screen puts that link in
    recording_url, so an uploaded file goes through the same intake as a pasted link.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in AUDIO_EXTENSIONS and not (file.content_type or "").startswith("audio/"):
        return _audio_error(f"must be an audio file ({', '.join(sorted(AUDIO_EXTENSIONS))})")
    if ext not in AUDIO_EXTENSIONS:
        ext = ".mp3"
    content = await file.read(MAX_AUDIO_BYTES + 1)
    if not content:
        return _audio_error("is empty")
    if len(content) > MAX_AUDIO_BYTES:
        return _audio_error(f"must be at most {MAX_AUDIO_BYTES // (1024 * 1024)} MB")

    # Named by content, so dropping the same file twice gives the same link and so the same call.
    name = f"{hashlib.sha256(content).hexdigest()[:32]}{ext}"
    storage = get_storage_instance()
    await storage.upload(f"{AUDIO_DIR}/{name}", content, file.content_type)
    # Absolute link, because the recording link must be a full http(s) URL.
    base_path = os.getenv("BASE_PATH", "")
    url = f"{str(request.base_url).rstrip('/')}{base_path}/api/calls/audio/{name}"
    return {"url": url, "filename": file.filename, "size": len(content)}


@router.get("/calls/audio/{name}")
async def get_call_audio(name: str):
    if not re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]+", name):
        raise HTTPException(status_code=404, detail="Audio not found")
    try:
        content = await get_storage_instance().download(f"{AUDIO_DIR}/{name}")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio not found")
    media = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(content=content, media_type=media)


@router.post("/calls")
async def drop_call(request: Request, db: Session = Depends(get_db)):
    """Drop form. Same intake as the inbound webhook."""
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        record_rejection(db, INTAKE_DROP_ENDPOINT, "Body was not valid JSON.", {"_raw": "unparseable"})
        return JSONResponse(
            status_code=422,
            content={"detail": {"error": "validation_failed", "errors": [{"field": "payload", "message": "must be valid JSON"}]}},
        )

    # AUTO STUB START: the scenario is a test-mode extra, not part of the call data
    stub_scenario = None
    if isinstance(payload, dict) and payload.get("stub_scenario") not in (None, ""):
        stub_scenario = payload.get("stub_scenario")
        if not auto_gateway.test_mode_enabled():
            record_rejection(
                db, INTAKE_DROP_ENDPOINT, "stub_scenario sent while test mode is off.", payload
            )
            return JSONResponse(
                status_code=422,
                content={"detail": {"error": "validation_failed", "errors": [
                    {"field": "stub_scenario", "message": "is only available in test mode"}]}},
            )
        if stub_scenario not in {s["value"] for s in auto_gateway.stub_scenarios()}:
            record_rejection(db, INTAKE_DROP_ENDPOINT, "Unknown stub_scenario.", payload)
            return JSONResponse(
                status_code=422,
                content={"detail": {"error": "validation_failed", "errors": [
                    {"field": "stub_scenario", "message": "is not a known scenario"}]}},
            )
    # AUTO STUB END

    try:
        call, created = intake_call(
            db, payload, endpoint=INTAKE_DROP_ENDPOINT, stub_scenario=stub_scenario
        )
    except IntakeRejected as e:
        return JSONResponse(
            status_code=422, content={"detail": {"error": "validation_failed", "errors": e.errors}}
        )
    return JSONResponse(
        status_code=201 if created else 200,
        content={"created": created, "call": call_detail(call)},
    )


@router.get("/calls/ops")
def calls_ops(db: Session = Depends(get_db)):
    """Operator summary: Auto mode, stuck calls, recent failures."""
    from ..services.alerts import ops_summary

    return ops_summary(db)


@router.get("/calls/auto-policies")
def auto_policies():
    """The two Supervity Auto policies the call agent uses, shown read-only."""
    from ..services.auto_policies import AUTO_POLICIES, snapshot_info

    return {"items": AUTO_POLICIES, "snapshot": snapshot_info()}


@router.get("/calls/stats")
def calls_stats(
    days: int = 14,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    """Numbers for the dashboard. Computed in the service so the screen only displays them."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    return compute_stats(db, days, date_from, date_to)


@router.get("/calls/agents")
def list_agents(db: Session = Depends(get_db)):
    """Distinct sales agents, for the list filter."""
    rows = (
        db.query(Call.agent_id, func.max(Call.agent_name))
        .group_by(Call.agent_id)
        .order_by(func.max(Call.agent_name))
        .all()
    )
    return [{"agent_id": a, "agent_name": n} for a, n in rows]


def _filtered_calls(
    db: Session,
    band: int | None,
    agent_id: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    flagged: bool | None = None,
):
    """The one place the list and the CSV export decide which calls match."""
    if status is not None and status not in CallStatus.ALL:
        raise HTTPException(status_code=422, detail=f"status must be one of: {', '.join(CallStatus.ALL)}")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    q = db.query(Call)
    if band is not None:
        q = q.join(LeadScore, LeadScore.task_id == Call.task_id).filter(LeadScore.band == band)
    if agent_id:
        q = q.filter(Call.agent_id == agent_id)
    if status:
        q = q.filter(Call.status == status)
    if flagged:
        q = q.filter(Call.task_id.in_(db.query(CallFlag.task_id)))
    return apply_date_range(q, date_from, date_to)


@router.get("/calls")
def list_calls(
    band: int | None = None,
    agent_id: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    flagged: bool | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = _filtered_calls(db, band, agent_id, status, date_from, date_to, flagged)
    total = q.count()
    rows = (
        q.order_by(Call.created_at.desc(), Call.id.desc())
        .offset(max(0, offset))
        .limit(min(max(1, limit), 500))
        .all()
    )
    return {"total": total, "limit": min(max(1, limit), 500), "offset": max(0, offset), "items": [call_summary(c) for c in rows]}


EXPORT_COLUMNS = [
    "task_id", "lead_id", "agent_id", "agent_name", "customer_name", "call_date", "status",
    "failure_reason", "lead_band", "audit_score_percent", "flags", "created_at",
]
MAX_EXPORT_ROWS = 10000


def _csv_safe(value) -> str:
    """Stop a spreadsheet from running a cell as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/calls/export.csv")
def export_calls_csv(
    band: int | None = None,
    agent_id: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    flagged: bool | None = None,
    db: Session = Depends(get_db),
):
    """Download the calls that match the same filters as the list (newest first, at most 10,000)."""
    rows = (
        _filtered_calls(db, band, agent_id, status, date_from, date_to, flagged)
        .order_by(Call.created_at.desc(), Call.id.desc())
        .limit(MAX_EXPORT_ROWS)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(EXPORT_COLUMNS)
    for c in rows:
        s = call_summary(c)
        s["flags"] = "; ".join(f["policy"] for f in s["flags"])
        writer.writerow([_csv_safe(s[col]) for col in EXPORT_COLUMNS])
    stamp = utcnow().strftime("%Y%m%d-%H%M")
    return Response(
        content="\ufeff" + buf.getvalue(),  # BOM so Excel reads UTF-8 names correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="calls-{stamp}.csv"'},
    )


@router.get("/calls/{task_id}")
def get_call(task_id: str, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.task_id == task_id).first()
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return call_detail(call)


@router.post("/calls/{task_id}/retry")
def retry_failed_call(task_id: str, db: Session = Depends(get_db)):
    """Run a failed call again. Any other status is refused."""
    call = db.query(Call).filter(Call.task_id == task_id).first()
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    try:
        call = retry_call(db, call)
    except RetryNotAllowed as e:
        raise HTTPException(status_code=409, detail=str(e))
    return call_detail(call)


@router.patch("/calls/{task_id}/lead-id")
async def set_lead_id(task_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Fill in the Lead ID of a call saved before Lead ID became required.
    An existing Lead ID is never overwritten.
    """
    call = db.query(Call).filter(Call.task_id == task_id).first()
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = None
    try:
        lead_id = validate_lead_id(payload.get("lead_id") if isinstance(payload, dict) else None)
    except RuleError as e:
        return JSONResponse(
            status_code=422, content={"detail": {"error": "validation_failed", "errors": e.errors}}
        )
    if call.lead_id and call.lead_id.strip():
        raise HTTPException(status_code=409, detail="This call already has a Lead ID.")
    call.lead_id = lead_id
    db.commit()
    db.refresh(call)
    return call_detail(call)


@router.get("/rejected-requests")
def list_rejected_requests(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(RejectedRequest)
        .order_by(RejectedRequest.created_at.desc(), RejectedRequest.id.desc())
        .limit(min(max(1, limit), 500))
        .all()
    )
    return {"items": [rejected_view(r) for r in rows]}
