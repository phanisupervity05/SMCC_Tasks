# app/services/policy_templates.py
"""Ready-made starting points for the policy builder. They are never created automatically."""

TEMPLATES = [
    {
        "id": "duplicate_lead_id",
        "title": "Duplicate Lead ID",
        "summary": "Flag a call whose Lead ID was already used on an earlier call.",
        "policy": {
            "name": "Duplicate Lead ID", "description": "The same Lead ID was already used on an earlier call.",
            "stage": "intake", "action": "flag", "match_mode": "all", "message": "This Lead ID was already used on an earlier call.",
            "conditions": [{"field": "lead_id_calls", "operator": "gte", "value": 1}],
        },
    },
    {
        "id": "recording_reused",
        "title": "Same recording dropped again",
        "summary": "Flag a recording that was already dropped under a different call date.",
        "policy": {
            "name": "Recording already used", "description": "This recording link was already used on an earlier call.",
            "stage": "intake", "action": "flag", "match_mode": "all", "message": "This recording was already dropped under another call date.",
            "conditions": [{"field": "recording_calls", "operator": "gte", "value": 1}],
        },
    },
    {
        "id": "lead_id_format",
        "title": "Lead ID format",
        "summary": "Reject a Lead ID that does not look like LEAD-1234 (edit the format to match yours).",
        "policy": {
            "name": "Lead ID format", "description": "Lead IDs must follow the company format.",
            "stage": "intake", "action": "reject", "match_mode": "all", "message": "Lead ID must look like LEAD-1234.",
            "conditions": [{"field": "lead_id", "operator": "not_matches_format", "value": "LEAD-####"}],
        },
    },
    {
        "id": "future_call_date",
        "title": "Call date in the future",
        "summary": "Reject a call dated after today.",
        "policy": {
            "name": "Call date in the future", "description": "A call cannot have happened in the future.",
            "stage": "intake", "action": "reject", "match_mode": "all", "message": "The call date is in the future.",
            "conditions": [{"field": "call_age_days", "operator": "lt", "value": 0}],
        },
    },
    {
        "id": "agent_burst",
        "title": "Unusual number of calls from one agent",
        "summary": "Flag a sales agent who has dropped more than 50 calls in 24 hours (change the number to suit).",
        "policy": {
            "name": "Agent call volume", "description": "Possible bulk or repeated upload.",
            "stage": "intake", "action": "flag", "match_mode": "all", "message": "This sales agent has dropped over 50 calls in 24 hours.",
            "conditions": [{"field": "agent_calls_24h", "operator": "gt", "value": 50}],
        },
    },
    {
        "id": "hot_lead",
        "title": "High-intent lead follow-up",
        "summary": "Flag finished calls with a lead band of 4 or 5 so someone follows up.",
        "policy": {
            "name": "High-intent lead", "description": "Band 4 or 5 leads need a quick follow-up.",
            "stage": "results", "action": "flag", "match_mode": "all", "message": "High-intent lead (band 4-5): follow up today.",
            "conditions": [{"field": "lead_band", "operator": "gte", "value": 4}],
        },
    },
    {
        "id": "low_audit",
        "title": "Low audit score",
        "summary": "Flag finished calls where the agent scored below 60% or any check was 2 or lower.",
        "policy": {
            "name": "Low audit score", "description": "The agent's call quality needs a review.",
            "stage": "results", "action": "flag", "match_mode": "any", "message": "Audit score is low: review this call for coaching.",
            "conditions": [
                {"field": "audit_score_percent", "operator": "lt", "value": 60},
                {"field": "audit_lowest_check", "operator": "lte", "value": 2},
            ],
        },
    },
]
