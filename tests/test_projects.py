def test_project_crud(client, auth, make_project, make_task):
    project = make_project(color="#10b981")
    assert project["role"] == "owner" and project["icon"] == "🚀" and project["color"] == "#10b981"
    assert project["members"][0]["user"]["username"] == "alice"
    auto = make_project(name="Second")
    assert auto["color"].startswith("#")

    make_task(project_id=project["id"])
    listed = client.get("/api/projects", headers=auth).get_json()["projects"]
    assert [p["name"] for p in listed] == ["Capstone", "Second"] and listed[0]["open_count"] == 1

    upd = client.patch(f"/api/projects/{project['id']}", json={"name": "Final Year", "icon": "🎓"}, headers=auth)
    assert upd.get_json()["project"]["name"] == "Final Year"
    bad = client.patch(f"/api/projects/{project['id']}", json={"color": "red", "icon": "", "name": ""}, headers=auth)
    assert set(bad.get_json()["fields"]) == {"color", "icon", "name"}

    assert client.delete(f"/api/projects/{project['id']}", headers=auth).status_code == 204
    assert client.get("/api/tasks", headers=auth).get_json()["count"] == 0      # tasks removed with project
    assert client.get(f"/api/tasks?project_id={project['id']}", headers=auth).status_code == 404


def test_members_and_roles(client, auth, bob, make_project):
    project = make_project()
    pid = project["id"]
    assert client.get("/api/projects", headers=bob).get_json()["projects"] == []
    added = client.post(f"/api/projects/{pid}/members", json={"username": "bob", "role": "viewer"}, headers=auth)
    assert [m["role"] for m in added.get_json()["project"]["members"]] == ["owner", "viewer"]
    as_bob = client.get("/api/projects", headers=bob).get_json()["projects"][0]
    assert as_bob["role"] == "viewer"

    # viewers cannot edit, share or delete
    assert client.patch(f"/api/projects/{pid}", json={"name": "x"}, headers=bob).status_code == 403
    assert client.post(f"/api/projects/{pid}/members", json={"username": "alice"}, headers=bob).status_code == 403
    assert client.delete(f"/api/projects/{pid}", headers=bob).status_code == 403

    # role change, validation
    changed = client.post(f"/api/projects/{pid}/members", json={"username": "bob", "role": "editor"}, headers=auth)
    assert changed.get_json()["project"]["members"][1]["role"] == "editor"
    assert client.post(f"/api/projects/{pid}/members", json={"username": "ghost"}, headers=auth).status_code == 400
    assert client.post(f"/api/projects/{pid}/members", json={"username": "bob", "role": "owner"},
                       headers=auth).status_code == 400
    assert client.post(f"/api/projects/{pid}/members", json={"username": "alice"}, headers=auth).status_code == 400
    assert client.delete(f"/api/projects/{pid}/members/1", headers=auth).status_code == 400   # owner stays
    assert client.delete(f"/api/projects/{pid}/members/99", headers=auth).status_code == 404

    # an assigned task loses its assignee when the member leaves
    task = client.post("/api/tasks", json={"title": "t", "project_id": pid, "assignee_id": 2}, headers=auth)
    assert task.get_json()["task"]["assignee"]["username"] == "bob"
    left = client.delete(f"/api/projects/{pid}/members/2", headers=bob)        # bob leaves himself
    assert left.status_code == 200
    tid = task.get_json()["task"]["id"]
    assert client.get(f"/api/tasks/{tid}", headers=auth).get_json()["task"]["assignee"] is None
    assert client.get(f"/api/projects/{pid}/members", headers=bob).status_code in (404, 405)


def test_non_owner_cannot_remove_others(client, auth, bob, make_project):
    from tests.conftest import register
    carol = register(client, "carol")
    project = make_project()
    for name in ("bob", "carol"):
        client.post(f"/api/projects/{project['id']}/members", json={"username": name}, headers=auth)
    assert client.delete(f"/api/projects/{project['id']}/members/3", headers=bob).status_code == 403
    assert client.delete(f"/api/projects/{project['id']}/members/3", headers=auth).status_code == 200
    assert client.get("/api/projects", headers=carol).get_json()["projects"] == []


def test_labels(client, auth, bob, make_task):
    created = client.post("/api/labels", json={"name": "urgent", "color": "#ef4444"}, headers=auth)
    assert created.status_code == 201
    label = created.get_json()["label"]
    assert client.post("/api/labels", json={"name": "URGENT"}, headers=auth).status_code == 409
    assert client.post("/api/labels", json={"name": "two words"}, headers=auth).status_code == 400
    assert client.post("/api/labels", json={"name": "x", "color": "blue"}, headers=auth).status_code == 400
    auto = client.post("/api/labels", json={"name": "later"}, headers=auth).get_json()["label"]
    assert auto["color"].startswith("#")

    make_task(label_ids=[label["id"]])
    labels = client.get("/api/labels", headers=auth).get_json()["labels"]
    assert [lb["name"] for lb in labels] == ["later", "urgent"] and labels[1]["open_count"] == 1

    upd = client.patch(f"/api/labels/{label['id']}", json={"name": "asap", "color": "#000000"}, headers=auth)
    assert upd.get_json()["label"]["name"] == "asap"
    assert client.patch(f"/api/labels/{label['id']}", json={"name": "a"}, headers=bob).status_code == 404
    assert client.delete(f"/api/labels/{label['id']}", headers=auth).status_code == 204
    assert client.get("/api/tasks", headers=auth).get_json()["tasks"][0]["labels"] == []
