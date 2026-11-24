"""Database models for Orbit.

User ──< ProjectMember >── Project ──< Task >── Label (many-to-many)
                                       Task ──< Subtask, Comment, Activity, FocusSession
Tasks with project_id = NULL live in the owner's personal Inbox.
"""
from datetime import date, datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

TASK_STATUSES = ("todo", "in_progress", "done")
PRIORITIES = (1, 2, 3, 4)                     # 1 = P1 (urgent) ... 4 = P4 (no priority)
RECURRENCES = ("daily", "weekdays", "weekly", "monthly", "yearly")
PROJECT_ROLES = ("owner", "editor", "viewer")
THEMES = ("light", "dark", "system")
PALETTE = ("#6d5cff", "#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#ec4899", "#14b8a6", "#8b5cf6",
           "#f97316", "#64748b")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.isoformat() if value else None


task_labels = db.Table(
    "task_labels",
    db.Column("task_id", db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    db.Column("label_id", db.Integer, db.ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_color = db.Column(db.String(9), default="#6d5cff", nullable=False)
    theme = db.Column(db.String(10), default="system", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def set_password(self, password):
        # PBKDF2 is available on every Python build (scrypt is missing on some, e.g. macOS system Python).
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256:600000")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def name(self):
        return self.display_name or self.username

    @property
    def initials(self):
        parts = self.name.replace("_", " ").replace(".", " ").split()
        letters = "".join(p[0] for p in parts[:2]) if len(parts) > 1 else self.name[:2]
        return letters.upper()

    def to_dict(self):
        return {"id": self.id, "username": self.username, "display_name": self.name,
                "avatar_color": self.avatar_color, "theme": self.theme, "initials": self.initials,
                "created_at": iso(self.created_at)}

    def to_public(self):
        return {"id": self.id, "username": self.username, "display_name": self.name,
                "avatar_color": self.avatar_color, "initials": self.initials}


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    color = db.Column(db.String(9), default="#6d5cff", nullable=False)
    icon = db.Column(db.String(16), default="📁", nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    members = db.relationship("ProjectMember", backref="project", cascade="all, delete-orphan", lazy=True)
    tasks = db.relationship("Task", backref="project", cascade="all", lazy=True)  # tasks can move to Inbox

    def role_of(self, user):
        for m in self.members:
            if m.user_id == user.id:
                return m.role
        return None

    def lite(self):
        return {"id": self.id, "name": self.name, "color": self.color, "icon": self.icon}

    def to_dict(self, user=None):
        live = [t for t in self.tasks if t.deleted_at is None]
        data = self.lite()
        data.update({
            "role": self.role_of(user) if user else None,
            "open_count": sum(1 for t in live if t.status != "done"),
            "done_count": sum(1 for t in live if t.status == "done"),
            "members": [{"user": m.user.to_public(), "role": m.role}
                        for m in sorted(self.members, key=lambda m: PROJECT_ROLES.index(m.role))],
            "created_at": iso(self.created_at),
        })
        return data


class ProjectMember(db.Model):
    __tablename__ = "project_members"

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    role = db.Column(db.String(10), nullable=False, default="editor")
    user = db.relationship("User")


class Label(db.Model):
    __tablename__ = "labels"
    __table_args__ = (db.UniqueConstraint("owner_id", "name", name="uq_label_owner_name"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False)
    color = db.Column(db.String(9), default="#64748b", nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    def lite(self):
        return {"id": self.id, "name": self.name, "color": self.color}

    def to_dict(self):
        data = self.lite()
        data["open_count"] = sum(1 for t in self.tasks if t.deleted_at is None and t.status != "done")
        return data


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(20), default="todo", nullable=False, index=True)
    priority = db.Column(db.Integer, default=4, nullable=False)
    due_date = db.Column(db.Date, nullable=True, index=True)
    due_time = db.Column(db.String(5), nullable=True)
    recurrence = db.Column(db.String(10), nullable=True)
    estimate_minutes = db.Column(db.Integer, nullable=True)
    position = db.Column(db.Float, default=0.0, nullable=False)
    pinned = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)   # creator
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[user_id])
    assignee = db.relationship("User", foreign_keys=[assignee_id])
    labels = db.relationship("Label", secondary=task_labels, backref="tasks", lazy="selectin")
    subtasks = db.relationship("Subtask", backref="task", cascade="all, delete-orphan",
                               order_by="Subtask.position", lazy="selectin")
    comments = db.relationship("Comment", backref="task", cascade="all, delete-orphan",
                               order_by="Comment.created_at", lazy=True)
    activity = db.relationship("Activity", backref="task", cascade="all, delete-orphan",
                               order_by="Activity.created_at.desc()", lazy=True)
    focus_sessions = db.relationship("FocusSession", backref="task", cascade="all, delete-orphan", lazy=True)

    @property
    def is_overdue(self):
        return bool(self.due_date and self.status != "done" and self.due_date < date.today())

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": iso(self.due_date),
            "due_time": self.due_time,
            "overdue": self.is_overdue,
            "recurrence": self.recurrence,
            "estimate_minutes": self.estimate_minutes,
            "position": self.position,
            "pinned": self.pinned,
            "project": self.project.lite() if self.project else None,
            "labels": [lb.lite() for lb in sorted(self.labels, key=lambda lb: lb.name)],
            "assignee": self.assignee.to_public() if self.assignee else None,
            "creator": self.creator.to_public(),
            "subtasks_total": len(self.subtasks),
            "subtasks_done": sum(1 for s in self.subtasks if s.done),
            "comments_count": len(self.comments),
            "focus_minutes": sum(f.minutes for f in self.focus_sessions),
            "completed_at": iso(self.completed_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }

    def to_detail(self):
        data = self.to_dict()
        data["subtasks"] = [s.to_dict() for s in self.subtasks]
        data["comments"] = [c.to_dict() for c in self.comments]
        data["activity"] = [a.to_dict() for a in self.activity[:50]]
        return data


class Subtask(db.Model):
    __tablename__ = "subtasks"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Float, default=0.0, nullable=False)

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "title": self.title, "done": self.done,
                "position": self.position}


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    author = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "body": self.body, "author": self.author.to_public(),
                "created_at": iso(self.created_at)}


class Activity(db.Model):
    __tablename__ = "activity"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(40), nullable=False)
    detail = db.Column(db.String(300), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    actor = db.relationship("User")

    def to_dict(self, with_task=False):
        data = {"id": self.id, "action": self.action, "detail": self.detail,
                "actor": self.actor.to_public(), "created_at": iso(self.created_at)}
        if with_task:
            data["task"] = {"id": self.task.id, "title": self.task.title} if self.task else None
        return data


class FocusSession(db.Model):
    __tablename__ = "focus_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)
    minutes = db.Column(db.Integer, nullable=False)
    ended_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "minutes": self.minutes, "ended_at": iso(self.ended_at)}
