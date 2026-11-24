"""Application configuration loaded from environment variables.

Every value can be overridden at runtime (Docker env, Kubernetes ConfigMap/Secret),
which keeps the image identical across environments (12-factor app).
"""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///taskmanager.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    APP_VERSION = os.environ.get("APP_VERSION", "2.0.0")
    DEPLOY_COLOR = os.environ.get("DEPLOY_COLOR", "blue")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    TOKEN_MAX_AGE = int(os.environ.get("TOKEN_MAX_AGE", "86400"))
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    DEMO_DATA = os.environ.get("DEMO_DATA", "").lower() in ("1", "true", "yes")
    DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    ADMIN_PASSWORD = ""
    CSRF_ENABLED = False
    DEMO_DATA = False
