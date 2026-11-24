"""Orbit Task Manager - Flask application factory."""
from flask import Flask, jsonify, render_template, request
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from .config import Config
from .models import User, db
from .observability import configure_logging, register_observability
from .security import register_security
from .validation import ValidationError


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    configure_logging(app)
    db.init_app(app)
    register_observability(app)
    register_security(app)

    from .api import api_bp
    from .auth import auth_bp
    from .demo import register_cli, seed_demo
    from .insights import insights_bp
    from .projects import projects_bp
    from .web import web_bp
    for bp in (auth_bp, api_bp, projects_bp, insights_bp, web_bp):
        app.register_blueprint(bp)
    register_cli(app)

    register_health(app)
    register_error_handlers(app)

    with app.app_context():
        db.create_all()
        seed_admin(app)
        if app.config.get("DEMO_DATA"):
            seed_demo(app)

    @app.context_processor
    def inject_globals():
        return {"app_version": app.config["APP_VERSION"], "deploy_color": app.config["DEPLOY_COLOR"]}

    return app


def seed_admin(app):
    """Create the initial admin user from ADMIN_USERNAME/ADMIN_PASSWORD (a K8s Secret)."""
    password = app.config.get("ADMIN_PASSWORD")
    username = app.config.get("ADMIN_USERNAME")
    if password and username and not User.query.filter_by(username=username).first():
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        app.logger.info("seeded admin user", extra={"user": username})


def register_health(app):
    @app.get("/health/live")
    def live():
        return jsonify(status="ok")

    @app.get("/health/ready")
    def ready():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            app.logger.exception("readiness check failed")
            return jsonify(status="unavailable", database="down"), 503
        return jsonify(status="ok", database="up")

    @app.get("/version")
    def version():
        return jsonify(version=app.config["APP_VERSION"], color=app.config["DEPLOY_COLOR"])


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation(exc):
        db.session.rollback()
        return jsonify(error="validation_error", message="Please fix the highlighted fields.",
                       fields=exc.errors), 400

    @app.errorhandler(HTTPException)
    def handle_http(exc):
        if request.path.startswith("/api/"):
            return jsonify(error=exc.name.lower().replace(" ", "_"), message=exc.description), exc.code
        return render_template("error.html", code=exc.code, name=exc.name,
                               description=exc.description), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        db.session.rollback()
        app.logger.exception("unhandled exception")
        if request.path.startswith("/api/"):
            return jsonify(error="internal_server_error", message="Something went wrong."), 500
        return render_template("error.html", code=500, name="Internal Server Error",
                               description="Something went wrong. Please try again."), 500
