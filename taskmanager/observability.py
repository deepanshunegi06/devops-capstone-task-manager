"""Structured JSON logging + Prometheus metrics.

Logs go to stdout as one JSON object per line so Fluentd can parse them without
regexes. Metrics are exposed on /metrics for Prometheus to scrape.
"""
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

from flask import Response, g, request
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, Info,
                               generate_latest)

REQUEST_COUNT = Counter(
    "taskmanager_http_requests_total", "Total HTTP requests",
    ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram(
    "taskmanager_http_request_duration_seconds", "HTTP request latency",
    ["method", "endpoint"], buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
IN_PROGRESS = Gauge("taskmanager_http_requests_in_progress", "Requests currently being served")
TASKS_GAUGE = Gauge("taskmanager_tasks", "Number of tasks by status", ["status"])
USERS_GAUGE = Gauge("taskmanager_users", "Number of registered users")
APP_INFO = Info("taskmanager_app", "Application build information")
TASKS_CREATED = Counter("taskmanager_tasks_created_total", "Tasks created", ["source"])
TASKS_COMPLETED = Counter("taskmanager_tasks_completed_total", "Tasks completed", ["priority"])
FOCUS_MINUTES = Counter("taskmanager_focus_minutes_total", "Minutes logged in focus (Pomodoro) sessions")

_STD_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def __init__(self, version, color):
        super().__init__()
        self.version, self.color = version, color

    def format(self, record):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "taskmanager",
            "version": self.version,
            "deploy_color": self.color,
        }
        try:
            entry["request_id"] = g.get("request_id")
        except RuntimeError:  # outside of an app/request context
            pass
        for key, value in record.__dict__.items():
            if key not in _STD_ATTRS and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(app):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(app.config["APP_VERSION"], app.config["DEPLOY_COLOR"]))
    app.logger.handlers = [handler]
    app.logger.setLevel(app.config["LOG_LEVEL"])
    app.logger.propagate = False
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def _endpoint_label():
    # Use the route rule (e.g. /api/tasks/<int:task_id>) to keep label cardinality low.
    return request.url_rule.rule if request.url_rule else "unmatched"


def register_observability(app):
    APP_INFO.info({"version": app.config["APP_VERSION"], "deploy_color": app.config["DEPLOY_COLOR"]})

    @app.before_request
    def _start():
        g.start_time = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        IN_PROGRESS.inc()

    @app.after_request
    def _finish(response):
        elapsed = time.perf_counter() - g.get("start_time", time.perf_counter())
        endpoint = _endpoint_label()
        if endpoint != "/metrics":
            REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
            REQUEST_LATENCY.labels(request.method, endpoint).observe(elapsed)
            app.logger.info("request", extra={
                "method": request.method, "path": request.path, "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 2), "remote_addr": request.remote_addr})
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["X-App-Version"] = app.config["APP_VERSION"]
        response.headers["X-Deploy-Color"] = app.config["DEPLOY_COLOR"]
        return response

    @app.teardown_request
    def _teardown(_exc):
        IN_PROGRESS.dec()

    @app.get("/metrics")
    def metrics():
        from .models import TASK_STATUSES, Task, User, db
        try:
            for status in TASK_STATUSES:
                TASKS_GAUGE.labels(status).set(
                    db.session.query(Task).filter(Task.status == status, Task.deleted_at.is_(None)).count())
            USERS_GAUGE.set(db.session.query(User).count())
        except Exception:  # metrics must never fail because the DB is down
            app.logger.exception("metrics collection failed")
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
