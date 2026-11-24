"""Input validation shared by every API endpoint. Raises ValidationError -> HTTP 400."""
import re
from datetime import date

from .models import PRIORITIES, RECURRENCES, TASK_STATUSES, THEMES

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("validation failed")
        self.errors = errors


def _check(errors):
    if errors:
        raise ValidationError(errors)


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
    _check(errors)
    return username, password


def _text(data, key, errors, clean, max_len, required=False):
    value = (data.get(key) or "").strip() if isinstance(data.get(key), (str, type(None))) else None
    if value is None:
        errors[key] = f"{key} must be a string."
    elif required and not value:
        errors[key] = f"{key.capitalize()} is required."
    elif len(value) > max_len:
        errors[key] = f"{key.capitalize()} must be at most {max_len} characters."
    else:
        clean[key] = value


def _int(value):
    if isinstance(value, bool):
        raise ValueError
    return int(value)


def validate_task(data, partial=False):
    """Clean task fields. Relations (project_id, label_ids, assignee_id) are checked by the caller."""
    errors, clean = {}, {}

    if "title" in data or not partial:
        _text(data, "title", errors, clean, 200, required=True)
    if "description" in data:
        _text(data, "description", errors, clean, 10000)

    if "status" in data:
        if data["status"] not in TASK_STATUSES:
            errors["status"] = "Status must be one of: " + ", ".join(TASK_STATUSES)
        clean["status"] = data["status"]

    if "priority" in data:
        try:
            clean["priority"] = _int(data["priority"])
            if clean["priority"] not in PRIORITIES:
                raise ValueError
        except (TypeError, ValueError):
            errors["priority"] = "Priority must be 1 (urgent) to 4 (none)."

    if "due_date" in data:
        raw = data.get("due_date")
        if raw in (None, ""):
            clean["due_date"] = None
        else:
            try:
                clean["due_date"] = date.fromisoformat(str(raw))
            except ValueError:
                errors["due_date"] = "Due date must be in YYYY-MM-DD format."

    if "due_time" in data:
        raw = data.get("due_time")
        if raw in (None, ""):
            clean["due_time"] = None
        elif not TIME.match(str(raw)):
            errors["due_time"] = "Due time must be HH:MM (24h)."
        else:
            clean["due_time"] = str(raw)

    if "recurrence" in data:
        raw = data.get("recurrence")
        if raw in (None, "", "none"):
            clean["recurrence"] = None
        elif raw not in RECURRENCES:
            errors["recurrence"] = "Recurrence must be one of: " + ", ".join(RECURRENCES)
        else:
            clean["recurrence"] = raw

    if "estimate_minutes" in data:
        raw = data.get("estimate_minutes")
        if raw in (None, ""):
            clean["estimate_minutes"] = None
        else:
            try:
                clean["estimate_minutes"] = _int(raw)
                if not 0 < clean["estimate_minutes"] <= 24 * 60:
                    raise ValueError
            except (TypeError, ValueError):
                errors["estimate_minutes"] = "Estimate must be 1-1440 minutes."

    if "pinned" in data:
        clean["pinned"] = bool(data["pinned"])

    _check(errors)
    return clean


def validate_project(data, partial=False):
    errors, clean = {}, {}
    if "name" in data or not partial:
        _text(data, "name", errors, clean, 80, required=True)
    if "color" in data:
        if not HEX_COLOR.match(str(data["color"] or "")):
            errors["color"] = "Color must be a hex value like #6d5cff."
        clean["color"] = data["color"]
    if "icon" in data:
        icon = str(data["icon"] or "").strip()
        if not 1 <= len(icon) <= 8:
            errors["icon"] = "Icon must be a short emoji."
        clean["icon"] = icon
    _check(errors)
    return clean


def validate_label(data, partial=False):
    errors, clean = {}, {}
    if "name" in data or not partial:
        _text(data, "name", errors, clean, 40, required=True)
        name = clean.get("name", "")
        if name and not re.match(r"^[\w\-]+$", name):
            errors["name"] = "Label names use letters, numbers, '-' or '_' (no spaces)."
    if "color" in data:
        if not HEX_COLOR.match(str(data["color"] or "")):
            errors["color"] = "Color must be a hex value like #ef4444."
        clean["color"] = data["color"]
    _check(errors)
    return clean


def validate_profile(data):
    errors, clean = {}, {}
    if "display_name" in data:
        _text(data, "display_name", errors, clean, 80)
    if "theme" in data:
        if data["theme"] not in THEMES:
            errors["theme"] = "Theme must be light, dark or system."
        clean["theme"] = data["theme"]
    if "avatar_color" in data:
        if not HEX_COLOR.match(str(data["avatar_color"] or "")):
            errors["avatar_color"] = "Color must be a hex value."
        clean["avatar_color"] = data["avatar_color"]
    _check(errors)
    return clean
