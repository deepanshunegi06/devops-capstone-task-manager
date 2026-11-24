import csv
import io
from datetime import date, datetime, timedelta

from taskmanager.insights import _streaks
from taskmanager.models import Task, db


def test_me_and_profile(client, auth):
    me = client.get("/api/me", headers=auth).get_json()["user"]
    assert me["username"] == "alice" and me["initials"] == "AL" and me["theme"] == "system"
    upd = client.patch("/api/me", json={"display_name": "Alice Wong", "theme": "dark", "avatar_color": "#10b981"},
                       headers=auth).get_json()["user"]
    assert upd["display_name"] == "Alice Wong" and upd["initials"] == "AW" and upd["theme"] == "dark"
    bad = client.patch("/api/me", json={"theme": "neon", "avatar_color": "x"}, headers=auth)
    assert set(bad.get_json()["fields"]) == {"theme", "avatar_color"}
    cleared = client.patch("/api/me", json={"display_name": ""}, headers=auth).get_json()["user"]
    assert cleared["display_name"] == "alice"


def test_bootstrap_counts(client, auth, make_task, make_project):
    project = make_project()
    today = date.today()
    make_task(due_date=today.isoformat())
    make_task(due_date=(today - timedelta(days=1)).isoformat())
    make_task(due_date=(today + timedelta(days=2)).isoformat(), project_id=project["id"])
    done = make_task()
    client.post(f"/api/tasks/{done['id']}/complete", headers=auth)
    body = client.get("/api/bootstrap", headers=auth).get_json()
    assert body["user"]["username"] == "alice" and body["projects"][0]["name"] == "Capstone"
    assert body["counts"] == {"inbox": 2, "today": 2, "upcoming": 2, "overdue": 1, "assigned": 0,
                              "completed_today": 1}


def test_activity_feed(client, auth, make_task):
    task = make_task(title="Feed me")
    client.patch(f"/api/tasks/{task['id']}", json={"priority": 1}, headers=auth)
    client.post(f"/api/tasks/{task['id']}/complete", headers=auth)
    feed = client.get("/api/activity?limit=10", headers=auth).get_json()["activity"]
    assert [a["action"] for a in feed] == ["completed", "updated", "created"]
    assert feed[0]["task"]["title"] == "Feed me" and feed[0]["actor"]["username"] == "alice"


def test_search(client, auth, make_task, make_project):
    make_project(name="Deploy pipeline")
    make_task(title="Deploy to staging")
    client.post("/api/labels", json={"name": "deploys"}, headers=auth)
    res = client.get("/api/search?q=deploy", headers=auth).get_json()
    assert len(res["tasks"]) == 1 and len(res["projects"]) == 1 and len(res["labels"]) == 1
    assert client.get("/api/search?q=", headers=auth).get_json() == {"tasks": [], "projects": [], "labels": []}


def test_analytics(app, client, auth, make_task):
    today = date.today()
    on_time = make_task(title="on time", due_date=today.isoformat(), priority=1)
    late = make_task(title="late", due_date=(today - timedelta(days=3)).isoformat())
    make_task(title="open", priority=2)
    for t in (on_time, late):
        client.post(f"/api/tasks/{t['id']}/complete", headers=auth)
    with app.app_context():          # back-date one completion to build a 2-day streak
        task = db.session.get(Task, late["id"])
        task.completed_at = datetime.now() - timedelta(days=1)
        db.session.commit()
    client.post("/api/focus", json={"minutes": 25, "task_id": on_time["id"]}, headers=auth)

    a = client.get("/api/analytics?days=7", headers=auth).get_json()
    assert a["days"] == 7 and len(a["completed_per_day"]) == 7 and len(a["heatmap"]) == 7
    assert a["totals"]["open"] == 1 and a["totals"]["done"] == 2 and a["totals"]["focus_minutes"] == 25
    assert a["completed_per_day"][-1]["count"] == 1 and a["created_per_day"][-1]["count"] == 3
    assert a["by_priority"] == {"1": 0, "2": 1, "3": 0, "4": 0}
    assert a["by_status"]["done"] == 2 and a["by_project"][0]["name"] == "Inbox"
    assert a["streak"] == {"current": 2, "best": 2}
    assert a["on_time_rate"] == 0.5 and a["avg_completion_hours"] is not None
    assert sum(map(sum, a["heatmap"])) == 2
    clamp = client.get("/api/analytics?days=1000", headers=auth).get_json()
    assert clamp["days"] == 90
    empty = client.get("/api/analytics", headers={"Authorization": auth["Authorization"]}).get_json()
    assert empty["days"] == 30


def test_streaks():
    t = date(2026, 11, 24)
    days = {t - timedelta(days=i) for i in (1, 2, 3, 7, 8, 9, 10, 11)}
    assert _streaks(days, t) == {"current": 3, "best": 5}
    assert _streaks(set(), t) == {"current": 0, "best": 0}


def test_focus_sessions(client, auth, bob, make_task):
    task = make_task()
    first = client.post("/api/focus", json={"minutes": 25}, headers=auth)
    assert first.status_code == 201 and first.get_json()["today_minutes"] == 25
    second = client.post("/api/focus", json={"minutes": 50, "task_id": task["id"]}, headers=auth).get_json()
    assert second["today_minutes"] == 75
    assert client.get(f"/api/tasks/{task['id']}", headers=auth).get_json()["task"]["focus_minutes"] == 50
    assert client.post("/api/focus", json={"minutes": 0}, headers=auth).status_code == 400
    assert client.post("/api/focus", json={"minutes": "x"}, headers=auth).status_code == 400
    assert client.post("/api/focus", json={"minutes": 5, "task_id": task["id"]}, headers=bob).status_code == 404


def test_export(client, auth, make_task, make_project):
    project = make_project()
    label = client.post("/api/labels", json={"name": "cli"}, headers=auth).get_json()["label"]
    make_task(title="Exported", project_id=project["id"], label_ids=[label["id"]])
    make_task(title="Inbox one")
    js = client.get("/api/export.json", headers=auth)
    assert js.headers["Content-Disposition"].endswith("orbit-tasks.json")
    body = js.get_json()
    assert body["user"] == "alice" and len(body["tasks"]) == 2 and body["projects"][0]["name"] == "Capstone"
    rows = list(csv.DictReader(io.StringIO(client.get("/api/export.csv", headers=auth).data.decode())))
    assert {r["title"] for r in rows} == {"Exported", "Inbox one"}
    assert {r["project"] for r in rows} == {"Capstone", "Inbox"} and "cli" in {r["labels"] for r in rows}


def test_demo_seed(app):
    from taskmanager.demo import seed_demo
    with app.app_context():
        password = seed_demo(app, "demo-password")
        assert password == "demo-password"
        assert seed_demo(app) is None                    # idempotent
    client = app.test_client()
    tok = client.post("/api/auth/login", json={"username": "demo", "password": "demo-password"}).get_json()["token"]
    headers = {"Authorization": f"Bearer {tok}"}
    boot = client.get("/api/bootstrap", headers=headers).get_json()
    assert len(boot["projects"]) == 4 and len(boot["labels"]) == 8
    a = client.get("/api/analytics", headers=headers).get_json()
    assert a["totals"]["done"] > 20 and a["totals"]["focus_minutes"] > 0


def test_seed_demo_cli(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed-demo", "--password", "cli-password"])
    assert "demo / cli-password" in result.output
    assert "already exists" in runner.invoke(args=["seed-demo"]).output


def test_demo_data_env_flag():
    from taskmanager import create_app
    from taskmanager.config import TestConfig

    class DemoConfig(TestConfig):
        DEMO_DATA = True
        DEMO_PASSWORD = "env-demo-password"

    client = create_app(DemoConfig).test_client()
    assert client.post("/api/auth/login", json={"username": "demo", "password": "env-demo-password"}).status_code == 200
