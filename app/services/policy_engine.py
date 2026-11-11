# app/services/policy_engine.py
"""
Command Center policies: rules the app enforces itself on every call.

A policy has a stage, an action, and conditions:

  stage "intake"   runs before a call is saved (drop form and inbound webhook)
  stage "results"  runs once a call is done (lead score and audit both saved)
  action "reject"  intake only: the request is refused and logged under Rejected requests
  action "flag"    the call carries on, but is marked for review with the policy's message

Conditions compare one FIELD with one OPERATOR and a value. "all" means every condition must hold,
"any" means one is enough. Some fields compare with the database (for example how many earlier calls
used the same Lead ID), which is how duplicate checks are written.

Nothing here uses patterns that can run away (no user regular expressions). The "matches format"
operator uses a simple mask: # is a digit, A is a letter, * is anything, every other character is literal.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.call import Call, CallFlag, CallStatus, CommandPolicy, utcnow
from .call_rules import normalize_recording_url

log = logging.getLogger(__name__)

STAGES = ("intake", "results")
ACTIONS = ("reject", "flag")
MATCH_MODES = ("all", "any")
MAX_CONDITIONS = 10
MAX_VALUE_LEN = 200
MAX_LIST_ITEMS = 50

TEXT_OPS = {
    "equals": "equals",
    "not_equals": "does not equal",
    "contains": "contains",
    "not_contains": "does not contain",
    "starts_with": "starts with",
    "ends_with": "ends with",
    "in_list": "is one of",
    "not_in_list": "is not one of",
    "matches_format": "matches format",
    "not_matches_format": "does not match format",
    "is_empty": "is empty",
    "is_not_empty": "is not empty",
}
NUMBER_OPS = {
    "equals": "equals",
    "not_equals": "does not equal",
    "gt": "is greater than",
    "gte": "is at least",
    "lt": "is less than",
    "lte": "is at most",
    "is_empty": "is empty",
    "is_not_empty": "is not empty",
}
NO_VALUE_OPS = {"is_empty", "is_not_empty"}

# key: (label, type, stages, help)
FIELDS: dict[str, dict] = {
    # From the call itself
    "recording_url": {"label": "Recording link", "type": "text", "stages": ["intake", "results"], "group": "Call details"},
    "recording_domain": {"label": "Recording link domain", "type": "text", "stages": ["intake", "results"], "group": "Call details",
                         "help": "For example recordings.example.com"},
    "agent_id": {"label": "Sales agent ID", "type": "text", "stages": ["intake", "results"], "group": "Call details"},
    "agent_name": {"label": "Sales agent name", "type": "text", "stages": ["intake", "results"], "group": "Call details"},
    "lead_id": {"label": "Lead ID", "type": "text", "stages": ["intake", "results"], "group": "Call details"},
    "customer_name": {"label": "Customer name", "type": "text", "stages": ["intake", "results"], "group": "Call details"},
    "call_age_days": {"label": "Call age (days)", "type": "number", "stages": ["intake", "results"], "group": "Call details",
                      "help": "Days since the call date. Negative means the call date is in the future. Empty when no call date was given."},
    # Compared with the database
    "lead_id_calls": {"label": "Earlier calls with the same Lead ID", "type": "number", "stages": ["intake", "results"],
                      "group": "Compared with the database", "help": "Use 'is at least 1' to catch a duplicate Lead ID."},
    "lead_id_calls_24h": {"label": "Calls with the same Lead ID in the last 24 hours", "type": "number",
                          "stages": ["intake", "results"], "group": "Compared with the database"},
    "recording_calls": {"label": "Earlier calls with the same recording link", "type": "number", "stages": ["intake", "results"],
                        "group": "Compared with the database", "help": "The same recording dropped again under a different call date."},
    "agent_calls_24h": {"label": "Calls by this sales agent in the last 24 hours", "type": "number",
                        "stages": ["intake", "results"], "group": "Compared with the database"},
    # Only known once the call is scored
    "lead_band": {"label": "Lead band (0 to 5)", "type": "number", "stages": ["results"], "group": "Results"},
    "audit_score_percent": {"label": "Audit score (%)", "type": "number", "stages": ["results"], "group": "Results"},
    "audit_lowest_check": {"label": "Lowest audit check score (1 to 5)", "type": "number", "stages": ["results"], "group": "Results"},
}

DB_FIELDS = {"lead_id_calls", "lead_id_calls_24h", "recording_calls", "agent_calls_24h"}


def field_catalog() -> dict:
    """What the policy builder offers."""
    return {
        "stages": [
            {"value": "intake", "label": "At intake (before a call is saved)"},
            {"value": "results", "label": "After results (lead score and audit are in)"},
        ],
        "actions": [
            {"value": "flag", "label": "Flag for review"},
            {"value": "reject", "label": "Reject the request (intake only)"},
        ],
        "match_modes": [{"value": "all", "label": "All conditions"}, {"value": "any", "label": "Any condition"}],
        "fields": [{"key": k, **v, "operators": operators_for(v["type"])} for k, v in FIELDS.items()],
    }


def operators_for(field_type: str) -> list[dict]:
    ops = TEXT_OPS if field_type == "text" else NUMBER_OPS
    return [{"value": k, "label": v, "needs_value": k not in NO_VALUE_OPS} for k, v in ops.items()]


# --------------------------------------------------------------------------- validation


class PolicyInvalid(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))


def _err(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def _clean_value(field_type: str, operator: str, raw: Any, path: str, errors: list) -> Any:
    if operator in NO_VALUE_OPS:
        return None
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        errors.append(_err(path, "needs a value"))
        return None
    if field_type == "number":
        if isinstance(raw, bool):
            errors.append(_err(path, "must be a number"))
            return None
        try:
            return float(raw) if not isinstance(raw, (int, float)) else raw
        except (TypeError, ValueError):
            errors.append(_err(path, "must be a number"))
            return None
    text = str(raw).strip()
    if len(text) > MAX_VALUE_LEN:
        errors.append(_err(path, f"must be at most {MAX_VALUE_LEN} characters"))
        return None
    if operator in ("in_list", "not_in_list"):
        items = [i.strip() for i in text.split(",") if i.strip()]
        if not items:
            errors.append(_err(path, "needs at least one item"))
            return None
        if len(items) > MAX_LIST_ITEMS:
            errors.append(_err(path, f"must have at most {MAX_LIST_ITEMS} items"))
            return None
        return ", ".join(items)
    return text


def validate_policy(payload: Any) -> dict:
    """Clean a policy from the API. Raises PolicyInvalid with field-level errors."""
    if not isinstance(payload, dict):
        raise PolicyInvalid([_err("payload", "must be a JSON object")])
    errors: list[dict] = []

    name = str(payload.get("name") or "").strip()
    if len(name) < 3:
        errors.append(_err("name", "must be at least 3 characters"))
    elif len(name) > 120:
        errors.append(_err("name", "must be at most 120 characters"))

    description = str(payload.get("description") or "").strip()
    if len(description) > 500:
        errors.append(_err("description", "must be at most 500 characters"))
    message = str(payload.get("message") or "").strip()
    if len(message) > 255:
        errors.append(_err("message", "must be at most 255 characters"))

    stage = payload.get("stage")
    if stage not in STAGES:
        errors.append(_err("stage", f"must be one of: {', '.join(STAGES)}"))
    action = payload.get("action", "flag")
    if action not in ACTIONS:
        errors.append(_err("action", f"must be one of: {', '.join(ACTIONS)}"))
    elif action == "reject" and stage == "results":
        errors.append(_err("action", "a policy that runs after results can only flag a call, not reject it"))
    match_mode = payload.get("match_mode", "all")
    if match_mode not in MATCH_MODES:
        errors.append(_err("match_mode", f"must be one of: {', '.join(MATCH_MODES)}"))

    raw_conditions = payload.get("conditions")
    conditions: list[dict] = []
    if not isinstance(raw_conditions, list) or not raw_conditions:
        errors.append(_err("conditions", "add at least one condition"))
    elif len(raw_conditions) > MAX_CONDITIONS:
        errors.append(_err("conditions", f"at most {MAX_CONDITIONS} conditions"))
    else:
        for i, c in enumerate(raw_conditions):
            path = f"conditions[{i}]"
            if not isinstance(c, dict):
                errors.append(_err(path, "must be an object"))
                continue
            field = c.get("field")
            spec = FIELDS.get(field)
            if spec is None:
                errors.append(_err(f"{path}.field", "is not a known field"))
                continue
            if stage in STAGES and stage not in spec["stages"]:
                errors.append(_err(f"{path}.field", f"'{spec['label']}' is only known after results, not at intake"))
                continue
            operator = c.get("operator")
            allowed = TEXT_OPS if spec["type"] == "text" else NUMBER_OPS
            if operator not in allowed:
                errors.append(_err(f"{path}.operator", f"is not valid for '{spec['label']}'"))
                continue
            value = _clean_value(spec["type"], operator, c.get("value"), f"{path}.value", errors)
            conditions.append({"field": field, "operator": operator, "value": value})

    if errors:
        raise PolicyInvalid(errors)
    return {
        "name": name,
        "description": description or None,
        "message": message or None,
        "stage": stage,
        "action": action,
        "match_mode": match_mode,
        "conditions": conditions,
        "enabled": bool(payload.get("enabled", True)),
    }


# --------------------------------------------------------------------------- evaluation


def matches_format(value: str, mask: str) -> bool:
    """# digit, A letter, * anything (any length), everything else literal. Case-insensitive."""
    pattern = "".join(
        r"\d" if ch == "#" else "[A-Za-z]" if ch == "A" else ".*" if ch == "*" else re.escape(ch) for ch in mask
    )
    return re.fullmatch(pattern, value, flags=re.IGNORECASE) is not None


def _as_text(v: Any) -> str:
    return "" if v is None else str(v).strip()


def compare(operator: str, actual: Any, expected: Any, field_type: str) -> bool:
    """One condition. A missing value never satisfies a comparison, only 'is empty' and the negative operators."""
    if operator == "is_empty":
        return actual is None or _as_text(actual) == ""
    if operator == "is_not_empty":
        return not (actual is None or _as_text(actual) == "")

    if field_type == "number":
        if actual is None:
            return operator == "not_equals"
        a, e = float(actual), float(expected)
        return {"equals": a == e, "not_equals": a != e, "gt": a > e, "gte": a >= e, "lt": a < e, "lte": a <= e}[operator]

    a, e = _as_text(actual).lower(), _as_text(expected).lower()
    if operator == "equals":
        return a == e
    if operator == "not_equals":
        return a != e
    if operator == "contains":
        return e in a
    if operator == "not_contains":
        return e not in a
    if operator == "starts_with":
        return a.startswith(e)
    if operator == "ends_with":
        return a.endswith(e)
    items = [i.strip().lower() for i in e.split(",") if i.strip()]
    if operator == "in_list":
        return a in items
    if operator == "not_in_list":
        return a not in items
    if operator == "matches_format":
        return matches_format(_as_text(actual), _as_text(expected))
    if operator == "not_matches_format":
        return not matches_format(_as_text(actual), _as_text(expected))
    return False


def describe_condition(c: dict) -> str:
    spec = FIELDS.get(c["field"], {"label": c["field"], "type": "text"})
    ops = TEXT_OPS if spec["type"] == "text" else NUMBER_OPS
    text = f"{spec['label']} {ops.get(c['operator'], c['operator'])}"
    if c["operator"] not in NO_VALUE_OPS:
        v = c.get("value")
        text += f" {int(v) if isinstance(v, float) and v.is_integer() else v}"
    return text


def default_message(policy: dict) -> str:
    return policy.get("message") or f"{policy['name']}: " + (
        " and " if policy.get("match_mode", "all") == "all" else " or "
    ).join(describe_condition(c) for c in policy["conditions"])


class Facts:
    """The values a policy can look at. Database lookups happen only if a policy asks for them."""

    def __init__(self, db: Session, base: dict, before_id: int | None = None):
        """before_id: when judging a call that is already saved, only calls saved before it count as "earlier"."""
        self.db = db
        self.base = base
        self.before_id = before_id
        self._cache: dict[str, Any] = {}

    def get(self, field: str) -> Any:
        if field in self.base:
            return self.base[field]
        if field not in self._cache:
            self._cache[field] = self._lookup(field)
        return self._cache[field]

    def _calls(self):
        q = self.db.query(func.count(Call.id))
        if self.before_id is not None:
            q = q.filter(Call.id < self.before_id)
        return q

    def _lookup(self, field: str) -> Any:
        since = utcnow() - timedelta(hours=24)
        lead, agent, url = self.base.get("lead_id"), self.base.get("agent_id"), self.base.get("recording_url")
        if field == "lead_id_calls":
            return self._calls().filter(func.lower(Call.lead_id) == _as_text(lead).lower()).scalar() or 0 if lead else 0
        if field == "lead_id_calls_24h":
            return (
                self._calls().filter(func.lower(Call.lead_id) == _as_text(lead).lower(), Call.created_at >= since).scalar() or 0
                if lead else 0
            )
        if field == "recording_calls":
            if not url:
                return 0
            variants = {url, normalize_recording_url(url)}
            return self._calls().filter(Call.recording_url.in_(variants)).scalar() or 0
        if field == "agent_calls_24h":
            return self._calls().filter(Call.agent_id == agent, Call.created_at >= since).scalar() or 0 if agent else 0
        return None


def policy_matches(policy: dict, facts: Facts) -> bool:
    results = []
    for c in policy["conditions"]:
        spec = FIELDS[c["field"]]
        results.append(compare(c["operator"], facts.get(c["field"]), c.get("value"), spec["type"]))
    return all(results) if policy.get("match_mode", "all") == "all" else any(results)


def policy_dict(p: CommandPolicy) -> dict:
    return {
        "id": p.id, "name": p.name, "stage": p.stage, "action": p.action, "match_mode": p.match_mode,
        "conditions": list(p.conditions or []), "message": p.message,
    }


# --------------------------------------------------------------------------- facts from a call


def _domain(url: str | None) -> str | None:
    host = urlsplit(url or "").hostname
    return host.lower() if host else None


def _age_days(call_date: datetime | None) -> float | None:
    if call_date is None:
        return None
    if call_date.tzinfo is None:
        call_date = call_date.replace(tzinfo=timezone.utc)
    return float((utcnow().date() - call_date.astimezone(timezone.utc).date()).days)


def intake_facts(data: dict) -> dict:
    return {
        "recording_url": data.get("recording_url"),
        "recording_domain": _domain(data.get("recording_url")),
        "agent_id": data.get("agent_id"),
        "agent_name": data.get("agent_name"),
        "lead_id": data.get("lead_id"),
        "customer_name": data.get("customer_name"),
        "call_age_days": _age_days(data.get("call_date")),
    }


def call_facts(call: Call) -> dict:
    base = intake_facts({
        "recording_url": call.recording_url, "agent_id": call.agent_id, "agent_name": call.agent_name,
        "lead_id": call.lead_id, "customer_name": call.customer_name, "call_date": call.call_date,
    })
    base["lead_band"] = call.lead_score.band if call.lead_score else None
    base["audit_score_percent"] = call.call_audit.score_percent if call.call_audit else None
    scores = []
    for ch in (call.call_audit.checks if call.call_audit else None) or []:
        try:
            scores.append(float(ch["score"]))
        except (KeyError, TypeError, ValueError):
            pass
    base["audit_lowest_check"] = min(scores) if scores else None
    return base


# --------------------------------------------------------------------------- running policies


def _enabled(db: Session, stage: str) -> list[CommandPolicy]:
    return (
        db.query(CommandPolicy)
        .filter(CommandPolicy.enabled.is_(True), CommandPolicy.stage == stage)
        .order_by(CommandPolicy.id)
        .all()
    )


def run_intake_policies(db: Session, data: dict) -> list[dict]:
    """
    Policies that match a call about to be saved. Returns one hit per policy:
    {"policy_id", "policy_name", "action", "message"}. A broken policy never blocks intake.
    """
    hits = []
    facts = Facts(db, intake_facts(data))
    for p in _enabled(db, "intake"):
        try:
            pd = policy_dict(p)
            if policy_matches(pd, facts):
                hits.append({"policy_id": p.id, "policy_name": p.name, "action": p.action, "message": default_message(pd)})
        except Exception:
            log.exception("Policy %s could not be evaluated; skipped", p.id)
    return hits


def count_hits(db: Session, hits: list[dict]) -> None:
    for h in hits:
        db.query(CommandPolicy).filter(CommandPolicy.id == h["policy_id"]).update(
            {"hit_count": CommandPolicy.hit_count + 1}
        )


def add_flags(db: Session, task_id: str, hits: list[dict]) -> None:
    """Attach flags to a call (once per policy)."""
    existing = {f.policy_id for f in db.query(CallFlag).filter(CallFlag.task_id == task_id).all()}
    for h in hits:
        if h["policy_id"] in existing:
            continue
        db.add(CallFlag(task_id=task_id, policy_id=h["policy_id"], policy_name=h["policy_name"], message=h["message"][:500]))
    count_hits(db, [h for h in hits if h["policy_id"] not in existing])
    db.commit()


def run_results_policies(db: Session, call: Call) -> list[dict]:
    """Flag a finished call. Called once, when both results are saved."""
    hits = []
    facts = Facts(db, call_facts(call), before_id=call.id)
    for p in _enabled(db, "results"):
        try:
            pd = policy_dict(p)
            if policy_matches(pd, facts):
                hits.append({"policy_id": p.id, "policy_name": p.name, "action": "flag", "message": default_message(pd)})
        except Exception:
            log.exception("Policy %s could not be evaluated; skipped", p.id)
    if hits:
        add_flags(db, call.task_id, hits)
    return hits


def test_policy_on_recent_calls(db: Session, policy: dict, limit: int = 200) -> dict:
    """Dry run: how many of the latest calls would this policy match? Nothing is saved or changed."""
    calls = db.query(Call).order_by(Call.created_at.desc(), Call.id.desc()).limit(limit).all()
    matched = []
    for c in calls:
        facts = Facts(db, call_facts(c), before_id=c.id)
        if policy_matches(policy, facts):
            matched.append({"task_id": c.task_id, "agent_name": c.agent_name, "lead_id": c.lead_id})
    return {"checked": len(calls), "matched": len(matched), "examples": matched[:10]}
