"""Authentication: session login for the web UI, signed bearer tokens for the REST API."""
from functools import wraps

from flask import (Blueprint, current_app, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import User, db
from .validation import ValidationError, validate_credentials

auth_bp = Blueprint("auth", __name__)


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="api-token")


def issue_token(user):
    return _serializer().dumps({"uid": user.id})


def user_from_token(token):
    try:
        data = _serializer().loads(token, max_age=current_app.config["TOKEN_MAX_AGE"])
    except (BadSignature, SignatureExpired):
        return None
    return db.session.get(User, data.get("uid"))


def load_current_user():
    """Resolve the user from a Bearer token (API) or the session cookie (web)."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return user_from_token(header[7:].strip())
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.user = load_current_user()
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="unauthorized", message="Authentication required."), 401
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


# ---------- REST API ----------

@auth_bp.post("/api/auth/register")
def api_register():
    data = request.get_json(silent=True) or {}
    try:
        username, password = validate_credentials(data)
    except ValidationError as exc:
        return jsonify(error="validation_error", fields=exc.errors), 400
    if User.query.filter_by(username=username).first():
        return jsonify(error="conflict", message="Username already exists."), 409
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    current_app.logger.info("user registered", extra={"user": username})
    return jsonify(user=user.to_dict(), token=issue_token(user)), 201


@auth_bp.post("/api/auth/login")
def api_login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=(data.get("username") or "").strip()).first()
    if not user or not user.check_password(data.get("password") or ""):
        current_app.logger.warning("failed login", extra={"user": data.get("username")})
        return jsonify(error="unauthorized", message="Invalid username or password."), 401
    return jsonify(user=user.to_dict(), token=issue_token(user))


@auth_bp.get("/api/auth/me")
@login_required
def api_me():
    return jsonify(user=g.user.to_dict())


# ---------- Web UI ----------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if user and user.check_password(request.form.get("password", "")):
            session.clear()
            session["user_id"] = user.id
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//")
                            else url_for("web.dashboard"))
        current_app.logger.warning("failed login", extra={"user": request.form.get("username")})
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            username, password = validate_credentials(request.form)
        except ValidationError as exc:
            for msg in exc.errors.values():
                flash(msg, "error")
            return render_template("register.html"), 400
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return render_template("register.html"), 409
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session.clear()
        session["user_id"] = user.id
        flash("Welcome! Your account was created.", "success")
        return redirect(url_for("web.dashboard"))
    return render_template("register.html")


@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
