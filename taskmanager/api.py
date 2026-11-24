"""REST API for task CRUD. All routes require authentication and are scoped to the caller."""
from flask import Blueprint, abort, g, jsonify, request

from .auth import login_required
from .models import TASK_STATUSES, Task, db
from .validation import ValidationError, validate_task

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _get_owned_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=g.user.id).first()
    if task is None:
        abort(404)
    return task


@api_bp.get("/tasks")
@login_required
def list_tasks():
    query = Task.query.filter_by(user_id=g.user.id)
    status = request.args.get("status")
    if status:
        if status not in TASK_STATUSES:
            return jsonify(error="validation_error", fields={"status": "Invalid status filter."}), 400
        query = query.filter_by(status=status)
    search = request.args.get("q")
    if search:
        query = query.filter(Task.title.ilike(f"%{search}%"))
    tasks = query.order_by(Task.created_at.desc()).all()
    return jsonify(tasks=[t.to_dict() for t in tasks], count=len(tasks))


@api_bp.post("/tasks")
@login_required
def create_task():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="bad_request", message="Request body must be JSON."), 400
    try:
        fields = validate_task(data)
    except ValidationError as exc:
        return jsonify(error="validation_error", fields=exc.errors), 400
    task = Task(user_id=g.user.id, **fields)
    db.session.add(task)
    db.session.commit()
    return jsonify(task=task.to_dict()), 201


@api_bp.get("/tasks/<int:task_id>")
@login_required
def get_task(task_id):
    return jsonify(task=_get_owned_task(task_id).to_dict())


@api_bp.route("/tasks/<int:task_id>", methods=["PUT", "PATCH"])
@login_required
def update_task(task_id):
    task = _get_owned_task(task_id)
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="bad_request", message="Request body must be JSON."), 400
    try:
        fields = validate_task(data, partial=request.method == "PATCH")
    except ValidationError as exc:
        return jsonify(error="validation_error", fields=exc.errors), 400
    for key, value in fields.items():
        setattr(task, key, value)
    db.session.commit()
    return jsonify(task=task.to_dict())


@api_bp.delete("/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    task = _get_owned_task(task_id)
    db.session.delete(task)
    db.session.commit()
    return "", 204


@api_bp.get("/stats")
@login_required
def stats():
    counts = {s: Task.query.filter_by(user_id=g.user.id, status=s).count() for s in TASK_STATUSES}
    return jsonify(counts=counts, total=sum(counts.values()))
