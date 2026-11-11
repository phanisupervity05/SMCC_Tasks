# app/routers/policies.py
"""
Command Center policies API (any approved user, see authz.map.json).

Thin on purpose: parse, call the service, return. Rules live in app/services/policy_engine.py.
Every change is written to the audit log.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.audit import AuditCategory
from ..models.call import CommandPolicy, utcnow
from ..security import get_current_user
from ..services.ai.guard import rate_limiter
from ..services.audit import audit
from ..services.policy_ai import DraftFailed, DraftUnavailable, MAX_TEXT, draft_policy
from ..services.policy_engine import (
    PolicyInvalid,
    default_message,
    describe_condition,
    field_catalog,
    policy_dict,
    test_policy_on_recent_calls,
    validate_policy,
)
from ..services.policy_templates import TEMPLATES

log = logging.getLogger(__name__)

router = APIRouter(tags=["Policies"])


def _who(user: dict | None) -> str:
    return str((user or {}).get("preferred_username") or (user or {}).get("email") or (user or {}).get("sub") or "unknown")


def view(p: CommandPolicy) -> dict:
    pd = policy_dict(p)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "enabled": p.enabled,
        "stage": p.stage,
        "action": p.action,
        "match_mode": p.match_mode,
        "conditions": list(p.conditions or []),
        "message": p.message,
        "summary": [describe_condition(c) for c in (p.conditions or [])],
        "effective_message": default_message(pd),
        "source": p.source,
        "natural_language": p.natural_language,
        "hit_count": p.hit_count,
        "created_by": p.created_by,
        "updated_by": p.updated_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _invalid(errors: list[dict], status: int = 422) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": {"error": "validation_failed", "errors": errors}})


async def _body(request: Request):
    try:
        return await request.json()
    except Exception:
        return None


def _extras(payload: dict) -> dict:
    """Where the policy came from: the builder or the AI draft box."""
    source = payload.get("source") if payload.get("source") in ("builder", "ai") else "builder"
    nl = str(payload.get("natural_language") or "").strip()[:MAX_TEXT] or None
    return {"source": source, "natural_language": nl if source == "ai" else None}


@router.get("/policies/catalog")
def catalog():
    """Everything the builder needs: stages, actions, fields with their operators, ready-made templates."""
    return {**field_catalog(), "templates": TEMPLATES}


@router.get("/policies")
def list_policies(db: Session = Depends(get_db)):
    rows = db.query(CommandPolicy).order_by(CommandPolicy.stage, CommandPolicy.id).all()
    return {"items": [view(p) for p in rows]}


@router.get("/policies/{policy_id}")
def get_policy(policy_id: int, db: Session = Depends(get_db)):
    p = db.get(CommandPolicy, policy_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return view(p)


@router.post("/policies", status_code=201)
async def create_policy(request: Request, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    payload = await _body(request)
    try:
        clean = validate_policy(payload)
    except PolicyInvalid as e:
        return _invalid(e.errors)
    p = CommandPolicy(**clean, **_extras(payload), created_by=_who(user), updated_by=_who(user))
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _invalid([{"field": "name", "message": "is already used by another policy"}], 409)
    db.refresh(p)
    await audit.log(
        action="policy.create", description=f"Created policy '{p.name}' ({p.stage}, {p.action})", actor=user,
        category=AuditCategory.SETTINGS, resource_type="policy", resource_id=str(p.id), resource_name=p.name,
        metadata={"conditions": p.conditions, "enabled": p.enabled},
    )
    return JSONResponse(status_code=201, content=view(p))


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: int, request: Request, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    p = db.get(CommandPolicy, policy_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    payload = await _body(request)
    try:
        clean = validate_policy(payload)
    except PolicyInvalid as e:
        return _invalid(e.errors)
    for k, v in {**clean, **_extras(payload)}.items():
        setattr(p, k, v)
    p.updated_by = _who(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _invalid([{"field": "name", "message": "is already used by another policy"}], 409)
    db.refresh(p)
    await audit.log(
        action="policy.update", description=f"Updated policy '{p.name}'", actor=user, category=AuditCategory.SETTINGS,
        resource_type="policy", resource_id=str(p.id), resource_name=p.name, metadata={"conditions": p.conditions, "enabled": p.enabled},
    )
    return view(p)


@router.patch("/policies/{policy_id}/enabled")
async def set_enabled(policy_id: int, request: Request, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    p = db.get(CommandPolicy, policy_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    payload = await _body(request)
    if not isinstance(payload, dict) or not isinstance(payload.get("enabled"), bool):
        return _invalid([{"field": "enabled", "message": "must be true or false"}])
    p.enabled = payload["enabled"]
    p.updated_by = _who(user)
    db.commit()
    db.refresh(p)
    await audit.log(
        action="policy.enable" if p.enabled else "policy.disable",
        description=f"{'Enabled' if p.enabled else 'Disabled'} policy '{p.name}'", actor=user,
        category=AuditCategory.SETTINGS, resource_type="policy", resource_id=str(p.id), resource_name=p.name,
    )
    return view(p)


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(policy_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    p = db.get(CommandPolicy, policy_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    name, pid = p.name, p.id
    db.delete(p)  # flags already raised keep the policy's name, so review history is not lost
    db.commit()
    await audit.log(
        action="policy.delete", description=f"Deleted policy '{name}'", actor=user, category=AuditCategory.SETTINGS,
        resource_type="policy", resource_id=str(pid), resource_name=name,
    )
    return Response(status_code=204)


@router.post("/policies/test")
async def test_policy(request: Request, db: Session = Depends(get_db)):
    """Dry run a policy (saved or not) against the latest calls. Nothing is saved or changed."""
    payload = await _body(request)
    try:
        clean = validate_policy(payload)
    except PolicyInvalid as e:
        return _invalid(e.errors)
    return test_policy_on_recent_calls(db, {**clean, "match_mode": clean["match_mode"]})


@router.post("/policies/from-text")
async def policy_from_text(request: Request, user: dict = Depends(get_current_user)):
    """Plain English to a DRAFT policy for the builder. Nothing is saved."""
    rate_limiter.check(f"policy-ai:{(user or {}).get('sub') or 'anonymous'}")
    payload = await _body(request)
    text = payload.get("text") if isinstance(payload, dict) else None
    try:
        draft = await draft_policy(text or "")
    except DraftUnavailable as e:
        return JSONResponse(status_code=503, content={"detail": str(e)})
    except DraftFailed as e:
        return JSONResponse(status_code=422, content={"detail": {"error": "draft_failed", "message": str(e), "errors": e.errors}})
    return {"draft": {**draft, "source": "ai", "natural_language": text.strip()[:MAX_TEXT]}}
