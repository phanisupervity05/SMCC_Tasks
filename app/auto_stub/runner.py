# app/auto_stub/runner.py
"""Delivers the stub's fake results after a short delay, through the real output logic."""

import logging
import os
import threading

from ..core.database import SessionLocal
from ..services.auto_gateway import AutoHandoffError, HandOff
from ..services.call_output import OutputRejected, process_output
from .scenarios import DEFAULT_SCENARIO, SCENARIOS, build_events

log = logging.getLogger(__name__)

STUB_ENDPOINT = "/api/webhooks/output [stub]"

_threads: list[threading.Thread] = []
_lock = threading.Lock()


def _delay() -> float:
    try:
        return max(0.0, float(os.getenv("AUTO_STUB_DELAY_SECONDS", "3")))
    except ValueError:
        return 3.0


def _deliver(events: list[dict], delay: float, gap: float) -> None:
    import time

    for i, payload in enumerate(events):
        time.sleep(delay if i == 0 else gap)
        db = SessionLocal()
        try:
            # Same function the real /api/webhooks/output route calls.
            process_output(db, payload, endpoint=STUB_ENDPOINT)
        except OutputRejected:
            pass  # already logged to rejected_requests by process_output
        except Exception:
            log.exception("Stub delivery failed unexpectedly")
        finally:
            db.close()


def deliver_handoff(handoff: HandOff, scenario: str | None) -> None:
    scenario = scenario or DEFAULT_SCENARIO
    if scenario not in SCENARIOS:
        raise AutoHandoffError(f"Unknown stub scenario '{scenario}'.")
    events = build_events(scenario, handoff.task_id)  # may raise AutoHandoffError
    t = threading.Thread(
        target=_deliver, args=(events, _delay(), 1.0 if _delay() else 0.0), daemon=True
    )
    with _lock:
        _threads.append(t)
    t.start()


def wait_for_idle(timeout: float = 15.0) -> None:
    """Block until every pending stub delivery has finished (used by tests)."""
    with _lock:
        pending = list(_threads)
    for t in pending:
        t.join(timeout)
    with _lock:
        _threads[:] = [t for t in _threads if t.is_alive()]
