"""Profile, sidebar bootstrap, activity feed, search, analytics, focus sessions and export."""
import csv
import io
import json
from collections import Counter
from datetime import datetime, timedelta

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import or_

from .auth import login_required
from .models import TASK_STATUSES, Activity, FocusSession, Label, Project, Task, db
from .observability import FOCUS_MINUTES
from .projects import user_projects
from .services import get_task, json_body, member_project_ids, today, visible_tasks
from .validation import ValidationError, validate_profile

insights_bp = Blueprint("insights", __name__, url_prefix="/api")


@insights_bp.get("/me")
@login_required
def me():
    return jsonify(user=g.user.to_dict())


@insights_bp.patch("/me")
@login_required
def update_me():
    for key, value in validate_profile(json_body()).items():
        setattr(g.user, key, value or None if key == "display_name" else value)
    db.session.commit()
    return jsonify(user=g.user.to_dict())


def view_counts(user):
    t = today()
    open_q = visible_tasks(user).filter(Task.status != "done")
    start = datetime.combine(t, datetime.min.time())
    return {
        "inbox": open_q.filter(Task.project_id.is_(None)).count(),
        "today": open_q.filter(Task.due_date <= t).count(),
        "upcoming": open_q.filter(Task.due_date >= t, Task.due_date <= t + timedelta(days=13)).count(),
        "overdue": open_q.filter(Task.due_date < t).count(),
        "assigned": open_q.filter(Task.assignee_id == user.id).count(),
        "completed_today": visible_tasks(user).filter(Task.completed_at >= start).count(),
    }


@insights_bp.get("/bootstrap")
@login_required
def bootstrap():
    labels = Label.query.filter_by(owner_id=g.user.id).order_by(Label.name).all()
    return jsonify(user=g.user.to_dict(), projects=[p.to_dict(g.user) for p in user_projects(g.user)],
                   labels=[lb.to_dict() for lb in labels], counts=view_counts(g.user))


@insights_bp.get("/activity")
@login_required
def activity():
    limit = min(max(int(request.args.get("limit", 30)), 1), 200)
    visible_ids = visible_tasks(g.user).with_entities(Task.id)
    items = (Activity.query.filter(or_(Activity.task_id.in_(visible_ids), Activity.actor_id == g.user.id))
             .filter(Activity.task_id.isnot(None))
             .order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit).all())
    return jsonify(activity=[a.to_dict(with_task=True) for a in items])


@insights_bp.get("/search")
@login_required
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify(tasks=[], projects=[], labels=[])
    like = f"%{q}%"
    tasks = (visible_tasks(g.user).filter(or_(Task.title.ilike(like), Task.description.ilike(like)))
             .order_by(Task.status == "done", Task.updated_at.desc()).limit(8).all())
    projects = [p for p in user_projects(g.user) if q.lower() in p.name.lower()][:5]
    labels = Label.query.filter(Label.owner_id == g.user.id, Label.name.ilike(like)).limit(5).all()
    return jsonify(tasks=[t.to_dict() for t in tasks], projects=[p.to_dict(g.user) for p in projects],
                   labels=[lb.to_dict() for lb in labels])


def _streaks(done_days, t):
    current = 0
    day = t if t in done_days else t - timedelta(days=1)   # today not finished yet is fine
    while day in done_days:
        current += 1
        day -= timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(done_days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return {"current": current, "best": max(best, current)}


@insights_bp.get("/analytics")
@login_required
def analytics():
    days = min(max(int(request.args.get("days", 30)), 7), 90)
    t = today()
    start = t - timedelta(days=days - 1)
    tasks = visible_tasks(g.user).all()
    done = [x for x in tasks if x.status == "done" and x.completed_at]
    open_ = [x for x in tasks if x.status != "done"]

    completed = Counter(x.completed_at.date() for x in done)
    created = Counter(x.created_at.date() for x in tasks)
    sessions = FocusSession.query.filter(FocusSession.user_id == g.user.id).all()
    focus = Counter()
    for s in sessions:
        focus[s.ended_at.date()] += s.minutes
    span = [start + timedelta(days=i) for i in range(days)]

    heatmap = [[0] * 24 for _ in range(7)]
    for x in done:
        if x.completed_at.date() >= start:
            heatmap[x.completed_at.weekday()][x.completed_at.hour] += 1

    with_due = [x for x in done if x.due_date]
    on_time = sum(1 for x in with_due if x.completed_at.date() <= x.due_date)
    durations = [(x.completed_at - x.created_at).total_seconds() / 3600 for x in done]

    by_project = {}
    for x in tasks:
        key = x.project_id
        if key not in by_project:
            p = x.project
            by_project[key] = {"id": key, "name": p.name if p else "Inbox", "color": p.color if p else "#64748b",
                               "icon": p.icon if p else "📥", "open": 0, "done": 0}
        by_project[key]["done" if x.status == "done" else "open"] += 1

    week_start = t - timedelta(days=t.weekday())
    return jsonify(
        days=days,
        totals={
            "open": len(open_), "done": len(done),
            "overdue": sum(1 for x in open_ if x.is_overdue),
            "due_today": sum(1 for x in open_ if x.due_date == t),
            "focus_minutes": sum(focus[d] for d in span),
            "completed_this_week": sum(1 for x in done if x.completed_at.date() >= week_start),
        },
        completed_per_day=[{"date": d.isoformat(), "count": completed[d]} for d in span],
        created_per_day=[{"date": d.isoformat(), "count": created[d]} for d in span],
        focus_per_day=[{"date": d.isoformat(), "minutes": focus[d]} for d in span],
        by_priority={str(p): sum(1 for x in open_ if x.priority == p) for p in (1, 2, 3, 4)},
        by_status={s: sum(1 for x in tasks if x.status == s) for s in TASK_STATUSES},
        by_project=sorted(by_project.values(), key=lambda r: -(r["open"] + r["done"])),
        heatmap=heatmap,
        streak=_streaks(set(completed), t),
        on_time_rate=round(on_time / len(with_due), 3) if with_due else None,
        avg_completion_hours=round(sum(durations) / len(durations), 1) if durations else None,
    )


@insights_bp.post("/focus")
@login_required
def log_focus():
    data = json_body()
    try:
        minutes = int(data.get("minutes"))
        if not 1 <= minutes <= 240:
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError({"minutes": "Minutes must be 1-240."})
    task_id = data.get("task_id")
    task = get_task(int(task_id)) if task_id else None
    session = FocusSession(user_id=g.user.id, task=task, minutes=minutes)
    db.session.add(session)
    db.session.commit()
    FOCUS_MINUTES.inc(minutes)
    start = datetime.combine(today(), datetime.min.time())
    total = sum(s.minutes for s in FocusSession.query.filter(FocusSession.user_id == g.user.id,
                                                             FocusSession.ended_at >= start))
    return jsonify(session=session.to_dict(), today_minutes=total), 201


EXPORT_FIELDS = ["id", "title", "description", "status", "priority", "due_date", "due_time", "recurrence",
                 "estimate_minutes", "project", "labels", "assignee", "completed_at", "created_at"]


def _export_rows():
    for t in visible_tasks(g.user).order_by(Task.id):
        d = t.to_dict()
        d["project"] = d["project"]["name"] if d["project"] else "Inbox"
        d["labels"] = " ".join(lb["name"] for lb in d["labels"])
        d["assignee"] = d["assignee"]["username"] if d["assignee"] else ""
        yield {k: d[k] for k in EXPORT_FIELDS}


@insights_bp.get("/export.json")
@login_required
def export_json():
    payload = {"exported_at": datetime.utcnow().isoformat() + "Z", "user": g.user.username,
               "projects": [p.lite() for p in Project.query.filter(Project.id.in_(member_project_ids(g.user)))],
               "tasks": list(_export_rows())}
    return Response(json.dumps(payload, indent=2, ensure_ascii=False), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=orbit-tasks.json"})


@insights_bp.get("/export.csv")
@login_required
def export_csv():
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    writer.writerows(_export_rows())
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=orbit-tasks.csv"})
