# tests/test_policy_engine.py
"""The Command Center policy engine: validation, operators, database comparisons."""

from datetime import timedelta

import pytest

from app.models.call import Call, utcnow
from app.services.policy_engine import (
    Facts, PolicyInvalid, compare, default_message, field_catalog, matches_format, policy_matches, validate_policy,
)


def good(**over):
    p = {
        "name": "Duplicate Lead ID", "stage": "intake", "action": "flag", "match_mode": "all",
        "conditions": [{"field": "lead_id_calls", "operator": "gte", "value": 1}],
    }
    p.update(over)
    return p


# ---- validation -------------------------------------------------------------
def test_a_good_policy_is_cleaned():
    p = validate_policy(good(name="  Duplicate Lead ID  ", description=" x "))
    assert p["name"] == "Duplicate Lead ID" and p["description"] == "x" and p["enabled"] is True
    assert p["conditions"] == [{"field": "lead_id_calls", "operator": "gte", "value": 1.0}]


@pytest.mark.parametrize("bad, field", [
    ({"name": "ab"}, "name"),
    ({"stage": "later"}, "stage"),
    ({"action": "delete"}, "action"),
    ({"match_mode": "some"}, "match_mode"),
    ({"conditions": []}, "conditions"),
    ({"conditions": "x"}, "conditions"),
    ({"conditions": [{"field": "nope", "operator": "equals", "value": "x"}]}, "conditions[0].field"),
    ({"conditions": [{"field": "lead_id", "operator": "gt", "value": "1"}]}, "conditions[0].operator"),
    ({"conditions": [{"field": "lead_id", "operator": "equals"}]}, "conditions[0].value"),
    ({"conditions": [{"field": "lead_id_calls", "operator": "gte", "value": "many"}]}, "conditions[0].value"),
    ({"conditions": [{"field": "lead_id", "operator": "equals", "value": "x" * 201}]}, "conditions[0].value"),
    ({"conditions": [{"field": "lead_band", "operator": "gte", "value": 4}]}, "conditions[0].field"),  # results-only field at intake
    ({"stage": "results", "action": "reject", "conditions": [{"field": "lead_band", "operator": "gte", "value": 4}]}, "action"),
    ({"conditions": [{"field": "lead_id", "operator": "equals", "value": "a"}] * 11}, "conditions"),
])
def test_bad_policies_name_the_field_at_fault(bad, field):
    with pytest.raises(PolicyInvalid) as e:
        validate_policy(good(**bad))
    assert field in {x["field"] for x in e.value.errors}


def test_all_errors_are_reported_together():
    with pytest.raises(PolicyInvalid) as e:
        validate_policy({"name": "x", "stage": "z", "conditions": []})
    assert {"name", "stage", "conditions"} <= {x["field"] for x in e.value.errors}


def test_non_object_payload_is_refused():
    with pytest.raises(PolicyInvalid):
        validate_policy(["not", "an", "object"])


def test_catalog_lists_fields_with_their_operators():
    cat = field_catalog()
    keys = {f["key"] for f in cat["fields"]}
    assert {"lead_id", "recording_domain", "lead_id_calls", "lead_band", "audit_score_percent"} <= keys
    text = next(f for f in cat["fields"] if f["key"] == "lead_id")
    assert "matches_format" in {o["value"] for o in text["operators"]}
    num = next(f for f in cat["fields"] if f["key"] == "lead_band")
    assert "gte" in {o["value"] for o in num["operators"]} and "contains" not in {o["value"] for o in num["operators"]}


# ---- operators --------------------------------------------------------------
@pytest.mark.parametrize("mask, value, expected", [
    ("LEAD-####", "LEAD-1234", True), ("LEAD-####", "lead-1234", True), ("LEAD-####", "LEAD-12", False),
    ("LEAD-####", "LEAD-12345", False), ("AA-##", "ab-12", True), ("*@example.com", "x@example.com", True),
    ("a.b", "a.b", True), ("a.b", "axb", False),  # a dot is literal, not "any character"
])
def test_format_masks(mask, value, expected):
    assert matches_format(value, mask) is expected


@pytest.mark.parametrize("op, actual, expected, result", [
    ("equals", "Asha", "asha", True), ("not_equals", "Asha", "ben", True), ("contains", "recordings.acme.com", "acme", True),
    ("not_contains", "x", "y", True), ("starts_with", "LEAD-1", "lead", True), ("ends_with", "a.mp3", ".mp3", True),
    ("in_list", "b", "a, b, c", True), ("in_list", "z", "a, b, c", False), ("not_in_list", "z", "a, b, c", True),
    ("matches_format", "LEAD-1234", "LEAD-####", True), ("not_matches_format", "X-1", "LEAD-####", True),
    ("is_empty", None, None, True), ("is_empty", "  ", None, True), ("is_not_empty", "x", None, True),
    ("contains", None, "x", False), ("equals", None, "x", False),
])
def test_text_operators(op, actual, expected, result):
    assert compare(op, actual, expected, "text") is result


@pytest.mark.parametrize("op, actual, expected, result", [
    ("gt", 5, 4, True), ("gt", 4, 4, False), ("gte", 4, 4, True), ("lt", 3, 4, True), ("lte", 4, 4, True),
    ("equals", 4.0, 4, True), ("not_equals", 3, 4, True),
    ("gt", None, 1, False), ("lt", None, 1, False), ("is_empty", None, None, True), ("not_equals", None, 1, True),
])
def test_number_operators(op, actual, expected, result):
    assert compare(op, actual, expected, "number") is result


def test_all_versus_any():
    p = {"match_mode": "all", "conditions": [
        {"field": "agent_id", "operator": "equals", "value": "A-1"},
        {"field": "lead_id", "operator": "starts_with", "value": "L-"},
    ]}
    f = Facts(None, {"agent_id": "A-1", "lead_id": "X-9"})
    assert policy_matches(p, f) is False
    assert policy_matches({**p, "match_mode": "any"}, f) is True


def test_default_message_describes_the_conditions():
    p = validate_policy(good(match_mode="any", conditions=[
        {"field": "lead_id_calls", "operator": "gte", "value": 1},
        {"field": "recording_domain", "operator": "not_in_list", "value": "a.com, b.com"},
    ]))
    msg = default_message(p)
    assert msg.startswith("Duplicate Lead ID:") and "at least 1" in msg and " or " in msg
    assert default_message({**p, "message": "Looks like a duplicate"}) == "Looks like a duplicate"


# ---- database comparisons ---------------------------------------------------
def test_duplicate_lookups_use_the_database(db):
    old = utcnow() - timedelta(days=3)
    db.add_all([
        Call(task_id="c1", agent_id="A-1", agent_name="X", lead_id="LEAD-1", recording_url="https://r.example.com/a.mp3", status="done", created_at=old),
        Call(task_id="c2", agent_id="A-1", agent_name="X", lead_id="lead-1", recording_url="https://r.example.com/b.mp3", status="done"),
        Call(task_id="c3", agent_id="A-2", agent_name="Y", lead_id="LEAD-2", recording_url="https://r.example.com/a.mp3", status="done"),
    ])
    db.commit()
    f = Facts(db, {"lead_id": "LEAD-1", "agent_id": "A-1", "recording_url": "https://R.example.com/a.mp3"})
    assert f.get("lead_id_calls") == 2  # case-insensitive
    assert f.get("lead_id_calls_24h") == 1  # c1 is 3 days old
    assert f.get("recording_calls") == 2  # the host's case does not matter
    assert f.get("agent_calls_24h") == 1
    # For a call already saved, only calls saved before it count as "earlier" (never itself, never later ones).
    c1, c2 = (db.query(Call).filter(Call.task_id == t).one().id for t in ("c1", "c2"))
    base = {"lead_id": "LEAD-1", "agent_id": "A-1", "recording_url": "x"}
    assert Facts(db, base, before_id=c1).get("lead_id_calls") == 0
    assert Facts(db, base, before_id=c2).get("lead_id_calls") == 1
    # Nothing to compare: zero, never an error.
    assert Facts(db, {}).get("lead_id_calls") == 0 and Facts(db, {}).get("recording_calls") == 0
