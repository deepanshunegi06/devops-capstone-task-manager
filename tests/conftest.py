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


@pytest.fixture
def token(client):
    resp = client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 201
    return resp.get_json()["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}
