from taskmanager import create_app
from taskmanager.config import TestConfig


def test_index_and_app_shell_redirects(client):
    resp = client.get("/")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/login")
    resp = client.get("/app")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_app_shell_after_login(client):
    client.post("/register", data={"username": "webuser", "password": "password123", "display_name": "Web User"})
    assert client.get("/").headers["Location"].endswith("/app")
    page = client.get("/app")
    assert page.status_code == 200 and b'name="csrf-token"' in page.data
    assert client.get("/login").status_code == 302                     # already logged in
    # the session cookie also authenticates the JSON API
    assert client.get("/api/me").get_json()["user"]["display_name"] == "Web User"


def test_web_404_page_and_api_404_json(client):
    resp = client.get("/no-such-page")
    assert resp.status_code == 404 and b"404" in resp.data
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
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


def _csrf_client():
    class CsrfConfig(TestConfig):
        CSRF_ENABLED = True
    return create_app(CsrfConfig).test_client()


def test_csrf_on_forms():
    client = _csrf_client()
    assert client.post("/login", data={"username": "a", "password": "b"}).status_code == 400
    client.get("/login")
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    resp = client.post("/login", data={"username": "a", "password": "b", "csrf_token": token})
    assert resp.status_code == 200          # reaches the view; credentials are wrong


def test_csrf_on_cookie_authenticated_api():
    client = _csrf_client()
    # anonymous API calls and bearer-token calls need no CSRF token
    reg = client.post("/api/auth/register", json={"username": "spa", "password": "password123"})
    bearer = {"Authorization": f"Bearer {reg.get_json()['token']}"}
    assert client.post("/api/tasks", json={"title": "via token"}, headers=bearer).status_code == 201

    client.get("/login")
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    client.post("/login", data={"username": "spa", "password": "password123", "csrf_token": token})
    assert client.get("/app").status_code == 200          # login rotated the session; the SPA page has the new token
    with client.session_transaction() as sess:
        token = sess["_csrf"]
    assert client.get("/api/tasks").status_code == 200                                      # reads are fine
    assert client.post("/api/tasks", json={"title": "forged"}).status_code == 400            # no header
    ok = client.post("/api/tasks", json={"title": "real"}, headers={"X-CSRF-Token": token})
    assert ok.status_code == 201


def test_unhandled_exception_returns_500_json(app, client):
    @app.get("/api/boom")
    def boom():
        raise RuntimeError("kaboom")

    resp = client.get("/api/boom")
    assert resp.status_code == 500 and resp.get_json()["error"] == "internal_server_error"


def test_unhandled_exception_html(app, client):
    @app.get("/boom")
    def boom_html():
        raise RuntimeError("kaboom")

    resp = client.get("/boom")
    assert resp.status_code == 500 and b"500" in resp.data
