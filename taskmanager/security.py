"""CSRF protection for HTML forms and security response headers."""
import hmac
import secrets

from flask import abort, request, session


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def register_security(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def _csrf_protect():
        if not app.config.get("CSRF_ENABLED", True):
            return
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        if request.path.startswith("/api/"):
            # Bearer-token clients are not vulnerable to CSRF; anonymous calls (login/register) carry no
            # session to abuse. Cookie-authenticated SPA calls must echo the token in a header.
            if request.headers.get("Authorization", "").startswith("Bearer ") or not session.get("user_id"):
                return
            sent = request.headers.get("X-CSRF-Token", "")
        else:
            sent = request.form.get("csrf_token", "")
        if not sent or not hmac.compare_digest(sent, session.get("_csrf", "")):
            abort(400, description="Invalid or missing CSRF token.")

    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; img-src 'self' data:; script-src 'self'")
        return response
