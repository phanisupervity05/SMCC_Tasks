# tests/test_policies_flow.py
"""Command Center policies enforced on real calls: intake rejects and flags, results flags."""

from app.models.call import CallFlag, CommandPolicy, RejectedRequest


def add_policy(db, **over):
    p = {
        "name": "P", "stage": "intake", "action": "flag", "match_mode": "all", "enabled": True,
        "conditions": [{"field": "lead_id_calls", "operator": "gte", "value": 1}],
    }
    p.update(over)
    row = CommandPolicy(**p)
    db.add(row)
    db.commit()
    return row


def get_call(client, headers, task_id):
    return client.get(f"/api/calls/{task_id}", headers=headers).json()


# ---- intake: reject ---------------------------------------------------------
def test_reject_policy_blocks_the_call_and_logs_it(client, user_headers, drop, db):
    row = add_policy(
        db, name="Lead ID format", action="reject", message="Lead ID must look like LEAD-1234",
        conditions=[{"field": "lead_id", "operator": "not_matches_format", "value": "LEAD-####"}],
    )
    bad = drop("normal", lead_id="X-1")
    assert bad.status_code == 422
    errors = bad.json()["detail"]["errors"]
    assert errors == [{"field": "policy", "message": "Lead ID must look like LEAD-1234"}]
    assert client.get("/api/calls", headers=user_headers).json()["total"] == 0  # never saved
    assert "Blocked by policy: Lead ID format" in [r.reason for r in db.query(RejectedRequest).all()]
    db.refresh(row)
    assert row.hit_count == 1

    ok = drop("normal", lead_id="LEAD-1234", recording_url="https://r.example.com/ok.mp3")
    assert ok.status_code == 201


def test_a_disabled_policy_does_nothing(client, user_headers, drop, db):
    add_policy(db, action="reject", enabled=False, conditions=[{"field": "agent_id", "operator": "is_not_empty", "value": None}])
    assert drop("normal").status_code == 201


def test_a_broken_policy_never_blocks_intake(client, user_headers, drop, db):
    add_policy(db, action="reject", conditions=[{"field": "no_such_field", "operator": "equals", "value": "x"}])
    assert drop("normal").status_code == 201


def test_domain_allowlist(client, user_headers, drop, db):
    add_policy(
        db, name="Allowed recording hosts", action="reject",
        conditions=[{"field": "recording_domain", "operator": "not_in_list", "value": "recordings.example.com, cdn.example.com"}],
    )
    assert drop("normal", recording_url="https://evil.example.org/a.mp3").status_code == 422
    assert drop("normal", recording_url="https://recordings.example.com/a.mp3").status_code == 201


def test_a_repeat_of_the_same_call_is_still_the_same_call(client, user_headers, drop, db):
    first = drop("normal")
    assert first.status_code == 201
    add_policy(db, action="reject", conditions=[{"field": "agent_id", "operator": "is_not_empty", "value": None}])
    again = drop("normal")  # same recording and date: idempotent, policies do not re-judge it
    assert again.status_code == 200 and again.json()["created"] is False


# ---- intake: flag (duplicate checks) ---------------------------------------
def test_duplicate_lead_id_flags_the_second_call(client, user_headers, drop, db):
    add_policy(db, name="Duplicate Lead ID", message="This Lead ID was already used")
    first = drop("normal", lead_id="LEAD-9", recording_url="https://r.example.com/f1.mp3").json()["call"]
    second = drop("normal", lead_id="LEAD-9", recording_url="https://r.example.com/f2.mp3").json()["call"]
    assert get_call(client, user_headers, first["task_id"])["flags"] == []
    flags = get_call(client, user_headers, second["task_id"])["flags"]
    assert flags == [{"policy_id": flags[0]["policy_id"], "policy": "Duplicate Lead ID", "message": "This Lead ID was already used"}]
    # The flagged call still runs normally.
    assert get_call(client, user_headers, second["task_id"])["status"] == "done"

    flagged = client.get("/api/calls?flagged=true", headers=user_headers).json()
    assert flagged["total"] == 1 and flagged["items"][0]["task_id"] == second["task_id"]
    assert client.get("/api/calls/stats", headers=user_headers).json()["flagged"] == 1


def test_csv_export_lists_the_flags_and_can_filter_to_flagged(client, user_headers, drop, db):
    import csv, io

    add_policy(db, name="Duplicate Lead ID")
    drop("normal", lead_id="LEAD-7", recording_url="https://r.example.com/x1.mp3")
    drop("normal", lead_id="LEAD-7", recording_url="https://r.example.com/x2.mp3")
    rows = list(csv.DictReader(io.StringIO(client.get("/api/calls/export.csv", headers=user_headers).text.lstrip("﻿"))))
    assert sorted(r["flags"] for r in rows) == ["", "Duplicate Lead ID"]
    only = list(csv.DictReader(io.StringIO(client.get("/api/calls/export.csv?flagged=true", headers=user_headers).text.lstrip("﻿"))))
    assert [r["flags"] for r in only] == ["Duplicate Lead ID"]


def test_same_recording_under_a_new_date_is_flagged(client, user_headers, drop, db):
    add_policy(db, name="Recording reused", conditions=[{"field": "recording_calls", "operator": "gte", "value": 1}])
    drop("normal", recording_url="https://r.example.com/same.mp3", call_date="2026-11-01")
    second = drop("normal", recording_url="https://r.example.com/same.mp3", call_date="2026-11-02").json()["call"]
    assert [f["policy"] for f in get_call(client, user_headers, second["task_id"])["flags"]] == ["Recording reused"]


def test_future_call_date_and_old_calls(client, user_headers, drop, db):
    add_policy(db, name="Future date", conditions=[{"field": "call_age_days", "operator": "lt", "value": 0}])
    add_policy(db, name="Too old", conditions=[{"field": "call_age_days", "operator": "gt", "value": 30}])
    future = drop("normal", recording_url="https://r.example.com/g1.mp3", call_date="2099-01-01").json()["call"]
    old = drop("normal", recording_url="https://r.example.com/g2.mp3", call_date="2020-01-01").json()["call"]
    fine = drop("normal", recording_url="https://r.example.com/g3.mp3").json()["call"]
    assert [f["policy"] for f in get_call(client, user_headers, future["task_id"])["flags"]] == ["Future date"]
    assert [f["policy"] for f in get_call(client, user_headers, old["task_id"])["flags"]] == ["Too old"]
    assert get_call(client, user_headers, fine["task_id"])["flags"] == []


# ---- results ---------------------------------------------------------------
def test_results_policy_flags_a_finished_call(client, user_headers, drop, db):
    add_policy(
        db, name="Follow up hot lead", stage="results", message="Band 4-5: follow up today",
        conditions=[{"field": "lead_band", "operator": "gte", "value": 4}],
    )
    add_policy(
        db, name="Weak audit", stage="results", conditions=[{"field": "audit_score_percent", "operator": "lt", "value": 10}],
    )
    hot = drop("normal", recording_url="https://r.example.com/h1.mp3").json()["call"]  # band 4
    cold = drop("band_zero", recording_url="https://r.example.com/h2.mp3").json()["call"]
    assert [f["policy"] for f in get_call(client, user_headers, hot["task_id"])["flags"]] == ["Follow up hot lead"]
    assert get_call(client, user_headers, cold["task_id"])["flags"] == []


def test_results_policy_is_not_run_on_a_call_that_failed(client, user_headers, drop, db):
    add_policy(db, stage="results", conditions=[{"field": "lead_band", "operator": "gte", "value": 0}])
    failed = drop("recording_link_fails").json()["call"]
    assert get_call(client, user_headers, failed["task_id"])["flags"] == []


def test_flags_are_removed_with_the_call_by_the_purge(db):
    import asyncio
    from datetime import timedelta

    from app.models.call import Call, utcnow
    from app.services.retention import purge_old_calls

    db.add(Call(task_id="old1", agent_id="A", agent_name="X", lead_id="L", recording_url="https://x.example.com/1.mp3",
                status="done", created_at=utcnow() - timedelta(days=400)))
    db.add(CallFlag(task_id="old1", policy_id=1, policy_name="P", message="m"))
    db.commit()
    asyncio.run(purge_old_calls(db, 180, apply=True))
    assert db.query(Call).count() == 0 and db.query(CallFlag).count() == 0
