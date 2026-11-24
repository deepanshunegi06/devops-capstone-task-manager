"""Realistic demo workspace for presentations, screenshots and the Kubernetes demo.

    flask --app wsgi seed-demo                 # prints the generated password
    DEMO_DATA=true DEMO_PASSWORD=... (env)     # seeds automatically at start-up (idempotent)

Creates user `demo` with 4 projects, labels, teammates, ~50 tasks (subtasks, comments, recurring
tasks), and 6 weeks of completion + focus history so every chart in Analytics has data.
"""
import random
import secrets
from datetime import date, datetime, time, timedelta

import click

from .models import (Activity, Comment, FocusSession, Label, Project, ProjectMember, Subtask, Task, User, db)

PROJECTS = [
    ("Capstone Project", "🚀", "#6d5cff"),
    ("Website Redesign", "🎨", "#ec4899"),
    ("Personal", "🏡", "#10b981"),
    ("Learning", "📚", "#f59e0b"),
]
LABELS = [("urgent", "#ef4444"), ("backend", "#3b82f6"), ("frontend", "#ec4899"), ("devops", "#6d5cff"),
          ("reading", "#f59e0b"), ("health", "#10b981"), ("errand", "#64748b"), ("meeting", "#14b8a6")]

# (project index or None, title, priority, labels, due offset days or None, status, recurrence, subtasks)
OPEN_TASKS = [
    (0, "Record the 12-minute demo video", 1, ["urgent"], 1, "todo", None,
     ["Write the script", "Record terminal walkthrough", "Edit and export 1080p"]),
    (0, "Final review of the technical report", 1, ["urgent"], 0, "in_progress", None,
     ["Proofread chapters 1-4", "Insert Grafana and Kibana screenshots", "Export to PDF"]),
    (0, "Blue-green switch rehearsal on minikube", 2, ["devops"], 2, "todo", None, []),
    (0, "Tune HPA thresholds after load test", 3, ["devops", "backend"], 5, "todo", None, []),
    (0, "Add Slack alert for failed quality gate", 3, ["devops"], 8, "todo", None, []),
    (0, "Prepare viva questions on GitOps", 2, ["reading"], 3, "in_progress", None,
     ["ArgoCD sync waves", "Self-heal vs prune", "Rollback strategies"]),
    (0, "Fix flaky Trivy timeout in pipeline", 2, ["devops"], -2, "todo", None, []),
    (1, "Design new onboarding flow", 2, ["frontend"], 4, "in_progress", None,
     ["Wireframes", "Hi-fi mockups", "Usability test with 3 users"]),
    (1, "Migrate icons to SVG sprite", 3, ["frontend"], 6, "todo", None, []),
    (1, "Dark mode contrast audit", 3, ["frontend"], 9, "todo", None, []),
    (1, "Client feedback call", 2, ["meeting"], 1, "todo", None, []),
    (1, "Optimise hero images (WebP)", 4, ["frontend"], None, "todo", None, []),
    (2, "Gym - leg day", 3, ["health"], 0, "todo", "weekly", []),
    (2, "Pay electricity bill", 1, ["errand"], 0, "todo", "monthly", []),
    (2, "Call grandparents", 3, [], 2, "todo", "weekly", []),
    (2, "Renew passport", 2, ["errand"], 12, "todo", None, ["Book appointment", "Collect documents"]),
    (2, "Plan weekend trek", 4, [], 5, "todo", None, []),
    (3, "Read 'Accelerate' - chapter 4", 3, ["reading"], 1, "todo", "daily", []),
    (3, "Finish CKA practice exam", 2, ["devops"], 7, "todo", None, []),
    (3, "Terraform associate notes", 4, ["reading", "devops"], None, "todo", None, []),
    (None, "Buy a new notebook", 4, ["errand"], None, "todo", None, []),
    (None, "Reply to placement cell email", 2, [], 0, "todo", None, []),
    (None, "Back up laptop", 3, [], -1, "todo", None, []),
]
DONE_TITLES = [
    "Write Jenkinsfile", "Configure SonarQube quality gate", "Containerise Flask app", "Write Helm chart",
    "Set up ArgoCD application", "Grafana dashboard as code", "Fluentd DaemonSet config", "Terraform VPC module",
    "Ansible kubeadm role", "Unit tests for quick add parser", "Kanban drag and drop", "Calendar view",
    "Analytics charts", "Pomodoro timer", "Command palette", "Landing page copy", "Logo exploration",
    "Accessibility pass", "Morning run", "Groceries", "Laundry", "Read DevOps Handbook ch.2", "Mock interview",
    "Fix login redirect bug", "Rotate Docker Hub token", "Add NetworkPolicies", "Weekly review",
]
COMMENTS = ["Looks good - merging after the pipeline goes green.", "Can we demo this on Friday?",
            "Pushed a fix, please re-check.", "Added screenshots to the report draft.",
            "Blocked until the cluster is back up."]


def _user(username, display, color, password):
    user = User.query.filter_by(username=username).first()
    if user:
        return user, False
    user = User(username=username, display_name=display, avatar_color=color)
    user.set_password(password)
    db.session.add(user)
    return user, True


def seed_demo(app, password=None):
    if User.query.filter_by(username="demo").first():
        return None
    rnd = random.Random(2301350026)  # nosec B311
    password = password or app.config.get("DEMO_PASSWORD") or secrets.token_urlsafe(9)
    demo, _ = _user("demo", "Deepanshu Negi", "#6d5cff", password)
    aisha, _ = _user("aisha", "Aisha Khan", "#ec4899", secrets.token_urlsafe(16))
    rohan, _ = _user("rohan", "Rohan Mehta", "#14b8a6", secrets.token_urlsafe(16))
    db.session.flush()

    projects = []
    for i, (name, icon, color) in enumerate(PROJECTS):
        p = Project(name=name, icon=icon, color=color, owner_id=demo.id)
        p.members.append(ProjectMember(user_id=demo.id, role="owner"))
        if i == 0:
            p.members.append(ProjectMember(user_id=aisha.id, role="editor"))
            p.members.append(ProjectMember(user_id=rohan.id, role="viewer"))
        if i == 1:
            p.members.append(ProjectMember(user_id=aisha.id, role="editor"))
        db.session.add(p)
        projects.append(p)
    labels = {name: Label(name=name, color=color, owner_id=demo.id) for name, color in LABELS}
    db.session.add_all(labels.values())
    db.session.flush()

    today = date.today()
    now = datetime.now().replace(microsecond=0)
    for n, (pi, title, prio, lbls, due, status, rec, subs) in enumerate(OPEN_TASKS):
        project = projects[pi] if pi is not None else None
        t = Task(title=title, priority=prio, status=status, recurrence=rec, user_id=demo.id, project=project,
                 due_date=today + timedelta(days=due) if due is not None else None,
                 due_time=rnd.choice([None, None, "09:00", "11:30", "17:00", "19:30"]),
                 estimate_minutes=rnd.choice([None, 25, 30, 45, 60, 90]), position=(n + 1) * 1000.0,
                 description=rnd.choice(["", "", "Keep it short and demo-friendly.",
                                         "Acceptance: works on minikube and on the AWS cluster.",
                                         "See the runbook in docs/SETUP_GUIDE.md for the exact steps."]),
                 created_at=now - timedelta(days=rnd.randint(1, 14), hours=rnd.randint(0, 10)))
        t.labels = [labels[x] for x in lbls]
        if pi == 0 and n % 3 == 0:
            t.assignee = aisha
        elif pi in (0, 1):
            t.assignee = demo
        t.subtasks = [Subtask(title=s, done=j == 0 and status == "in_progress", position=(j + 1) * 1000.0)
                      for j, s in enumerate(subs)]
        t.pinned = n == 1
        db.session.add(t)
        db.session.flush()
        db.session.add(Activity(task=t, actor_id=demo.id, action="created", detail=title, created_at=t.created_at))
        if n % 4 == 0:
            author = aisha if pi in (0, 1) else demo
            db.session.add(Comment(task=t, author_id=author.id, body=rnd.choice(COMMENTS),
                                   created_at=t.created_at + timedelta(hours=5)))

    # six weeks of completed work - more on weekdays, peaks late morning and evening
    for d in range(42, -1, -1):
        day = today - timedelta(days=d)
        if rnd.random() < (0.12 if day.weekday() >= 5 else 0.04) and d > 2:
            continue                                   # a few rest days so streaks are realistic
        for _ in range(rnd.randint(1, 4 if day.weekday() < 5 else 2)):
            hour = rnd.choice([9, 10, 11, 11, 12, 14, 15, 16, 19, 20, 21, 22])
            if day == today and hour > now.hour:
                hour = max(now.hour - 1, 0)
            done_at = datetime.combine(day, time(hour, rnd.randint(0, 59)))
            created = done_at - timedelta(hours=rnd.randint(3, 96))
            pi = rnd.choice([0, 0, 0, 1, 1, 2, 3, None])
            due = (done_at.date() + timedelta(days=rnd.choice([-1, 0, 0, 1, 2]))) if rnd.random() < 0.8 else None
            t = Task(title=rnd.choice(DONE_TITLES), status="done", priority=rnd.choice([1, 2, 2, 3, 3, 4]),
                     user_id=demo.id, project=projects[pi] if pi is not None else None, due_date=due,
                     completed_at=done_at, created_at=created, updated_at=done_at,
                     labels=[labels[rnd.choice(list(labels))]])
            db.session.add(t)
            db.session.flush()
            db.session.add(Activity(task=t, actor_id=demo.id, action="completed", detail=t.title,
                                    created_at=done_at))
        if d <= 30 and rnd.random() < 0.75:
            for _ in range(rnd.randint(1, 4)):
                db.session.add(FocusSession(user_id=demo.id, minutes=rnd.choice([25, 25, 25, 50]),
                                            ended_at=datetime.combine(day, time(rnd.randint(8, 22), 0))))
    db.session.commit()
    app.logger.info("demo workspace seeded", extra={"user": "demo"})
    return password


def register_cli(app):
    @app.cli.command("seed-demo")
    @click.option("--password", default=None, help="Password for the demo user (random if omitted).")
    def seed_demo_command(password):
        """Create the demo workspace (user `demo`)."""
        result = seed_demo(app, password)
        if result is None:
            click.echo("Demo user already exists - nothing to do.")
        else:
            click.echo(f"Demo workspace ready. Log in as demo / {result}")
