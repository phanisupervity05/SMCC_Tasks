# app/routers/health.py
"""
Health check endpoints.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..core.database import SessionLocal

log = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
def read_health():
    """
    Liveness probe.
    Public via public.map.json.
    """
    return {"status": "ok"}


@router.get("/ready")
def read_ready():
    """
    Readiness probe: the app is ready only when the database answers.
    Public via public.map.json, so it reveals nothing beyond ready / not ready.
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        log.exception("Readiness check failed: database not reachable")
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    finally:
        db.close()
    return {"status": "ready"}

