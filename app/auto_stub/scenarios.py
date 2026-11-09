# app/auto_stub/scenarios.py
"""Stub scenarios: what the fake Auto sends back. All text is made up."""

from ..services.auto_gateway import AutoHandoffError

DEFAULT_SCENARIO = "normal"

SCENARIOS: dict[str, str] = {
    "normal": "Normal result",
    "band_zero": "Band 0 call",
    "invalid_band": "Invalid band (7)",
    "missing_reason": "Lead score missing reason",
    "duplicate_result": "Duplicate result (same lead score sent twice)",
    "recording_link_fails": "Recording link fails",
}


def _lead(band: int, **over) -> dict:
    result = {
        "band": band,
        "label": {0: "No fit", 4: "Strong fit"}.get(band),
        "reason": (
            "Customer confirmed budget, a decision date this quarter, and asked for a proposal."
            if band >= 4
            else "Customer said there is no project and asked not to be contacted again."
        ),
        "evidence": (
            ["We have budget set aside for this quarter.", "Please send the proposal by Friday."]
            if band >= 4
            else ["We are not planning anything like this.", "Please take us off your list."]
        ),
    }
    result.update(over)
    return result


def _audit() -> dict:
    return {
        "checks": [
            {"name": "Greeting and introduction", "score": 5, "evidence": ["Hi, this is the sales rep from Sample Co."]},
            {"name": "Needs discovery", "score": 4, "evidence": ["What is slowing your team down today?"]},
            {"name": "Product explanation", "score": 3, "evidence": ["It automates the review step."]},
            {"name": "Objection handling", "score": 4, "evidence": ["I understand the concern about timing."]},
            {"name": "Next step agreed", "score": 5, "evidence": ["I will send the proposal tomorrow."]},
        ],
        "summary": "Clear opening and good discovery. Product explanation could be more specific.",
        # Deliberately wrong: the backend must ignore this and recalculate.
        "score_percent": 99,
    }


def build_events(scenario: str, task_id: str) -> list[dict]:
    """Payloads for the output webhook, in the order they will be delivered."""
    if scenario == "recording_link_fails":
        raise AutoHandoffError("Recording link could not be fetched (HTTP 404 from the recording host).")

    def msg(agent: str, result: dict) -> dict:
        return {"agent": agent, "task_id": task_id, "result": result}

    if scenario == "normal":
        return [msg("lead_score", _lead(4)), msg("call_audit", _audit())]
    if scenario == "band_zero":
        return [msg("lead_score", _lead(0)), msg("call_audit", _audit())]
    if scenario == "invalid_band":
        return [msg("call_audit", _audit()), msg("lead_score", _lead(7))]
    if scenario == "missing_reason":
        bad = _lead(4)
        del bad["reason"]
        return [msg("call_audit", _audit()), msg("lead_score", bad)]
    if scenario == "duplicate_result":
        return [msg("lead_score", _lead(4)), msg("lead_score", _lead(4)), msg("call_audit", _audit())]
    raise AutoHandoffError(f"Unknown stub scenario '{scenario}'.")
