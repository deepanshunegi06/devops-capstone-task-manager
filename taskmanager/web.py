"""Server-rendered, responsive web interface."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .auth import login_required
from .models import TASK_PRIORITIES, TASK_STATUSES, Task, db
from .validation import ValidationError, validate_task

web_bp = Blueprint("web", __name__)


def _owned(task_id):
    return Task.query.filter_by(id=task_id, user_id=g.user.id).first_or_404()


@web_bp.get("/")
@login_required
def dashboard():
    status = request.args.get("status", "")
    query = Task.query.filter_by(user_id=g.user.id)
    if status in TASK_STATUSES:
        query = query.filter_by(status=status)
    tasks = query.order_by(Task.created_at.desc()).all()
    counts = {s: Task.query.filter_by(user_id=g.user.id, status=s).count() for s in TASK_STATUSES}
    return render_template("dashboard.html", tasks=tasks, counts=counts, active=status,
                           statuses=TASK_STATUSES, priorities=TASK_PRIORITIES)


@web_bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
def new_task():
    if request.method == "POST":
        try:
            fields = validate_task(request.form.to_dict())
        except ValidationError as exc:
            for msg in exc.errors.values():
                flash(msg, "error")
            return render_template("task_form.html", task=None, form=request.form,
                                   statuses=TASK_STATUSES, priorities=TASK_PRIORITIES), 400
        db.session.add(Task(user_id=g.user.id, **fields))
        db.session.commit()
        flash("Task created.", "success")
        return redirect(url_for("web.dashboard"))
    return render_template("task_form.html", task=None, form={},
                           statuses=TASK_STATUSES, priorities=TASK_PRIORITIES)


@web_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = _owned(task_id)
    if request.method == "POST":
        try:
            fields = validate_task(request.form.to_dict())
        except ValidationError as exc:
            for msg in exc.errors.values():
                flash(msg, "error")
            return render_template("task_form.html", task=task, form=request.form,
                                   statuses=TASK_STATUSES, priorities=TASK_PRIORITIES), 400
        for key, value in fields.items():
            setattr(task, key, value)
        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for("web.dashboard"))
    return render_template("task_form.html", task=task, form={},
                           statuses=TASK_STATUSES, priorities=TASK_PRIORITIES)


@web_bp.post("/tasks/<int:task_id>/status")
@login_required
def set_status(task_id):
    task = _owned(task_id)
    status = request.form.get("status")
    if status in TASK_STATUSES:
        task.status = status
        db.session.commit()
    return redirect(request.referrer or url_for("web.dashboard"))


@web_bp.post("/tasks/<int:task_id>/delete")
@login_required
def delete_task(task_id):
    db.session.delete(_owned(task_id))
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("web.dashboard"))
