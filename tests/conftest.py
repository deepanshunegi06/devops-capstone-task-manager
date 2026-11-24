import pytest

from taskmanager import create_app
from taskmanager.config import TestConfig
from taskmanager.models import db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username, password="password123", **extra):
    resp = client.post("/api/auth/register", json={"username": username, "password": password, **extra})
    assert resp.status_code == 201, resp.get_json()
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


@pytest.fixture
def token(client):
    resp = client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 201
    return resp.get_json()["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bob(client):
    return register(client, "bob")


@pytest.fixture
def make_task(client, auth):
    def _make(headers=None, **fields):
        payload = {"title": "Write Jenkinsfile", **fields}
        resp = client.post("/api/tasks", json=payload, headers=headers or auth)
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()["task"]
    return _make


@pytest.fixture
def make_project(client, auth):
    def _make(headers=None, **fields):
        resp = client.post("/api/projects", json={"name": "Capstone", "icon": "🚀", **fields},
                           headers=headers or auth)
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()["project"]
    return _make
