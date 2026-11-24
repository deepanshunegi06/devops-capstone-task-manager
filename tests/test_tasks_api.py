from datetime import date, timedelta

from tests.conftest import register

TODAY = date.today()


def d(days):
    return (TODAY + timedelta(days=days)).isoformat()


def test_requires_auth(client):
    assert client.get("/api/tasks").status_code == 401


def test_crud_lifecycle(client, auth, make_task):
    task = make_task(description="CI pipeline", due_date="2030-01-01", due_time="09:30", priority=1,
                     recurrence="weekly", estimate_minutes=45, pinned=True)
    assert task["status"] == "todo" and task["priority"] == 1 and task["pinned"] is True
    assert task["due_time"] == "09:30" and task["recurrence"] == "weekly" and task["estimate_minutes"] == 45
    assert task["project"] is None and task["creator"]["username"] == "alice"

    assert client.get("/api/tasks", headers=auth).get_json()["count"] == 1
    detail = client.get(f"/api/tasks/{task['id']}", headers=auth).get_json()["task"]
    assert detail["activity"][0]["action"] == "created" and detail["subtasks"] == []

    patched = client.patch(f"/api/tasks/{task['id']}", json={"status": "in_progress", "priority": 2,
                                                             "due_date": None, "recurrence": "none",
                                                             "description": "x", "estimate_minutes": ""},
                           headers=auth).get_json()["task"]
    assert patched["status"] == "in_progress" and patched["due_date"] is None and patched["recurrence"] is None

    put = client.put(f"/api/tasks/{task['id']}?detail=1", json={"title": "Renamed", "position": 5},
                     headers=auth).get_json()["task"]
    assert put["title"] == "Renamed" and put["position"] == 5 and "activity" in put
    assert any("priority → P2" in a["detail"] for a in put["activity"])

    assert client.delete(f"/api/tasks/{task['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task['id']}", headers=auth).status_code == 404
    restored = client.post(f"/api/tasks/{task['id']}/restore", headers=auth)
    assert restored.status_code == 200 and restored.get_json()["task"]["title"] == "Renamed"


def test_validation_errors(client, auth):
    resp = client.post("/api/tasks", json={"title": "", "status": "nope", "priority": 9, "due_date": "31-12-2030",
                                           "due_time": "25:00", "recurrence": "hourly", "estimate_minutes": -5},
                       headers=auth)
    assert resp.status_code == 400
    assert set(resp.get_json()["fields"]) == {"title", "status", "priority", "due_date", "due_time",
                                              "recurrence", "estimate_minutes"}
    assert client.post("/api/tasks", json={"title": 5}, headers=auth).status_code == 400
    assert client.post("/api/tasks", json={"title": "x" * 201}, headers=auth).status_code == 400
    assert client.post("/api/tasks", json={"title": "a", "priority": True}, headers=auth).status_code == 400
    assert client.post("/api/tasks", json={"title": "a", "estimate_minutes": "abc"}, headers=auth).status_code == 400


def test_non_json_body(client, auth, make_task):
    assert client.post("/api/tasks", data="not json", headers=auth).status_code == 400
    task = make_task()
    assert client.put(f"/api/tasks/{task['id']}", data="x", headers=auth).status_code == 400
    assert client.post("/api/tasks", json=[1, 2], headers=auth).status_code == 400


def test_put_requires_title_patch_does_not(client, auth, make_task):
    task = make_task()
    assert client.put(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth).status_code == 400
    assert client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth).status_code == 200


def test_smart_views(client, auth, make_task, make_project):
    project = make_project()
    make_task(title="overdue", due_date=d(-2))
    make_task(title="today", due_date=d(0))
    make_task(title="soon", due_date=d(3), project_id=project["id"])
    make_task(title="someday")
    done = make_task(title="finished", due_date=d(0))
    client.post(f"/api/tasks/{done['id']}/complete", json={"done": True}, headers=auth)

    def titles(query):
        return sorted(t["title"] for t in client.get(f"/api/tasks?{query}", headers=auth).get_json()["tasks"])

    assert titles("view=today") == ["overdue", "today"]
    assert titles("view=overdue") == ["overdue"]
    assert titles("view=upcoming") == ["soon", "today"]
    assert titles("view=inbox") == ["overdue", "someday", "today"]
    assert titles("view=completed") == ["finished"]
    assert titles(f"project_id={project['id']}") == ["soon"]
    assert "finished" in titles("include_done=1")
    assert titles("status=done") == ["finished"]
    assert client.get("/api/tasks?view=bogus", headers=auth).status_code == 400
    assert client.get("/api/tasks?status=bogus", headers=auth).status_code == 400
    # ordering: dated tasks first (earliest first), undated last
    ordered = [t["title"] for t in client.get("/api/tasks", headers=auth).get_json()["tasks"]]
    assert ordered == ["overdue", "today", "soon", "someday"]


def test_filters_search_priority_labels(client, auth, make_task):
    label = client.post("/api/labels", json={"name": "devops"}, headers=auth).get_json()["label"]
    make_task(title="Dockerfile", priority=1, label_ids=[label["id"]], description="multi-stage")
    make_task(title="Helm chart")
    assert client.get("/api/tasks?q=docker", headers=auth).get_json()["count"] == 1
    assert client.get("/api/tasks?q=multi", headers=auth).get_json()["count"] == 1
    assert client.get("/api/tasks?priority=1", headers=auth).get_json()["count"] == 1
    tasks = client.get(f"/api/tasks?label_id={label['id']}", headers=auth).get_json()["tasks"]
    assert [t["title"] for t in tasks] == ["Dockerfile"] and tasks[0]["labels"][0]["name"] == "devops"
    bad = client.post("/api/tasks", json={"title": "x", "label_ids": [999]}, headers=auth)
    assert bad.status_code == 400
    assert client.post("/api/tasks", json={"title": "x", "label_ids": "1"}, headers=auth).status_code == 400


def test_quick_add_and_parse(client, auth, make_project, bob):
    project = make_project(name="Capstone Project")
    client.post(f"/api/projects/{project['id']}/members", json={"username": "bob", "role": "editor"}, headers=auth)

    preview = client.post("/api/tasks/parse", json={"text": "Demo tomorrow 10am #capstoneproject @urgent p1 +bob"},
                          headers=auth).get_json()["parsed"]
    assert preview["project"]["name"] == "Capstone Project" and preview["assignee"]["username"] == "bob"
    assert preview["due_date"] == d(1) and preview["due_time"] == "10:00" and preview["labels"] == ["urgent"]
    assert client.get("/api/tasks", headers=auth).get_json()["count"] == 0          # parse does not create

    resp = client.post("/api/tasks/quick", json={"text": "Demo tomorrow 10am #capstoneproject @urgent p1 ~30m +bob"},
                       headers=auth)
    task = resp.get_json()["task"]
    assert resp.status_code == 201 and task["title"] == "Demo" and task["priority"] == 1
    assert task["project"]["id"] == project["id"] and task["assignee"]["username"] == "bob"
    assert task["labels"][0]["name"] == "urgent" and task["estimate_minutes"] == 30
    # existing label is reused, unknown project stays in the title, assignee outside the project is ignored
    register(client, "carol")
    task2 = client.post("/api/tasks/quick", json={"text": "Read @URGENT #nowhere +carol"}, headers=auth).get_json()
    assert task2["task"]["labels"][0]["id"] == task["labels"][0]["id"]
    assert task2["task"]["title"] == "Read #nowhere" and task2["task"]["assignee"] is None
    # default project from the current view
    task3 = client.post("/api/tasks/quick", json={"text": "Inside project", "project_id": project["id"]},
                        headers=auth).get_json()["task"]
    assert task3["project"]["id"] == project["id"]
    # unique prefix match: "#capstone" -> "Capstone Project"; ambiguous prefixes are not matched
    prefixed = client.post("/api/tasks/quick", json={"text": "Prefix #capstone"}, headers=auth).get_json()["task"]
    assert prefixed["project"]["id"] == project["id"]
    client.post("/api/projects", json={"name": "Capstone Two"}, headers=auth)
    ambiguous = client.post("/api/tasks/quick", json={"text": "Amb #capstone"}, headers=auth).get_json()["task"]
    assert ambiguous["project"] is None and ambiguous["title"] == "Amb #capstone"
    assert client.post("/api/tasks/quick", json={"text": "  p1 "}, headers=auth).status_code == 400


def test_complete_and_recurrence(client, auth, make_task):
    task = make_task(title="Standup", due_date=d(0), recurrence="daily", priority=2)
    client.post(f"/api/tasks/{task['id']}/subtasks", json={"title": "notes"}, headers=auth)
    resp = client.post(f"/api/tasks/{task['id']}/complete", json={"done": True}, headers=auth).get_json()
    assert resp["task"]["status"] == "done" and resp["task"]["completed_at"]
    nxt = resp["next_task"]
    assert nxt["due_date"] == d(1) and nxt["recurrence"] == "daily" and nxt["subtasks_total"] == 1
    # completing again is a no-op, reopening works
    again = client.post(f"/api/tasks/{task['id']}/complete", json={"done": True}, headers=auth).get_json()
    assert again["next_task"] is None
    reopened = client.post(f"/api/tasks/{task['id']}/complete", json={"done": False}, headers=auth).get_json()
    assert reopened["task"]["status"] == "todo" and reopened["task"]["completed_at"] is None


def test_duplicate_and_reorder(client, auth, make_task):
    a = make_task(title="A")
    client.post(f"/api/tasks/{a['id']}/subtasks", json={"title": "s1"}, headers=auth)
    copy = client.post(f"/api/tasks/{a['id']}/duplicate", headers=auth).get_json()["task"]
    assert copy["title"] == "A (copy)" and copy["subtasks_total"] == 1
    b = make_task(title="B")
    resp = client.post("/api/tasks/reorder", json={"ids": [b["id"], a["id"]], "status": "in_progress"}, headers=auth)
    tasks = resp.get_json()["tasks"]
    assert [t["title"] for t in tasks] == ["B", "A"] and all(t["status"] == "in_progress" for t in tasks)
    assert tasks[0]["position"] < tasks[1]["position"]
    assert client.post("/api/tasks/reorder", json={"ids": []}, headers=auth).status_code == 400
    assert client.post("/api/tasks/reorder", json={"ids": [a["id"]], "status": "x"}, headers=auth).status_code == 400
    assert client.post("/api/tasks/reorder", json={"ids": [9999]}, headers=auth).status_code == 404


def test_subtasks(client, auth, make_task):
    task = make_task()
    sub = client.post(f"/api/tasks/{task['id']}/subtasks", json={"title": "write tests"}, headers=auth)
    assert sub.status_code == 201
    sid = sub.get_json()["subtask"]["id"]
    assert client.post(f"/api/tasks/{task['id']}/subtasks", json={"title": ""}, headers=auth).status_code == 400
    done = client.patch(f"/api/subtasks/{sid}", json={"done": True, "title": "write more tests"}, headers=auth)
    assert done.get_json()["subtask"] == {"id": sid, "task_id": task["id"], "title": "write more tests",
                                          "done": True, "position": 1000.0}
    assert client.patch(f"/api/subtasks/{sid}", json={"title": " "}, headers=auth).status_code == 400
    listed = client.get("/api/tasks", headers=auth).get_json()["tasks"][0]
    assert listed["subtasks_total"] == 1 and listed["subtasks_done"] == 1
    assert client.delete(f"/api/subtasks/{sid}", headers=auth).status_code == 204
    assert client.delete(f"/api/subtasks/{sid}", headers=auth).status_code == 404


def test_comments(client, auth, bob, make_task, make_project):
    project = make_project()
    client.post(f"/api/projects/{project['id']}/members", json={"username": "bob", "role": "viewer"}, headers=auth)
    task = make_task(project_id=project["id"])
    mine = client.post(f"/api/tasks/{task['id']}/comments", json={"body": "Looks good"}, headers=auth)
    assert mine.status_code == 201 and mine.get_json()["comment"]["author"]["username"] == "alice"
    theirs = client.post(f"/api/tasks/{task['id']}/comments", json={"body": "viewer can comment"}, headers=bob)
    assert theirs.status_code == 201
    assert client.post(f"/api/tasks/{task['id']}/comments", json={"body": ""}, headers=auth).status_code == 400
    assert client.delete(f"/api/comments/{theirs.get_json()['comment']['id']}", headers=auth).status_code == 403
    assert client.delete(f"/api/comments/{mine.get_json()['comment']['id']}", headers=auth).status_code == 204
    assert client.delete("/api/comments/999", headers=auth).status_code == 404
    detail = client.get(f"/api/tasks/{task['id']}", headers=auth).get_json()["task"]
    assert detail["comments_count"] == 1 and detail["comments"][0]["body"] == "viewer can comment"


def test_isolation_and_roles(client, auth, bob, make_task, make_project):
    private = make_task(title="mine")
    assert client.get(f"/api/tasks/{private['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/tasks/{private['id']}", headers=bob).status_code == 404
    assert client.get("/api/tasks", headers=bob).get_json()["count"] == 0

    project = make_project()
    shared = make_task(title="shared", project_id=project["id"])
    client.post(f"/api/projects/{project['id']}/members", json={"username": "bob", "role": "viewer"}, headers=auth)
    assert client.get(f"/api/tasks/{shared['id']}", headers=bob).status_code == 200
    assert client.patch(f"/api/tasks/{shared['id']}", json={"title": "x"}, headers=bob).status_code == 403
    assert client.post("/api/tasks", json={"title": "x", "project_id": project["id"]}, headers=bob).status_code == 403
    assert client.post("/api/tasks/quick", json={"text": "x", "project_id": project["id"]},
                       headers=bob).status_code == 403
    assert client.post("/api/tasks/reorder", json={"ids": [shared["id"]]}, headers=bob).status_code == 403

    client.post(f"/api/projects/{project['id']}/members", json={"username": "bob", "role": "editor"}, headers=auth)
    assert client.patch(f"/api/tasks/{shared['id']}", json={"assignee_id": 2}, headers=bob).status_code == 200


def test_assignee_rules(client, auth, bob, make_task, make_project):
    me = client.get("/api/me", headers=auth).get_json()["user"]
    inbox = make_task(assignee_id=me["id"])
    assert inbox["assignee"]["username"] == "alice"
    assert client.post("/api/tasks", json={"title": "x", "assignee_id": 2}, headers=auth).status_code == 400
    assert client.post("/api/tasks", json={"title": "x", "assignee_id": 99}, headers=auth).status_code == 400
    project = make_project()
    client.post(f"/api/projects/{project['id']}/members", json={"username": "bob"}, headers=auth)
    task = make_task(project_id=project["id"], assignee_id=2)
    assert task["assignee"]["username"] == "bob"
    assert client.get("/api/tasks?view=assigned", headers=bob).get_json()["count"] == 1
    # moving to the Inbox drops an assignee who has no access there
    moved = client.patch(f"/api/tasks/{task['id']}", json={"project_id": None}, headers=auth).get_json()["task"]
    assert moved["project"] is None and moved["assignee"] is None
    unassigned = client.patch(f"/api/tasks/{inbox['id']}", json={"assignee_id": None}, headers=auth).get_json()
    assert unassigned["task"]["assignee"] is None


def test_move_between_projects_drops_foreign_assignee(client, auth, bob, make_task, make_project):
    p1 = make_project(name="One")
    p2 = make_project(name="Two")
    client.post(f"/api/projects/{p1['id']}/members", json={"username": "bob"}, headers=auth)
    task = make_task(project_id=p1["id"], assignee_id=2)
    moved = client.patch(f"/api/tasks/{task['id']}", json={"project_id": p2["id"]}, headers=auth).get_json()["task"]
    assert moved["project"]["name"] == "Two" and moved["assignee"] is None


def test_overdue_flag_and_stats(client, auth, make_task):
    task = make_task(due_date="2000-01-01", priority=1)
    assert task["overdue"] is True
    client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth)
    make_task()
    body = client.get("/api/stats", headers=auth).get_json()
    assert body["total"] == 2 and body["counts"]["done"] == 1 and body["open_by_priority"]["4"] == 1
