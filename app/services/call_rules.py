# app/services/call_rules.py
"""
Business rules for the call lead-score / call-audit flow.

Everything here is a pure function (no database, no HTTP), so the rules can be
read and tested on their own. Screens never repeat any of this.
"""

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# --- Constants -------------------------------------------------------------

AGENT_LEAD_SCORE = "lead_score"
AGENT_CALL_AUDIT = "call_audit"
AGENTS = (AGENT_LEAD_SCORE, AGENT_CALL_AUDIT)

BAND_MIN, BAND_MAX = 0, 5
CHECK_SCORE_MIN, CHECK_SCORE_MAX = 1, 5

MAX_SHORT_TEXT = 255
MAX_URL = 2048


class RuleError(Exception):
    """One or more rule violations. `errors` is a list of {field, message}."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))

    def summary(self) -> str:
        return "; ".join(f"{e['field']}: {e['message']}" for e in self.errors)


def _err(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def _short(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 40 else text[:40] + "..."


# --- Intake ------------------------------------------------------------------


def _clean_text(value: Any, field: str, errors: list, *, required: bool) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            errors.append(_err(field, "is required"))
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        errors.append(_err(field, "must be text"))
        return None
    text = str(value).strip()
    if len(text) > MAX_SHORT_TEXT:
        errors.append(_err(field, f"must be at most {MAX_SHORT_TEXT} characters"))
        return None
    return text


def parse_call_date(value: Any) -> datetime | None:
    """Accepts YYYY-MM-DD or an ISO 8601 datetime. Returns UTC. Raises ValueError."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise ValueError("must be a date or ISO 8601 datetime string")
    text = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            d = date.fromisoformat(text)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("must be a date (YYYY-MM-DD) or ISO 8601 datetime")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_recording_url(url: str) -> str:
    """Trim, and lowercase the scheme and host (the rest of a URL is case-sensitive)."""
    parts = urlsplit(url.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, parts.fragment)
    )


def generate_task_id(recording_url: str, call_date: datetime | None) -> str:
    """
    TaskId = hash(recording link + call date). The same call dropped twice gives
    the same TaskId, so the backend can tell it is a repeat.
    """
    date_part = call_date.astimezone(timezone.utc).isoformat() if call_date else ""
    digest = hashlib.sha256(
        f"{normalize_recording_url(recording_url)}|{date_part}".encode("utf-8")
    ).hexdigest()
    return f"call_{digest[:24]}"


def validate_intake_payload(payload: Any) -> dict:
    """
    Returns clean fields {recording_url, agent_id, agent_name, lead_id,
    customer_name, call_date (datetime|None)} or raises RuleError.
    Unknown fields are ignored (never stored).
    """
    if not isinstance(payload, dict):
        raise RuleError([_err("payload", "must be a JSON object")])

    errors: list[dict] = []

    url_raw = payload.get("recording_url")
    recording_url = None
    if url_raw is None or (isinstance(url_raw, str) and not url_raw.strip()):
        errors.append(_err("recording_url", "is required"))
    elif not isinstance(url_raw, str):
        errors.append(_err("recording_url", "must be a link"))
    else:
        candidate = url_raw.strip()
        parts = urlsplit(candidate)
        if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
            errors.append(_err("recording_url", "must be a valid http(s) link"))
        elif len(candidate) > MAX_URL:
            errors.append(_err("recording_url", f"must be at most {MAX_URL} characters"))
        else:
            recording_url = candidate

    agent_id = _clean_text(payload.get("agent_id"), "agent_id", errors, required=True)
    agent_name = _clean_text(payload.get("agent_name"), "agent_name", errors, required=True)
    lead_id = _clean_text(payload.get("lead_id"), "lead_id", errors, required=False)
    customer_name = _clean_text(
        payload.get("customer_name"), "customer_name", errors, required=False
    )

    call_date = None
    try:
        call_date = parse_call_date(payload.get("call_date"))
    except ValueError as e:
        errors.append(_err("call_date", str(e)))

    if errors:
        raise RuleError(errors)

    return {
        "recording_url": recording_url,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "lead_id": lead_id,
        "customer_name": customer_name,
        "call_date": call_date,
    }


# --- Output webhook: result validation ---------------------------------------


def _is_whole_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and value.is_integer()


def _clean_evidence(value: Any, field: str, errors: list) -> list[str]:
    """Evidence is a list of quote strings. A single string is accepted as a list of one."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(_err(field, "must be a list of text quotes"))
        return []
    return [v.strip() for v in value if v.strip()]


def validate_lead_score(result: Any) -> dict:
    """band: whole number 0..5. reason: required. Returns normalized result or raises RuleError."""
    if not isinstance(result, dict):
        raise RuleError([_err("result", "must be a JSON object")])
    errors: list[dict] = []

    band = result.get("band")
    if not _is_whole_number(band) or not (BAND_MIN <= int(band) <= BAND_MAX):
        errors.append(
            _err("band", f"must be a whole number from {BAND_MIN} to {BAND_MAX} (got {_short(band)})")
        )

    reason = result.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(_err("reason", "is required"))

    label = result.get("label")
    if label is not None and not isinstance(label, str):
        errors.append(_err("label", "must be text"))

    evidence = _clean_evidence(result.get("evidence"), "evidence", errors)

    if errors:
        raise RuleError(errors)
    return {
        "band": int(band),
        "label": label.strip() if isinstance(label, str) and label.strip() else None,
        "reason": reason.strip(),
        "evidence": evidence,
    }


def compute_score_percent(scores: list[int]) -> float:
    """sum of scores / (5 x number of checks) x 100. Any percentage sent by Auto is ignored."""
    return round(sum(scores) / (CHECK_SCORE_MAX * len(scores)) * 100, 2)


def validate_call_audit(result: Any) -> dict:
    """Each check score must be a whole number 1..5. Recalculates score_percent."""
    if not isinstance(result, dict):
        raise RuleError([_err("result", "must be a JSON object")])
    errors: list[dict] = []

    raw_checks = result.get("checks")
    checks: list[dict] = []
    if not isinstance(raw_checks, list) or not raw_checks:
        errors.append(_err("checks", "must be a non-empty list"))
    else:
        for i, c in enumerate(raw_checks):
            where = f"checks[{i}]"
            if not isinstance(c, dict):
                errors.append(_err(where, "must be an object"))
                continue
            name = c.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(_err(f"{where}.name", "is required"))
            score = c.get("score")
            if not _is_whole_number(score) or not (
                CHECK_SCORE_MIN <= int(score) <= CHECK_SCORE_MAX
            ):
                errors.append(
                    _err(
                        f"{where}.score",
                        f"must be a whole number from {CHECK_SCORE_MIN} to {CHECK_SCORE_MAX} (got {_short(score)})",
                    )
                )
            evidence = _clean_evidence(c.get("evidence"), f"{where}.evidence", errors)
            if (
                isinstance(name, str)
                and name.strip()
                and _is_whole_number(score)
                and CHECK_SCORE_MIN <= int(score) <= CHECK_SCORE_MAX
            ):
                checks.append({"name": name.strip(), "score": int(score), "evidence": evidence})

    summary = result.get("summary")
    if summary is not None and not isinstance(summary, str):
        errors.append(_err("summary", "must be text"))

    if errors:
        raise RuleError(errors)
    return {
        "checks": checks,
        "score_percent": compute_score_percent([c["score"] for c in checks]),
        "summary": summary.strip() if isinstance(summary, str) and summary.strip() else None,
    }


VALIDATORS = {AGENT_LEAD_SCORE: validate_lead_score, AGENT_CALL_AUDIT: validate_call_audit}


# --- Safe copy of a payload for rejected_requests ------------------------------

_SENSITIVE_KEY = re.compile(
    r"(token|secret|password|passwd|authorization|api[_-]?key|apikey|credential|cookie|signature|^sig$|private)",
    re.I,
)
_URL_LIKE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
_MAX_STR, _MAX_LIST, _MAX_DEPTH = 500, 50, 6


def _scrub_url(value: str) -> str:
    """Blank sensitive query parameters (e.g. signed-link tokens) in a URL."""
    try:
        parts = urlsplit(value)
        if not parts.query:
            return value
        pairs = [
            (k, "***" if _SENSITIVE_KEY.search(k) or k.lower().startswith("x-amz-") else v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))
    except Exception:
        return value


def safe_payload_copy(payload: Any, _depth: int = 0) -> Any:
    """A copy that is safe to store: secrets masked, signed-link params blanked, size capped."""
    if _depth > _MAX_DEPTH:
        return "[truncated]"
    if isinstance(payload, dict):
        out = {}
        for k, v in list(payload.items())[:_MAX_LIST]:
            key = str(k)[:100]
            out[key] = "***MASKED***" if _SENSITIVE_KEY.search(key) else safe_payload_copy(v, _depth + 1)
        return out
    if isinstance(payload, list):
        return [safe_payload_copy(v, _depth + 1) for v in payload[:_MAX_LIST]]
    if isinstance(payload, str):
        text = _scrub_url(payload) if _URL_LIKE.match(payload) else payload
        return text if len(text) <= _MAX_STR else text[:_MAX_STR] + "...[truncated]"
    if isinstance(payload, (int, float, bool)) or payload is None:
        return payload
    return str(payload)[:_MAX_STR]
