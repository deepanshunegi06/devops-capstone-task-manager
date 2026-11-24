"""Task REST API: smart views, CRUD, quick add, completion + recurrence, ordering, undo,
subtasks and comments. See docs/API.md."""
from datetime import timedelta

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import case, or_

from . import quickadd
from .auth import login_required
from .observability import TASKS_COMPLETED, TASKS_CREATED
from .models import PRIORITIES, TASK_STATUSES, Comment, Project, Subtask, Task, User, db, utcnow
from .services import (can_write, get_project, get_task, json_body, labels_by_name, log, member_project_ids,
                       next_position, resolve_relations, set_status, today, visible_tasks)
from .validation import ValidationError, validate_task

api_bp = Blueprint("api", __name__, url_prefix="/api")

VIEWS = ("all", "inbox", "today", "upcoming", "overdue", "completed", "assigned")
PRIORITY_NAMES = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}


def _ordered(query):
    # Pinned first, then by date (no date last), time, priority, manual position.
    return query.order_by(Task.pinned.desc(), case((Task.due_date.is_(None), 1), else_=0),
                          Task.due_date, case((Task.due_time.is_(None), 1), else_=0), Task.due_time,
                          Task.priority, Task.position, Task.id)


@api_bp.get("/tasks")
@login_required
def list_tasks():
    args = request.args
    view = args.get("view", "all")
    if view not in VIEWS:
        raise ValidationError({"view": "View must be one of: " + ", ".join(VIEWS)})
    query = visible_tasks(g.user)
    t = today()

    if view == "inbox":
        query = query.filter(Task.project_id.is_(None))
    elif view == "today":
        query = query.filter(Task.due_date.isnot(None), Task.due_date <= t)
    elif view == "upcoming":
        query = query.filter(Task.due_date >= t, Task.due_date <= t + timedelta(days=13))
    elif view == "overdue":
        query = query.filter(Task.due_date < t)
    elif view == "assigned":
        query = query.filter(Task.assignee_id == g.user.id)

    if args.get("project_id"):
        get_project(int(args["project_id"]))
        query = query.filter(Task.project_id == int(args["project_id"]))
    if args.get("label_id"):
        query = query.filter(Task.labels.any(id=int(args["label_id"])))
    status = args.get("status")
    if status:
        if status not in TASK_STATUSES:
            raise ValidationError({"status": "Invalid status filter."})
        query = query.filter(Task.status == status)
    if args.get("priority"):
        query = query.filter(Task.priority == int(args["priority"]))
    if args.get("q"):
        like = f"%{args['q']}%"
        query = query.filter(or_(Task.title.ilike(like), Task.description.ilike(like)))

    if view == "completed":
        query = query.filter(Task.status == "done").order_by(Task.completed_at.desc())
    else:
        if not (args.get("include_done") or status == "done"):
            query = query.filter(Task.status != "done")
        query = _ordered(query)
    tasks = query.limit(500).all()
    return jsonify(tasks=[x.to_dict() for x in tasks], count=len(tasks))


def _apply(task, fields, relations):
    changes = []
    for key, value in fields.items():
        if key == "status":
            if value != task.status:
                changes.append(f"status → {value.replace('_', ' ')}")
            set_status(task, value)
            continue
        if getattr(task, key) != value:
            if key == "priority":
                changes.append(f"priority → {PRIORITY_NAMES[value]}")
            elif key == "due_date":
                changes.append(f"due → {value.isoformat() if value else 'none'}")
            elif key in ("title", "recurrence", "due_time", "estimate_minutes"):
                changes.append(f"{key.replace('_', ' ')} → {value if value is not None else 'none'}")
            elif key == "description":
                changes.append("description edited")
            setattr(task, key, value)
    if "project" in relations and relations["project"] != task.project:
        task.project = relations["project"]
        changes.append(f"moved to {task.project.name if task.project else 'Inbox'}")
        lost_access = (task.project.role_of(task.assignee) is None if task.project
                       else task.assignee_id != task.user_id) if task.assignee else False
        if lost_access:
            task.assignee = None
    if "labels" in relations and set(relations["labels"]) != set(task.labels):
        task.labels = relations["labels"]
        changes.append("labels: " + (", ".join(lb.name for lb in task.labels) or "none"))
    if "assignee" in relations and relations["assignee"] != task.assignee:
        task.assignee = relations["assignee"]
        changes.append(f"assigned to {task.assignee.name}" if task.assignee else "unassigned")
    return changes


@api_bp.post("/tasks")
@login_required
def create_task():
    data = json_body()
    fields = validate_task(data)
    relations = resolve_relations(data)
    project = relations.get("project")
    position = next_position(project.id if project else None, fields.get("status", "todo"))
    task = Task(user_id=g.user.id, priority=4, status="todo", project=project, position=position)
    db.session.add(task)
    with db.session.no_autoflush:
        _apply(task, fields, {k: v for k, v in relations.items() if k != "project"})
    db.session.flush()
    log(task, "created", task.title)
    db.session.commit()
    TASKS_CREATED.labels("form").inc()
    return jsonify(task=task.to_dict()), 201


def _resolve_parsed(parsed, default_project_id=None):
    """Map names from the quick-add parser onto real projects / labels / users."""
    result = dict(parsed)
    project = None
    if parsed["project"]:
        name = parsed["project"].lower()
        mine = Project.query.filter(Project.id.in_(member_project_ids(g.user))).all()
        project = next((p for p in mine if p.name.lower() == name or p.name.lower().replace(" ", "") == name), None)
        if project is None:     # unique prefix: "#Capstone" -> "Capstone Project"
            prefixed = [p for p in mine if p.name.lower().startswith(name)]
            project = prefixed[0] if len(prefixed) == 1 else None
        if project is None:     # unknown project: keep the text in the title
            result["title"] = f"{result['title']} #{parsed['project']}".strip()
    elif default_project_id:
        project = get_project(int(default_project_id))
    result["project"] = project
    assignee = None
    if parsed["assignee"]:
        user = User.query.filter_by(username=parsed["assignee"]).first()
        if user and (user.id == g.user.id or (project and project.role_of(user))):
            assignee = user
    result["assignee"] = assignee
    return result


def _parsed_json(resolved):
    out = {k: v for k, v in resolved.items() if k not in ("project", "assignee", "due_date")}
    out["project"] = resolved["project"].lite() if resolved["project"] else None
    out["assignee"] = resolved["assignee"].to_public() if resolved["assignee"] else None
    out["due_date"] = resolved["due_date"].isoformat() if resolved["due_date"] else None
    return out


@api_bp.post("/tasks/parse")
@login_required
def parse_task():
    data = json_body()
    resolved = _resolve_parsed(quickadd.parse(str(data.get("text", ""))[:500], today()), data.get("project_id"))
    return jsonify(parsed=_parsed_json(resolved))


@api_bp.post("/tasks/quick")
@login_required
def quick_add():
    data = json_body()
    resolved = _resolve_parsed(quickadd.parse(str(data.get("text", ""))[:500], today()), data.get("project_id"))
    if not resolved["title"]:
        raise ValidationError({"text": "Type a task title."})
    if resolved["project"] and not can_write(resolved["project"], g.user):
        abort(403, description="You have read-only access to this project.")
    labels = labels_by_name(resolved["labels"])
    position = next_position(resolved["project"].id if resolved["project"] else None, "todo")
    task = Task(user_id=g.user.id, title=resolved["title"][:200], project=resolved["project"],
                priority=resolved["priority"] or 4, due_date=resolved["due_date"], due_time=resolved["due_time"],
                recurrence=resolved["recurrence"], estimate_minutes=resolved["estimate_minutes"],
                assignee=resolved["assignee"], status="todo", labels=labels, position=position)
    db.session.add(task)
    db.session.flush()
    log(task, "created", f"{task.title} (quick add)")
    db.session.commit()
    TASKS_CREATED.labels("quick_add").inc()
    return jsonify(task=task.to_dict(), parsed=_parsed_json(resolved)), 201


@api_bp.get("/tasks/<int:task_id>")
@login_required
def get_task_detail(task_id):
    return jsonify(task=get_task(task_id).to_detail())


@api_bp.route("/tasks/<int:task_id>", methods=["PUT", "PATCH"])
@login_required
def update_task(task_id):
    task = get_task(task_id, write=True)
    data = json_body()
    fields = validate_task(data, partial=request.method == "PATCH")
    relations = resolve_relations(data, task)
    changes = _apply(task, fields, relations)
    if "position" in data:
        task.position = float(data["position"])
    if changes:
        log(task, "updated", "; ".join(changes))
    db.session.commit()
    return jsonify(task=task.to_detail() if request.args.get("detail") else task.to_dict())


@api_bp.delete("/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    task = get_task(task_id, write=True)
    task.deleted_at = utcnow()
    log(task, "deleted", task.title)
    db.session.commit()
    return "", 204


@api_bp.post("/tasks/<int:task_id>/restore")
@login_required
def restore_task(task_id):
    task = get_task(task_id, write=True, include_deleted=True)
    task.deleted_at = None
    log(task, "restored", task.title)
    db.session.commit()
    return jsonify(task=task.to_dict())


@api_bp.post("/tasks/<int:task_id>/complete")
@login_required
def complete_task(task_id):
    task = get_task(task_id, write=True)
    done = bool((request.get_json(silent=True) or {}).get("done", True))
    next_task = None
    if done and task.status != "done":
        set_status(task, "done")
        log(task, "completed", task.title)
        TASKS_COMPLETED.labels(f"p{task.priority}").inc()
        if task.recurrence:
            next_task = Task(
                user_id=task.user_id, project=task.project, assignee=task.assignee, title=task.title,
                description=task.description, priority=task.priority, due_time=task.due_time,
                recurrence=task.recurrence, estimate_minutes=task.estimate_minutes, status="todo",
                due_date=quickadd.next_occurrence(task.due_date, task.recurrence, today()),
                position=task.position, labels=list(task.labels))
            next_task.subtasks = [Subtask(title=s.title, position=s.position) for s in task.subtasks]
            db.session.add(next_task)
            db.session.flush()
            log(next_task, "created", f"next {task.recurrence} occurrence")
    elif not done and task.status == "done":
        set_status(task, "todo")
        log(task, "reopened", task.title)
    db.session.commit()
    return jsonify(task=task.to_dict(), next_task=next_task.to_dict() if next_task else None)


@api_bp.post("/tasks/<int:task_id>/duplicate")
@login_required
def duplicate_task(task_id):
    src = get_task(task_id, write=True)
    copy = Task(user_id=g.user.id, project=src.project, title=f"{src.title} (copy)"[:200],
                description=src.description, priority=src.priority, due_date=src.due_date, due_time=src.due_time,
                recurrence=src.recurrence, estimate_minutes=src.estimate_minutes, assignee=src.assignee,
                status="todo", position=src.position + 1, labels=list(src.labels))
    copy.subtasks = [Subtask(title=s.title, position=s.position) for s in src.subtasks]
    db.session.add(copy)
    db.session.flush()
    log(copy, "created", f"duplicated from #{src.id}")
    db.session.commit()
    return jsonify(task=copy.to_dict()), 201


@api_bp.post("/tasks/reorder")
@login_required
def reorder():
    data = json_body()
    ids = data.get("ids")
    if not isinstance(ids, list) or not ids:
        raise ValidationError({"ids": "ids must be a non-empty list."})
    status = data.get("status")
    if status is not None and status not in TASK_STATUSES:
        raise ValidationError({"status": "Invalid status."})
    tasks = {t.id: t for t in visible_tasks(g.user).filter(Task.id.in_(ids))}
    if len(tasks) != len(set(ids)):
        abort(404)
    for index, tid in enumerate(ids):
        task = tasks[tid]
        if not can_write(task, g.user):
            abort(403, description="You have read-only access to this project.")
        task.position = (index + 1) * 1000.0
        if status and task.status != status:
            set_status(task, status)
            log(task, "updated", f"status → {status.replace('_', ' ')} (board)")
    db.session.commit()
    return jsonify(tasks=[tasks[i].to_dict() for i in ids])


# ---------------- subtasks ----------------

@api_bp.post("/tasks/<int:task_id>/subtasks")
@login_required
def add_subtask(task_id):
    task = get_task(task_id, write=True)
    title = str(json_body().get("title", "")).strip()
    if not 1 <= len(title) <= 200:
        raise ValidationError({"title": "Subtask title must be 1-200 characters."})
    sub = Subtask(task=task, title=title, position=(max([s.position for s in task.subtasks], default=0) + 1000))
    db.session.add(sub)
    log(task, "subtask", f"added “{title}”")
    db.session.commit()
    return jsonify(subtask=sub.to_dict()), 201


def _owned_subtask(subtask_id):
    sub = db.session.get(Subtask, subtask_id)
    if sub is None:
        abort(404)
    get_task(sub.task_id, write=True)
    return sub


@api_bp.patch("/subtasks/<int:subtask_id>")
@login_required
def update_subtask(subtask_id):
    sub = _owned_subtask(subtask_id)
    data = json_body()
    if "title" in data:
        title = str(data["title"]).strip()
        if not 1 <= len(title) <= 200:
            raise ValidationError({"title": "Subtask title must be 1-200 characters."})
        sub.title = title
    if "done" in data and bool(data["done"]) != sub.done:
        sub.done = bool(data["done"])
        log(sub.task, "subtask", f"{'checked' if sub.done else 'unchecked'} “{sub.title}”")
    db.session.commit()
    return jsonify(subtask=sub.to_dict())


@api_bp.delete("/subtasks/<int:subtask_id>")
@login_required
def delete_subtask(subtask_id):
    sub = _owned_subtask(subtask_id)
    db.session.delete(sub)
    db.session.commit()
    return "", 204


# ---------------- comments ----------------

@api_bp.post("/tasks/<int:task_id>/comments")
@login_required
def add_comment(task_id):
    task = get_task(task_id)              # viewers may comment
    body = str(json_body().get("body", "")).strip()
    if not 1 <= len(body) <= 5000:
        raise ValidationError({"body": "Comment must be 1-5000 characters."})
    comment = Comment(task=task, author_id=g.user.id, body=body)
    db.session.add(comment)
    log(task, "commented", body[:120])
    db.session.commit()
    return jsonify(comment=comment.to_dict()), 201


@api_bp.delete("/comments/<int:comment_id>")
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        abort(404)
    get_task(comment.task_id)
    if comment.author_id != g.user.id:
        abort(403, description="You can only delete your own comments.")
    db.session.delete(comment)
    db.session.commit()
    return "", 204


@api_bp.get("/stats")
@login_required
def stats():
    counts = {s: visible_tasks(g.user).filter(Task.status == s).count() for s in TASK_STATUSES}
    by_priority = {str(p): visible_tasks(g.user).filter(Task.priority == p, Task.status != "done").count()
                   for p in PRIORITIES}
    return jsonify(counts=counts, total=sum(counts.values()), open_by_priority=by_priority)
