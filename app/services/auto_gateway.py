# app/services/auto_gateway.py
"""
The single seam between the Command Centre and Supervity Auto.

intake calls hand_off(). Today that goes to a local stub. When the real
Orchestrator is ready, replace the body of hand_off() (and delete the stub block
below). Nothing else in the app knows Auto exists.

Real Auto is NOT connected. AUTO_MODE must be "stub" for any hand-off to
succeed; any other value fails the hand-off with a clear reason.
"""

import ipaddress
import json
import logging
import os
import re
import socket
import threading
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)


class AutoHandoffError(Exception):
    """The hand-off to Auto did not succeed. The message becomes the call's failure_reason."""


@dataclass
class HandOff:
    """What the Orchestrator will need. Never contains a recording or transcript, only the link."""

    task_id: str
    recording_url: str
    agent_id: str
    agent_name: str
    lead_id: str | None
    customer_name: str | None
    call_date: datetime | None


AUTO_BASE_URL_DEFAULT = "https://auto.supervity.ai"
MAX_AUDIO_BYTES = 50 * 1024 * 1024
_OWN_AUDIO = re.compile(r"/api/calls/audio/(?P<name>[0-9a-f]{32}\.[a-z0-9]+)$")


def hand_off(handoff: HandOff, stub_scenario: str | None = None) -> None:
    """Pass a call to Auto. Raise AutoHandoffError if it cannot be handed over."""

    # --- AUTO STUB START (delete this block, app/auto_stub/, and the two helpers below) ---
    if os.getenv("AUTO_MODE", "").lower() == "stub":
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise AutoHandoffError("AUTO_MODE=stub is not allowed in production.")
        from ..auto_stub import deliver_handoff

        deliver_handoff(handoff, stub_scenario)
        return
    # --- AUTO STUB END ---

    if os.getenv("AUTO_MODE", "").lower() == "live":
        if not os.getenv("AUTO_API_KEY") or not os.getenv("AUTO_WORKFLOW_ID"):
            raise AutoHandoffError("AUTO_API_KEY and AUTO_WORKFLOW_ID must be set for AUTO_MODE=live.")
        # The run takes seconds to minutes, so it goes on a background thread and the
        # drop returns at once. The thread records the outcome on the call.
        threading.Thread(target=_run_live, args=(handoff,), daemon=True, name=f"auto-{handoff.task_id}").start()
        return

    raise AutoHandoffError(
        "Auto integration is not connected (set AUTO_MODE to 'live' or 'stub')."
    )


def _extension(url: str) -> str:
    ext = os.path.splitext(urlsplit(url).path)[1].lower()
    return ext if ext in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm", ".mp4"} else ".mp3"


def _check_public_host(url: str) -> None:
    """Refuse links that point inside our own network (the link comes from a user)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise AutoHandoffError("Recording link is not a valid http(s) link.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror:
        raise AutoHandoffError("Recording link host could not be found.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise AutoHandoffError("Recording link points to a private address.")


def _fetch_audio(url: str) -> tuple[bytes, str]:
    """Audio bytes and a file name. Our own uploads are read from storage; other links are downloaded."""
    import asyncio

    m = _OWN_AUDIO.search(urlsplit(url).path)
    if m:
        from ..core.storage import get_storage_instance

        name = m.group("name")
        try:
            data = asyncio.run(get_storage_instance().download(f"calls/audio/{name}"))
        except FileNotFoundError:
            raise AutoHandoffError("Uploaded audio file was not found in storage.")
        return data, name

    _check_public_host(url)
    chunks, size = [], 0
    try:
        with httpx.stream("GET", url, follow_redirects=False, timeout=60) as r:
            if r.status_code != 200:
                raise AutoHandoffError(f"Recording link returned HTTP {r.status_code}.")
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > MAX_AUDIO_BYTES:
                    raise AutoHandoffError("Recording is larger than 50 MB.")
                chunks.append(chunk)
    except httpx.HTTPError as e:
        raise AutoHandoffError(f"Recording could not be downloaded ({type(e).__name__}).")
    return b"".join(chunks), "recording" + _extension(url)


def _stream_workflow(handoff: HandOff, audio: bytes, filename: str) -> dict:
    """POST to Auto and read the event stream until the result. Returns the result payload."""
    base = os.getenv("AUTO_BASE_URL", AUTO_BASE_URL_DEFAULT).rstrip("/")
    headers = {
        "Authorization": f"Bearer {os.environ['AUTO_API_KEY']}",
        "x-source": "external",
        "x-active-org": os.getenv("AUTO_ORG", "Auto_cc_Training"),
        "x-user-timezone": os.getenv("AUTO_TIMEZONE", "Asia/Calcutta"),
    }
    fields = {
        "workflowId": os.environ["AUTO_WORKFLOW_ID"],
        "autoRetryAllowed": "false",  # one call, one run
        "inputs[task_id]": handoff.task_id,
        "inputs[sales_agent_id]": handoff.agent_id,
        "inputs[sales_agent_name]": handoff.agent_name,
    }
    for key, val in (
        ("customer_name", handoff.customer_name),
        ("lead_id", handoff.lead_id),
        ("call_date", handoff.call_date.date().isoformat() if handoff.call_date else None),
    ):
        if val:
            fields[f"inputs[{key}]"] = val

    timeout = httpx.Timeout(connect=15, read=900, write=120, pool=15)
    event, data_lines, result, error = None, [], None, None
    with httpx.stream(
        "POST", f"{base}/workflow/api/v1/workflow-runs/execute/stream",
        headers=headers, data=fields, files={"inputs[audio_file]": (filename, audio)}, timeout=timeout,
    ) as r:
        if r.status_code != 200:
            r.read()
            raise AutoHandoffError(f"Auto returned HTTP {r.status_code}: {r.text[:300]}")
        for line in r.iter_lines():
            if line:
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                continue
            # blank line = end of one event
            if event in ("result", "error") and data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except ValueError:
                    payload = {"raw": "\n".join(data_lines)}
                if event == "result":
                    result = payload
                else:
                    error = payload
                break
            event, data_lines = None, []
    if error is not None:
        raise AutoHandoffError(f"Auto reported an error: {str(error)[:300]}")
    if result is None:
        raise AutoHandoffError("Auto closed the stream without a result.")
    return result


def _run_live(handoff: HandOff) -> None:
    """Background thread: fetch audio, run the workflow, record the outcome on the call."""
    from ..core.database import SessionLocal
    from ..models.call import Call, CallStatus
    from .call_intake import fail_call

    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.task_id == handoff.task_id).first()
        if call is None:
            return
        try:
            audio, filename = _fetch_audio(handoff.recording_url)
            result = _stream_workflow(handoff, audio, filename)
        except AutoHandoffError as e:
            fail_call(db, call.id, f"Hand-off to Auto failed: {e}")
            return
        except Exception as e:
            log.exception("Live hand-off crashed for %s", handoff.task_id)
            fail_call(db, call.id, f"Hand-off to Auto failed: {type(e).__name__}")
            return

        found = _collect(result)
        if found["transcript"]:
            call.transcript = found["transcript"]
        # Keep the final JSON as Auto sent it, so the screen can show it as is.
        raw = found["combined"] if found["combined"] is not None else result
        if len(json.dumps(raw, default=str)) <= 200_000:
            call.auto_output = raw
        db.commit()

        # Feed each sub-workflow's {agent, task_id, result} through the same rules as the
        # output webhook, so there is one set of validation rules and one path to "done".
        from .call_output import OutputRejected, process_output
        from .call_rules import AGENTS

        for agent in AGENTS:
            item = found["outputs"].get(agent)
            if item is None:
                continue
            try:
                process_output(
                    db, {"agent": agent, "task_id": handoff.task_id, "result": item["result"]}
                )
            except OutputRejected as e:
                log.warning("Auto %s result rejected for %s: %s", agent, handoff.task_id, e.code)

        db.expire_all()
        call = db.query(Call).filter(Call.task_id == handoff.task_id).one()
        if call.status in (CallStatus.DONE, CallStatus.FAILED):
            return
        missing = [a for a in AGENTS if getattr(call, a) is None]
        if found["problem"]:
            fail_call(db, call.id, f"Auto could not process the call: {found['problem']}")
        else:
            fail_call(
                db, call.id,
                "Auto finished without a usable " + " or ".join(m.replace("_", " ") for m in missing) + " result.",
            )
    finally:
        db.close()


def _collect(payload) -> dict:
    """
    Walk whatever the stream returned (dicts, lists, JSON inside strings) and pull out the
    transcript, each {agent, task_id, result} output, and any rejection reason.
    """
    from .call_rules import AGENTS

    found = {"transcript": None, "outputs": {}, "problem": None, "combined": None}

    # The combined JSON may name the two results in a few ways; accept them all.
    key_to_agent = {
        "callaudit": "call_audit", "callauditresult": "call_audit", "callauditresults": "call_audit",
        "leadscore": "lead_score", "leadscoreresult": "lead_score", "leadscoreresults": "lead_score",
    }
    looks_valid = {"call_audit": "checks", "lead_score": "band"}

    def as_obj(v):
        if isinstance(v, str) and v.strip()[:1] == "{":
            try:
                return json.loads(v)
            except ValueError:
                return v
        return v

    def walk(o, depth=0):
        if depth > 12:
            return
        if isinstance(o, str):
            s = o.strip()
            if s[:1] in "{[":
                try:
                    walk(json.loads(s), depth + 1)
                except ValueError:
                    pass
            return
        if isinstance(o, list):
            for v in o:
                walk(v, depth + 1)
            return
        if not isinstance(o, dict):
            return
        if o.get("agent") in AGENTS and "result" in o:
            found["outputs"][o["agent"]] = o
        # {"call_audit": {...}, "lead_score": {...}}: each value is either the
        # {agent, task_id, result} block or the bare result.
        hits = {}
        for k, v in o.items():
            agent = key_to_agent.get(re.sub(r"[^a-z]", "", str(k).lower()))
            v = as_obj(v)
            if agent and isinstance(v, dict):
                res = as_obj(v.get("result")) if isinstance(v.get("result"), (dict, str)) else v
                if isinstance(res, dict) and looks_valid[agent] in res:
                    found["outputs"].setdefault(agent, {"agent": agent, "result": res})
                    hits[agent] = True
        if len(hits) == 2 and found["combined"] is None:
            found["combined"] = o
        if isinstance(o.get("transcript"), str) and o["transcript"].strip():
            found["transcript"] = o["transcript"]
        if str(o.get("status", "")).lower() in ("rejected", "skipped", "failed", "error"):
            found["problem"] = found["problem"] or str(
                o.get("rejection_reason") or o.get("reason") or o.get("error") or o.get("status")
            )[:300]
        # "partial" means one operator failed; the workflow lists why in "errors".
        if str(o.get("status", "")).lower() == "partial" and o.get("errors"):
            found["problem"] = found["problem"] or "; ".join(str(e) for e in o["errors"])[:300]
        for v in o.values():
            walk(v, depth + 1)

    walk(payload)
    return found


# --- AUTO STUB START: test-mode helpers used by the drop-call route ---------------
def test_mode_enabled() -> bool:
    """Scenario picking is allowed only in test mode, with the stub on, outside production."""
    return (
        os.getenv("TEST_MODE", "false").lower() == "true"
        and os.getenv("AUTO_MODE", "").lower() == "stub"
        and os.getenv("APP_ENV", "development").lower() != "production"
    )


def stub_scenarios() -> list[dict]:
    if not test_mode_enabled():
        return []
    from ..auto_stub import SCENARIOS

    return [{"value": k, "label": v} for k, v in SCENARIOS.items()]


# --- AUTO STUB END ---
