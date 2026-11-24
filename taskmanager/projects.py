"""Projects (with member sharing and roles) and labels."""
from flask import Blueprint, abort, g, jsonify

from .auth import login_required
from .models import PALETTE, Label, Project, ProjectMember, User, db
from .services import get_project, json_body, member_project_ids
from .validation import ValidationError, validate_label, validate_project

projects_bp = Blueprint("projects", __name__, url_prefix="/api")


def user_projects(user):
    return (Project.query.filter(Project.id.in_(member_project_ids(user)))
            .order_by(Project.created_at).all())


@projects_bp.get("/projects")
@login_required
def list_projects():
    return jsonify(projects=[p.to_dict(g.user) for p in user_projects(g.user)])


@projects_bp.post("/projects")
@login_required
def create_project():
    fields = validate_project(json_body())
    fields.setdefault("color", PALETTE[len(user_projects(g.user)) % len(PALETTE)])
    project = Project(owner_id=g.user.id, **fields)
    project.members.append(ProjectMember(user_id=g.user.id, role="owner"))
    db.session.add(project)
    db.session.commit()
    return jsonify(project=project.to_dict(g.user)), 201


@projects_bp.patch("/projects/<int:project_id>")
@login_required
def update_project(project_id):
    project = get_project(project_id, role="write")
    for key, value in validate_project(json_body(), partial=True).items():
        setattr(project, key, value)
    db.session.commit()
    return jsonify(project=project.to_dict(g.user))


@projects_bp.delete("/projects/<int:project_id>")
@login_required
def delete_project(project_id):
    project = get_project(project_id, role="owner")
    db.session.delete(project)
    db.session.commit()
    return "", 204


@projects_bp.post("/projects/<int:project_id>/members")
@login_required
def add_member(project_id):
    project = get_project(project_id, role="owner")
    data = json_body()
    role = data.get("role", "editor")
    if role not in ("editor", "viewer"):
        raise ValidationError({"role": "Role must be editor or viewer."})
    user = User.query.filter_by(username=str(data.get("username", "")).strip()).first()
    if user is None:
        raise ValidationError({"username": "No user with that username."})
    existing = next((m for m in project.members if m.user_id == user.id), None)
    if existing and existing.role == "owner":
        raise ValidationError({"username": "That user owns this project."})
    if existing:
        existing.role = role
    else:
        project.members.append(ProjectMember(user_id=user.id, role=role))
    db.session.commit()
    return jsonify(project=project.to_dict(g.user))


@projects_bp.delete("/projects/<int:project_id>/members/<int:user_id>")
@login_required
def remove_member(project_id, user_id):
    project = get_project(project_id)
    # owners can remove anyone except themselves; members can leave
    if user_id != g.user.id and project.role_of(g.user) != "owner":
        abort(403, description="Only the project owner can do this.")
    member = next((m for m in project.members if m.user_id == user_id), None)
    if member is None:
        abort(404)
    if member.role == "owner":
        raise ValidationError({"user_id": "The owner cannot be removed."})
    project.members.remove(member)
    for task in project.tasks:
        if task.assignee_id == user_id:
            task.assignee_id = None
    db.session.commit()
    return jsonify(project=project.to_dict(g.user))


# ---------------- labels ----------------

def _owned_label(label_id):
    label = db.session.get(Label, label_id)
    if label is None or label.owner_id != g.user.id:
        abort(404)
    return label


@projects_bp.get("/labels")
@login_required
def list_labels():
    labels = Label.query.filter_by(owner_id=g.user.id).order_by(Label.name).all()
    return jsonify(labels=[lb.to_dict() for lb in labels])


@projects_bp.post("/labels")
@login_required
def create_label():
    fields = validate_label(json_body())
    if Label.query.filter(Label.owner_id == g.user.id, db.func.lower(Label.name) == fields["name"].lower()).first():
        return jsonify(error="conflict", message="You already have a label with that name."), 409
    count = Label.query.filter_by(owner_id=g.user.id).count()
    fields.setdefault("color", PALETTE[count % len(PALETTE)])
    label = Label(owner_id=g.user.id, **fields)
    db.session.add(label)
    db.session.commit()
    return jsonify(label=label.to_dict()), 201


@projects_bp.patch("/labels/<int:label_id>")
@login_required
def update_label(label_id):
    label = _owned_label(label_id)
    for key, value in validate_label(json_body(), partial=True).items():
        setattr(label, key, value)
    db.session.commit()
    return jsonify(label=label.to_dict())


@projects_bp.delete("/labels/<int:label_id>")
@login_required
def delete_label(label_id):
    db.session.delete(_owned_label(label_id))
    db.session.commit()
    return "", 204
