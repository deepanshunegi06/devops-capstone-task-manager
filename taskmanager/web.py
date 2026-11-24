"""HTML entry points. Everything after login is the single-page app at /app (static/js)."""
from flask import Blueprint, redirect, render_template, session, url_for

from .auth import login_required

web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def index():
    return redirect(url_for("web.app_shell") if session.get("user_id") else url_for("auth.login"))


@web_bp.get("/app")
@login_required
def app_shell():
    return render_template("app.html")
