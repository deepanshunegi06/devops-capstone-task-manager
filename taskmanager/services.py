"""Access control and shared domain logic.

Visibility rule: a user sees
  * Inbox tasks (project_id IS NULL) they created, and
  * every task in a project they are a member of (owner / editor / viewer).
Write access: Inbox owner, or project owner/editor. Viewers are read-only.
"""
from datetime import date

from flask import abort, g, request
from sqlalchemy import and_, or_

from .models import Activity, Label, Project, ProjectMember, Task, User, db, utcnow
from .validation import ValidationError


def member_project_ids(user):
    return [pid for (pid,) in db.session.query(ProjectMember.project_id).filter_by(user_id=user.id)]


def visible_tasks(user, include_deleted=False):
    query = Task.query.filter(or_(
        and_(Task.project_id.is_(None), Task.user_id == user.id),
        Task.project_id.in_(member_project_ids(user)),
    ))
    if not include_deleted:
        query = query.filter(Task.deleted_at.is_(None))
    return query


def can_write(task_or_project, user):
    project = task_or_project if isinstance(task_or_project, Project) else task_or_project.project
    if project is None:
        return task_or_project.user_id == user.id
    return project.role_of(user) in ("owner", "editor")


def get_task(task_id, write=False, include_deleted=False):
    task = visible_tasks(g.user, include_deleted).filter(Task.id == task_id).first()
    if task is None:
        abort(404)
    if write and not can_write(task, g.user):
        abort(403, description="You have read-only access to this project.")
    return task


def get_project(project_id, role=None):
    project = db.session.get(Project, project_id)
    if project is None or project.role_of(g.user) is None:
        abort(404)
    if role == "write" and project.role_of(g.user) not in ("owner", "editor"):
        abort(403, description="You have read-only access to this project.")
    if role == "owner" and project.role_of(g.user) != "owner":
        abort(403, description="Only the project owner can do this.")
    return project


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"body": "Request body must be a JSON object."})
    return data


def log(task, action, detail=""):
    db.session.add(Activity(task=task, actor_id=g.user.id, action=action, detail=detail[:300]))


def resolve_relations(data, task=None):
    """Turn project_id / label_ids / assignee_id from the request into checked objects."""
    out = {}
    if "project_id" in data:
        pid = data.get("project_id")
        out["project"] = get_project(int(pid), role="write") if pid not in (None, "", 0) else None
    if "label_ids" in data:
        ids = data.get("label_ids") or []
        if not isinstance(ids, list):
            raise ValidationError({"label_ids": "label_ids must be a list."})
        labels = Label.query.filter(Label.id.in_(ids), Label.owner_id == g.user.id).all() if ids else []
        if len(labels) != len(set(ids)):
            raise ValidationError({"label_ids": "Unknown label."})
        out["labels"] = labels
    if "assignee_id" in data:
        aid = data.get("assignee_id")
        if aid in (None, "", 0):
            out["assignee"] = None
        else:
            user = db.session.get(User, int(aid))
            project = out.get("project", task.project if task else None)
            if user is None:
                allowed = False
            elif project is None:
                allowed = user.id == g.user.id
            else:
                allowed = project.role_of(user) is not None
            if not allowed:
                raise ValidationError({"assignee_id": "Assignee must be a member of the project."})
            out["assignee"] = user
    return out


def labels_by_name(names):
    """Find the user's labels by name (case-insensitive), creating missing ones."""
    from .models import PALETTE
    result = []
    existing = {lb.name.lower(): lb for lb in Label.query.filter_by(owner_id=g.user.id)}
    for i, name in enumerate(names):
        label = existing.get(name.lower())
        if label is None:
            label = Label(name=name[:40], owner_id=g.user.id, color=PALETTE[(len(existing) + i) % len(PALETTE)])
            db.session.add(label)
            existing[name.lower()] = label
        result.append(label)
    return result


def next_position(project_id, status):
    last = (db.session.query(db.func.max(Task.position))
            .filter(Task.project_id.is_(project_id) if project_id is None else Task.project_id == project_id,
                    Task.status == status).scalar())
    return (last or 0) + 1000.0


def set_status(task, status):
    if status == task.status:
        return
    task.status = status
    task.completed_at = utcnow() if status == "done" else None


def today():
    return date.today()
