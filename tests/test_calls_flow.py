# tests/test_calls_flow.py
"""Call lead-score / call-audit flow, exercised through the Auto stub and the real routes."""

from datetime import timedelta

import pytest

from app.models.call import Call, CallAudit, CallStatus, LeadScore, RejectedRequest, utcnow
from app.services.call_rules import compute_score_percent, generate_task_id, parse_call_date
from tests.conftest import INTAKE_TOKEN, OUTPUT_TOKEN, make_dev_token, post_output


def get_call(client, headers, task_id):
    r = client.get(f"/api/calls/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def rejected(db):
    db.expire_all()
    return db.query(RejectedRequest).order_by(RejectedRequest.id).all()


@pytest.fixture()
def idle_call(client, user_headers, monkeypatch):
    """A call handed to a stub that never answers, so tests can post results by hand."""
    monkeypatch.setattr("app.services.call_intake.auto_gateway.hand_off", lambda *a, **k: None)
    r = client.post(
        "/api/calls",
        json={"recording_url": "https://recordings.example.com/idle.mp3", "agent_id": "A-1", "agent_name": "Idle Agent", "lead_id": "L-1"},
        headers=user_headers,
    )
    assert r.status_code == 201
    return r.json()["call"]["task_id"]


GOOD_LEAD = {"band": 3, "reason": "Asked for pricing.", "evidence": ["How much is it?"]}
GOOD_AUDIT = {"checks": [{"name": "Greeting", "score": 4, "evidence": ["Hello"]}, {"name": "Close", "score": 2, "evidence": []}]}


# ---- 1. Normal call -----------------------------------------------------------
def test_normal_call_runs_through_stub_to_done(client, user_headers, drop, db):
    r = drop("normal")
    assert r.status_code == 201
    assert r.json()["call"]["status"] in ("received", "sent_to_auto", "done")
    c = get_call(client, user_headers, r.json()["call"]["task_id"])
    assert c["status"] == "done"
    assert c["lead_score"]["band"] == 4 and c["lead_score"]["reason"] and c["lead_score"]["evidence"]
    assert len(c["call_audit"]["checks"]) == 5
    assert c["results_received"] == {"lead_score": True, "call_audit": True}
    # The stub sent score_percent=99 on purpose. Checks 5,4,3,4,5 = 21/25 = 84.
    assert c["call_audit"]["score_percent"] == 84.0
    assert rejected(db) == []


# ---- 2. Band 0 call -----------------------------------------------------------
def test_band_zero_is_valid_and_done(client, user_headers, drop):
    c = get_call(client, user_headers, drop("band_zero").json()["call"]["task_id"])
    assert c["status"] == "done"
    assert c["lead_score"]["band"] == 0


# ---- 3. Missing recording link ------------------------------------------------
def test_missing_recording_link_is_rejected_and_logged_not_saved(client, user_headers, db):
    r = client.post("/api/calls", json={"agent_id": "A-1", "agent_name": "X", "lead_id": "L-1"}, headers=user_headers)
    assert r.status_code == 422
    assert any(e["field"] == "recording_url" for e in r.json()["detail"]["errors"])
    assert db.query(Call).count() == 0
    rows = rejected(db)
    assert len(rows) == 1 and "recording_url" in rows[0].reason


@pytest.mark.parametrize(
    "body,field",
    [
        ({"recording_url": "https://x.example.com/a.mp3", "agent_name": "X", "lead_id": "L-1"}, "agent_id"),
        ({"recording_url": "https://x.example.com/a.mp3", "agent_id": "A"}, "agent_name"),
        ({"recording_url": "not a link", "agent_id": "A", "agent_name": "X", "lead_id": "L-1"}, "recording_url"),
        ({"recording_url": "https://x.example.com/a.mp3", "agent_id": "A", "agent_name": "X", "lead_id": "L-1", "call_date": "yesterday"}, "call_date"),
    ],
)
def test_other_incomplete_payloads_rejected(client, user_headers, db, body, field):
    r = client.post("/api/calls", json=body, headers=user_headers)
    assert r.status_code == 422
    assert any(e["field"] == field for e in r.json()["detail"]["errors"])
    assert db.query(Call).count() == 0 and len(rejected(db)) == 1


def test_unparseable_body_is_rejected_and_logged(client, user_headers, db):
    r = client.post("/api/calls", content=b"{not json", headers={**user_headers, "Content-Type": "application/json"})
    assert r.status_code == 422
    assert db.query(Call).count() == 0 and len(rejected(db)) == 1


# ---- 4. Same call twice -----------------------------------------------------------
def test_same_call_twice_gives_one_call_one_run(client, user_headers, drop, db):
    first = drop("normal")
    second = drop("normal")
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["created"] is False
    assert first.json()["call"]["task_id"] == second.json()["call"]["task_id"]
    assert db.query(Call).count() == 1
    assert db.query(LeadScore).count() == 1 and db.query(CallAudit).count() == 1


def test_task_id_is_derived_from_link_and_date_only():
    d = parse_call_date("2026-11-01")
    a = generate_task_id("https://Rec.Example.com/x.mp3", d)
    assert a == generate_task_id("  https://rec.example.com/x.mp3 ", d)
    assert a != generate_task_id("https://rec.example.com/x.mp3", parse_call_date("2026-11-02"))
    assert a != generate_task_id("https://rec.example.com/y.mp3", d)


# ---- 5. No token (401) --------------------------------------------------------------
def test_no_login_returns_401_and_saves_nothing(client, db):
    r = client.post("/api/calls", json={"recording_url": "https://x.example.com/a.mp3", "agent_id": "A", "agent_name": "X", "lead_id": "L-1"})
    assert r.status_code == 401
    assert db.query(Call).count() == 0 and rejected(db) == []


def test_bad_login_token_returns_401(client, db):
    for headers in (
        {"Authorization": "Bearer garbage"},
        {"Authorization": f"Bearer {make_dev_token(secret='wrong-secret')}"},
        {"Authorization": f"Bearer {make_dev_token(exp_in=-10)}"},
    ):
        r = client.get("/api/calls", headers=headers)
        assert r.status_code == 401


def test_list_requires_login(client):
    assert client.get("/api/calls").status_code == 401
    assert client.get("/api/rejected-requests").status_code == 401
    assert client.get("/api/calls/config").status_code == 401


def test_intake_webhook_without_or_with_wrong_token_is_401(client, db):
    body = {"recording_url": "https://x.example.com/a.mp3", "agent_id": "A", "agent_name": "X", "lead_id": "L-1"}
    assert client.post("/api/webhooks/intake", json=body).status_code == 401
    assert client.post("/api/webhooks/intake", json=body, headers={"X-Webhook-Token": "nope"}).status_code == 401
    assert db.query(Call).count() == 0 and rejected(db) == []


def test_output_webhook_without_or_with_wrong_token_is_401(client, db, idle_call):
    payload = {"agent": "lead_score", "task_id": idle_call, "result": GOOD_LEAD}
    assert post_output(client, payload, token=None).status_code == 401
    assert post_output(client, payload, token="nope").status_code == 401
    assert db.query(LeadScore).count() == 0


def test_user_login_token_does_not_open_webhooks(client, user_headers, idle_call):
    payload = {"agent": "lead_score", "task_id": idle_call, "result": GOOD_LEAD}
    r = client.post("/api/webhooks/output", json=payload, headers=user_headers)
    assert r.status_code == 401


def test_intake_webhook_with_token_creates_call_and_ignores_stub_scenario(client, db):
    body = {"recording_url": "https://x.example.com/hook.mp3", "agent_id": "A", "agent_name": "X", "lead_id": "L-1", "stub_scenario": "invalid_band"}
    r = client.post("/api/webhooks/intake", json=body, headers={"X-Webhook-Token": INTAKE_TOKEN})
    assert r.status_code == 201
    from app.auto_stub import wait_for_idle

    wait_for_idle()
    db.expire_all()
    call = db.query(Call).one()
    assert call.status == CallStatus.DONE  # default "normal", the webhook cannot pick a scenario


# ---- 6. Band 7 -----------------------------------------------------------------------
def test_band_7_is_rejected_and_call_failed(client, user_headers, drop, db):
    c = get_call(client, user_headers, drop("invalid_band").json()["call"]["task_id"])
    assert c["status"] == "failed"
    assert "band" in c["failure_reason"]
    assert c["lead_score"] is None
    assert c["call_audit"] is not None  # the audit that arrived first is kept, shown as partial
    assert any("band" in r.reason for r in rejected(db))


# ---- 7. Missing reason -----------------------------------------------------------------
def test_missing_reason_is_rejected_and_call_failed(client, user_headers, drop, db):
    c = get_call(client, user_headers, drop("missing_reason").json()["call"]["task_id"])
    assert c["status"] == "failed"
    assert "reason" in c["failure_reason"]
    assert c["lead_score"] is None
    assert any("reason" in r.reason for r in rejected(db))


@pytest.mark.parametrize("band", [-1, 6, 7, 2.5, "3", None, True])
def test_band_must_be_whole_number_0_to_5(client, user_headers, idle_call, band):
    r = post_output(client, {"agent": "lead_score", "task_id": idle_call, "result": {**GOOD_LEAD, "band": band}})
    assert r.status_code == 422
    assert get_call(client, user_headers, idle_call)["status"] == "failed"


def test_blank_reason_is_rejected(client, user_headers, idle_call):
    r = post_output(client, {"agent": "lead_score", "task_id": idle_call, "result": {**GOOD_LEAD, "reason": "   "}})
    assert r.status_code == 422


# ---- 8. Same result twice --------------------------------------------------------------
def test_stub_duplicate_result_changes_nothing(client, user_headers, drop, db):
    c = get_call(client, user_headers, drop("duplicate_result").json()["call"]["task_id"])
    assert c["status"] == "done"
    assert db.query(LeadScore).count() == 1
    assert rejected(db) == []  # an identical repeat is a quiet no-op


def test_same_result_posted_twice_is_noop(client, user_headers, idle_call, db):
    p = {"agent": "lead_score", "task_id": idle_call, "result": GOOD_LEAD}
    first = post_output(client, p)
    before = get_call(client, user_headers, idle_call)
    second = post_output(client, p)
    after = get_call(client, user_headers, idle_call)
    assert first.json()["outcome"] == "saved" and second.status_code == 200
    assert second.json()["outcome"] == "duplicate"
    assert before == after
    assert db.query(LeadScore).count() == 1


def test_different_result_for_saved_one_is_ignored_and_logged(client, user_headers, idle_call, db):
    post_output(client, {"agent": "lead_score", "task_id": idle_call, "result": GOOD_LEAD})
    r = post_output(client, {"agent": "lead_score", "task_id": idle_call, "result": {**GOOD_LEAD, "band": 5}})
    assert r.status_code == 409
    c = get_call(client, user_headers, idle_call)
    assert c["lead_score"]["band"] == 3 and c["status"] != "failed"
    assert any("Conflicting" in x.reason for x in rejected(db))


# ---- 9. Dead recording link --------------------------------------------------------------
def test_dead_recording_link_fails_handoff_with_reason(client, user_headers, drop, db):
    r = drop("recording_link_fails")
    assert r.status_code == 201
    c = get_call(client, user_headers, r.json()["call"]["task_id"])
    assert c["status"] == "failed"
    assert "Recording link" in c["failure_reason"]
    assert c["sent_to_auto_at"] is None
    assert db.query(LeadScore).count() == 0


# ---- Output webhook: other rules -----------------------------------------------------------
def test_unknown_task_id_rejected_and_logged(client, db):
    r = post_output(client, {"agent": "lead_score", "task_id": "call_nope", "result": GOOD_LEAD})
    assert r.status_code == 404
    assert any("Unknown task_id" in x.reason for x in rejected(db))


def test_unknown_agent_and_missing_fields_rejected(client, idle_call, db):
    assert post_output(client, {"agent": "bogus", "task_id": idle_call, "result": GOOD_LEAD}).status_code == 422
    assert post_output(client, {"task_id": idle_call}).status_code == 422
    assert len(rejected(db)) == 2


def test_audit_percent_is_recalculated_and_sent_value_ignored(client, user_headers, idle_call):
    result = {**GOOD_AUDIT, "score_percent": 100}
    r = post_output(client, {"agent": "call_audit", "task_id": idle_call, "result": result})
    assert r.status_code == 200
    # (4 + 2) / (5 x 2) x 100 = 60
    assert get_call(client, user_headers, idle_call)["call_audit"]["score_percent"] == 60.0
    assert compute_score_percent([5, 5, 5]) == 100.0
    assert compute_score_percent([1, 1, 1, 1]) == 20.0


@pytest.mark.parametrize("score", [0, 6, 3.5, "4", None])
def test_audit_check_score_must_be_1_to_5(client, user_headers, idle_call, score):
    bad = {"checks": [{"name": "Greeting", "score": score, "evidence": []}]}
    r = post_output(client, {"agent": "call_audit", "task_id": idle_call, "result": bad})
    assert r.status_code == 422
    c = get_call(client, user_headers, idle_call)
    assert c["call_audit"] is None and c["status"] == "failed"


def test_call_is_done_only_when_both_results_saved(client, user_headers, idle_call):
    post_output(client, {"agent": "lead_score", "task_id": idle_call, "result": GOOD_LEAD})
    c = get_call(client, user_headers, idle_call)
    assert c["status"] == "sent_to_auto" or c["status"] == "received"
    assert c["results_received"] == {"lead_score": True, "call_audit": False}
    post_output(client, {"agent": "call_audit", "task_id": idle_call, "result": GOOD_AUDIT})
    assert get_call(client, user_headers, idle_call)["status"] == "done"


def test_result_for_failed_call_is_rejected(client, user_headers, idle_call, db):
    post_output(client, {"agent": "lead_score", "task_id": idle_call, "result": {**GOOD_LEAD, "band": 9}})
    r = post_output(client, {"agent": "call_audit", "task_id": idle_call, "result": GOOD_AUDIT})
    assert r.status_code == 409
    c = get_call(client, user_headers, idle_call)
    assert c["status"] == "failed" and c["call_audit"] is None


# ---- Stuck calls --------------------------------------------------------------------------
def test_call_in_sent_to_auto_over_15_minutes_is_flagged_stuck(client, user_headers, idle_call, db):
    assert get_call(client, user_headers, idle_call)["is_stuck"] is False
    call = db.query(Call).one()
    call.sent_to_auto_at = utcnow() - timedelta(minutes=16)
    db.commit()
    c = get_call(client, user_headers, idle_call)
    assert c["status"] == "sent_to_auto" and c["is_stuck"] is True
    call.sent_to_auto_at = utcnow() - timedelta(minutes=14)
    db.commit()
    assert get_call(client, user_headers, idle_call)["is_stuck"] is False


# ---- List, filters, safety ------------------------------------------------------------------
def test_list_filters(client, user_headers, drop):
    drop("normal", recording_url="https://r.example.com/1.mp3", agent_id="A-1", agent_name="Ana")
    drop("band_zero", recording_url="https://r.example.com/2.mp3", agent_id="A-2", agent_name="Ben")
    drop("invalid_band", recording_url="https://r.example.com/3.mp3", agent_id="A-2", agent_name="Ben")
    q = lambda s: client.get(f"/api/calls?{s}", headers=user_headers).json()
    assert q("")["total"] == 3
    assert q("status=done")["total"] == 2
    assert q("status=failed")["total"] == 1
    assert q("agent_id=A-2")["total"] == 2
    assert q("band=0")["total"] == 1
    assert q("band=4&agent_id=A-1")["total"] == 1
    assert client.get("/api/calls?status=bogus", headers=user_headers).status_code == 422
    agents = client.get("/api/calls/agents", headers=user_headers).json()
    assert {a["agent_id"] for a in agents} == {"A-1", "A-2"}


def test_scenario_rejected_when_test_mode_off(client, user_headers, monkeypatch, db):
    monkeypatch.setenv("TEST_MODE", "false")
    r = client.post(
        "/api/calls",
        json={"recording_url": "https://x.example.com/a.mp3", "agent_id": "A", "agent_name": "X", "lead_id": "L-1", "stub_scenario": "normal"},
        headers=user_headers,
    )
    assert r.status_code == 422 and db.query(Call).count() == 0
    cfg = client.get("/api/calls/config", headers=user_headers).json()
    assert cfg["test_mode"] is False and cfg["stub_scenarios"] == []


def test_config_offers_all_six_scenarios_in_test_mode(client, user_headers):
    cfg = client.get("/api/calls/config", headers=user_headers).json()
    assert cfg["test_mode"] is True
    assert {s["value"] for s in cfg["stub_scenarios"]} == {
        "normal", "band_zero", "invalid_band", "missing_reason", "duplicate_result", "recording_link_fails",
    }


def test_rejected_payload_copy_has_no_tokens(client, user_headers, db):
    client.post(
        "/api/calls",
        json={"agent_id": "A", "agent_name": "X", "lead_id": "L-1", "api_token": "SECRET-VALUE", "recording_url": "ftp://x.example.com/a?token=SECRET-VALUE&x=1"},
        headers=user_headers,
    )
    dumped = str([r.payload for r in rejected(db)])
    assert "SECRET-VALUE" not in dumped


def test_unconfigured_webhook_token_fails_closed(client, monkeypatch):
    monkeypatch.setenv("OUTPUT_WEBHOOK_TOKEN", "")
    r = client.post("/api/webhooks/output", json={}, headers={"X-Webhook-Token": ""})
    assert r.status_code == 401


def test_dev_mock_refuses_to_load_in_production(monkeypatch):
    from app.auth.dev_mock_provider import DevMockProvider

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        DevMockProvider()


def test_stats_requires_login_and_counts(client, user_headers, db):
    assert client.get("/api/calls/stats").status_code == 401
    s = client.get("/api/calls/stats", headers=user_headers).json()
    assert s["total"] == 0 and s["processed"] == 0 and s["rejected"] >= 0
    assert [b["band"] for b in s["bands"]] == [0, 1, 2, 3, 4, 5]
    assert len(s["per_day"]) == 14


def test_lead_id_is_required(client, user_headers, db):
    body = {"recording_url": "https://x.example.com/a.mp3", "agent_id": "A", "agent_name": "X"}
    r = client.post("/api/calls", json=body, headers=user_headers)
    assert r.status_code == 422
    assert any(e["field"] == "lead_id" for e in r.json()["detail"]["errors"])
    body["lead_id"] = "   "
    assert client.post("/api/calls", json=body, headers=user_headers).status_code == 422


def test_retry_failed_call_runs_again_and_finishes(client, user_headers, drop, db):
    from app.auto_stub import wait_for_idle

    task_id = drop("recording_link_fails").json()["call"]["task_id"]
    assert get_call(client, user_headers, task_id)["status"] == "failed"

    r = client.post(f"/api/calls/{task_id}/retry", headers=user_headers)
    assert r.status_code == 200
    wait_for_idle()
    c = get_call(client, user_headers, task_id)
    assert c["status"] in ("sent_to_auto", "done", "failed")
    assert c["task_id"] == task_id


def test_retry_refused_unless_failed_or_unknown(client, user_headers, drop, db):
    task_id = drop("normal").json()["call"]["task_id"]
    assert get_call(client, user_headers, task_id)["status"] == "done"
    assert client.post(f"/api/calls/{task_id}/retry", headers=user_headers).status_code == 409
    assert client.post("/api/calls/nope/retry", headers=user_headers).status_code == 404
    assert client.post(f"/api/calls/{task_id}/retry").status_code == 401


def test_auto_policies_lists_the_two_agent_policies(client, user_headers, db):
    assert client.get("/api/calls/auto-policies").status_code == 401
    items = client.get("/api/calls/auto-policies", headers=user_headers).json()["items"]
    assert [p["agent"] for p in items] == ["Lead Score", "Call Audit"]
    assert [len(p["judgments"]) for p in items] == [8, 3]
    assert all(p["published"] and p["rules"] for p in items)


def test_ai_insights_come_from_real_calls(client, user_headers, drop, db):
    # Empty database: one honest "no calls yet" insight, no demo data.
    empty = client.get("/api/ai/insights", headers=user_headers).json()
    assert [i["title"] for i in empty["insights"]] == ["No calls yet"]

    drop("normal", recording_url="https://r.example.com/i1.mp3")
    drop("recording_link_fails", recording_url="https://r.example.com/i2.mp3")
    data = client.post("/api/ai/insights/analyze", json={}, headers=user_headers).json()
    text = " ".join(i["title"] + " " + i["description"] for i in data["insights"])
    assert "DEMO" not in text and "transaction" not in text.lower()
    assert any("failed" in i["title"] for i in data["insights"])
    assert any(a["action_type"] == "retry_failed" for a in data["actions"])
    assert data["patterns"]


def test_ai_manager_answers_about_calls(client, user_headers, drop, db, monkeypatch):
    from app.services.ai import chat_service

    monkeypatch.setattr(chat_service, "client", None)  # no model: the data-backed fallback answers
    drop("normal", recording_url="https://r.example.com/c1.mp3")
    drop("recording_link_fails", recording_url="https://r.example.com/c2.mp3")
    ask = lambda q: client.post("/api/ai/chat", json={"message": q}, headers=user_headers).json()
    assert "2" in ask("How are my sales calls doing?")["response"]
    assert "failed" in ask("Show failed calls")["response"].lower()
    reply = ask("Create a policy and show recent logins")["response"]
    assert "policy" not in ask("Show high-intent leads")["response"].lower()
    assert "Sample Agent" in ask("How are my agents scoring on audit?")["response"]
    assert reply


def test_legacy_call_can_get_a_lead_id_once(client, user_headers, db):
    from app.models.call import Call

    db.add(Call(task_id="call_legacy", agent_id="A", agent_name="X", recording_url="https://x.example.com/old.mp3", status="done"))
    db.commit()
    stats = client.get("/api/calls/stats", headers=user_headers).json()
    assert stats["missing_lead_id"] == 1

    url = "/api/calls/call_legacy/lead-id"
    assert client.patch(url, json={"lead_id": "  "}, headers=user_headers).status_code == 422
    assert client.patch("/api/calls/nope/lead-id", json={"lead_id": "L-9"}, headers=user_headers).status_code == 404
    r = client.patch(url, json={"lead_id": " L-9 "}, headers=user_headers)
    assert r.status_code == 200 and r.json()["lead_id"] == "L-9"
    # An existing Lead ID is never overwritten.
    assert client.patch(url, json={"lead_id": "L-10"}, headers=user_headers).status_code == 409
    assert client.get("/api/calls/stats", headers=user_headers).json()["missing_lead_id"] == 0


def test_stats_numbers_match_the_calls(client, user_headers, drop, db):
    drop("normal", recording_url="https://r.example.com/s1.mp3", agent_id="A-1", agent_name="Asha")
    drop("band_zero", recording_url="https://r.example.com/s2.mp3", agent_id="A-2", agent_name="Ben")
    drop("recording_link_fails", recording_url="https://r.example.com/s3.mp3", agent_id="A-2", agent_name="Ben")
    s = client.get("/api/calls/stats", headers=user_headers).json()
    assert s["total"] == 3 and s["processed"] == 2 and s["failed"] == 1
    assert s["success_rate"] == 66.7
    bands = {b["band"]: b["count"] for b in s["bands"]}
    assert bands[4] == 1 and bands[0] == 1 and sum(bands.values()) == 2
    assert s["avg_band"] == 2.0
    assert s["avg_audit_percent"] is not None
    agents = {a["agent_id"]: a for a in s["agents"]}
    assert agents["A-2"]["calls"] == 2 and agents["A-2"]["done"] == 1 and agents["A-1"]["avg_band"] == 4.0
    assert s["per_day"][-1]["count"] == 3 and len(s["per_day"]) == 14
    # list pagination info
    page = client.get("/api/calls?limit=2&offset=2", headers=user_headers).json()
    assert page["total"] == 3 and len(page["items"]) == 1 and page["offset"] == 2


def test_date_range_filters_list_and_stats(client, user_headers, drop, db):
    from datetime import date, timedelta

    drop("normal", recording_url="https://r.example.com/d1.mp3")
    drop("normal", recording_url="https://r.example.com/d2.mp3")
    today, tomorrow = date.today(), date.today() + timedelta(days=1)
    q = lambda p: client.get(f"/api/calls?{p}", headers=user_headers)
    assert q(f"date_from={today}&date_to={today}").json()["total"] == 2
    assert q(f"date_from={tomorrow}").json()["total"] == 0
    assert q(f"date_to={today - timedelta(days=1)}").json()["total"] == 0
    assert q(f"date_from={tomorrow}&date_to={today}").status_code == 422
    assert q("date_from=not-a-date").status_code == 422
    s = client.get(f"/api/calls/stats?date_from={tomorrow}&date_to={tomorrow}", headers=user_headers).json()
    assert s["total"] == 0 and s["range"] == {"from": str(tomorrow), "to": str(tomorrow)}
    s = client.get(f"/api/calls/stats?date_from={today}&date_to={today}", headers=user_headers).json()
    assert s["total"] == 2 and len(s["per_day"]) == 1


def test_csv_export_matches_filters_and_blocks_formulas(client, user_headers, drop, db):
    import csv, io

    assert client.get("/api/calls/export.csv").status_code == 401
    drop("normal", recording_url="https://r.example.com/e1.mp3", agent_name="=HYPERLINK(\"http://evil\")")
    drop("band_zero", recording_url="https://r.example.com/e2.mp3")
    r = client.get("/api/calls/export.csv?band=0", headers=user_headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text.lstrip("﻿"))))
    assert len(rows) == 1 and rows[0]["lead_band"] == "0"
    allrows = list(csv.DictReader(io.StringIO(client.get("/api/calls/export.csv", headers=user_headers).text.lstrip("﻿"))))
    assert len(allrows) == 2
    assert all(not row["agent_name"].startswith("=") for row in allrows)
    assert any(row["agent_name"].startswith("'=") for row in allrows)
    assert client.get("/api/calls/export.csv?status=bogus", headers=user_headers).status_code == 422


def test_ready_checks_the_database_and_requests_get_an_id(client, user_headers, monkeypatch):
    r = client.get("/api/ready")
    assert r.status_code == 200 and r.json() == {"status": "ready"}
    assert r.headers.get("x-request-id")
    assert client.get("/api/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"

    from app.routers import health

    class Broken:
        def execute(self, *a, **k):
            raise RuntimeError("db down")

        def close(self):
            pass

    monkeypatch.setattr(health, "SessionLocal", lambda: Broken())
    assert client.get("/api/ready").status_code == 503


def test_ops_summary_and_alerts(client, user_headers, drop, db, caplog, monkeypatch):
    import asyncio
    import logging

    from app.services import alerts

    assert client.get("/api/calls/ops").status_code == 401
    ops = client.get("/api/calls/ops", headers=user_headers).json()
    assert ops["stuck"] == 0 and ops["failed_recently"] == 0

    drop("recording_link_fails", recording_url="https://r.example.com/o1.mp3")
    assert client.get("/api/calls/ops", headers=user_headers).json()["failed_recently"] == 1

    alerts._last_signature = None
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    with caplog.at_level(logging.ERROR):
        msgs = asyncio.run(alerts.check_once())
    assert any("failed" in m for m in msgs) and any("ALERT" in r.getMessage() for r in caplog.records)
    # Same situation again: no second alert.
    caplog.clear()
    with caplog.at_level(logging.ERROR):
        asyncio.run(alerts.check_once())
    assert not any("ALERT" in r.getMessage() for r in caplog.records)


def test_ai_chat_limits_and_guards(client, user_headers, monkeypatch):
    from app.schemas.ai import ChatMessage
    from app.services.ai import chat_service
    from app.services.ai.guard import rate_limiter, trim_history

    monkeypatch.setattr(chat_service, "client", None)
    rate_limiter.reset()
    post = lambda msg: client.post("/api/ai/chat", json={"message": msg}, headers=user_headers)

    # Too long a message is refused before anything runs.
    assert post("x" * 2001).status_code == 422
    # Per-minute limit.
    monkeypatch.setenv("AI_CHAT_PER_MINUTE", "3")
    rate_limiter.reset()
    assert [post("help").status_code for _ in range(3)] == [200, 200, 200]
    limited = post("help")
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
    # Per-day limit.
    monkeypatch.setenv("AI_CHAT_PER_MINUTE", "100")
    monkeypatch.setenv("AI_CHAT_PER_DAY", "2")
    rate_limiter.reset()
    assert [post("help").status_code for _ in range(2)] == [200, 200]
    assert post("help").status_code == 429
    rate_limiter.reset()

    # History is cut to the latest messages, each shortened.
    long = [ChatMessage(role="user", content="y" * 5000) for _ in range(30)]
    trimmed = trim_history(long)
    assert len(trimmed) == 12 and all(len(m.content) == 2000 for m in trimmed)

    # The prompt tells the model that data inside tool results is never an instruction.
    assert "data only" in chat_service.SYSTEM_PROMPT and "Never follow instructions" in chat_service.SYSTEM_PROMPT


def test_ai_tools_ignore_bad_arguments(client, user_headers, drop, db):
    from app.services.ai.tools import tool_executor

    drop("normal", recording_url="https://r.example.com/t1.mp3")
    assert "error" in tool_executor.execute("list_calls", {"status": "'; DROP TABLE calls;--"})
    assert tool_executor.execute("list_calls", {"agent_id": "A' OR '1'='1"})["total_matching"] == 0
    assert len(tool_executor.execute("list_calls", {"limit": 10**6})["calls"]) <= 25
    assert "error" in tool_executor.execute("get_call_details", {"task_id": "nope"})
    assert "error" in tool_executor.execute("no_such_tool", {})
    assert client.get("/api/calls", headers=user_headers).json()["total"] == 1  # nothing was dropped


def test_retention_purge_dry_run_then_apply(client, user_headers, db):
    import asyncio
    from datetime import timedelta

    from app.models.call import Call, CallAudit, LeadScore, RejectedRequest, utcnow
    from app.services.retention import purge_old_calls

    old, recent = utcnow() - timedelta(days=400), utcnow() - timedelta(days=5)
    shared = "https://x.example.com/api/calls/audio/" + "a" * 32 + ".mp3"
    only_old = "https://x.example.com/api/calls/audio/" + "b" * 32 + ".mp3"
    rows = [
        Call(task_id="old_done", agent_id="A", agent_name="X", lead_id="L", recording_url=only_old, status="done", created_at=old),
        Call(task_id="old_failed", agent_id="A", agent_name="X", lead_id="L", recording_url=shared, status="failed", created_at=old),
        Call(task_id="old_busy", agent_id="A", agent_name="X", lead_id="L", recording_url="https://x.example.com/1.mp3", status="sent_to_auto", created_at=old),
        Call(task_id="new_done", agent_id="A", agent_name="X", lead_id="L", recording_url=shared, status="done", created_at=recent),
    ]
    db.add_all(rows)
    db.add(LeadScore(task_id="old_done", band=3, reason="r", evidence=[]))
    db.add(CallAudit(task_id="old_done", checks=[], score_percent=50.0))
    db.add(RejectedRequest(endpoint="/api/calls", reason="old", created_at=old))
    db.add(RejectedRequest(endpoint="/api/calls", reason="new", created_at=recent))
    db.commit()

    class FakeStorage:
        deleted = []

        async def delete(self, path):
            self.deleted.append(path)

    storage = FakeStorage()
    run = lambda **kw: asyncio.run(purge_old_calls(db, 180, storage=storage, **kw))

    dry = run()
    assert dry["dry_run"] and dry["calls"] == 2 and dry["lead_scores"] == 1 and dry["call_audits"] == 1
    assert dry["audio_files"] == 1 and dry["rejected_requests"] == 1  # the shared file is still used by new_done
    assert db.query(Call).count() == 4 and storage.deleted == []

    done = run(apply=True)
    assert done["calls"] == 2 and not done["dry_run"]
    assert {c.task_id for c in db.query(Call).all()} == {"old_busy", "new_done"}  # in-progress and recent kept
    assert db.query(LeadScore).count() == 0 and db.query(CallAudit).count() == 0
    assert [r.reason for r in db.query(RejectedRequest).all()] == ["new"]
    assert storage.deleted == ["calls/audio/" + "b" * 32 + ".mp3"]

    import pytest

    with pytest.raises(ValueError):
        asyncio.run(purge_old_calls(db, 7, apply=True))


def test_auto_policies_snapshot_age_and_staleness(client, user_headers):
    from datetime import date, timedelta

    from app.services.auto_policies import SYNCED_AT, snapshot_info

    synced = date.fromisoformat(SYNCED_AT)
    assert snapshot_info(synced) == {**snapshot_info(synced), "age_days": 0, "stale": False}
    assert snapshot_info(synced + timedelta(days=14))["stale"] is False
    assert snapshot_info(synced + timedelta(days=15))["stale"] is True
    assert snapshot_info(synced + timedelta(days=40))["age_days"] == 40
    snap = client.get("/api/calls/auto-policies", headers=user_headers).json()["snapshot"]
    assert snap["synced_at"] == SYNCED_AT and set(snap) >= {"source", "age_days", "stale", "stale_after_days"}
