import pytest

from taskmanager import create_app
from taskmanager.config import TestConfig


@pytest.fixture
def web(client):
    client.post("/register", data={"username": "webuser", "password": "password123"})
    return client


def test_dashboard_redirects_when_logged_out(client):
    resp = client.get("/")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_web_task_crud(web):
    assert web.get("/tasks/new").status_code == 200
    resp = web.post("/tasks/new", data={
        "title": "Deploy to K8s", "priority": "high", "status": "todo", "due_date": "2030-05-01"})
    assert resp.status_code == 302
    page = web.get("/").data
    assert b"Deploy to K8s" in page

    assert web.get("/tasks/1/edit").status_code == 200
    resp = web.post("/tasks/1/edit", data={
        "title": "Deploy with ArgoCD", "priority": "low", "status": "in_progress", "due_date": ""})
    assert resp.status_code == 302
    assert b"Deploy with ArgoCD" in web.get("/?status=in_progress").data

    web.post("/tasks/1/status", data={"status": "done"})
    assert b"Deploy with ArgoCD" in web.get("/?status=done").data

    assert web.post("/tasks/1/delete").status_code == 302
    assert b"No tasks here yet" in web.get("/").data


def test_web_validation_errors(web):
    assert web.post("/tasks/new", data={"title": ""}).status_code == 400
    web.post("/tasks/new", data={"title": "ok"})
    assert web.post("/tasks/1/edit", data={"title": "", "priority": "zzz"}).status_code == 400


def test_web_404_page(web):
    resp = web.get("/tasks/999/edit")
    assert resp.status_code == 404 and b"404" in resp.data


def test_api_404_is_json(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404 and resp.get_json()["error"] == "not_found"


def test_health_and_version(client):
    assert client.get("/health/live").get_json() == {"status": "ok"}
    assert client.get("/health/ready").get_json()["database"] == "up"
    assert client.get("/version").get_json()["color"] in ("blue", "green")


def test_metrics_endpoint(client, auth):
    client.post("/api/tasks", json={"title": "metric me"}, headers=auth)
    body = client.get("/metrics").data.decode()
    assert "taskmanager_http_requests_total" in body
    assert 'taskmanager_tasks{status="todo"} 1.0' in body
    assert "taskmanager_users 1.0" in body


def test_security_headers_and_request_id(client):
    resp = client.get("/health/live", headers={"X-Request-ID": "abc123"})
    assert resp.headers["X-Request-ID"] == "abc123"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in resp.headers


def test_csrf_enforced_when_enabled():
    class CsrfConfig(TestConfig):
        CSRF_ENABLED = True

    app = create_app(CsrfConfig)
    client = app.test_client()
    assert client.post("/login", data={"username": "a", "password": "b"}).status_code == 400
    client.get("/login")  # issues the token into the session
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    resp = client.post("/login", data={"username": "a", "password": "b", "csrf_token": token})
    assert resp.status_code == 200  # reaches the view; credentials are wrong


def test_unhandled_exception_returns_500_json(app, client):
    @app.get("/api/boom")
    def boom():
        raise RuntimeError("kaboom")

    resp = client.get("/api/boom")
    assert resp.status_code == 500 and resp.get_json()["error"] == "internal_server_error"
