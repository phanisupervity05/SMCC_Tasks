# tests/test_main.py
"""Basic app-level checks: the public probes answer, and protected routes need a login."""


def test_health_check(client):
    """The public liveness probe answers without a login."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_check(client):
    """The public readiness probe answers once the database is reachable."""
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_unauthorized_access(client):
    """Protected endpoints require authentication."""
    assert client.get("/api/test").status_code == 401
    assert client.get("/api/calls").status_code == 401
    assert client.get("/api/ai/insights").status_code == 401
