"""Input validation shared by the REST API and the web forms."""
from datetime import date

from .models import TASK_PRIORITIES, TASK_STATUSES


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("validation failed")
        self.errors = errors


def validate_credentials(data):
    errors = {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not 3 <= len(username) <= 80:
        errors["username"] = "Username must be 3-80 characters."
    elif not username.replace("_", "").replace(".", "").isalnum():
        errors["username"] = "Use letters, numbers, '.' or '_' only."
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    if errors:
        raise ValidationError(errors)
    return username, password


def validate_task(data, partial=False):
    """Return a dict of clean task fields. `partial` allows PATCH-style updates."""
    errors, clean = {}, {}

    if "title" in data or not partial:
        title = (data.get("title") or "").strip()
        if not title:
            errors["title"] = "Title is required."
        elif len(title) > 200:
            errors["title"] = "Title must be at most 200 characters."
        clean["title"] = title

    if "description" in data:
        description = data.get("description") or ""
        if len(description) > 5000:
            errors["description"] = "Description must be at most 5000 characters."
        clean["description"] = description

    if "status" in data:
        if data["status"] not in TASK_STATUSES:
            errors["status"] = "Status must be one of: " + ", ".join(TASK_STATUSES)
        clean["status"] = data["status"]

    if "priority" in data:
        if data["priority"] not in TASK_PRIORITIES:
            errors["priority"] = "Priority must be one of: " + ", ".join(TASK_PRIORITIES)
        clean["priority"] = data["priority"]

    if "due_date" in data:
        raw = data.get("due_date")
        if raw in (None, ""):
            clean["due_date"] = None
        else:
            try:
                clean["due_date"] = date.fromisoformat(str(raw))
            except ValueError:
                errors["due_date"] = "Due date must be in YYYY-MM-DD format."

    if errors:
        raise ValidationError(errors)
    return clean
