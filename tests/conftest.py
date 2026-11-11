# tests/conftest.py
"""
Test setup for the call flow. Runs against a throwaway SQLite file with the dev-mock
login, the Auto stub on, and no stub delay. Run from the project root: `pytest`.
"""

import base64
import hashlib
import hmac
import json
import os
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="cc-tests-")

# Must be set before the app is imported.
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
        "APP_ENV": "development",
        "AUTH_PROVIDER": "dev_mock",
        "DEV_AUTH_ENABLED": "true",
        "DEV_AUTH_SECRET": "test-dev-secret",
        "INTAKE_WEBHOOK_TOKEN": "test-intake-token",
        "OUTPUT_WEBHOOK_TOKEN": "test-output-token",
        "AUTO_MODE": "stub",
        "TEST_MODE": "true",
        "AUTO_STUB_DELAY_SECONDS": "0",
        "AUDIT_MIDDLEWARE_ENABLED": "false",
        "STUCK_AFTER_MINUTES": "15",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auto_stub import wait_for_idle  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
import app.models as _models  # noqa: E402,F401  (register tables)

INTAKE_TOKEN = os.environ["INTAKE_WEBHOOK_TOKEN"]
OUTPUT_TOKEN = os.environ["OUTPUT_WEBHOOK_TOKEN"]


def make_dev_token(username="tester", roles=("user",), secret="test-dev-secret", exp_in=3600):
    claims = {
        "sub": f"dev-{username}",
        "preferred_username": username,
        "email": f"{username}@example.com",
        "name": username,
        "realm_access": {"roles": list(roles)},
        "exp": int(time.time()) + exp_in,
    }
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"devmock.{payload}.{sig}"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    wait_for_idle()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def user_headers():
    return {"Authorization": f"Bearer {make_dev_token()}"}


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def drop(client, user_headers):
    """Drop a call through the dashboard route, wait for the stub, return (response, task_id)."""

    def _drop(scenario="normal", **overrides):
        body = {
            "recording_url": "https://recordings.example.com/call-001.mp3",
            "agent_id": "A-100",
            "agent_name": "Sample Agent",
            "lead_id": "L-100",
            "customer_name": "Sample Customer",
            "call_date": "2026-11-01",
        }
        if scenario:
            body["stub_scenario"] = scenario
        body.update(overrides)
        r = client.post("/api/calls", json=body, headers=user_headers)
        wait_for_idle()
        return r

    return _drop


def post_output(client, payload, token=OUTPUT_TOKEN):
    headers = {"X-Webhook-Token": token} if token else {}
    r = client.post("/api/webhooks/output", json=payload, headers=headers)
    return r
