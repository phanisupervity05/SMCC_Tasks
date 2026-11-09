# app/routers/webhooks.py
"""
Machine-to-machine webhooks. Listed in public.map.json because they do not use a
user login; each route is protected by its own service token instead (401 on a
missing or wrong token, before the body is read, so nothing is saved).

    POST /api/webhooks/intake   inbound call (same intake as the drop form)
    POST /api/webhooks/output   result from Auto: {agent, task_id, result}
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..auth import require_intake_token, require_output_token
from ..core.database import get_db
from ..services.call_intake import (
    INTAKE_WEBHOOK_ENDPOINT,
    IntakeRejected,
    intake_call,
    record_rejection,
)
from ..services.call_output import OUTPUT_ENDPOINT, OutputRejected, process_output
from ..services.call_views import call_detail

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _json_or_none(request: Request, db: Session, endpoint: str):
    try:
        return await request.json(), True
    except (json.JSONDecodeError, UnicodeDecodeError):
        record_rejection(db, endpoint, "Body was not valid JSON.", {"_raw": "unparseable"})
        return None, False


@router.post("/intake", dependencies=[Depends(require_intake_token)])
async def intake_webhook(request: Request, db: Session = Depends(get_db)):
    payload, ok = await _json_or_none(request, db, INTAKE_WEBHOOK_ENDPOINT)
    if not ok:
        return JSONResponse(
            status_code=422,
            content={"detail": {"error": "validation_failed", "errors": [{"field": "payload", "message": "must be valid JSON"}]}},
        )
    try:
        # The webhook never carries a stub scenario: that is a dashboard test-mode feature.
        call, created = intake_call(db, payload, endpoint=INTAKE_WEBHOOK_ENDPOINT)
    except IntakeRejected as e:
        return JSONResponse(
            status_code=422, content={"detail": {"error": "validation_failed", "errors": e.errors}}
        )
    return JSONResponse(
        status_code=201 if created else 200,
        content={"created": created, "call": call_detail(call)},
    )


@router.post("/output", dependencies=[Depends(require_output_token)])
async def output_webhook(request: Request, db: Session = Depends(get_db)):
    payload, ok = await _json_or_none(request, db, OUTPUT_ENDPOINT)
    if not ok:
        return JSONResponse(
            status_code=422,
            content={"detail": {"error": "invalid_payload", "errors": [{"field": "payload", "message": "must be valid JSON"}]}},
        )
    try:
        return process_output(db, payload, endpoint=OUTPUT_ENDPOINT)
    except OutputRejected as e:
        return JSONResponse(
            status_code=e.http_status, content={"detail": {"error": e.code, "errors": e.errors}}
        )
