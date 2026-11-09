# app/auto_stub/__init__.py
"""
=============================================================================
TEMPORARY STUB FOR SUPERVITY AUTO.  DELETE THIS WHOLE FOLDER WHEN AUTO IS REAL.
=============================================================================
Stands in for the Orchestrator and the two operators (Lead Score, Call Audit).
After a short delay it posts sample results into the SAME output-webhook logic
(app.services.call_output.process_output) that the real webhook route uses, so
every result passes through the real validation, not around it.

Everything here is fake sample text. No real recordings or transcripts.

Removal checklist: see app/auto_stub/README.md
=============================================================================
"""

from .runner import deliver_handoff, wait_for_idle
from .scenarios import DEFAULT_SCENARIO, SCENARIOS

__all__ = ["deliver_handoff", "wait_for_idle", "SCENARIOS", "DEFAULT_SCENARIO"]
