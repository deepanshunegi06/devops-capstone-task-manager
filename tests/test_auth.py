def test_register_returns_token(client):
    resp = client.post("/api/auth/register", json={"username": "bob", "password": "secret1234",
                                                   "display_name": "Bob Builder"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["user"]["username"] == "bob" and body["user"]["initials"] == "BB"
    assert body["token"]


def test_register_validation(client):
    resp = client.post("/api/auth/register", json={"username": "x", "password": "short"})
    assert resp.status_code == 400
    assert set(resp.get_json()["fields"]) == {"username", "password"}


def test_register_rejects_bad_characters(client):
    resp = client.post("/api/auth/register", json={"username": "bad name!", "password": "secret1234"})
    assert resp.status_code == 400


def test_duplicate_username(client, token):
    resp = client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 409


def test_login_success_and_failure(client, token):
    ok = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert ok.status_code == 200 and ok.get_json()["token"]
    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrong-pass"})
    assert bad.status_code == 401


def test_me_requires_auth(client, auth):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get("/api/auth/me", headers=auth).get_json()["user"]["username"] == "alice"


def test_web_register_login_logout(client):
    resp = client.post("/register", data={"username": "carol", "password": "password123"})
    assert resp.status_code == 302
    assert client.get("/app").status_code == 200
    client.get("/logout")
    assert client.get("/app").status_code == 302
    resp = client.post("/login", data={"username": "carol", "password": "password123"})
    assert resp.status_code == 302


def test_web_login_bad_password(client, token):
    resp = client.post("/login", data={"username": "alice", "password": "nope-nope"})
    assert resp.status_code == 200
    assert b"Invalid username or password" in resp.data


def test_web_login_next_redirect(client, token):
    resp = client.post("/login?next=/app", data={"username": "alice", "password": "password123"})
    assert resp.headers["Location"] == "/app"


def test_web_login_open_redirect_blocked(client, token):
    resp = client.post("/login?next=//evil.example.com",
                       data={"username": "alice", "password": "password123"})
    assert resp.headers["Location"] == "/app"


def test_web_register_validation_and_duplicate(client, token):
    assert client.post("/register", data={"username": "a", "password": "x"}).status_code == 400
    assert client.post("/register", data={"username": "alice", "password": "password123"}).status_code == 409


def test_admin_seeded_from_env():
    from taskmanager import create_app
    from taskmanager.config import TestConfig

    class SeedConfig(TestConfig):
        ADMIN_USERNAME = "admin"
        ADMIN_PASSWORD = "admin-password"

    app = create_app(SeedConfig)
    client = app.test_client()
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    assert resp.status_code == 200
