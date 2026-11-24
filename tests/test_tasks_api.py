def _create(client, auth, **kw):
    payload = {"title": "Write Jenkinsfile", "priority": "high", **kw}
    resp = client.post("/api/tasks", json=payload, headers=auth)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["task"]


def test_requires_auth(client):
    assert client.get("/api/tasks").status_code == 401


def test_crud_lifecycle(client, auth):
    task = _create(client, auth, description="CI pipeline", due_date="2030-01-01")
    assert task["status"] == "todo" and task["due_date"] == "2030-01-01"

    listed = client.get("/api/tasks", headers=auth).get_json()
    assert listed["count"] == 1

    got = client.get(f"/api/tasks/{task['id']}", headers=auth).get_json()["task"]
    assert got["title"] == "Write Jenkinsfile"

    patched = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth)
    assert patched.get_json()["task"]["status"] == "done"

    put = client.put(f"/api/tasks/{task['id']}", json={"title": "Renamed"}, headers=auth)
    assert put.get_json()["task"]["title"] == "Renamed"

    assert client.delete(f"/api/tasks/{task['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task['id']}", headers=auth).status_code == 404


def test_validation_errors(client, auth):
    resp = client.post("/api/tasks", json={"title": "", "status": "nope", "priority": "x",
                                           "due_date": "31-12-2030"}, headers=auth)
    assert resp.status_code == 400
    assert set(resp.get_json()["fields"]) == {"title", "status", "priority", "due_date"}


def test_non_json_body(client, auth):
    resp = client.post("/api/tasks", data="not json", headers=auth)
    assert resp.status_code == 400
    task = _create(client, auth)
    assert client.put(f"/api/tasks/{task['id']}", data="x", headers=auth).status_code == 400


def test_put_requires_title_patch_does_not(client, auth):
    task = _create(client, auth)
    assert client.put(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth).status_code == 400
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth).status_code == 200


def test_filter_and_search(client, auth):
    _create(client, auth, title="Dockerfile")
    t = _create(client, auth, title="Helm chart")
    client.patch(f"/api/tasks/{t['id']}", json={"status": "in_progress"}, headers=auth)
    assert client.get("/api/tasks?status=in_progress", headers=auth).get_json()["count"] == 1
    assert client.get("/api/tasks?q=docker", headers=auth).get_json()["count"] == 1
    assert client.get("/api/tasks?status=bogus", headers=auth).status_code == 400


def test_users_cannot_see_each_others_tasks(client, auth):
    task = _create(client, auth)
    other = client.post("/api/auth/register", json={"username": "mallory", "password": "password123"})
    other_auth = {"Authorization": f"Bearer {other.get_json()['token']}"}
    assert client.get(f"/api/tasks/{task['id']}", headers=other_auth).status_code == 404
    assert client.delete(f"/api/tasks/{task['id']}", headers=other_auth).status_code == 404
    assert client.get("/api/tasks", headers=other_auth).get_json()["count"] == 0


def test_stats(client, auth):
    _create(client, auth)
    t = _create(client, auth)
    client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}, headers=auth)
    body = client.get("/api/stats", headers=auth).get_json()
    assert body["total"] == 2 and body["counts"]["done"] == 1


def test_overdue_flag(client, auth):
    task = _create(client, auth, due_date="2000-01-01")
    assert task["overdue"] is True
